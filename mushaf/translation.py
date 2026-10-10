"""Arabic with translation: each mushaf page followed by the English of its verses."""
import json
from pathlib import Path

from PIL import ImageFont

from .companion import wrap
from .render import INK, Renderer

TEXT_INK = 24


def load_translation(cloud: Path) -> tuple:
    """Saheeh International, as {verse_key: text}, and {surah: English name}."""
    verses, names = {}, {}
    for chapter in json.loads((cloud / "dist" / "quran_en.json").read_text()):
        names[chapter["id"]] = chapter["translation"]
        for v in chapter["verses"]:
            verses[f"{chapter['id']}:{v['id']}"] = v["translation"]
    return verses, names


class TranslationRenderer(Renderer):
    def __init__(self, *args, verses: dict, names: dict, serif: str, italic: str, bold: str, **kw):
        super().__init__(*args, **kw)
        self.verses, self.names = verses, names
        self.serif, self.italic, self.bold = serif, italic, bold
        w, h = self.device.width, self.device.height
        self.side = round(w * 0.07)
        self.text_top = self.top + h * 0.025
        self.text_bottom = h - h * 0.03
        # === start near 10 pt on a 6-inch 167-ppi screen and shrink until the page's verses fit ===
        self.sizes = range(round(w * 0.04), round(w * 0.015), -1)

    def link_target(self, page):
        return f"t{page.number:03d}a"

    def blocks(self, page) -> list:
        """Surah headings and verses on the page, in reading order."""
        out, seen = [], set()
        for line in page.lines:
            for w in line["words"]:
                key = w.get("verse_key")
                if not key or key in seen:
                    continue
                seen.add(key)
                surah, ayah = map(int, key.split(":"))
                if ayah == 1:
                    chapter = self.mushaf.chapters[surah - 1]
                    out.append(("heading", f"{chapter.name} · {self.names[surah]}"))
                continued = w["type"] == "word" and w.get("position", 1) > 1
                out.append(("verse", ayah, self.verses[key], continued))
        return out

    def layout(self, page, size: int) -> list:
        """Lines as (kind, x, text, font) with their heights, for one type size."""
        body = ImageFont.truetype(self.serif, size)
        number = ImageFont.truetype(self.bold, size)
        note = ImageFont.truetype(self.italic, size)
        heading = ImageFont.truetype(self.bold, round(size * 1.1))
        width = self.device.width - 2 * self.side
        leading = size * 1.32
        rows = []
        for block in self.blocks(page):
            if block[0] == "heading":
                rows.append(("space", leading * 0.4))
                rows.append(("center", block[1], heading, leading * 1.25))
                rows.append(("space", leading * 0.2))
                continue
            _, ayah, text, continued = block
            prefix = f"{ayah} "
            indent = number.getlength(prefix)
            if continued:
                prefix_note = "(continued) "
                indent += note.getlength(prefix_note)
            # === the first line makes room for the verse number (and the note) ===
            first = wrap(text, body, width - indent)[0] if text else ""
            rest = wrap(text[len(first):].strip(), body, width) if len(first) < len(text) else []
            parts = [("number", prefix, number, indent)]
            if continued:
                parts.append(("note", prefix_note, note))
            rows.append(("verse", parts, first, body, leading))
            for line in rest:
                rows.append(("line", line, body, leading))
            rows.append(("space", leading * 0.35))
        return rows

    def screens_layout(self, page) -> list:
        """Rows for one screen, at the largest type size at which the whole page fits."""
        room = self.text_bottom - self.text_top
        for size in self.sizes:
            rows = self.layout(page, size)
            if sum(_height(r) for r in rows) <= room:
                break
        # === drop a trailing spacer so nothing hangs below the last verse ===
        while rows and rows[-1][0] == "space":
            rows.pop()
        return [rows]

    def draw_screen(self, draw, page, rows, index, count):
        italic = ImageFont.truetype(self.italic, round(self.top * 0.4))
        label = "Translation" + (f" · {index + 1} of {count}" if count > 1 else "")
        self.frame(draw, page, center=lambda d, xy, band: d.text(xy, label, font=italic, fill=96, anchor="mm"))
        y = self.text_top
        x0 = self.side
        for row in rows:
            if row[0] == "space":
                y += row[1]
                continue
            base = y + _height(row) * 0.78
            if row[0] == "center":
                draw.text((self.device.width / 2, base), row[1], font=row[2], fill=INK, anchor="ms")
            elif row[0] == "verse":
                parts, text, body = row[1], row[2], row[3]
                x = x0
                for part in parts:
                    draw.text((x, base), part[1], font=part[2], fill=INK if part[0] == "number" else 96,
                              anchor="ls")
                    if part[0] == "number" and hasattr(draw, "link"):
                        # === the verse number jumps back to the mushaf page, with a generous tap area ===
                        size = part[2].size
                        draw.link((x - size * 0.4, base - size * 1.1, x + part[2].getlength(part[1]) + size * 0.2,
                                   base + size * 0.4), f"p{page.number:03d}")
                    x += part[2].getlength(part[1])
                draw.text((x, base), text, font=body, fill=TEXT_INK, anchor="ls")
            else:
                draw.text((x0, base), row[1], font=row[2], fill=TEXT_INK, anchor="ls")
            y += _height(row)

    def screens_ops(self, page) -> list:
        """The mushaf page, then its translation screen(s), as (Screen, recorded ops)."""
        from .epub import Screen
        from .textbook import Recorder

        rec = Recorder()
        self.draw_page(rec, page)
        out = [(Screen(f"p{page.number:03d}", page.number, True), rec.ops)]
        parts = self.screens_layout(page)
        for i, rows in enumerate(parts):
            rec = Recorder()
            self.draw_screen(rec, page, rows, i, len(parts))
            out.append((Screen(f"t{page.number:03d}{chr(ord('a') + i)}", page.number, False), rec.ops))
        return out


def _height(row) -> float:
    return row[-1] if row[0] != "space" else row[1]
