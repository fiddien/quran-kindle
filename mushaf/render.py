"""Render mushaf pages to grayscale images sized for a specific e-reader screen."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .data import Mushaf, Page, arabic_number

INK = 0
PAPER = 255
BASELINE = 0.58  # === baseline position within a line's slot, as a share of the pitch ===
SHORT_LINE = 0.9  # === lines narrower than this share of the text width are centered ===


@dataclass(frozen=True)
class Device:
    name: str
    width: int
    height: int


DEVICES = {
    "paperwhite": Device("Kindle Paperwhite (2021+), 6.8in 300ppi", 1236, 1648),
    "paperwhite-old": Device("Kindle Paperwhite 3/4, 6in 300ppi", 1072, 1448),
    "kindle": Device("Kindle Basic (2022+), 6in 300ppi", 1072, 1448),
    "oasis": Device("Kindle Oasis, 7in 300ppi", 1264, 1680),
    "scribe": Device("Kindle Scribe, 10.2in 300ppi", 1860, 2480),
    "kobo-clara": Device("Kobo Clara HD/2E/BW, 6in 300ppi", 1072, 1448),
    "kobo-libra": Device("Kobo Libra 2/Colour, 7in 300ppi", 1264, 1680),
}


class Renderer:
    def __init__(self, mushaf: Mushaf, fonts: Path, device: Device, ui_font: str,
                 text_scale: float = 0.85):
        self.mushaf = mushaf
        self.fonts = fonts
        self.device = device
        self.ui_font = ui_font
        w, h = device.width, device.height
        # === Smaller text means narrower lines, so the side margins grow with it and ===
        # === the fixed 15-line pitch leaves more white space between lines. ===
        self.text_width = round(w * 0.95 * text_scale)
        self.margin = (w - self.text_width) // 2
        self.top = round(h * 0.045)  # === running header band ===
        self.bottom = round(h * 0.012)  # === just enough to keep descenders off the edge ===
        # === QCF4 lines are about 16.1 em wide; fit the median line to the text width. ===
        self.size = round(self.text_width / 16.2)
        # === start the lines low enough that the tallest first-line marks clear the header rule ===
        reach = self._tallest_first_line()
        pad = self.size * 0.12
        self.lines_top = max(self.top, (self.top - 3 + pad + reach - BASELINE * (h - self.bottom) / 15)
                             / (1 - BASELINE / 15))
        self.pitch = (h - self.lines_top - self.bottom) / 15

    def _tallest_first_line(self) -> float:
        """How far the highest ink of any page's first text line rises above its baseline."""
        reach = 0
        for page in self.mushaf.pages:
            for w in page.lines[0]["words"]:
                if w["type"] in ("word", "end", "quarter"):
                    top = self.font(w["font"], self.size).getbbox(w["char"], anchor="ls")[1]
                    reach = max(reach, -top)
        return reach

    @lru_cache(maxsize=None)
    def font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        path = self.fonts / f"{name}_W.woff2"
        if not path.exists():
            path = self.fonts / f"{name}.woff2"
        return ImageFont.truetype(
            str(path),
            size,
            layout_engine=ImageFont.Layout.BASIC,
        )

    @lru_cache(maxsize=None)
    def ui(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(self.ui_font, size)

    # === page ===

    def render(self, page: Page) -> Image.Image:
        img = Image.new("L", (self.device.width, self.device.height), PAPER)
        self.draw_page(ImageDraw.Draw(img), page)
        return quantize(img)

    def draw_page(self, draw, page: Page) -> None:
        """Draw one page onto anything with ImageDraw's text/line/rectangle methods."""
        self.frame(draw, page)
        if len(page.lines) == 15:
            slots = [self.lines_top + i * self.pitch for i in range(15)]
        else:  # === the two opening pages: center the short block vertically ===
            n = len(page.lines)
            start = self.lines_top + (15 - n) * self.pitch / 2
            slots = [start + i * self.pitch for i in range(n)]
        opening = page.number <= 2
        for line, y in zip(page.lines, slots):
            kind = line["words"][0]["type"]
            if kind == "surah_header":
                self.surah_banner(draw, line["words"][0], y, self.pitch)
            elif kind == "bismillah":
                word = line["words"][0]
                font = self.font(word["font"], round(self.size * 0.82))
                ink_centered(draw, (self.device.width / 2, y + self.pitch * 0.42), word["char"], font)
            else:
                self._line(draw, line["words"], y, centered=opening)

    def _baseline(self, y: float) -> float:
        # === QCF4 ink sits roughly 0.55 em above and 0.4 em below the baseline. ===
        return y + self.pitch * BASELINE

    def _line(self, draw, words, y, centered=False):
        size = self.size
        widths = [self.font(w["font"], size).getlength(w["char"]) for w in words]
        natural = sum(widths)
        if natural > self.text_width:  # === rare wide line: shrink it to fit ===
            size = int(size * self.text_width / natural)
            widths = [self.font(w["font"], size).getlength(w["char"]) for w in words]
            natural = sum(widths)
        if centered or natural < self.text_width * SHORT_LINE or len(words) == 1:
            gap = size * 0.12 if len(words) > 1 else 0
            span = natural + gap * (len(words) - 1)
            x = self.device.width - (self.device.width - span) / 2
        else:
            gap = (self.text_width - natural) / (len(words) - 1)
            x = self.device.width - self.margin
        base = self._baseline(y)
        # === Arabic runs right to left: place each glyph leftwards from the right edge. ===
        for word, width in zip(words, widths):
            x -= width
            draw.text((x, base), word["char"], font=self.font(word["font"], size),
                      fill=INK, anchor="ls")
            x -= gap

    def surah_banner(self, draw, word, y, h):
        """A rounded double-frame cartouche around the surah name, ornaments outside its ends."""
        w = self.device.width
        title = self.font("QCF4_QBSML", round(h * 0.46))
        left, _, right, _ = title.getbbox(word["char"], anchor="ls")
        half = (right - left) / 2 + h * 0.9
        cx, mid = w / 2, y + h / 2
        top, bottom = y + h * 0.16, y + h * 0.84
        draw.rounded_rectangle((cx - half, top, cx + half, bottom), radius=h * 0.3, outline=INK, width=3)
        inset = h * 0.08
        draw.rounded_rectangle((cx - half + inset, top + inset, cx + half - inset, bottom - inset),
                               radius=h * 0.24, outline=INK, width=1)
        cap = self.font("QCF4_QBSML", round(h * 0.8))
        ink_centered(draw, (cx - half - h * 0.05, mid), "\ufaf3", cap, "r")
        ink_centered(draw, (cx + half + h * 0.05, mid), "\ufaf2", cap, "l")
        # === hairlines from the ornaments out to the text margins ===
        draw.line((self.margin, mid, cx - half - h * 0.7, mid), fill=120, width=1)
        draw.line((cx + half + h * 0.7, mid, w - self.margin, mid), fill=120, width=1)
        ink_centered(draw, (cx, mid), word["char"], title)

    # === frame: spine shadow and running header ===

    def frame(self, draw, page: Page, center=None):
        """Mark which side of the open mushaf this page sits on.

        Odd pages are right-hand pages: the binding is on their left, so the
        spine shadow runs down the left edge and the page number sits in the
        outer (right) corner. Even pages mirror this.
        """
        w, h = self.device.width, self.device.height
        right_hand = page.number % 2 == 1
        shadow = round(self.margin * 0.45)
        for i in range(shadow):
            # === darkest at the binding, fading quadratically into the paper ===
            gray = round(PAPER - 64 * (1 - i / shadow) ** 2)
            x = i if right_hand else w - 1 - i
            draw.line((x, 0, x, h), fill=gray)

        y = self.top * 0.55
        band = self.top * 0.9
        inner_x = self.margin if right_hand else w - self.margin
        outer_x = w - self.margin if right_hand else self.margin
        number = self.ui(round(band * 0.55))
        draw.text((outer_x, y), arabic_number(page.number), font=number, fill=INK,
                  anchor="rm" if right_hand else "lm")
        name = self.font("QCF4_QBSML", round(band * 0.62))
        ink_centered(draw, (inner_x, y), chr(0xF1F8 + page.surah - 1), name,
                     "l" if right_hand else "r")
        if center is None:
            # === juz' label with the hizb beside it, both centered between the corners ===
            juz = self.font("QCF4_QBSML", round(band * 0.9))
            juz_char = chr(0xF2D0 + page.juz - 1)
            left, _, right, _ = juz.getbbox(juz_char, anchor="ls")
            ink_centered(draw, (w / 2 + band * 0.15, y), juz_char, juz, "l")
            draw.text((w / 2 - band * 0.15, y), f"الحزب {arabic_number(page.hizb)}",
                      font=self.ui(round(band * 0.34)), fill=96, anchor="rm", direction="rtl")
        else:
            center(draw, (w / 2, y), band)
        rule_y = self.top - 3
        draw.line((self.margin, rule_y, w - self.margin, rule_y), fill=160, width=1)


def quantize(img: Image.Image) -> Image.Image:
    """Snap to the 16 gray levels e-ink panels show, so edges don't shimmer."""
    return img.point(lambda v: min(255, round(v / 17) * 17))


def ink_centered(draw, xy, char, font, align="m"):
    """Draw a glyph so its visible ink (not its font box) is centered on xy.

    QCF glyphs carry large, uneven ascent/descent boxes, so metric-based
    anchors leave titles visibly off-center.
    """
    x, y = xy
    left, top, right, bottom = font.getbbox(char, anchor="ls")
    dy = y - (top + bottom) / 2
    if align == "l":
        dx = x - left
    elif align == "r":
        dx = x - right
    else:
        dx = x - (left + right) / 2
    draw.text((dx, dy), char, font=font, fill=INK, anchor="ls")
