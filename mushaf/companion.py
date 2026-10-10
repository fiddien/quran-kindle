"""Word-by-word companion: each mushaf line with an English gloss under every word.

A mushaf page needs about three screens' area at readable sizes, so each
page becomes three screens of five lines. Every screen carries the page's
number as its label, so "Go to page 50" can still find page 50.
"""
from PIL import Image, ImageDraw, ImageFont

from .data import Page
from .render import INK, PAPER, Renderer, ink_centered, quantize

GLOSS_INK = 48


class CompanionRenderer(Renderer):
    def __init__(self, *args, glosses: dict, gloss_font: str, gloss_italic: str,
                 lines_per_screen: int = 5, gloss_scale: float = 0.04, **kw):
        super().__init__(*args, **kw)
        self.lines_per_screen = lines_per_screen
        self.glosses = glosses
        self.gloss_font = gloss_font
        self.gloss_italic = gloss_italic
        w = self.device.width
        # === narrower margins than the mushaf: glosses need the width ===
        self.margin = round(w * 0.04)
        self.width = w - 2 * self.margin
        self.ar_size = round(w * 0.052)
        # === about 10 pt on a 6-inch 167-ppi screen ===
        self.gloss_size = round(w * gloss_scale)

    def parts(self, page: Page) -> list:
        n = self.lines_per_screen
        return [page.lines[i:i + n] for i in range(0, len(page.lines), n)]

    def screens(self, page: Page) -> list:
        """The page's screens as images."""
        parts = self.parts(page)
        out = []
        for i, part in enumerate(parts):
            img = Image.new("L", (self.device.width, self.device.height), PAPER)
            self.draw_screen(ImageDraw.Draw(img), page, part, i, len(parts))
            out.append(quantize(img))
        return out

    def screens_ops(self, page: Page) -> list:
        """The page's screens as (Screen, recorded ops), for the text edition."""
        from .epub import Screen
        from .textbook import Recorder

        parts = self.parts(page)
        out = []
        for i, part in enumerate(parts):
            rec = Recorder()
            self.draw_screen(rec, page, part, i, len(parts))
            out.append((Screen(f"c{page.number:03d}{chr(ord('a') + i)}", page.number, i == 0), rec.ops))
        return out

    # === one screen ===

    def draw_screen(self, draw, page, lines, index, count):
        label = "Word by word" + (f" · {index + 1} of {count}" if count > 1 else "")
        italic = ImageFont.truetype(self.gloss_italic, round(self.top * 0.4))

        def center(d, xy, band):
            d.text(xy, label, font=italic, fill=96, anchor="mm")

        self.frame(draw, page, center=center)
        top = self.top + self.device.height * 0.01
        bottom = self.device.height - self.device.height * 0.012

        # === shrink everything a little if a dense screen would overflow ===
        scale = 1.0
        while True:
            rows = [self._layout(line, scale) for line in lines]
            need = sum(r["height"] for r in rows)
            if need <= bottom - top or scale < 0.7:
                break
            scale -= 0.04
        gap = max(0, (bottom - top - need) / len(rows))
        y = top + gap / 2
        for row in rows:
            self._draw_row(draw, row, y)
            y += row["height"] + gap

    def _layout(self, line, scale):
        words = line["words"]
        kind = words[0]["type"]
        ar = round(self.ar_size * scale)
        if kind == "surah_header":
            return {"kind": kind, "word": words[0], "height": ar * 1.7}
        if kind == "bismillah":
            return {"kind": kind, "word": words[0], "height": ar * 1.5, "size": ar}

        # === wrap glosses narrower, then shrink them, until the row fits the width ===
        # === as a last resort, shrink the Arabic of a very dense line too ===
        attempts = [(1.0, f, w) for f in (1.0, 0.92, 0.85, 0.78) for w in (4.5, 3.6, 2.8, 2.2)]
        attempts += [(a, 0.78, 2.2) for a in (0.94, 0.88, 0.82, 0.76, 0.7)]
        full = ar
        for ar_scale, font_scale, wrap_em in attempts:
            ar = round(full * ar_scale)
            gsize = round(self.gloss_size * scale * font_scale)
            gfont = ImageFont.truetype(self.gloss_font, gsize)
            min_gap = gsize * 0.6
            cells = []
            for w in words:
                font = self.font(w["font"], ar)
                aw = font.getlength(w["char"])
                gloss = self.glosses.get((w.get("verse_key"), w.get("position"))) if w["type"] == "word" else None
                lines = wrap(gloss, gfont, max(aw, gsize * wrap_em)) if gloss else []
                cw = max([aw] + [gfont.getlength(s) for s in lines])
                cells.append({"word": w, "font": font, "aw": aw, "gloss": lines, "cw": cw})
            natural = sum(c["cw"] for c in cells)
            if natural + min_gap * (len(cells) - 1) <= self.width:
                break
        gloss_lines = max((len(c["gloss"]) for c in cells), default=0)
        return {
            "kind": "text", "cells": cells, "ar": ar, "full": full, "gfont": gfont, "gsize": gsize,
            "natural": natural, "min_gap": min_gap,
            "height": full * 1.38 + gloss_lines * gsize * 1.12,
        }

    def _draw_row(self, draw, row, y):
        w = self.device.width
        if row["kind"] == "surah_header":
            self.surah_banner(draw, row["word"], y, row["height"])
            return
        if row["kind"] == "bismillah":
            font = self.font(row["word"]["font"], row["size"])
            ink_centered(draw, (w / 2, y + row["height"] / 2), row["word"]["char"], font)
            return

        cells, gsize = row["cells"], row["gsize"]
        if row["natural"] + row["min_gap"] * (len(cells) - 1) >= self.width * 0.85 and len(cells) > 1:
            gap = max(row["min_gap"], (self.width - row["natural"]) / (len(cells) - 1))
            x = w - self.margin
        else:  # === short line: keep words together, centered ===
            gap = gsize * 1.2
            span = row["natural"] + gap * (len(cells) - 1)
            x = w - (w - span) / 2
        base = y + row["full"] * 0.8
        # === a shared baseline keeps short glosses ("as", "we") level with the rest ===
        gloss_base = y + row["full"] * 1.3 + row["gfont"].getmetrics()[0]
        # === right to left, as in the mushaf; each gloss is centered under its word ===
        for c in cells:
            cw = c["cw"]
            mid = x - cw / 2
            draw.text((mid - c["aw"] / 2, base), c["word"]["char"], font=c["font"],
                      fill=INK, anchor="ls")
            for i, text in enumerate(c["gloss"]):
                draw.text((mid, gloss_base + i * gsize * 1.12), text, font=row["gfont"],
                          fill=GLOSS_INK, anchor="ms")
            x -= cw + gap


def wrap(text: str, font, width: float) -> list:
    lines, current = [], ""
    for token in text.split():
        candidate = f"{current} {token}".strip()
        if not current or font.getlength(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = token
    if current:
        lines.append(current)
    return lines
