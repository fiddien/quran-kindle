"""Package rendered screens as a PDF with a nested outline (bookmarks).

The page size is the screen size at 300 dpi, so the reader shows each page
edge to edge without rescaling. Every PDF page is labelled with its mushaf
page number, so a two-screen page shows as "50" on both screens in readers
that honour PDF page labels.
"""
from pathlib import Path

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def write_pdf(screens: list, tree: list, images: Path, out: Path, w: int, h: int,
              title: str) -> None:
    pw, ph = w * 72 / 300, h * 72 / 300
    c = canvas.Canvas(str(out), pagesize=(pw, ph), pageCompression=1)
    c.setTitle(title)
    c.setAuthor("King Fahd Glorious Qur'an Printing Complex")
    c.setViewerPreference("Direction", "R2L")
    for i, s in enumerate(screens):
        c.drawImage(ImageReader(str(images / f"{s.stem}.png")), 0, 0, pw, ph)
        if s.first:
            c.bookmarkPage(f"p{s.page}")
        c.addPageLabel(i, "D", s.page)
        c.showPage()

    def add(entries, level):
        for label, page, children in entries:
            c.addOutlineEntry(label, f"p{page}", level=level, closed=bool(children))
            add(children, level + 1)

    add(tree, 0)
    c.showOutline()
    c.save()
