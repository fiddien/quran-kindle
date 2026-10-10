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


# === alternative styles ===

SANS_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
PARTS = {"mushaf": "I", "translation": "II", "companion": "III"}


def _bestseller(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Bold modern type over one large shape, like a popular non-fiction paperback."""
    img = Image.new("L", (w, h), 238)
    d = ImageDraw.Draw(img)
    # === one big arch, the shape of a mihrab, in a mid gray ===
    aw, top = w * 0.62, h * 0.12
    d.rectangle((w / 2 - aw / 2, top + aw / 2, w / 2 + aw / 2, h * 0.62), fill=85)
    d.ellipse((w / 2 - aw / 2, top, w / 2 + aw / 2, top + aw), fill=85)
    title = ImageFont.truetype(str(amiri), round(w * 0.11))
    _ink(d, (w / 2, h * 0.38), ARABIC, title, 255)
    # === the English title, very large and tight ===
    big = ImageFont.truetype(SANS_BOLD, round(w * 0.105))
    for i, word in enumerate(("THE NOBLE", "QUR'AN")):
        f = big
        while f.getlength(word) > w * 0.84:
            f = ImageFont.truetype(SANS_BOLD, f.size - 2)
        d.text((w / 2, h * 0.705 + i * w * 0.115), word, font=f, fill=0, anchor="mm")
    small = ImageFont.truetype(SANS, round(w * 0.03))
    for i, line in enumerate(_wrap(BOOKS[book].upper(), small, w * 0.8)):
        d.text((w / 2, h * 0.9 + i * w * 0.04), line.replace(chr(0xA0), " "), font=small, fill=60, anchor="mm")
    return quantize(img)


def _ordinary(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """A neutral cover that doesn't say what the book is."""
    img = Image.new("L", (w, h), 230)
    d = ImageDraw.Draw(img)
    d.rectangle((0, h * 0.58, w, h), fill=70)
    head = ImageFont.truetype(serif, round(w * 0.11))
    d.text((w * 0.1, h * 0.3), "Daily", font=head, fill=30, anchor="ls")
    d.text((w * 0.1, h * 0.3 + w * 0.13), "Reading", font=head, fill=30, anchor="ls")
    d.line((w * 0.1, h * 0.47, w * 0.35, h * 0.47), fill=30, width=max(2, round(w * 0.006)))
    part = ImageFont.truetype(SANS, round(w * 0.04))
    d.text((w * 0.1, h * 0.52), f"Part {PARTS[book]}", font=part, fill=60, anchor="ls")
    # === a quiet geometric mark in the dark band ===
    cx, cy, r = w * 0.72, h * 0.79, w * 0.12
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=200, width=max(2, round(w * 0.005)))
    d.ellipse((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55), fill=200)
    return quantize(img)


def _popart(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Halftone dots, flat shapes and strong contrast, in grayscale for e-ink."""
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    # === halftone background: dots grow toward the bottom ===
    step = w / 24
    y = step / 2
    while y < h:
        x = step / 2 + (step / 2 if int(y / step) % 2 else 0)
        rad = step * (0.12 + 0.3 * y / h)
        while x < w:
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=150)
            x += step
        y += step
    # === a bold eight-pointed star, black outline with an offset shadow ===
    cx, cy, r = w / 2, h * 0.42, w * 0.40
    shadow = [(x + w * 0.025, y + w * 0.025) for x, y in _pop_star(cx, cy, r)]
    d.polygon(shadow, fill=0)
    d.polygon(_pop_star(cx, cy, r), fill=255, outline=0, width=max(4, round(w * 0.012)))
    title = ImageFont.truetype(str(amiri), round(w * 0.13))
    while _ink_width2(title, ARABIC) > r * 1.3:
        title = ImageFont.truetype(str(amiri), title.size - 2)
    _ink(d, (cx, cy), ARABIC, title, 0)
    # === the English title on a black banner ===
    bh = h * 0.1
    d.rectangle((0, h * 0.72, w, h * 0.72 + bh), fill=0)
    f = ImageFont.truetype(SANS_BOLD, round(bh * 0.55))
    d.text((w / 2, h * 0.72 + bh / 2), "THE NOBLE QUR'AN", font=f, fill=255, anchor="mm")
    small = ImageFont.truetype(SANS_BOLD, round(w * 0.032))
    label = BOOKS[book].upper().replace(chr(0xA0), " ")
    tw = small.getlength(label) + w * 0.06
    d.rectangle((w / 2 - tw / 2, h * 0.86, w / 2 + tw / 2, h * 0.86 + w * 0.065), fill=255, outline=0, width=3)
    d.text((w / 2, h * 0.86 + w * 0.0325), label, font=small, fill=0, anchor="mm")
    return quantize(img)


def _pop_star(cx, cy, r):
    import math
    inner = r * math.cos(math.pi / 4) / math.cos(math.pi / 8)
    return [(cx + (r if i % 2 == 0 else inner) * math.cos(math.pi / 8 * i - math.pi / 2),
             cy + (r if i % 2 == 0 else inner) * math.sin(math.pi / 8 * i - math.pi / 2)) for i in range(16)]


def _ink_width2(font, text):
    left, _, right, _ = font.getbbox(text, anchor="ls")
    return right - left


def _calligraphy(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Bestseller: oversized pale calligraphy running off the edges, crisp English over it."""
    img = Image.new("L", (w, h), 245)
    d = ImageDraw.Draw(img)
    huge = ImageFont.truetype(str(amiri), round(w * 0.62))
    _ink(d, (w * 0.42, h * 0.40), "القرآن", huge, 205)
    big = ImageFont.truetype(SANS_BOLD, round(w * 0.1))
    d.text((w * 0.08, h * 0.74), "THE NOBLE", font=big, fill=0, anchor="ls")
    d.text((w * 0.08, h * 0.74 + w * 0.11), "QUR'AN", font=big, fill=0, anchor="ls")
    title = ImageFont.truetype(str(amiri), round(w * 0.06))
    d.text((w * 0.92, h * 0.74 + w * 0.11), ARABIC, font=title, fill=0, anchor="rs")
    small = ImageFont.truetype(SANS, round(w * 0.028))
    d.text((w * 0.08, h * 0.93), BOOKS[book].upper().replace(chr(0xA0), " "), font=small, fill=60, anchor="ls")
    return quantize(img)


def _swiss(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Bestseller: left-aligned bold type, a thick rule, a small Arabic title."""
    img = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(img)
    x = w * 0.09
    d.rectangle((x, h * 0.1, x + w * 0.16, h * 0.1 + w * 0.025), fill=0)
    big = ImageFont.truetype(SANS_BOLD, round(w * 0.135))
    for i, word in enumerate(("The", "Noble", "Qur'an")):
        d.text((x - w * 0.006, h * 0.27 + i * w * 0.15), word, font=big, fill=0, anchor="ls")
    d.line((x, h * 0.63, w - x, h * 0.63), fill=0, width=max(3, round(w * 0.008)))
    title = ImageFont.truetype(str(amiri), round(w * 0.08))
    d.text((w - x, h * 0.74), ARABIC, font=title, fill=0, anchor="rs", direction="rtl")
    small = ImageFont.truetype(SANS, round(w * 0.03))
    for i, line in enumerate(_wrap(BOOKS[book].replace(chr(0xA0), " "), small, w * 0.5)):
        d.text((x, h * 0.70 + i * w * 0.045), line, font=small, fill=80, anchor="ls")
    return quantize(img)


def _lattice(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Bestseller: an arch window filled with a fine eight-pointed-star lattice."""
    img = Image.new("L", (w, h), 240)
    d = ImageDraw.Draw(img)
    aw, top, bottom = w * 0.6, h * 0.08, h * 0.56
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle((w / 2 - aw / 2, top + aw / 2, w / 2 + aw / 2, bottom), fill=255)
    md.ellipse((w / 2 - aw / 2, top, w / 2 + aw / 2, top + aw), fill=255)
    pattern = Image.new("L", (w, h), 70)
    pd = ImageDraw.Draw(pattern)
    step = w * 0.1
    for row in range(-1, int(h / step) + 2):
        for col in range(-1, int(w / step) + 2):
            pd.polygon(_pop_star(col * step, row * step, step * 0.46), outline=170, width=max(1, round(w * 0.003)))
    img.paste(pattern, (0, 0), mask)
    d.arc((w / 2 - aw / 2, top, w / 2 + aw / 2, top + aw), 180, 360, fill=0, width=max(2, round(w * 0.005)))
    title = ImageFont.truetype(str(amiri), round(w * 0.1))
    _ink(d, (w / 2, h * 0.65), ARABIC, title, 0)
    big = ImageFont.truetype(SANS_BOLD, round(w * 0.065))
    d.text((w / 2, h * 0.76), "THE NOBLE QUR'AN", font=big, fill=0, anchor="mm")
    small = ImageFont.truetype(SANS, round(w * 0.028))
    for i, line in enumerate(_wrap(BOOKS[book].upper(), small, w * 0.8)):
        d.text((w / 2, h * 0.83 + i * w * 0.04), line.replace(chr(0xA0), " "), font=small, fill=70, anchor="mm")
    return quantize(img)


def _notebook(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Ordinary: a plain dark notebook with an elastic band and a small label."""
    img = Image.new("L", (w, h), 45)
    d = ImageDraw.Draw(img)
    d.rectangle((w * 0.84, 0, w * 0.87, h), fill=25)
    lw, lh = w * 0.42, w * 0.16
    lx, ly = w * 0.18, h * 0.62
    d.rectangle((lx, ly, lx + lw, ly + lh), fill=225)
    label = ImageFont.truetype(serif, round(w * 0.045))
    d.text((lx + lw / 2, ly + lh * 0.42), "Daily Reading", font=label, fill=40, anchor="mm")
    part = ImageFont.truetype(italic, round(w * 0.03))
    d.text((lx + lw / 2, ly + lh * 0.75), f"Part {PARTS[book]}", font=part, fill=90, anchor="mm")
    return quantize(img)


def _paperback(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Ordinary: a classic paperback, centred serif title inside a simple frame."""
    img = Image.new("L", (w, h), 236)
    d = ImageDraw.Draw(img)
    m = w * 0.08
    d.rectangle((m, m, w - m, h - m), outline=60, width=max(2, round(w * 0.004)))
    head = ImageFont.truetype(serif, round(w * 0.095))
    d.text((w / 2, h * 0.36), "Daily Reading", font=head, fill=30, anchor="mm")
    d.line((w * 0.42, h * 0.43, w * 0.58, h * 0.43), fill=60, width=max(1, round(w * 0.003)))
    part = ImageFont.truetype(italic, round(w * 0.045))
    d.text((w / 2, h * 0.49), f"Part {PARTS[book]}", font=part, fill=70, anchor="mm")
    dot = w * 0.012
    for i in (-1, 0, 1):
        cx = w / 2 + i * w * 0.05
        d.ellipse((cx - dot, h * 0.8 - dot, cx + dot, h * 0.8 + dot), fill=90)
    return quantize(img)


def _geometric(book, w, h, qcf_fonts, amiri, serif, italic, bold):
    """Ordinary: abstract stacked shapes, a small title in the corner."""
    img = Image.new("L", (w, h), 250)
    d = ImageDraw.Draw(img)
    d.ellipse((w * 0.18, h * 0.12, w * 0.82, h * 0.12 + w * 0.64), fill=200)
    d.rectangle((w * 0.3, h * 0.38, w * 0.95, h * 0.62), fill=110)
    d.ellipse((w * 0.08, h * 0.5, w * 0.38, h * 0.5 + w * 0.3), fill=40)
    head = ImageFont.truetype(SANS_BOLD, round(w * 0.055))
    d.text((w * 0.08, h * 0.84), "Daily Reading", font=head, fill=20, anchor="ls")
    part = ImageFont.truetype(SANS, round(w * 0.035))
    d.text((w * 0.08, h * 0.89), f"Part {PARTS[book]}", font=part, fill=90, anchor="ls")
    return quantize(img)


STYLES = {"bestseller": _bestseller, "calligraphy": _calligraphy, "swiss": _swiss, "lattice": _lattice,
          "ordinary": _ordinary, "notebook": _notebook, "paperback": _paperback, "geometric": _geometric,
          "popart": _popart}


def render_style(style: str, book: str, w: int, h: int, qcf_fonts: Path, amiri: Path, serif: str,
                 italic: str, bold: str) -> Image.Image:
    """Cover in one of the alternative STYLES."""
    return STYLES[style](book, w, h, qcf_fonts, amiri, serif, italic, bold)
