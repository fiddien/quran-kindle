"""Download and verify the pinned npm packages that hold the mushaf data.

quran-qcf4  : 604 page layouts (15 lines each) + KFGQPC QCF4 glyph fonts.
quran-meta  : juz' and hizb-quarter boundaries (absolute ayah numbers).
quran-wbw   : English word-by-word glosses (a dump of quran.com's word data).
amiri-quran : Amiri Quran typeface (OFL), fallback for Arabic titles.
aref-ruqaa  : Aref Ruqaa typeface (OFL) for the ruq'ah title on the covers.
quran-cloud : English surah names (and a plain Saheeh International text).

The fonts are not ours to redistribute, so they are fetched at build time
into ./cache and never committed.

Files from QUL (qul.tarteel.ai) are downloaded by hand, since QUL serves them
to signed-in users, and committed under ./sources with their hashes pinned here.

qul-surah-info-en : English surah introductions (QUL "Surah info", English).
qul-saheeh        : Saheeh International English with the translator's footnotes.
"""
import base64
import hashlib
import io
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

PACKAGES = {
    "quran-qcf4": (
        "https://registry.npmjs.org/quran-qcf4/-/quran-qcf4-1.1.0.tgz",
        "sha512-TJOKlv7l6U+eFsgaJJVP1cMkW5FOxSayJR9UJGb0KPv/+HjEGEJBMqcvNaSda/AmKpRt44xoxw1arWJPPbuG+Q==",
    ),
    "quran-meta": (
        "https://registry.npmjs.org/quran-meta/-/quran-meta-7.0.0.tgz",
        "sha512-nxC+DBRb3ibTUyNVxWz6O7oS6/2ZYGaKlSG4XR43U9FdsVvgg1CVdlQFwy7/orUaLJ5sfDx2gBmTS/ixi8M7xQ==",
    ),
    "amiri-quran": (
        "https://registry.npmjs.org/@fontsource/amiri-quran/-/amiri-quran-5.3.0.tgz",
        "sha512-z/Y3JCqGWnWLpfJGBWPf7C42IxHjxxuwgcCHLmsU/hYd65GHXkZ/XTVpEGtWrEx9VlzdzMMRHDNTJvs8OwAeEw==",
    ),
    "aref-ruqaa": (
        "https://registry.npmjs.org/@fontsource/aref-ruqaa/-/aref-ruqaa-5.3.0.tgz",
        "sha512-GC+ckm4v2zndUWuR2JiMdO333mNZqrzxHN/9rpBJhLwDwcwYXzr+GzCRzgK6afGMhYnV0pwrqeGeLm4ZNmWhWQ==",
    ),
    "quran-cloud": (
        "https://registry.npmjs.org/quran-cloud/-/quran-cloud-1.0.0.tgz",
        "sha512-DIXV0mX9E9IA5ZNEpuSA4W1QepNQCsCVlcvCY6P5bqEBuczqNAjIkPrs0wDXyMXaJnN8h7vbpygQV55ghStiKQ==",
    ),
    "quran-wbw": (
        "https://registry.npmjs.org/@kmaslesa/holy-quran-word-by-word-full-data/-/holy-quran-word-by-word-full-data-1.0.6.tgz",
        "sha512-wQk4azEWNXoQyDB1JwxkdNAj2sFyiErI2K+CMPs83LQEUqysp4B/tw4AfJ+HLNObYo84Iw29QznkOy8FkPyl3A==",
    ),
}

FILES = {
    "qul-surah-info-en": (
        "qul-surah-info-en.csv.zip",
        "sha512-SLrs0SLMSi2zD5DUwqHbCAVVpJGwz+2weRwPedYZY1mvXO4mCw588HDQ1YyLsfpSs3D9oy/YD8o7QmWpqOmwog==",
    ),
    "qul-saheeh": (
        "qul-en-sahih-international-with-footnote-tags.db.zip",
        "sha512-0oEr3ETmDqSHrTbzNc52eW0kLXnIehwlj34YgTqYEoQlIcF0IcFjoyeybW8L3PuoQ+W83BpZM70ad25q4OEOcw==",
    ),
}
COMMITTED = Path(__file__).resolve().parent.parent / "sources"


def _verify(blob: bytes, integrity: str) -> None:
    algo, expected = integrity.split("-", 1)
    actual = base64.b64encode(hashlib.new(algo, blob).digest()).decode()
    if actual != expected:
        raise RuntimeError(f"integrity mismatch: expected {expected}, got {actual}")


def fetch(name: str, cache: Path) -> Path:
    """Return the extracted package directory, downloading it if needed."""
    url, integrity = PACKAGES[name]
    dest = cache / name
    if (dest / ".ok").exists():
        return dest / "package"
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as resp:
        blob = resp.read()
    _verify(blob, integrity)
    # === unpack beside the target, then move it into place, so no reader sees half a package ===
    cache.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=cache, prefix=f".{name}-"))
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        tar.extractall(staging, filter="data")
    (staging / ".ok").write_text(integrity)
    shutil.rmtree(dest, ignore_errors=True)
    staging.rename(dest)
    return dest / "package"


def local(name: str) -> Path:
    """Return a committed source file after checking it against its pinned hash."""
    filename, integrity = FILES[name]
    path = COMMITTED / filename
    _verify(path.read_bytes(), integrity)
    return path
