"""Package rendered pages as a PDF with a nested outline (bookmarks).

PDF page N is mushaf page N. The page size is the screen size at 300 dpi, so
the reader shows each page edge to edge without rescaling.
"""
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .data import Mushaf
from .epub import toc_tree


def write_pdf(mushaf: Mushaf, images: Path, out: Path, w: int, h: int, title: str) -> None:
    pw, ph = w * 72 / 300, h * 72 / 300
    c = canvas.Canvas(str(out), pagesize=(pw, ph), pageCompression=1)
    c.setTitle(title)
    c.setAuthor("King Fahd Glorious Qur'an Printing Complex")
    c.setViewerPreference("Direction", "R2L")
    for n in range(1, len(mushaf.pages) + 1):
        c.drawImage(ImageReader(str(images / f"p{n:03d}.png")), 0, 0, pw, ph)
        c.bookmarkPage(f"p{n}")
        c.showPage()

    def add(entries, level):
        for label, page, children in entries:
            c.addOutlineEntry(label, f"p{page}", level=level, closed=bool(children))
            add(children, level + 1)

    add(toc_tree(mushaf), 0)
    c.showOutline()
    c.save()
