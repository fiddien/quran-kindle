"""Covers for the books: bold shapes that stay recognisable as library thumbnails."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .render import INK, PAPER, quantize

ARABIC = "القرآن الكريم"
ENGLISH = "The Noble Qur'an"
NBSP = "\u00a0"
# === (label in the bottom band, subtitle) per book; NBSP keeps a name on one line ===
BOOKS = {
    "mushaf": ("MADINAH MUSHAF", "Madinah Mushaf, riwayat Hafs"),
    "translation": ("WITH TRANSLATION", f"with the English translation of Saheeh{NBSP}International"),
    "companion": ("WORD BY WORD", "Word by word, in English"),
}


def render_cover(book: str, w: int, h: int, qcf_fonts: Path, amiri: Path, serif: str, italic: str,
                 bold: str) -> Image.Image:
    label, subtitle = BOOKS[book]
    img = Image.new("L", (w, h), PAPER)
    d = ImageDraw.Draw(img)

    # === black bands: the bismillah above, the book's name below ===
    band = round(h * 0.15)
    d.rectangle((0, 0, w, band), fill=INK)
    d.rectangle((0, h - band, w, h), fill=INK)
    bism = ImageFont.truetype(str(qcf_fonts / "QCF4_Hafs_01_W.woff2"), round(w * 0.085))
    _ink(d, (w / 2, band * 0.52), "\uf8dd", bism, PAPER)
    tag = ImageFont.truetype(bold, round(w * 0.07))
    while tag.getlength(label) > w * 0.86:
        tag = ImageFont.truetype(bold, tag.size - 2)
    d.text((w / 2, h - band / 2), label, font=tag, fill=PAPER, anchor="mm")

    # === the eight-pointed star (khatam) with the Arabic title inside ===
    cx, cy, r = w / 2, h * 0.43, w * 0.33
    for radius, width in ((r, max(3, round(w * 0.01))), (r * 0.93, max(1, round(w * 0.003)))):
        d.polygon(_star(cx, cy, radius), outline=INK, width=width)
    title = ImageFont.truetype(str(amiri), round(w * 0.13))
    while _ink_width(title, ARABIC) > r * 1.32:
        title = ImageFont.truetype(str(amiri), title.size - 2)
    _ink(d, (cx, cy), ARABIC, title, INK, stroke=max(1, round(w * 0.002)))

    # === English titles under the star ===
    d.text((w / 2, h * 0.715), ENGLISH, font=ImageFont.truetype(bold, round(w * 0.065)), fill=INK, anchor="mm")
    sub = ImageFont.truetype(italic, round(w * 0.036))
    for i, line in enumerate(_wrap(subtitle, sub, w * 0.8)):
        d.text((w / 2, h * 0.765 + i * w * 0.048), line.replace(NBSP, " "), font=sub, fill=64, anchor="mm")
    return quantize(img)


def _star(cx, cy, r):
    """Two overlapping squares, drawn as one 16-point outline."""
    inner = r * math.cos(math.pi / 4) / math.cos(math.pi / 8)
    points = []
    for i in range(16):
        angle = math.pi / 8 * i - math.pi / 2
        radius = r if i % 2 == 0 else inner
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _ink(d, xy, text, font, fill, stroke=0):
    """Draw text centred on its ink; a thin stroke adds weight to a regular face."""
    left, top, right, bottom = font.getbbox(text, anchor="ls", stroke_width=stroke)
    x, y = xy
    d.text((x - (left + right) / 2, y - (top + bottom) / 2), text, font=font, fill=fill, anchor="ls",
           stroke_width=stroke, stroke_fill=fill)


def _ink_width(font, text):
    left, _, right, _ = font.getbbox(text, anchor="ls")
    return right - left


def _wrap(text, font, width):
    """Wrap on ordinary spaces only, so NBSP-joined names stay together."""
    lines, current = [], ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip(" ")
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines
