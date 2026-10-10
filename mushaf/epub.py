"""Package rendered pages as a fixed-layout, right-to-left EPUB 3.

Spine position N is mushaf page N (there is no separate cover page), so the
reader's "Go to page" lands on the same page as the printed mushaf. The
Kindle-specific metadata mirrors what Kindle Comic Converter emits, which
Amazon's Send to Kindle turns into a full-screen fixed-layout book.
"""
import uuid
import zipfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from .data import Mushaf, arabic_number


def _page_xhtml(n: int, w: int, h: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ar" dir="rtl">
<head><title>{n}</title><meta name="viewport" content="width={w}, height={h}"/>
<style>html,body{{margin:0;padding:0}} img{{position:absolute;top:0;left:0;width:{w}px;height:{h}px}}</style>
</head>
<body><div><img src="../img/p{n:03d}.png" alt="{n}"/></div></body>
</html>
"""


def toc_tree(mushaf: Mushaf) -> list:
    """(label, page, children) entries shared by the EPUB and PDF outlines."""
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
    return [
        ("Surahs · السور", 1, surahs),
        ("Juz' & Hizb · الأجزاء والأحزاب", 1, juz),
    ]


def _nav_ol(entries, depth=0) -> str:
    pad = "  " * (depth + 2)
    out = [f"{pad}<ol>"]
    for label, page, children in entries:
        out.append(f'{pad}  <li><a href="text/p{page:03d}.xhtml">{escape(label)}</a>')
        if children:
            out.append(_nav_ol(children, depth + 1))
        out.append(f"{pad}  </li>")
    out.append(f"{pad}</ol>")
    return "\n".join(out)


def _ncx_points(entries, counter) -> str:
    out = []
    for label, page, children in entries:
        counter[0] += 1
        out.append(
            f'<navPoint id="n{counter[0]}"><navLabel><text>{escape(label)}</text></navLabel>'
            f'<content src="text/p{page:03d}.xhtml"/>'
        )
        out.append(_ncx_points(children, counter))
        out.append("</navPoint>")
    return "".join(out)


def write_epub(mushaf: Mushaf, images: Path, out: Path, w: int, h: int, title: str) -> None:
    pages = range(1, len(mushaf.pages) + 1)
    book_id = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'quran-kindle/' + title)}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tree = toc_tree(mushaf)

    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>']
    spine = []
    for n in pages:
        props = ' properties="cover-image"' if n == 1 else ""
        manifest.append(f'<item id="i{n:03d}" href="img/p{n:03d}.png" media-type="image/png"{props}/>')
        manifest.append(f'<item id="p{n:03d}" href="text/p{n:03d}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="p{n:03d}"/>')

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
<meta name="cover" content="i001"/>
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
        f'      <li><a href="text/p{n:03d}.xhtml">{n}</a></li>' for n in pages
    )
    nav = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="ar">
<head><title>{escape(title)}</title></head>
<body>
  <nav epub:type="toc" id="toc"><h1>{escape(title)}</h1>
{_nav_ol(tree)}
  </nav>
  <nav epub:type="page-list" hidden=""><ol>
{page_list}
  </ol></nav>
  <nav epub:type="landmarks" hidden=""><ol>
    <li><a epub:type="bodymatter" href="text/p001.xhtml">Al-Fatihah</a></li>
  </ol></nav>
</body>
</html>
"""
    ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ar">
<head><meta name="dtb:uid" content="{book_id}"/><meta name="dtb:depth" content="3"/></head>
<docTitle><text>{escape(title)}</text></docTitle>
<navMap>{_ncx_points(tree, [0])}</navMap>
<pageList>{"".join(f'<pageTarget id="pg{n}" type="normal" value="{n}"><navLabel><text>{n}</text></navLabel><content src="text/p{n:03d}.xhtml"/></pageTarget>' for n in pages)}</pageList>
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
        for n in pages:
            z.writestr(f"OEBPS/text/p{n:03d}.xhtml", _page_xhtml(n, w, h), zipfile.ZIP_DEFLATED)
            # === PNGs are already compressed; storing them keeps the build fast. ===
            z.write(images / f"p{n:03d}.png", f"OEBPS/img/p{n:03d}.png", zipfile.ZIP_STORED)
