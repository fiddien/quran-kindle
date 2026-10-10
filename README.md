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

Each size comes as three books:

- `mushaf-text-….pdf`: the mushaf as real text, so you can highlight words and add
  notes. Copy it over USB into the Kindle's `documents` folder.
- `mushaf-….epub` and `.pdf`: the mushaf as page images.
- `companion-….epub` and `.pdf`: the word-by-word companion.

## Text edition

In `mushaf-text` every word is real text in the King Fahd Complex font, placed exactly
where the printed mushaf has it, so the page looks the same as the image edition. Kindle's
PDF reader can highlight single words and attach notes to them. In the notes list and in "My Clippings", highlighted Qur'an text shows as codes rather than
Arabic, because those views don't use the book's font.

## Word-by-word companion

A second book shows every mushaf line with an English gloss under each word.
At readable sizes a page needs two screens (lines 1–8, then 9–15). Both screens
are labelled with the mushaf page number, so "Go to page 50" can still find
page 50.

## Build

```sh
pip install -r requirements.txt
python -m mushaf --device paperwhite          # both books, EPUB + PDF, in out/paperwhite/
python -m mushaf --book mushaf                # only the mushaf
python -m mushaf --pages 1-3,604              # quick preview PNGs only
python -m mushaf --text-scale 0.85            # smaller script, more space between lines
python -m mushaf --book mushaf-text --formats pdf   # the text edition as a PDF
```

Devices: `paperwhite` (2021+),
`paperwhite-old`, `kindle` (2022+), `kindle-2019`, `oasis`, `scribe`, `kobo-clara`, `kobo-libra`.

Pushing a tag such as `v1.0.0`, or running the *Build books* workflow by hand with a
release version, makes GitHub Actions build the `paperwhite`, `kindle` and
`oasis` sizes and publish them as a release. Run by hand without a version, the workflow
only builds; its files then appear as downloads on that run's page for 7 days.

## Put it on the Kindle

- **EPUB:** send it with [Send to Kindle](https://www.amazon.com/sendtokindle).
- **PDF:** copy it over USB into the `documents` folder.

## Sources and licensing

The build downloads three pinned npm packages:

- [`quran-qcf4`](https://github.com/MohamadHajjRabee/quran-qcf4) for the page layouts
  (MIT) and the KFGQPC QCF4 fonts;
- [`quran-meta`](https://github.com/quran-center/quran-meta) for the juz' and hizb
  boundaries (MIT);
- [`@kmaslesa/holy-quran-word-by-word-full-data`](https://www.npmjs.com/package/@kmaslesa/holy-quran-word-by-word-full-data)
  for the English glosses. This is a dump of quran.com's word-by-word data, so the
  translation's rights rest with its original authors.

The fonts belong to the King Fahd Complex.
They may be used only for rendering the Qur'an. The released books contain rendered pages,
not the fonts, and are shared free of charge for reading the Qur'an.
