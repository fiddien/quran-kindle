"""Arabic with translation: each mushaf page followed by the English of its verses."""
import csv
import io
import json
import re
import sqlite3
import zipfile
from html import unescape
from pathlib import Path

from functools import lru_cache

from PIL import ImageFont

from .companion import wrap
from .render import INK, Renderer

TEXT_INK = 24
INTRO_INK = 64
NOTE_INK = 40
TOPIC_INK = 110
SALLA = "\ufdfa"  # === the salla symbol, which the serif faces lack: drawn in Amiri Quran instead ===
MARK = 0xE000  # === footnote n of a verse is stood in for by chr(MARK + n) while wrapping ===
SUP = re.compile(r'<sup foot_note="?(\d+)"?>[^<]*</sup>')


@lru_cache(maxsize=None)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Fonts are loaded once per size: layout tries many sizes for every page."""
    return ImageFont.truetype(str(path), size)


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


def load_themes(info: Path) -> dict:
    """The theme section of QUL's English introduction to each surah.

    Returns {surah: (heading, paragraphs)}, a paragraph being ("p" | "h3", text).
    The few introductions without a theme section give their short text instead.
    """
    csv.field_size_limit(1 << 24)  # === the full introductions run to tens of kilobytes ===
    with zipfile.ZipFile(info) as z:
        rows = list(csv.DictReader(io.TextIOWrapper(z.open("surah-info-en.csv"), encoding="utf-8")))
    themes = {}
    for r in rows:
        parts = re.split(r"<h2>(.*?)</h2>", r["text"])
        sections = list(zip(parts[1::2], parts[2::2]))
        theme = next(((h, body) for h, body in sections if THEME.search(h)), None)
        if theme:
            themes[int(r["surah_number"])] = (_plain(theme[0]).rstrip(".:"), _paragraphs(theme[1]))
        else:
            themes[int(r["surah_number"])] = ("Name", [("p", r["short_text"].strip())])
    return themes


THEME = re.compile(r"them|subject|topic", re.I)


def _plain(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split()).replace(" ,", ",").replace(" .", ".")


def _paragraphs(html: str) -> list:
    """Paragraphs, list items (numbered) and sub-headings of a section, as plain text."""
    out, number = [], 0
    for tag, body in re.findall(r"<(p|li|h3|/?ol)\b[^>]*>(?:(.*?)</(?:p|li|h3)>)?", html, re.S):
        if tag in ("ol", "/ol"):
            number = 0
            continue
        text = _plain(body)
        if not text:
            continue
        if tag == "li":
            number += 1
            text = f"{number}. {text}"
        out.append(("h3" if tag == "h3" else "p", text))
    return out


class TranslationRenderer(Renderer):
    def __init__(self, *args, verses: dict, names: dict, serif: str, italic: str, bold: str,
                 themes: dict = None, notes: dict = None, symbol: str = None, **kw):
        super().__init__(*args, **kw)
        self.verses, self.names = verses, names
        self.themes, self.notes = themes or {}, notes or {}
        self.serif, self.italic, self.bold, self.symbol = serif, italic, bold, symbol
        # === {verse_key: main topic entries} and {entry: index screen stem}, set once the index is laid out ===
        self.topics, self.entries = {}, {}
        self.column_share = 0.22  # === share of the text width given to the topic column ===
        w, h = self.device.width, self.device.height
        self.side = round(w * 0.07)
        self.text_top = self.top + h * 0.025
        self.text_bottom = h - h * 0.03
        # === start near 10 pt on a 6-inch 167-ppi screen and shrink until the page's verses fit ===
        self.sizes = range(round(w * 0.04), round(w * 0.015), -1)
        # === below 14 px on that screen (about 6 pt), a page moves on to a second screen instead ===
        self.floor = round(w * 14 / 600)
        self.reading = round(w * 0.03)  # === type size of the surah introductions and the index ===

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
                out.append(("verse", ayah, self.verses[key], continued, self.notes.get(key, []), key))
        return out

    # === runs: (text, font, fill, rise); a line is drawn as its runs side by side ===

    def _symbol(self, font):
        return _font(self.symbol, font.size) if self.symbol else font

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

    def _paragraph(self, text: str, font, fill, leading: float, width: float) -> list:
        words = [self._runs(w, font, fill) for w in text.split()]
        return [("runs", 0, line, leading) for line in self._wrap_runs(words, font.getlength(" "), width, width)]

    def layout(self, blocks: list, size: int) -> tuple:
        """Rows for the verses and rows for their footnotes, at one type size."""
        body = _font(self.serif, size)
        number = _font(self.bold, size)
        italic = _font(self.italic, size)
        marker = _font(self.bold, round(size * 0.62))
        heading = _font(self.bold, round(size * 1.1))
        note_size = max(round(size * 0.8), 8)
        note_font = _font(self.serif, note_size)
        note_number = _font(self.bold, note_size)
        topic_font = _font(self.italic, max(round(size * 0.8), 8))
        full = self.device.width - 2 * self.side
        # === with topics, the topics take a column at the right and the verses keep the rest ===
        column = full * self.column_share if self.topics else 0
        gutter = size * 0.8 if self.topics else 0
        width = full - column - gutter
        leading = size * 1.32
        rows, notes = [], []
        for block in blocks:
            if block[0] == "heading":
                rows.append(("space", leading * 0.4))
                rows.append(("center", block[1], heading, leading * 1.25))
                rows.append(("space", leading * 0.2))
                continue
            _, ayah, text, continued, verse_notes, _ = block
            # === footnotes are numbered through the screen, in reading order ===
            numbers = list(range(len(notes) + 1, len(notes) + len(verse_notes) + 1))
            notes.extend(verse_notes)
            lead = [(f"{ayah} ", number, INK, 0)]
            if continued:
                lead.append(("(continued) ", italic, 96, 0))
            indent = sum(_length(r) for r in lead)
            words = [self._word_runs(w, body, marker, numbers) for w in text.split()]
            lines = self._wrap_runs(words, body.getlength(" "), width - indent, width)
            topics = self._topic_lines(self.topics.get(block[-1], []), topic_font, column)
            if topics:
                # === the topics stand beside the verse's first line; a long list lengthens the verse ===
                rows.append(("side", full - column, topics, topic_font.size * 1.2))
            for i, line in enumerate(lines or [[]]):
                rows.append(("runs", 0, lead + line if i == 0 else line, leading))
            spill = len(topics) * topic_font.size * 1.2 - len(lines or [[]]) * leading
            if spill > 0:
                rows.append(("space", spill))
            rows.append(("space", leading * 0.35))
        while rows and rows[0][0] == "space":
            rows.pop(0)
        while rows and rows[-1][0] == "space":
            rows.pop()

        note_rows = []
        if notes:
            note_leading = note_size * 1.25
            note_rows.append(("rule", note_leading * 0.8))
            hang = note_number.getlength(f"{len(notes)}  ")
            for n, note in enumerate(notes, 1):
                words = [self._runs(w, note_font, NOTE_INK) for w in note.split()]
                # === below the verses the topic column is empty, so the notes take the full width ===
                lines = self._wrap_runs(words, note_font.getlength(" "), full - hang, full - hang)
                for i, line in enumerate(lines):
                    lead = [(f"{n}", note_number, INK, 0)] if i == 0 else []
                    note_rows.append(("note", hang, lead, line, note_leading))
                note_rows.append(("space", note_leading * 0.15))
            note_rows.pop()
        return rows, note_rows

    def _fits(self, layout, size) -> bool:
        rows, notes = layout
        gap = size if notes else 0
        return sum(_height(r) for r in rows) + gap + sum(_height(r) for r in notes) <= self.text_bottom - self.text_top

    def _split(self, blocks: list, size: int) -> list:
        """Blocks shared out over as few screens as hold them at this size, breaking between verses."""
        groups, current = [], []
        for block in blocks:
            if current and block[0] == "verse" and not self._fits(self.layout(current + [block], size), size):
                # === a surah heading moves on with the verse it introduces ===
                carry = []
                while current and current[-1][0] == "heading":
                    carry.insert(0, current.pop())
                if current:
                    groups.append(current)
                current = carry
            current = current + [block]
        return groups + [current]

    def screens_layout(self, page) -> list:
        """(verse rows, note rows) per screen, at the largest size that keeps one screen
        at or above the floor, or else two."""
        blocks = self.blocks(page)
        sizes = [s for s in self.sizes if s >= self.floor]
        for size in sizes:
            layout = self.layout(blocks, size)
            if self._fits(layout, size):
                return [layout]
        for size in sizes:
            groups = self._split(blocks, size)
            if len(groups) <= 2:
                break
        return [self.layout(group, size) for group in groups]

    def draw_screen(self, draw, page, layout, index, count):
        rows, notes = layout
        italic = _font(self.italic, round(self.top * 0.4))
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
            elif row[0] == "side":
                self._draw_side(draw, x0 + row[1], y, row[2], row[3])
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

    def theme_layouts(self, page) -> list:
        """Rows per screen for the introductions of the surahs that begin on this page."""
        body = _font(self.serif, self.reading)
        bold = _font(self.bold, self.reading)
        heading = _font(self.bold, round(self.reading * 1.15))
        label = _font(self.italic, self.reading)
        width = self.device.width - 2 * self.side
        leading = self.reading * 1.32
        room = self.text_bottom - self.text_top
        screens = []
        for surah in page.starts:
            if surah not in self.themes:
                continue
            title, paragraphs = self.themes[surah]
            chapter = self.mushaf.chapters[surah - 1]
            rows = [("center", f"{chapter.name} · {self.names[surah]}", heading, leading * 1.3),
                    ("center", title, label, leading * 1.1), ("space", leading * 0.5)]
            for kind, text in paragraphs:
                font = bold if kind == "h3" else body
                rows += self._paragraph(text, font, TEXT_INK, leading, width)
                rows.append(("space", leading * 0.45))
            # === one surah's introduction starts on a fresh screen and runs on as far as it needs ===
            current, used = [], 0.0
            for row in rows:
                if used + _height(row) > room and current:
                    screens.append(current)
                    current, used = [], 0.0
                if not current and row[0] == "space":
                    continue
                current.append(row)
                used += _height(row)
            screens.append(current)
        return screens

    def draw_theme(self, draw, page, rows, index, count):
        italic = _font(self.italic, round(self.top * 0.4))
        label = "Introduction" + (f" · {index + 1} of {count}" if count > 1 else "")
        self.frame(draw, page, center=lambda d, xy, band: d.text(xy, label, font=italic, fill=96, anchor="mm"))
        y = self.text_top
        for row in rows:
            if row[0] != "space":
                base = y + _height(row) * 0.78
                if row[0] == "center":
                    draw.text((self.device.width / 2, base), row[1], font=row[2], fill=INK, anchor="ms")
                else:
                    _draw_runs(draw, self.side + row[1], base, row[2])
            y += _height(row)

    def _topic_lines(self, names: list, font, width: float) -> list:
        """A verse's topics wrapped into the column, as lines of (x, text, target, font);
        each word of a name links to the name's index entry."""
        lines, line, x = [], [], 0.0
        space = font.getlength(" ")
        for i, name in enumerate(names):
            target = self.entries.get(name)
            words = name.split() + (["·"] if i < len(names) - 1 else [])
            for j, word in enumerate(words):
                pieces = [(text, run_font) for text, run_font, _, _ in self._runs(word, font, TOPIC_INK)]
                w = sum(run_font.getlength(text) for text, run_font in pieces)
                separator = j == len(words) - 1 and i < len(names) - 1
                # === a separating dot stays at the end of its line, never opens the next ===
                if line and x + w > width and not separator:
                    lines.append(line)
                    line, x = [], 0.0
                for text, run_font in pieces:
                    line.append((x, text, None if separator else target, run_font))
                    x += run_font.getlength(text)
                x += space
        if line:
            lines.append(line)
        return [(font, ln) for ln in lines]

    def _draw_side(self, draw, x, y, lines, height):
        """A verse's topics in the right-hand column, with a hairline to their left."""
        draw.line((x - 6, y + height * 0.15, x - 6, y + height * len(lines)), fill=200, width=1)
        for _, items in lines:
            base = y + height * 0.8
            for dx, text, target, font in items:
                draw.text((x + dx, base), text, font=font, fill=TOPIC_INK, anchor="ls")
                if target and hasattr(draw, "link"):
                    draw.link((x + dx - 1, y, x + dx + font.getlength(text) + 1, y + height), target)
            y += height

    def screens_ops(self, page) -> list:
        """The mushaf page, the introductions of surahs that begin on it, then its translation,
        as (Screen, recorded ops)."""
        from .epub import Screen
        from .textbook import Recorder

        rec = Recorder()
        self.draw_page(rec, page)
        out = [(Screen(f"p{page.number:03d}", page.number, True), rec.ops)]
        themes = self.theme_layouts(page)
        for i, rows in enumerate(themes):
            rec = Recorder()
            self.draw_theme(rec, page, rows, i, len(themes))
            out.append((Screen(f"i{page.number:03d}{i:02d}", page.number, False), rec.ops))
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
    if row[0] == "side":  # === drawn beside the rows that follow it, so it adds no height ===
        return 0
    return row[-1] if row[0] != "space" else row[1]
