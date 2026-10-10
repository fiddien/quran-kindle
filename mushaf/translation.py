"""Arabic with translation: each mushaf page followed by the English of its verses."""
import csv
import io
import json
import re
import sqlite3
import zipfile
from pathlib import Path

from PIL import ImageFont

from .companion import wrap
from .render import INK, Renderer

TEXT_INK = 24
INTRO_INK = 64
NOTE_INK = 40
SALLA = "\ufdfa"  # === the salla symbol, which the serif faces lack: drawn in Amiri Quran instead ===
MARK = 0xE000  # === footnote n of a verse is stood in for by chr(MARK + n) while wrapping ===
SUP = re.compile(r'<sup foot_note="?(\d+)"?>[^<]*</sup>')


def load_translation(cloud: Path) -> tuple:
    """Saheeh International, as {verse_key: text}, and {surah: English name}."""
    verses, names = {}, {}
    for chapter in json.loads((cloud / "dist" / "quran_en.json").read_text()):
        names[chapter["id"]] = chapter["translation"]
        for v in chapter["verses"]:
            verses[f"{chapter['id']}:{v['id']}"] = v["translation"]
    return verses, names


def load_footnoted(db_zip: Path) -> tuple:
    """QUL's Saheeh International with the translator's footnotes.

    Returns {verse_key: text} with each footnote marker replaced by chr(MARK + n),
    n counting from 0 within the verse, and {verse_key: [note, ...]} in that order.
    """
    with zipfile.ZipFile(db_zip) as z:
        name = next(n for n in z.namelist() if n.endswith(".db"))
        blob = z.read(name)
    # === sqlite reads only files, so the database is opened from memory ===
    db = sqlite3.connect(":memory:")
    db.deserialize(blob)
    verses, notes = {}, {}
    for key, text, footnotes in db.execute("SELECT ayah_key, text, footnotes FROM translation"):
        text, footnotes = json.loads(text), json.loads(footnotes)
        ids = []

        def mark(m):
            ids.append(m.group(1))
            return chr(MARK + len(ids) - 1)

        verses[key] = " ".join(SUP.sub(mark, text).split())
        notes[key] = [_clean_note(footnotes[i]) for i in ids]
    return verses, notes


def _clean_note(note: str) -> str:
    """A footnote as plain text: no tags, and without the dash some notes open with."""
    note = " ".join(re.sub(r"<[^>]+>", " ", note).split())
    return note[2:] if note.startswith("- ") else note


def load_intros(info: Path) -> dict:
    """QUL's short English introduction to each surah, as {surah: text}."""
    csv.field_size_limit(1 << 24)  # === the full introductions run to tens of kilobytes ===
    with zipfile.ZipFile(info) as z:
        rows = csv.DictReader(io.TextIOWrapper(z.open("surah-info-en.csv"), encoding="utf-8"))
        return {int(r["surah_number"]): r["short_text"].strip() for r in rows}


class TranslationRenderer(Renderer):
    def __init__(self, *args, verses: dict, names: dict, serif: str, italic: str, bold: str,
                 intros: dict = None, notes: dict = None, symbol: str = None, **kw):
        super().__init__(*args, **kw)
        self.verses, self.names = verses, names
        self.intros, self.notes = intros or {}, notes or {}
        self.serif, self.italic, self.bold, self.symbol = serif, italic, bold, symbol
        w, h = self.device.width, self.device.height
        self.side = round(w * 0.07)
        self.text_top = self.top + h * 0.025
        self.text_bottom = h - h * 0.03
        # === start near 10 pt on a 6-inch 167-ppi screen and shrink until the page's verses fit ===
        self.sizes = range(round(w * 0.04), round(w * 0.015), -1)

    def blocks(self, page) -> list:
        """Surah headings, introductions and verses on the page, in reading order."""
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
                    if self.intros.get(surah):
                        out.append(("intro", self.intros[surah]))
                continued = w["type"] == "word" and w.get("position", 1) > 1
                out.append(("verse", ayah, self.verses[key], continued, self.notes.get(key, [])))
        return out

    # === runs: (text, font, fill, rise); a line is drawn as its runs side by side ===

    def _symbol(self, font):
        return ImageFont.truetype(self.symbol, font.size) if self.symbol else font

    def _runs(self, text: str, font, fill, rise=0.0) -> list:
        """Text as runs, with the salla symbol split out into the symbol font."""
        runs = []
        for i, part in enumerate(text.split(SALLA)):
            if i:
                runs.append((SALLA, self._symbol(font), fill, rise))
            if part:
                runs.append((part, font, fill, rise))
        return runs

    def _word_runs(self, word: str, body, marker, numbers: list) -> list:
        """One word's runs; a footnote placeholder becomes its raised screen number."""
        runs, text = [], ""
        for ch in word:
            if MARK <= ord(ch) < MARK + 256:
                runs += self._runs(text, body, TEXT_INK)
                runs.append((str(numbers[ord(ch) - MARK]), marker, INK, body.size * 0.38))
                text = ""
            else:
                text += ch
        return runs + self._runs(text, body, TEXT_INK)

    def _wrap_runs(self, words: list, space: float, first: float, width: float) -> list:
        """Lines of run lists; words are lists of runs, the first line is `first` wide."""
        lines, current, used = [], [], 0.0
        for runs in words:
            w = sum(_length(r) for r in runs)
            room = first if not lines else width
            if current and used + space + w > room:
                lines.append(current)
                current, used = [], 0.0
            if current:
                current = current + [(" ", runs[0][1], runs[0][2], 0)]
                used += space
            current = current + runs
            used += w
        if current:
            lines.append(current)
        return [_merge(line) for line in lines]

    def layout(self, page, size: int) -> tuple:
        """Rows for the verses and rows for the footnotes, at one type size."""
        body = ImageFont.truetype(self.serif, size)
        number = ImageFont.truetype(self.bold, size)
        italic = ImageFont.truetype(self.italic, size)
        marker = ImageFont.truetype(self.bold, round(size * 0.62))
        heading = ImageFont.truetype(self.bold, round(size * 1.1))
        intro = ImageFont.truetype(self.italic, round(size * 0.9))
        note_size = max(round(size * 0.8), 8)
        note_font = ImageFont.truetype(self.serif, note_size)
        note_number = ImageFont.truetype(self.bold, note_size)
        width = self.device.width - 2 * self.side
        leading = size * 1.32
        rows, notes = [], []
        for block in self.blocks(page):
            if block[0] == "heading":
                rows.append(("space", leading * 0.4))
                rows.append(("center", block[1], heading, leading * 1.25))
                rows.append(("space", leading * 0.2))
                continue
            if block[0] == "intro":
                # === the surah's introduction, set apart from the verses in smaller gray italic ===
                for line in wrap(block[1], intro, width):
                    rows.append(("runs", 0, self._runs(line, intro, INTRO_INK), leading * 0.9))
                rows.append(("space", leading * 0.6))
                continue
            _, ayah, text, continued, verse_notes = block
            # === footnotes are numbered through the screen, in reading order ===
            numbers = list(range(len(notes) + 1, len(notes) + len(verse_notes) + 1))
            notes.extend(verse_notes)
            lead = [(f"{ayah} ", number, INK, 0)]
            if continued:
                lead.append(("(continued) ", italic, 96, 0))
            indent = sum(_length(r) for r in lead)
            words = [self._word_runs(w, body, marker, numbers) for w in text.split()]
            lines = self._wrap_runs(words, body.getlength(" "), width - indent, width)
            for i, line in enumerate(lines or [[]]):
                rows.append(("runs", 0, lead + line if i == 0 else line, leading))
            rows.append(("space", leading * 0.35))
        while rows and rows[-1][0] == "space":
            rows.pop()

        note_rows = []
        if notes:
            note_leading = note_size * 1.25
            note_rows.append(("rule", note_leading * 0.8))
            hang = note_number.getlength(f"{len(notes)}  ")
            for n, note in enumerate(notes, 1):
                words = [self._runs(w, note_font, NOTE_INK) for w in note.split()]
                lines = self._wrap_runs(words, note_font.getlength(" "), width - hang, width - hang)
                for i, line in enumerate(lines):
                    lead = [(f"{n}", note_number, INK, 0)] if i == 0 else []
                    note_rows.append(("note", hang, lead, line, note_leading))
                note_rows.append(("space", note_leading * 0.15))
            note_rows.pop()
        return rows, note_rows

    def screens_layout(self, page) -> list:
        """(verse rows, note rows) for one screen, at the largest size at which the page fits."""
        room = self.text_bottom - self.text_top
        for size in self.sizes:
            rows, notes = self.layout(page, size)
            gap = size if notes else 0
            if sum(_height(r) for r in rows) + gap + sum(_height(r) for r in notes) <= room:
                break
        return [(rows, notes)]

    def draw_screen(self, draw, page, layout, index, count):
        rows, notes = layout
        italic = ImageFont.truetype(self.italic, round(self.top * 0.4))
        label = "Translation" + (f" · {index + 1} of {count}" if count > 1 else "")
        self.frame(draw, page, center=lambda d, xy, band: d.text(xy, label, font=italic, fill=96, anchor="mm"))
        x0 = self.side
        y = self.text_top
        for row in rows:
            if row[0] == "space":
                y += row[1]
                continue
            base = y + _height(row) * 0.78
            if row[0] == "center":
                draw.text((self.device.width / 2, base), row[1], font=row[2], fill=INK, anchor="ms")
            else:
                _draw_runs(draw, x0 + row[1], base, row[2])
            y += _height(row)
        # === the notes sit at the foot of the screen, under a short rule ===
        y = self.text_bottom - sum(_height(r) for r in notes)
        for row in notes:
            if row[0] == "rule":
                draw.line((x0, y + row[1] * 0.4, x0 + self.device.width * 0.25, y + row[1] * 0.4),
                          fill=128, width=1)
            elif row[0] == "note":
                base = y + row[-1] * 0.78
                _draw_runs(draw, x0, base, row[2])
                _draw_runs(draw, x0 + row[1], base, row[3])
            y += _height(row)

    def screens_ops(self, page) -> list:
        """The mushaf page, then its translation screen, as (Screen, recorded ops)."""
        from .epub import Screen
        from .textbook import Recorder

        rec = Recorder()
        self.draw_page(rec, page)
        out = [(Screen(f"p{page.number:03d}", page.number, True), rec.ops)]
        parts = self.screens_layout(page)
        for i, layout in enumerate(parts):
            rec = Recorder()
            self.draw_screen(rec, page, layout, i, len(parts))
            out.append((Screen(f"t{page.number:03d}{chr(ord('a') + i)}", page.number, False), rec.ops))
        return out


def _length(run) -> float:
    return run[1].getlength(run[0])


def _merge(runs: list) -> list:
    """Join neighbouring runs that share font, ink and rise, so a line is few spans."""
    out = []
    for r in runs:
        if out and out[-1][1:] == r[1:]:
            out[-1] = (out[-1][0] + r[0],) + r[1:]
        else:
            out.append(r)
    return out


def _draw_runs(draw, x, base, runs):
    for text, font, fill, rise in runs:
        if text.strip():
            draw.text((x, base - rise), text, font=font, fill=fill, anchor="ls")
        x += font.getlength(text)


def _height(row) -> float:
    return row[-1] if row[0] != "space" else row[1]
