"""Topic index: QUL's Qur'an topics A to Z, each with the mushaf pages where it appears.

A topic's sub-entries are worded to follow it (Pharaoh: "torture by and
deliverance from"), so they are nested beneath it, as in a printed index.
Every page number links to that mushaf page.
"""
import sqlite3
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


from .folds import DROPPED, FOLDS
from .render import INK
from .translation import _font

INDEX = "x000"  # === stem of the index's first screen, the A to Z ===


@dataclass
class Topic:
    name: str
    pages: set = field(default_factory=set)
    children: list = field(default_factory=list)


def load_topics(db_zip: Path, verse_page: dict, pages: set) -> tuple:
    """Main entries A to Z with their sub-entries, keeping only the given mushaf pages,
    and {verse_key: names of the main entries that cite the verse}."""
    with zipfile.ZipFile(db_zip) as z:
        blob = z.read(next(n for n in z.namelist() if n.endswith(".db")))
    db = sqlite3.connect(":memory:")
    db.deserialize(blob)
    nodes, parent, verses = {}, {}, {}
    for tid, name, pid, tpid, ayahs in db.execute(
            "SELECT topic_id, name, parent_id, thematic_parent_id, ayahs FROM topics"):
        if tid in DROPPED:
            continue
        name = " ".join(name.split())
        name = FOLDS.get(name, name)  # === several of QUL's names for one topic become one entry ===
        refs = [a.strip() for a in (ayahs or "").split(",")]
        verses[tid] = [a for a in refs if verse_page.get(a) in pages]
        nodes[tid] = Topic(name, {verse_page[a] for a in verses[tid]})
        # === parent_id always marks a sub-entry; in the thematic tree only lower-case names do ===
        if pid:
            parent[tid] = pid
        elif tpid and name[:1].islower():
            parent[tid] = tpid

    def rooted(tid):
        seen = {tid}
        while tid in parent and parent[tid] in nodes:
            tid = parent[tid]
            if tid in seen:
                return False
            seen.add(tid)
        return True

    def nested(tid):
        return parent.get(tid) in nodes and rooted(tid)

    for tid, node in nodes.items():
        if nested(tid):
            nodes[parent[tid]].children.append(node)
    # === the same name listed twice at the top becomes one entry ===
    roots = {}
    for tid, node in nodes.items():
        if nested(tid):
            continue
        same = roots.setdefault(node.name.casefold(), node)
        if same is not node:
            same.pages |= node.pages
            same.children += node.children
    topics = _tidy(list(roots.values()))

    # === each verse lists the main entries under which it is cited, in index order ===
    def top(tid):
        while nested(tid):
            tid = parent[tid]
        return roots[nodes[tid].name.casefold()].name

    by_verse = {}
    for tid, keys in verses.items():
        for key in keys:
            by_verse.setdefault(key, set()).add(top(tid))
    return topics, {key: sorted(names, key=lambda n: (sort_key(n), n)) for key, names in by_verse.items()}


def _tidy(topics: list) -> list:
    """Sorted, without entries that point to no page."""
    out = []
    for t in topics:
        t.children = _tidy(t.children)
        if t.pages or t.children:
            out.append(t)
    return sorted(out, key=lambda t: (sort_key(t.name), t.name))


def sort_key(name: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return "".join(c for c in plain.casefold() if c.isalnum() or c == " ").strip()


def letter(name: str) -> str:
    key = sort_key(name)
    return key[0].upper() if key and key[0].isalpha() else "#"


def index_screens(r, topics: list, last_page: int) -> tuple:
    """(Screen, recorded ops) for the index, the A to Z then the entries, and
    {main entry: stem of the screen where it starts}."""
    from .epub import Screen
    from .textbook import Recorder

    w, h = r.device.width, r.device.height
    size = r.reading
    body = _font(r.serif, size)
    main = _font(r.bold, size)
    letter_font = _font(r.bold, round(size * 1.6))
    leading = size * 1.3
    width = w - 2 * r.side
    step = size * 1.1  # === indent per level, and the hang of a wrapped line ===

    italic = _font(r.italic, size)
    # === rows: ("letter", text, main entry, height) or ("line", [(x, text, font, target)], main entry, height) ===
    rows, starts = [], set()
    for t in topics:
        first = letter(t.name)
        if first not in starts:
            starts.add(first)
            rows.append(("letter", first, t.name, leading * 1.9))
        rows += [(kind, items, t.name, height) for kind, items, height in _entry(t, 0, body, main, step, width, leading)]

    room = r.text_bottom - r.text_top
    screens, current, used, at, entry = [], [], 0.0, {}, {}
    for i, row in enumerate(rows):
        # === a letter heading never ends a screen ===
        need = row[-1] + (rows[i + 1][-1] if row[0] == "letter" and i + 1 < len(rows) else 0)
        if current and used + need > room:
            screens.append(current)
            current, used = [], 0.0
            # === a screen that opens inside an entry names it again ===
            if row[0] == "line" and rows[i - 1][2] == row[2]:
                current.append(("line", [(0, f"{row[2]} (continued)", italic, None)], row[2], leading))
                used += leading
        if row[0] == "letter":
            at[row[1]] = len(screens) + 1
        entry.setdefault(row[2], f"x{len(screens) + 1:03d}")
        current.append(row)
        used += row[-1]
    if current:
        screens.append(current)
    stems = [f"x{i + 1:03d}" for i in range(len(screens))]

    out = []
    rec = Recorder()
    _frame(rec, r, "Topic index")
    _contents(rec, r, sorted(at, key=lambda c: (c == "#", c)), {c: stems[n - 1] for c, n in at.items()})
    out.append((Screen(INDEX, last_page, False), rec.ops))
    for stem, screen_rows in zip(stems, screens):
        rec = Recorder()
        _frame(rec, r, f"Topic index · {letter(screen_rows[0][2])}", back=True)
        y = r.text_top
        for row in screen_rows:
            base = y + row[-1] * 0.78
            if row[0] == "letter":
                rec.text((r.side, y + row[-1] * 0.85), row[1], font=letter_font, fill=INK, anchor="ls")
            else:
                for x, text, font, target in row[1]:
                    rec.text((r.side + x, base), text, font=font, fill=INK if target is None else 40, anchor="ls")
                    if target:
                        rec.link((r.side + x - 2, y, r.side + x + font.getlength(text.rstrip(",")) + 2, y + row[-1]),
                                 target)
            y += row[-1]
        out.append((Screen(stem, last_page, False), rec.ops))
    return out, entry


def _entry(t: Topic, depth: int, body, main, step, width, leading) -> list:
    """The lines of one entry and its sub-entries: name, then page numbers that wrap with a hang."""
    indent = depth * step
    name_font = main if depth == 0 else body
    tokens = [(t.name, name_font, None)]
    pages = sorted(t.pages)
    for i, n in enumerate(pages):
        tokens.append((f"{n}," if i < len(pages) - 1 else f"{n}", body, f"p{n:03d}"))
    space = body.getlength(" ")
    lines, line, x = [], [], indent
    for text, font, target in tokens:
        if target is None:  # === the name itself may need to wrap ===
            for word in text.split():
                wl = font.getlength(word)
                if line and x + wl > width:
                    lines.append(line)
                    line, x = [], indent + step
                line.append((x, word, font, None))
                x += wl + space
            continue
        wl = font.getlength(text)
        if line and x + wl > width:
            lines.append(line)
            line, x = [], indent + step
        line.append((x, text, font, target))
        x += wl + space
    lines.append(line)
    rows = [("line", ln, leading) for ln in lines]
    for child in t.children:
        rows += _entry(child, depth + 1, body, main, step, width, leading)
    return rows


def _frame(rec, r, label: str, back: bool = False):
    """The index's running header: its label, centered over a rule; tapping it opens the A to Z."""
    font = _font(r.italic, round(r.top * 0.4))
    w = r.device.width
    rec.text((w / 2, r.top * 0.55), label, font=font, fill=96, anchor="mm")
    rec.line((r.side, r.top, w - r.side, r.top), fill=160, width=1)
    if back:
        rec.link((w * 0.3, 0, w * 0.7, r.top), INDEX)


def _contents(rec, r, letters: list, target: dict):
    """The first index screen: a note on its use and a grid of letters."""
    w = r.device.width
    size = r.reading
    title = _font(r.bold, round(size * 1.3))
    note = _font(r.italic, size)
    big = _font(r.bold, round(size * 1.7))
    y = r.text_top + size * 2
    rec.text((w / 2, y), "Topic index", font=title, fill=INK, anchor="ms")
    y += size * 1.8
    for line in ("Numbers are mushaf pages; tap one to open it.",
                 "Tap the header of an index screen to return here.",
                 "Topics from QUL (qul.tarteel.ai)."):
        rec.text((w / 2, y), line, font=note, fill=96, anchor="ms")
        y += size * 1.4
    y += size * 1.5
    cols = 6
    cell = (w - 2 * r.side) / cols
    for i, c in enumerate(letters):
        cx = r.side + cell * (i % cols + 0.5)
        cy = y + (i // cols) * cell
        rec.text((cx, cy), c, font=big, fill=INK, anchor="ms")
        rec.link((cx - cell / 2, cy - cell * 0.75, cx + cell / 2, cy + cell * 0.25), target[c])
