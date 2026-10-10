"""Download and verify the pinned npm packages that hold the mushaf data.

quran-qcf4  : 604 page layouts (15 lines each) + KFGQPC QCF4 glyph fonts.
quran-meta  : juz' and hizb-quarter boundaries (absolute ayah numbers).
quran-wbw   : English word-by-word glosses (a dump of quran.com's word data).

The fonts are not ours to redistribute, so they are fetched at build time
into ./cache and never committed.
"""
import base64
import hashlib
import io
import tarfile
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
    "quran-wbw": (
        "https://registry.npmjs.org/@kmaslesa/holy-quran-word-by-word-full-data/-/holy-quran-word-by-word-full-data-1.0.6.tgz",
        "sha512-wQk4azEWNXoQyDB1JwxkdNAj2sFyiErI2K+CMPs83LQEUqysp4B/tw4AfJ+HLNObYo84Iw29QznkOy8FkPyl3A==",
    ),
}


def _verify(blob: bytes, integrity: str) -> None:
    algo, expected = integrity.split("-", 1)
    actual = base64.b64encode(hashlib.new(algo, blob).digest()).decode()
    if actual != expected:
        raise RuntimeError(f"integrity mismatch: expected {expected}, got {actual}")


def fetch(name: str, cache: Path) -> Path:
    """Return the extracted package directory, downloading it if needed."""
    url, integrity = PACKAGES[name]
    dest = cache / name
    marker = dest / ".ok"
    if marker.exists():
        return dest / "package"
    print(f"downloading {url}")
    with urllib.request.urlopen(url) as resp:
        blob = resp.read()
    _verify(blob, integrity)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")
    marker.write_text(integrity)
    return dest / "package"
