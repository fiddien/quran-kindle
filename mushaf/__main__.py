"""Command line: python -m mushaf --device paperwhite"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import sources
from .data import load
from .epub import write_epub
from .pdf import write_pdf
from .render import DEVICES, Renderer

UI_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_renderer = None


def _init(qcf4, meta, device, ui_font, text_scale):
    global _renderer
    _renderer = Renderer(load(qcf4, meta), qcf4 / "fonts-woff2", device, ui_font, text_scale)


def _render(args):
    n, out = args
    _renderer.render(_renderer.mushaf.pages[n - 1]).save(out / f"p{n:03d}.png", optimize=True)
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", choices=sorted(DEVICES), default="paperwhite")
    p.add_argument("--formats", default="epub,pdf", help="comma list of epub,pdf,png")
    p.add_argument("--pages", help="render only these pages, e.g. 1-3,604 (for previews)")
    p.add_argument("--cache", type=Path, default=Path("cache"))
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--text-scale", type=float, default=0.92,
                   help="script size relative to full width; lower = more space between lines")
    p.add_argument("--ui-font", help="TTF with Arabic glyphs for header/page numbers")
    a = p.parse_args(argv)

    ui_font = a.ui_font or next((f for f in UI_FONT_CANDIDATES if Path(f).exists()), None)
    if not ui_font:
        sys.exit("no UI font found; pass --ui-font /path/to/font.ttf (e.g. DejaVuSans.ttf)")

    qcf4 = sources.fetch("quran-qcf4", a.cache)
    meta = sources.fetch("quran-meta", a.cache)
    device = DEVICES[a.device]
    images = a.out / a.device / "png"
    images.mkdir(parents=True, exist_ok=True)

    if a.pages:
        wanted = []
        for part in a.pages.split(","):
            lo, _, hi = part.partition("-")
            wanted.extend(range(int(lo), int(hi or lo) + 1))
    else:
        wanted = list(range(1, 605))

    print(f"rendering {len(wanted)} pages for {device.name} ({device.width}x{device.height})")
    with ProcessPoolExecutor(initializer=_init, initargs=(qcf4, meta, device, ui_font, a.text_scale)) as pool:
        for i, _ in enumerate(pool.map(_render, [(n, images) for n in wanted]), 1):
            if i % 50 == 0 or i == len(wanted):
                print(f"  {i}/{len(wanted)}")

    if a.pages:
        print(f"preview pages written to {images}")
        return

    mushaf = load(qcf4, meta)
    title = "المصحف الشريف · Madinah Mushaf"
    formats = a.formats.split(",")
    stem = a.out / a.device / f"mushaf-madinah-{a.device}"
    if "epub" in formats:
        write_epub(mushaf, images, stem.with_suffix(".epub"), device.width, device.height, title)
        print(f"wrote {stem.with_suffix('.epub')}")
    if "pdf" in formats:
        write_pdf(mushaf, images, stem.with_suffix(".pdf"), device.width, device.height, title)
        print(f"wrote {stem.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
