"""Word-by-word companion: each mushaf line with an English gloss under every word.

A mushaf page needs about three screens' area at readable sizes, so each
page becomes three screens of five lines. Every screen carries the page's
number as its label, so "Go to page 50" can still find page 50.
"""
from PIL import Image, ImageDraw, ImageFont

from .data import Page
from .render import INK, PAPER, Renderer, ink_centered, quantize

GLOSS_INK = 48
# === sizes relative to the screen width; on a 300-ppi Paperwhite, 0.039 is about 11.5 pt ===
AR_SCALE = 0.039
GLOSS_SCALE = 0.0243

_hyphenator = None


class CompanionRenderer(Renderer):
    def __init__(self, *args, glosses: dict, gloss_font: str, gloss_italic: str,
                 lines_per_screen: int = 5, ar_scale: float = AR_SCALE, gloss_scale: float = GLOSS_SCALE,
                 **kw):
        super().__init__(*args, **kw)
        self.lines_per_screen = lines_per_screen
        self.glosses = glosses
        self.gloss_font = gloss_font
        self.gloss_italic = gloss_italic
        w = self.device.width
        # === narrower margins than the mushaf: glosses need the width ===
        self.margin = round(w * 0.04)
        self.width = w - 2 * self.margin
        # === one Arabic size and one English size for the whole book ===
        self.ar_size = round(w * ar_scale)
        self.gloss_size = round(w * gloss_scale)
        self.gfont = ImageFont.truetype(gloss_font, self.gloss_size)
        # === counts of rows too wide and screens too tall even after wrapping and hyphenating ===
        self.unfit = self.overfull = 0

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

        rows = [self._layout(line) for line in lines]
        need = sum(r["height"] for r in rows)
        self.overfull += need > bottom - top
        gap = max(0, (bottom - top - need) / len(rows))
        y = top + gap / 2
        for row in rows:
            self._draw_row(draw, row, y)
            y += row["height"] + gap

    def _layout(self, line):
        words = line["words"]
        kind = words[0]["type"]
        ar, gsize, gfont = self.ar_size, self.gloss_size, self.gfont
        if kind == "surah_header":
            return {"kind": kind, "word": words[0], "height": ar * 1.7}
        if kind == "bismillah":
            return {"kind": kind, "word": words[0], "height": ar * 1.5, "size": ar}

        # === both scripts keep one size for the whole book, and every mushaf line stays one row ===
        # === a crowded row first wraps its glosses narrower, then tightens the word spacing, ===
        # === and only then hyphenates its longest English words ===
        font = [self.font(w["font"], ar) for w in words]
        aw = [f.getlength(w["char"]) for f, w in zip(font, words)]
        gloss = [self.glosses.get((w.get("verse_key"), w.get("position"))) if w["type"] == "word" else None
                 for w in words]

        def cell(i, width, hyphenate=False):
            g = gloss[i]
            lines = wrap(g, gfont, width, hyphenate=hyphenate) if g else []
            cw = max([aw[i]] + [gfont.getlength(s) for s in lines])
            return {"word": words[i], "font": font[i], "aw": aw[i], "gloss": lines, "cw": cw}

        def fits(cells, gap_em):
            return sum(c["cw"] for c in cells) + gsize * gap_em * (len(cells) - 1) <= self.width

        gap_em = 0.45
        for wrap_em in (4.5, 3.6, 2.8, 2.2, 1.6, 1.0, 0):
            cells = [cell(i, max(aw[i], gsize * wrap_em)) for i in range(len(words))]
            if fits(cells, gap_em):
                break
        else:
            for gap_em in (0.38, 0.3):
                if fits(cells, gap_em):
                    break
            else:
                # === hyphenate one column at a time, widest first, until the line fits ===
                done = set()
                while not fits(cells, gap_em):
                    open_ = [i for i, c in enumerate(cells) if i not in done and c["cw"] > c["aw"] + 1]
                    if not open_:
                        break
                    i = max(open_, key=lambda k: cells[k]["cw"])
                    narrower = cell(i, cells[i]["cw"] - gsize * 0.2, hyphenate=True)
                    if narrower["cw"] < cells[i]["cw"]:
                        cells[i] = narrower
                    else:
                        done.add(i)
        natural = sum(c["cw"] for c in cells)
        min_gap = gsize * gap_em
        if natural + min_gap * (len(cells) - 1) > self.width:
            # === last resort, for the densest line or two: whatever spacing is left ===
            min_gap = max(0, (self.width - natural) / max(1, len(cells) - 1))
            self.unfit += natural > self.width
        gloss_lines = max((len(c["gloss"]) for c in cells), default=0)
        return {
            "kind": "text", "cells": cells, "ar": ar, "full": ar, "gfont": gfont, "gsize": gsize,
            "natural": natural, "min_gap": min_gap,
            "height": ar * 1.38 + gloss_lines * gsize * 1.12,
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


def wrap(text: str, font, width: float, hyphenate: bool = False) -> list:
    """Break text into lines no wider than `width`; with hyphenate, split overlong words at syllables."""
    lines, current = [], ""
    tokens = text.split()
    if hyphenate:
        tokens = [piece for token in tokens for piece in _hyphenate(token, font, width)]
    for token in tokens:
        candidate = f"{current} {token}".strip()
        if not current or (font.getlength(candidate) <= width and not current.endswith("-")):
            current = candidate
        else:
            lines.append(current)
            current = token
    if current:
        lines.append(current)
    return lines


def _hyphenate(token: str, font, width: float) -> list:
    """Split a word too wide for `width` into hyphen-ended pieces that fit, breaking at syllables."""
    global _hyphenator
    if font.getlength(token) <= width:
        return [token]
    if _hyphenator is None:
        import pyphen
        _hyphenator = pyphen.Pyphen(lang="en_US")
    pieces, rest = [], token
    while font.getlength(rest) > width:
        # === the longest head that fits with its hyphen; a word's own hyphen is kept, not doubled ===
        heads = [(rest[:i] + ("" if rest[i - 1] == "-" else "-"), rest[i:])
                 for i in _breaks(rest)]
        fitting = [h for h in heads if font.getlength(h[0]) <= width]
        if not fitting:
            if not heads:
                break
            fitting = heads[:1]  # === no syllable fits: take the shortest head anyway ===
        head, rest = fitting[-1]
        pieces.append(head)
    return pieces + [rest]


def _breaks(word: str) -> list:
    """Positions where `word` may break: after its own hyphens, and at syllables of its letters."""
    out = {i + 1 for i, ch in enumerate(word[:-1]) if ch == "-"}
    out |= set(_hyphenator.positions(word))
    return sorted(i for i in out if 1 < i < len(word) - 1)
