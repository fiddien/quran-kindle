# Madinah Mushaf for Kindle

Builds a crisp, easy-to-navigate copy of the **Madinah mushaf** (King Fahd Complex,
1441 AH, calligraphy by Uthman Taha) for Kindle and other e-readers. Every page keeps
the printed layout: 604 pages, 15 lines, same line breaks. Your page memory carries over.

Each page is rendered at the exact pixel size of your screen in 16 gray levels, so
the device never rescales it. The book has:

- a table of contents with all **114 surahs** and **30 juz'**, each with its **2 hizb**;
- right-to-left page turning;
- "Go to page N" landing on mushaf page N;
- a running header (surah, juz', hizb) on every page;
- a cue for which side of the open mushaf each page sits on: odd pages are
  right-hand pages, with a soft spine shadow on their left edge and the page
  number in the top-right corner, and even pages mirror this.

## Word-by-word companion

A second book shows every mushaf line with an English gloss under each word.
At readable sizes a page needs two screens (lines 1–8, then 9–15). Both screens
are labelled with the mushaf page number, so "Go to page 50" can still find
page 50. Whether your Kindle honours these labels after Amazon's conversion
needs testing on the device. If it doesn't, the table of contents lists every
page under its juz'.

## Build

```sh
pip install -r requirements.txt
python -m mushaf --device paperwhite          # both books, EPUB + PDF, in out/paperwhite/
python -m mushaf --book mushaf                # only the mushaf
python -m mushaf --pages 1-3,604              # quick preview PNGs only
python -m mushaf --text-scale 0.85            # smaller script, more space between lines
```

A full build of both books takes about 6 minutes on 4 cores. Devices: `paperwhite` (2021+), `paperwhite-old`, `kindle`, `oasis`, `scribe`,
`kobo-clara`, `kobo-libra`.

## Put it on the Kindle

- **EPUB:** send it with [Send to Kindle](https://www.amazon.com/sendtokindle). Amazon
  converts it into a full-screen fixed-layout book.
- **PDF:** copy it over USB into the `documents` folder. It is less smooth than the
  EPUB but needs no conversion.

## Sources and licensing

The build downloads two pinned npm packages, checks their hashes, and caches them in `cache/`:

- [`quran-qcf4`](https://github.com/MohamadHajjRabee/quran-qcf4) for the page layouts
  (MIT) and the KFGQPC QCF4 fonts;
- [`quran-meta`](https://github.com/quran-center/quran-meta) for the juz' and hizb
  boundaries (MIT);
- [`@kmaslesa/holy-quran-word-by-word-full-data`](https://www.npmjs.com/package/@kmaslesa/holy-quran-word-by-word-full-data)
  for the English glosses. This is a dump of quran.com's word-by-word data, so the
  translation's rights rest with its original authors.

The fonts belong to the King Fahd Complex, and this repository does not include them.
They may be used only for rendering the Qur'an. Keep the generated books for personal
use; don't redistribute them.
