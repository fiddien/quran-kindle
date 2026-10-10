"""Command line: python -m mushaf --device paperwhite --book mushaf,companion"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import sources, textbook
from .companion import CompanionRenderer
from .cover import render_cover
from .translation import TranslationRenderer, load_translation
from .data import PAGE_COUNT, load, load_glosses
from .epub import Screen, toc_tree, write_epub
from .pdf import write_pdf
from .render import DEVICES, Device, Renderer

# === Arabic-capable font for the hizb label and page numbers ===
UI_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
# === serif faces for the English text (regular, italic, bold) ===
GLOSS_FONTS = [
    ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Times New Roman.ttf",
     "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
     "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"),
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesi.ttf", "C:/Windows/Fonts/timesbd.ttf"),
]
TITLES = {
    "mushaf": "القرآن الكريم · Madinah Mushaf",
    "companion": "القرآن الكريم · Word by Word (English)",
    "mushaf-text": "القرآن الكريم · Madinah Mushaf (text)",
    "companion-text": "القرآن الكريم · Word by Word (English, text)",
    "translation-text": "القرآن الكريم · with Saheeh International translation",
}
# === text books and the cover each one wears ===
TEXT_BOOKS = {"mushaf-text": "mushaf", "companion-text": "companion", "translation-text": "translation"}

_renderer = None


def _init(book, cache, device, ui_font, gloss_fonts, text_scale):
    global _renderer
    qcf4 = sources.fetch("quran-qcf4", cache)
    mushaf = load(qcf4, sources.fetch("quran-meta", cache))
    args = (mushaf, qcf4 / "fonts-woff2", device, ui_font, text_scale)
    if book == "companion":
        glosses = load_glosses(mushaf, sources.fetch("quran-wbw", cache))
        _renderer = CompanionRenderer(*args, glosses=glosses, gloss_font=gloss_fonts[0],
                                      gloss_italic=gloss_fonts[1])
    else:
        _renderer = Renderer(*args)


def _render(job):
    """Render one mushaf page; return its screens in reading order."""
    n, out = job
    page = _renderer.mushaf.pages[n - 1]
    if isinstance(_renderer, CompanionRenderer):
        images = _renderer.screens(page)
        stems = [f"c{n:03d}{chr(ord('a') + i)}" for i in range(len(images))]
    else:
        images, stems = [_renderer.render(page)], [f"p{n:03d}"]
    for img, stem in zip(images, stems):
        img.save(out / f"{stem}.png", optimize=True)
    return [Screen(stem, n, i == 0) for i, stem in enumerate(stems)]


def _pages(spec):
    if not spec:
        return list(range(1, PAGE_COUNT + 1))
    wanted = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        wanted.extend(range(int(lo), int(hi or lo) + 1))
    return wanted


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", choices=sorted(DEVICES), default="paperwhite")
    p.add_argument("--book", default="mushaf,companion", help="comma list of mushaf,companion (images) and mushaf-text,companion-text,translation-text")
    p.add_argument("--formats", default="epub,pdf", help="comma list of epub,pdf")
    p.add_argument("--pages", help="render only these pages, e.g. 1-3,604 (for previews)")
    p.add_argument("--cache", type=Path, default=Path("cache"))
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--text-scale", type=float, default=0.85,
                   help="mushaf script size relative to full width; lower = more space between lines")
    p.add_argument("--script-scale", type=float, default=1.0,
                   help="script size within the same line width; below 1 widens the word spacing")
    p.add_argument("--pdf-footer", type=float, default=0.0,
                   help="shorten text-PDF pages by this share of the screen height (default: full height)")
    p.add_argument("--ui-font", help="TTF with Arabic glyphs for header/page numbers")
    a = p.parse_args(argv)

    ui_font = a.ui_font or next((f for f in UI_FONTS if Path(f).exists()), None)
    if not ui_font:
        sys.exit("no UI font found; pass --ui-font /path/to/font.ttf (e.g. DejaVuSans.ttf)")
    gloss_fonts = next((f for f in GLOSS_FONTS if all(Path(x).exists() for x in f)), None)

    # === download sources once, before the worker processes start reading them ===
    for name in ("quran-qcf4", "quran-meta", "quran-wbw", "amiri-quran", "quran-cloud"):
        sources.fetch(name, a.cache)

    device = DEVICES[a.device]
    wanted = _pages(a.pages)
    for book in a.book.split(","):
        if book in TEXT_BOOKS:
            if not gloss_fonts:
                sys.exit("no serif font found for the English text (install Liberation or DejaVu fonts)")
            # === each text book in its own process: reportlab keeps font state between PDFs ===
            with ProcessPoolExecutor(max_workers=1) as solo:
                solo.submit(_text_book, book, a, device, ui_font, gloss_fonts, wanted).result()
            continue
        if book == "companion" and not gloss_fonts:
            sys.exit("no serif font found for the English glosses (install Liberation or DejaVu fonts)")
        images = a.out / a.device / book
        images.mkdir(parents=True, exist_ok=True)
        print(f"{book}: rendering {len(wanted)} pages for {device.name} ({device.width}x{device.height})")
        screens = []
        init = (book, a.cache, device, ui_font, gloss_fonts, a.text_scale)
        with ProcessPoolExecutor(initializer=_init, initargs=init) as pool:
            for i, page_screens in enumerate(pool.map(_render, [(n, images) for n in wanted]), 1):
                screens.extend(page_screens)
                if i % 50 == 0 or i == len(wanted):
                    print(f"  {i}/{len(wanted)}")
        if a.pages:
            print(f"  preview images written to {images}")
            continue

        mushaf = load(sources.fetch("quran-qcf4", a.cache), sources.fetch("quran-meta", a.cache))
        tree = toc_tree(mushaf, pages=book == "companion")
        stem = a.out / a.device / f"{book}-{a.device}"
        size = (device.width, device.height, TITLES[book])
        if "epub" in a.formats:
            cover = _cover_png(book, device, a.cache, gloss_fonts)
            write_epub(screens, tree, images, stem.with_suffix(".epub"), *size,
                       assets={"img/cover.png": ("image/png", cover)}, cover="img/cover.png")
            print(f"  wrote {stem.with_suffix('.epub')}")
        if "pdf" in a.formats:
            write_pdf(screens, tree, images, stem.with_suffix(".pdf"), *size)
            print(f"  wrote {stem.with_suffix('.pdf')}")


def _cover_png(key: str, device, cache: Path, fonts) -> bytes:
    import io

    qcf4 = sources.fetch("quran-qcf4", cache)
    amiri = sources.fetch("amiri-quran", cache) / "files" / "amiri-quran-arabic-400-normal.woff2"
    img = render_cover(key, device.width, device.height, qcf4 / "fonts-woff2", amiri, *fonts)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _text_book(book, a, device, ui_font, fonts, wanted):
    """A text edition (real, highlightable text) as EPUB and/or PDF."""
    qcf4 = sources.fetch("quran-qcf4", a.cache)
    mushaf = load(qcf4, sources.fetch("quran-meta", a.cache))

    def renderer(dev):
        args = (mushaf, qcf4 / "fonts-woff2", dev, ui_font, a.text_scale, a.script_scale)
        if book == "companion-text":
            glosses = load_glosses(mushaf, sources.fetch("quran-wbw", a.cache))
            return CompanionRenderer(*args, glosses=glosses, gloss_font=fonts[0], gloss_italic=fonts[1])
        if book == "translation-text":
            verses, names = load_translation(sources.fetch("quran-cloud", a.cache))
            return TranslationRenderer(*args, verses=verses, names=names, serif=fonts[0], italic=fonts[1],
                                       bold=fonts[2])
        return Renderer(*args)

    def screens(r):
        if book == "mushaf-text":
            return textbook.mushaf_screens(r, wanted)
        return [s for n in wanted for s in r.screens_ops(r.mushaf.pages[n - 1])]

    tree = toc_tree(mushaf, pages=book != "mushaf-text")
    stem = a.out / a.device / f"{book}-{a.device}{'-sample' if a.pages else ''}"
    stem.parent.mkdir(parents=True, exist_ok=True)
    print(f"{book}: laying out {len(wanted)} pages for {device.name}")
    if "epub" in a.formats:
        cover = _cover_png(TEXT_BOOKS[book], device, a.cache, fonts)
        textbook.build(screens(renderer(device)), tree, stem.with_suffix(".epub"), device.width, device.height,
                       TITLES[book], a.cache / "ttf", cover)
        print(f"  wrote {stem.with_suffix('.epub')}")
    if "pdf" in a.formats:
        # === optionally shorter, to leave room below the page for a reader's progress bar ===
        short = Device(device.name, device.width, round(device.height * (1 - a.pdf_footer)))
        textbook.build_pdf(screens(renderer(short)), tree, stem.with_suffix(".pdf"), short.width, short.height,
                           TITLES[book], a.cache / "ttf")
        print(f"  wrote {stem.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
