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
              title: str, paint=None) -> None:
    """Write the book; `paint(canvas, screen, scale)` draws a page instead of its PNG."""
    # === reportlab identifies outline entries by key, so each entry gets its own bookmark ===
    entries = []

    def flatten(items, level):
        for label, page, children in items:
            entries.append((f"o{len(entries)}", label, page, level, bool(children)))
            flatten(children, level + 1)

    flatten(tree, 0)
    keys = {}
    for key, _, page, _, _ in entries:
        keys.setdefault(page, []).append(key)

    pw, ph = w * 72 / 300, h * 72 / 300
    c = canvas.Canvas(str(out), pagesize=(pw, ph), pageCompression=1)
    c.setTitle(title)
    c.setAuthor("King Fahd Glorious Qur'an Printing Complex")
    c.setViewerPreference("Direction", "R2L")
    for i, s in enumerate(screens):
        if paint:
            paint(c, s, 72 / 300)
        else:
            c.drawImage(ImageReader(str(images / f"{s.stem}.png")), 0, 0, pw, ph)
        if s.first:
            for key in keys.get(s.page, []):
                c.bookmarkPage(key)
        for key in keys.get(s.stem, []):
            c.bookmarkPage(key)
        # === every screen is a link target under its own stem ===
        c.bookmarkPage(s.stem)
        c.addPageLabel(i, "D", s.page)
        c.showPage()

    for key, label, _, level, closed in entries:
        c.addOutlineEntry(label, key, level=level, closed=closed)
    c.showOutline()
    c.save()
