"""Load page layouts and derive the navigation structure (surah, juz', hizb)."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PAGE_COUNT = 604
ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def arabic_number(n: int) -> str:
    return str(n).translate(ARABIC_DIGITS)


@dataclass
class Chapter:
    id: int
    name: str
    name_arabic: str
    verses: int
    page: int = 0


@dataclass
class Mark:
    """A navigation target: the page on which a juz', hizb or quarter begins."""
    number: int
    verse_key: str
    page: int


@dataclass
class Page:
    number: int
    lines: list
    first_verse: str
    surah: int = 0
    juz: int = 0
    hizb: int = 0
    starts: list = field(default_factory=list)  # === surah ids whose header is on this page ===


@dataclass
class Mushaf:
    chapters: list
    pages: list
    juz: list
    hizb: list
    quarters: list


def _js_list(source: str, name: str) -> list:
    match = re.search(name + r":\s*\[([^\]]*)\]", source)
    if not match:
        raise RuntimeError(f"{name} not found in quran-meta")
    return [int(x) for x in match.group(1).replace("\n", "").split(",") if x.strip()]


def load(qcf4: Path, meta: Path) -> Mushaf:
    index = json.loads((qcf4 / "index.json").read_text())
    verses = json.loads((qcf4 / "verses.json").read_text())
    chapters = [
        Chapter(c["id"], c["name"], c["name_arabic"], c["verses_count"])
        for c in index["chapters"]
    ]

    pages = []
    for n in range(1, PAGE_COUNT + 1):
        data = json.loads((qcf4 / "pages" / f"{n:03d}.json").read_text())
        first = next(
            w["verse_key"]
            for line in data["lines"]
            for w in line["words"]
            if w.get("verse_key")
        )
        page = Page(n, data["lines"], first, surah=int(first.split(":")[0]))
        for line in data["lines"]:
            head = line["words"][0]
            if head["type"] == "surah_header":
                page.starts.append(head["sura"])
                chapters[head["sura"] - 1].page = n
        pages.append(page)

    # === Absolute ayah number -> "surah:ayah" ===
    keys = [None]
    for c in chapters:
        keys.extend(f"{c.id}:{a}" for a in range(1, c.verses + 1))

    lists = next((meta / "dist").glob("HafsLists-*.js")).read_text()
    quarter_ayahs = _js_list(lists, "HizbQuarterList")[1:-1]
    juz_ayahs = _js_list(lists, "JuzList")[1:-1]
    assert len(quarter_ayahs) == 240 and len(juz_ayahs) == 30

    def marks(ayahs):
        return [
            Mark(i + 1, keys[a], verses[keys[a]]["page"]) for i, a in enumerate(ayahs)
        ]

    quarters = marks(quarter_ayahs)
    hizb = [Mark(i // 4 + 1, q.verse_key, q.page) for i, q in enumerate(quarters) if i % 4 == 0]
    juz = marks(juz_ayahs)

    # === Running-header info: the juz'/hizb in which each page's first ayah falls. ===
    for page in pages:
        page.juz = max(j.number for j in juz if j.page <= page.number)
        page.hizb = max(h.number for h in hizb if h.page <= page.number)

    return Mushaf(chapters, pages, juz, hizb, quarters)
