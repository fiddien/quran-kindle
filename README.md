# Madinah Mushaf for Kindle

Builds a crisp, easy-to-navigate copy of the **Madinah mushaf** (King Fahd Complex,
1441 AH, calligraphy by Uthman Taha) for Kindle and other e-readers. Every page keeps
the printed layout: 604 pages, 15 lines, same line breaks.

Each page is rendered at the exact pixel size of your screen in 16 gray levels. The book has:

- a table of contents with all **114 surahs** and **30 juz'**, each with its **2 hizb**;
- right-to-left page turning;
- "Go to page N" landing on mushaf page N;
- a running header (surah, juz', hizb) on every page;
- a cue for which side of the open mushaf each page sits on: odd pages are
  right-hand pages, with a soft spine shadow on their left edge and the page
  number in the top-right corner, and even pages mirror this.

## Download

Ready-made books are on the **[latest release](https://github.com/fiddien/quran-kindle/releases/latest)**.
Pick the files that match your screen:

| Files ending in | Screen | Devices |
|---|---|---|
| `-paperwhite` | 1236×1648 | Kindle Paperwhite 5 and later (6.8″, 2021+) |
| `-kindle` | 1072×1448 | Kindle Basic (2022+), Paperwhite 3/4, Kobo Clara |
| `-oasis` | 1264×1680 | Kindle Oasis, Kobo Libra |
| `-kindle-2019` | 600×800 | Kindle Basic 10th gen (2019, micro-USB) |

Each size comes as five books, each as an EPUB and a PDF:

- `mushaf-text-…`: the mushaf as real text, so you can highlight and add
  notes. The EPUB is faster and highlights whole lines; the PDF highlights single words.
  Copy the PDF over USB into the Kindle's `documents` folder.
- `translation-text-…`: each mushaf page followed by one screen of the Saheeh
  International English translation, as real text.
- `companion-text-…`: the word-by-word companion as real text.
- `mushaf-…`: the mushaf as page images.
- `companion-…`: the word-by-word companion as page images.

The text EPUBs show the cover only in the Kindle library; the text PDFs open on mushaf
page 1 and have no cover, so the PDF's page numbers stay aligned with the mushaf's.

## Text edition

In `mushaf-text` every word is real text in the King Fahd Complex font, placed exactly
where the printed mushaf has it, so the page looks the same as the image edition. Kindle's
PDF reader can highlight single words and attach notes to them; in the EPUB, highlights
cover whole lines. In the notes list and in "My Clippings", highlighted Qur'an text shows as codes rather than
Arabic, because those views don't use the book's font.

## Word-by-word companion

A second book shows every mushaf line with an English gloss under each word.
At readable sizes a page needs three screens of five lines each. Every screen
is labelled with the mushaf page number, so "Go to page 50" can still find
page 50. `companion-text` is the same book in real text.

## Translation

`translation-text` follows each mushaf page with the Saheeh International English
translation of the verses on it. The translator's footnotes are numbered through each
screen and printed at its foot. A verse that begins on the previous page is repeated in
full and marked *(continued)*. The type shrinks as needed to keep a page's translation on
one screen; where it would drop below about 6 pt (14 px on a 600-pixel-wide screen), the
page takes two screens instead, split between verses.

Where a surah begins, the mushaf page is followed by the theme of the surah from its
introduction in QUL, on screens of its own.

Beside each verse, a narrow column at the right lists the topics QUL assigns to it;
tapping a topic opens its entry in the topic index at the back. Names QUL lists
separately for one topic (spellings, Arabic and English names, singular and plural) are
folded into one entry, listed in `mushaf/folds.py`. The index
lists the topics A to Z with the mushaf pages where each appears, sub-topics nested
beneath; tapping a page number opens that page. The index is also in the table of
contents.

## Build

```sh
pip install -r requirements.txt
python -m mushaf --device paperwhite          # both books, EPUB + PDF, in out/paperwhite/
python -m mushaf --book mushaf                # only the mushaf
python -m mushaf --pages 1-3,604              # quick preview PNGs only
python -m mushaf --text-scale 0.85            # smaller script, more space between lines
python -m mushaf --book mushaf-text --formats pdf   # the text edition as a PDF
python -m mushaf --book translation-text --pages 1-21   # a quick sample (Juz' 1)
```

Devices: `paperwhite` (2021+),
`paperwhite-old`, `kindle` (2022+), `kindle-2019`, `oasis`, `scribe`, `kobo-clara`, `kobo-libra`.

Pushing a tag such as `v1.0.0`, or running the *Build books* workflow by hand with a
release version, makes GitHub Actions build the `paperwhite`, `kindle`, `oasis` and
`kindle-2019` sizes and publish them as a release. Run by hand without a version, the workflow
only builds; its files then appear as downloads on that run's page for 7 days.

## Put it on the Kindle

- **EPUB:** send it with [Send to Kindle](https://www.amazon.com/sendtokindle).
- **PDF:** copy it over USB into the `documents` folder.

## Sources and licensing

The build downloads pinned npm packages and checks each against its sha512 hash:

- [`quran-qcf4`](https://github.com/MohamadHajjRabee/quran-qcf4) for the page layouts
  (MIT) and the KFGQPC QCF4 fonts;
- [`quran-meta`](https://github.com/quran-center/quran-meta) for the juz' and hizb
  boundaries (MIT);
- [`@kmaslesa/holy-quran-word-by-word-full-data`](https://www.npmjs.com/package/@kmaslesa/holy-quran-word-by-word-full-data)
  for the English glosses. This is a dump of quran.com's word-by-word data, so the
  translation's rights rest with its original authors;
- [`quran-cloud`](https://www.npmjs.com/package/quran-cloud) for the English surah names;
- [QUL](https://qul.tarteel.ai) (Quranic Universal Library, by Tarteel) for the Saheeh
  International English translation with the translator's footnotes (Saheeh International,
  Abul-Qasim Publishing House), the English surah introductions, whose text matches the
  surah introductions of Sayyid Abul A'la Maududi's *Tafhim al-Qur'an*, and the topics.
  QUL serves its files to signed-in users, so they are committed under `sources/` and
  checked against pinned sha512 hashes;
- [`@fontsource/amiri-quran`](https://fontsource.org/fonts/amiri-quran) and
  [`@fontsource/aref-ruqaa`](https://fontsource.org/fonts/aref-ruqaa) for the cover
  titles (both OFL).

The fonts belong to the King Fahd Complex.
They may be used only for rendering the Qur'an. The released books contain rendered pages,
not the fonts, and are shared free of charge for reading the Qur'an.
