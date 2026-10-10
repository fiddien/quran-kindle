"""Covers for the books: discreet and light, like the title page of a printed mushaf."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .render import quantize

ARABIC = "القرآن الكريم"
ENGLISH = "The Noble Qur'an"
# === the book's name, set small under the title ===
BOOKS = {
    "mushaf": "Madinah Mushaf",
    "translation": "with the translation of Saheeh\u00a0International",
    "companion": "Word by Word",
}
INK, SOFT, PAPER = 0, 110, 255


def render_cover(book: str, w: int, h: int, qcf_fonts: Path, amiri: Path, serif: str, italic: str,
                 bold: str) -> Image.Image:
    img = Image.new("L", (w, h), PAPER)
    d = ImageDraw.Draw(img)
    hair = max(1, round(w * 0.0025))

    # === one fine frame ===
    m = round(w * 0.07)
    d.rectangle((m, m, w - m, h - m), outline=SOFT, width=hair)

    # === the title, modest, between two hairlines, with a small ornament above ===
    cy = h * 0.43
    title = ImageFont.truetype(str(amiri), round(w * 0.09))
    _ink(d, (w / 2, cy), ARABIC, title, INK)
    left, top, right, bottom = title.getbbox(ARABIC, anchor="ls")
    half = (bottom - top) / 2 + w * 0.05
    rule = w * 0.2
    for y in (cy - half, cy + half):
        d.line((w / 2 - rule, y, w / 2 + rule, y), fill=SOFT, width=hair)
    ornament = ImageFont.truetype(str(qcf_fonts / "QCF4_QBSML.woff2"), round(w * 0.07))
    # === the surah-header end caps, back to back, make a small symmetric motif ===
    oy = cy - half - w * 0.07
    for char, side in (("\ufaf3", "r"), ("\ufaf2", "l")):
        left, top, right, bottom = ornament.getbbox(char, anchor="ls")
        x = w / 2 - right if side == "r" else w / 2 - left
        d.text((x, oy - (top + bottom) / 2), char, font=ornament, fill=SOFT, anchor="ls")

    # === English, small and quiet ===
    english = ImageFont.truetype(serif, round(w * 0.045))
    d.text((w / 2, cy + half + w * 0.075), ENGLISH, font=english, fill=INK, anchor="mm")
    note = ImageFont.truetype(italic, round(w * 0.032))
    for i, line in enumerate(_wrap(BOOKS[book], note, w * 0.7)):
        d.text((w / 2, cy + half + w * 0.13 + i * w * 0.045), line.replace("\u00a0", " "), font=note,
               fill=SOFT, anchor="mm")
    return quantize(img)


def _ink(d, xy, text, font, fill):
    """Draw text centred on its ink rather than its font box."""
    left, top, right, bottom = font.getbbox(text, anchor="ls")
    x, y = xy
    d.text((x - (left + right) / 2, y - (top + bottom) / 2), text, font=font, fill=fill, anchor="ls")


def _wrap(text, font, width):
    """Wrap on ordinary spaces only, so no-break-joined names stay together."""
    lines, current = [], ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip(" ")
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines
