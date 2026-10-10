"""Package rendered screens as a fixed-layout, right-to-left EPUB 3.

Every screen that starts a mushaf page carries that page's number as its
label (page-list and an inline pagebreak), so "Go to page N" can land on
mushaf page N even when a page spans several screens. In the mushaf itself
spine position N is page N, with no separate cover. The Kindle-specific
metadata mirrors what Kindle Comic Converter emits, which Amazon's Send to
Kindle turns into a full-screen fixed-layout book.
"""
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .data import Mushaf, arabic_number


@dataclass
class Screen:
    stem: str  # === file name without extension, e.g. p050 or c050b ===
    page: int  # === mushaf page shown on this screen ===
    first: bool  # === True for the screen where the page begins ===


def _page_xhtml(screen: Screen, w: int, h: int) -> str:
    mark = (f'<span epub:type="pagebreak" id="page{screen.page}" title="{screen.page}" role="doc-pagebreak"></span>'
            if screen.first else "")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ar" dir="rtl">
<head><title>{screen.page}</title><meta name="viewport" content="width={w}, height={h}"/>
<style>html,body{{margin:0;padding:0}} img{{position:absolute;top:0;left:0;width:{w}px;height:{h}px}}</style>
</head>
<body><div>{mark}<img src="../img/{screen.stem}.png" alt="{screen.page}"/></div></body>
</html>
"""


def toc_tree(mushaf: Mushaf, pages: bool = False) -> list:
    """(label, page, children) entries shared by the EPUB and PDF outlines.

    With pages=True a third group lists every page under its juz', for books
    whose screens don't map one-to-one onto mushaf pages.
    """
    surahs = [
        (f"{c.id}. {c.name} · {c.name_arabic}", c.page, [])
        for c in mushaf.chapters
    ]
    juz = []
    for j in mushaf.juz:
        hizb = [
            (f"Hizb {h.number} · الحزب {arabic_number(h.number)}", h.page, [])
            for h in mushaf.hizb
            if (h.number + 1) // 2 == j.number
        ]
        juz.append((f"Juz' {j.number} · الجزء {arabic_number(j.number)}", j.page, hizb))
    tree = [
        ("Surahs · السور", 1, surahs),
        ("Juz' & Hizb · الأجزاء والأحزاب", 1, juz),
    ]
    if pages:
        bounds = [j.page for j in mushaf.juz] + [len(mushaf.pages) + 1]
        tree.append(("Pages · الصفحات", 1, [
            (f"Juz' {j.number} · pages {bounds[i]}–{bounds[i + 1] - 1}", j.page,
             [(f"Page {n}", n, []) for n in range(bounds[i], bounds[i + 1])])
            for i, j in enumerate(mushaf.juz)
        ]))
    return tree


def _nav_ol(entries, href, depth=0) -> str:
    pad = "  " * (depth + 2)
    out = [f"{pad}<ol>"]
    for label, page, children in entries:
        out.append(f'{pad}  <li><a href="{href[page]}">{escape(label)}</a>')
        if children:
            out.append(_nav_ol(children, href, depth + 1))
        out.append(f"{pad}  </li>")
    out.append(f"{pad}</ol>")
    return "\n".join(out)


def _ncx_points(entries, href, counter) -> str:
    out = []
    for label, page, children in entries:
        counter[0] += 1
        out.append(
            f'<navPoint id="n{counter[0]}"><navLabel><text>{escape(label)}</text></navLabel>'
            f'<content src="{href[page]}"/>'
        )
        out.append(_ncx_points(children, href, counter))
        out.append("</navPoint>")
    return "".join(out)


def write_epub(screens: list, tree: list, images: Path, out: Path, w: int, h: int,
               title: str) -> None:
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'quran-kindle/' + title)}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    href = {s.page: f"text/{s.stem}.xhtml" for s in reversed(screens)}
    firsts = [s for s in screens if s.first]

    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
    spine = []
    for i, s in enumerate(screens):
        props = ' properties="cover-image"' if i == 0 else ""
        manifest.append(f'<item id="i{s.stem}" href="img/{s.stem}.png" media-type="image/png"{props}/>')
        manifest.append(f'<item id="{s.stem}" href="text/{s.stem}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{s.stem}"/>')

    opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="ar" dir="rtl">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{book_id}</dc:identifier>
<dc:title>{escape(title)}</dc:title>
<dc:language>ar</dc:language>
<dc:creator>King Fahd Glorious Qur'an Printing Complex (calligraphy: Uthman Taha)</dc:creator>
<meta property="dcterms:modified">{modified}</meta>
<meta property="rendition:layout">pre-paginated</meta>
<meta property="rendition:spread">none</meta>
<meta property="rendition:orientation">portrait</meta>
<meta name="cover" content="i{screens[0].stem}"/>
<meta name="fixed-layout" content="true"/>
<meta name="original-resolution" content="{w}x{h}"/>
<meta name="book-type" content="comic"/>
<meta name="primary-writing-mode" content="horizontal-rl"/>
<meta name="zero-gutter" content="true"/>
<meta name="zero-margin" content="true"/>
<meta name="ke-border-color" content="#FFFFFF"/>
<meta name="ke-border-width" content="0"/>
<meta name="orientation-lock" content="portrait"/>
<meta name="region-mag" content="false"/>
</metadata>
<manifest>
{chr(10).join(manifest)}
</manifest>
<spine page-progression-direction="rtl" toc="ncx">
{chr(10).join(spine)}
</spine>
</package>
"""

    page_list = "\n".join(
        f'      <li><a href="text/{s.stem}.xhtml#page{s.page}">{s.page}</a></li>' for s in firsts
    )
    nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ar">
<head><title>{escape(title)}</title></head>
<body>
  <nav epub:type="toc" id="toc"><h1>{escape(title)}</h1>
{_nav_ol(tree, href)}
  </nav>
  <nav epub:type="page-list" hidden=""><ol>
{page_list}
  </ol></nav>
  <nav epub:type="landmarks" hidden=""><ol>
    <li><a epub:type="bodymatter" href="{href[1]}">Al-Fatihah</a></li>
  </ol></nav>
</body>
</html>
"""
    ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ar">
<head><meta name="dtb:uid" content="{book_id}"/><meta name="dtb:depth" content="3"/></head>
<docTitle><text>{escape(title)}</text></docTitle>
<navMap>{_ncx_points(tree, href, [0])}</navMap>
<pageList>{"".join(f'<pageTarget id="pg{s.page}" type="normal" value="{s.page}"><navLabel><text>{s.page}</text></navLabel><content src="text/{s.stem}.xhtml#page{s.page}"/></pageTarget>' for s in firsts)}</pageList>
</ncx>
"""
    container = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
        for s in screens:
            z.writestr(f"OEBPS/text/{s.stem}.xhtml", _page_xhtml(s, w, h), zipfile.ZIP_DEFLATED)
            # === PNGs are already compressed; storing them keeps the build fast. ===
            z.write(images / f"{s.stem}.png", f"OEBPS/img/{s.stem}.png", zipfile.ZIP_STORED)
