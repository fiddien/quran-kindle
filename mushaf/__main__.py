"""Command line: python -m mushaf --device paperwhite --book mushaf,companion"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import sources
from .companion import CompanionRenderer
from .data import PAGE_COUNT, load, load_glosses
from .epub import Screen, toc_tree, write_epub
from .pdf import write_pdf
from .render import DEVICES, Renderer

# === Arabic-capable font for the hizb label and page numbers ===
UI_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
# === serif faces for the English glosses (regular, italic) ===
GLOSS_FONTS = [
    ("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
    ("/System/Library/Fonts/Supplemental/Times New Roman.ttf",
     "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"),
    ("C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/timesi.ttf"),
]
TITLES = {
    "mushaf": "المصحف الشريف · Madinah Mushaf",
    "companion": "Madinah Mushaf · Word by Word (English)",
}

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
    p.add_argument("--book", default="mushaf,companion", help="comma list of mushaf,companion")
    p.add_argument("--formats", default="epub,pdf", help="comma list of epub,pdf")
    p.add_argument("--pages", help="render only these pages, e.g. 1-3,604 (for previews)")
    p.add_argument("--cache", type=Path, default=Path("cache"))
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--text-scale", type=float, default=0.85,
                   help="mushaf script size relative to full width; lower = more space between lines")
    p.add_argument("--ui-font", help="TTF with Arabic glyphs for header/page numbers")
    a = p.parse_args(argv)

    ui_font = a.ui_font or next((f for f in UI_FONTS if Path(f).exists()), None)
    if not ui_font:
        sys.exit("no UI font found; pass --ui-font /path/to/font.ttf (e.g. DejaVuSans.ttf)")
    gloss_fonts = next((f for f in GLOSS_FONTS if all(Path(x).exists() for x in f)), None)

    device = DEVICES[a.device]
    wanted = _pages(a.pages)
    for book in a.book.split(","):
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
            write_epub(screens, tree, images, stem.with_suffix(".epub"), *size)
            print(f"  wrote {stem.with_suffix('.epub')}")
        if "pdf" in a.formats:
            write_pdf(screens, tree, images, stem.with_suffix(".pdf"), *size)
            print(f"  wrote {stem.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
