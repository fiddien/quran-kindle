"""Covers for the books: the woven rosette pattern above, the title centred at the foot.

Every book wears the same pattern; only the title and its one-line description
differ. The pattern thins to hairlines as it nears the title and leaves a quiet
white foot for the type, which keeps the cover light on a white Kindle.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import pattern
from .render import quantize

TITLES = {
    "mushaf": ("Madinah Mushaf", "The 604-page Madinah mushaf, line for line"),
    "companion": ("Word by Word", "Every word of the mushaf with its English meaning"),
    "translation": ("Saheeh International", "The mushaf with an English translation"),
}
KICKER = "THE NOBLE QUR'AN"
# === one rosette at the centre, its neighbours on the diagonals, the field cropped by the page ===
CELLS = ((0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, -2), (0, 2), (-2, 0), (2, 0))
FOOT = 0.78  # === where the white foot for the type begins, as a share of the height ===


def render_cover(book: str, w: int, h: int, inter: Path) -> Image.Image:
    """The cover for `book` at w x h; `inter` is the folder of Inter's woff2 files."""
    img = pattern.draw(w, h, centre=(0.5, 0.36), tip=0.3, cells=CELLS, taper=(0.55, 0.76))
    d = ImageDraw.Draw(img)
    d.rectangle((0, round(h * FOOT), w, h), fill=255)

    def face(weight, size):
        return ImageFont.truetype(str(inter / f"inter-latin-{weight}-normal.woff2"), round(size))

    title, note = TITLES[book]
    _tracked(d, (w / 2, h * 0.83), KICKER, face(500, w * 0.024), 0, 0.22)
    big = face(600, w * 0.08)
    while big.getlength(title) > w * 0.84:
        big = face(600, big.size - 1)
    d.text((w / 2, h * 0.905), title, font=big, fill=0, anchor="ms")
    d.text((w / 2, h * 0.955), note, font=face(400, w * 0.024), fill=90, anchor="ms")
    return quantize(img)


def _tracked(d, xy, text, font, fill, tracking):
    """Letter-spaced capitals, centred on xy."""
    gap = font.size * tracking
    width = sum(font.getlength(ch) for ch in text) + gap * (len(text) - 1)
    x = xy[0] - width / 2
    for ch in text:
        d.text((x, xy[1]), ch, font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + gap
