"""Covers for the books, drawn in the mushaf's own vocabulary: frame, bismillah, cartouche."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .render import INK, PAPER, ink_centered, quantize

# === (Arabic title, English title, subtitle) per book ===
TITLES = {
    "mushaf": ("المصحف الشريف", "The Noble Qur'an", "Madinah Mushaf"),
    "translation": ("المصحف الشريف", "The Noble Qur'an", "with the English translation of Saheeh International"),
    "companion": ("المصحف الشريف", "The Noble Qur'an", "Word by word, in English"),
}


def render_cover(book: str, w: int, h: int, qcf_fonts: Path, amiri: Path, serif: str, italic: str) -> Image.Image:
    arabic, english, subtitle = TITLES[book]
    img = Image.new("L", (w, h), PAPER)
    d = ImageDraw.Draw(img)

    # === double frame, thick outside and thin inside ===
    m, gap = round(w * 0.05), round(w * 0.015)
    d.rectangle((m, m, w - m, h - m), outline=INK, width=max(3, round(w * 0.008)))
    d.rectangle((m + gap, m + gap, w - m - gap, h - m - gap), outline=INK, width=max(1, round(w * 0.002)))

    # === the bismillah in the mushaf's own calligraphy ===
    bism = ImageFont.truetype(str(qcf_fonts / "QCF4_Hafs_01_W.woff2"), round(w * 0.075))
    ink_centered(d, (w / 2, h * 0.17), "\uf8dd", bism)

    # === the Arabic title in a cartouche, flanked by the surah-header ornaments ===
    title = ImageFont.truetype(str(amiri), round(w * 0.085))
    left, top, right, bottom = title.getbbox(arabic, anchor="ls")
    mid = h * 0.42
    half_w, half_h = (right - left) / 2 + w * 0.05, (bottom - top) / 2 + w * 0.04
    box = (w / 2 - half_w, mid - half_h, w / 2 + half_w, mid + half_h)
    d.rounded_rectangle(box, radius=half_h * 0.6, outline=INK, width=max(2, round(w * 0.005)))
    inset = w * 0.012
    d.rounded_rectangle((box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset),
                        radius=half_h * 0.6 - inset, outline=INK, width=1)
    ink_centered(d, (w / 2, mid), arabic, title)
    caps = ImageFont.truetype(str(qcf_fonts / "QCF4_QBSML.woff2"), round(half_h * 2.0))
    ink_centered(d, (box[0] - w * 0.01, mid), "\ufaf3", caps, "r")
    ink_centered(d, (box[2] + w * 0.01, mid), "\ufaf2", caps, "l")

    # === English titles ===
    d.text((w / 2, h * 0.585), english, font=ImageFont.truetype(serif, round(w * 0.062)), fill=INK, anchor="mm")
    sub = ImageFont.truetype(italic, round(w * 0.038))
    lines = _wrap(subtitle, sub, w * 0.7)
    for i, line in enumerate(lines):
        d.text((w / 2, h * 0.65 + i * w * 0.05), line, font=sub, fill=64, anchor="mm")

    # === colophon: riwayah and edition ===
    small = ImageFont.truetype(str(amiri), round(w * 0.045))
    d.text((w / 2, h * 0.82), "برواية حفص عن عاصم", font=small, fill=64, anchor="mm", direction="rtl")
    d.text((w / 2, h * 0.875), "King Fahd Complex · 1441 AH", font=ImageFont.truetype(serif, round(w * 0.03)),
           fill=96, anchor="mm")
    return quantize(img)


def _wrap(text, font, width):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    return lines + [current] if current else lines
