"""Experimental text edition: every word is real, selectable text in the KFGQPC font.

The image renderer draws each page onto a Recorder instead of pixels; each
recorded glyph becomes an absolutely positioned span and each line or frame a
div, so the text edition shares the image edition's layout exactly. Real text
lets the reader highlight and annotate, and the page images are replaced by
the fonts the pages share.
"""
import hashlib
import io
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER = 255


class Recorder:
    """Stands in for ImageDraw: records what the renderer draws instead of painting it."""

    def __init__(self):
        self.ops = []

    def text(self, xy, text, font=None, fill=0, anchor="la", direction=None, **_):
        self.ops.append(("text", xy, text, font, fill, anchor, direction))

    def line(self, xy, fill=0, width=1):
        self.ops.append(("line", xy, fill, width))

    def rectangle(self, xy, outline=None, width=1, fill=None):
        self.ops.append(("rect", xy, outline, width, 0, fill))

    def rounded_rectangle(self, xy, radius=0, outline=None, width=1, fill=None):
        self.ops.append(("rect", xy, outline, width, radius, fill))


def _gray(v) -> str:
    v = PAPER if v is None else int(v)
    return f"#{v:02x}{v:02x}{v:02x}"


def font_family(font: ImageFont.FreeTypeFont) -> str:
    """CSS family name for a Pillow font: its file name without extension."""
    name = font.path.replace("\\", "/").rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0]


def _label_png(op) -> tuple:
    """Rasterise a small label (page number, hizb) to a PNG cropped to its ink.

    Header labels use an ordinary UI font whose baseline e-readers place
    unpredictably; as tiny images they land exactly where the image edition has them.
    """
    _, (x, y), text, font, fill, anchor, direction = op
    kw = {"direction": direction} if direction else {}
    left, top, right, bottom = font.getbbox(text, anchor=anchor, **kw)
    box = (int(x + left) - 1, int(y + top) - 1, int(x + right) + 2, int(y + bottom) + 2)
    img = Image.new("L", (box[2] - box[0], box[3] - box[1]), PAPER)
    ImageDraw.Draw(img).text((x - box[0], y - box[1]), text, font=font, fill=fill, anchor=anchor, **kw)
    img = img.point(lambda v: min(255, round(v / 17) * 17))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return box, buf.getvalue()


def to_html(ops, is_text_font=lambda family: True) -> tuple:
    """Turn recorded ops into absolutely positioned HTML.

    Returns the HTML, the characters each embedded font must cover, and the
    label images (name -> PNG bytes) the HTML refers to.
    """
    out, chars, images = [], {}, {}
    for op in ops:
        if op[0] == "text" and not is_text_font(font_family(op[3])):
            box, png = _label_png(op)
            name = f"l{len(images)}"
            images[name] = png
            out.append(f'<img src="{{img}}{name}.png" alt="" style="left:{box[0]}px;top:{box[1]}px;'
                       f'width:{box[2] - box[0]}px;height:{box[3] - box[1]}px"/>')
        elif op[0] == "text":
            _, (x, y), text, font, fill, anchor, direction = op
            kw = {"direction": direction} if direction else {}
            # === move the anchor point to the left end of the baseline, where CSS text starts ===
            left_a, top_a = font.getbbox(text, anchor=anchor, **kw)[:2]
            left_s, top_s = font.getbbox(text, anchor="ls", **kw)[:2]
            x += left_s - left_a
            y += top_s - top_a
            ascent, descent = font.getmetrics()
            family = font_family(font)
            chars.setdefault(family, set()).update(text)
            dir_attr = ' dir="rtl"' if direction == "rtl" else ""
            out.append(
                f'<span{dir_attr} style="left:{x:.1f}px;top:{y - ascent:.1f}px;'
                f"font:{font.size}px/{ascent + descent}px '{family}';color:{_gray(fill)}\">"
                f"{escape(text)}</span>"
            )
        elif op[0] == "line":
            _, (x0, y0, x1, y1), fill, width = op
            if y0 == y1:  # === horizontal rule ===
                box = (min(x0, x1), y0 - width / 2, abs(x1 - x0), width)
            else:  # === vertical line, e.g. one column of the spine shadow ===
                box = (x0 - width / 2, min(y0, y1), width, abs(y1 - y0))
            out.append(
                f'<div style="left:{box[0]:.1f}px;top:{box[1]:.1f}px;width:{box[2]:.1f}px;'
                f'height:{box[3]:.1f}px;background:{_gray(fill)}"></div>'
            )
        elif op[0] == "rect":
            _, (x0, y0, x1, y1), outline, width, radius, fill = op
            border = f"border:{width}px solid {_gray(outline)};" if outline is not None else ""
            background = f"background:{_gray(fill)};" if fill is not None else ""
            out.append(
                f'<div style="left:{x0:.1f}px;top:{y0:.1f}px;width:{x1 - x0:.1f}px;'
                f'height:{y1 - y0:.1f}px;{border}{background}border-radius:{radius:.1f}px"></div>'
            )
    return "\n".join(out), chars, images


def _ttf(woff2: Path, chars: set, cache: Path) -> bytes:
    """Convert a woff2 font to TTF, the format Kindle accepts, keeping only the glyphs used.

    Decoding woff2 in pure Python is slow, so results are cached per font.
    """
    from fontTools import subset
    from fontTools.ttLib import TTFont

    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1("".join(sorted(chars)).encode()).hexdigest()[:12]
    cached = cache / f"{woff2.stem}-{key}.ttf"
    if not cached.exists():
        font = TTFont(woff2)
        font.flavor = None
        sub = subset.Subsetter(subset.Options(layout_features=["*"], name_IDs=["*"], notdef_outline=True))
        sub.populate(unicodes={ord(c) for c in chars})
        sub.subset(font)
        tmp = cached.with_suffix(".tmp")
        font.save(tmp)
        tmp.rename(cached)
    return cached.read_bytes()


def build(renderer, out: Path, tree: list, title: str, font_cache: Path) -> None:
    """Write the text edition of the mushaf as a fixed-layout EPUB."""
    from .epub import Screen, write_epub

    w, h = renderer.device.width, renderer.device.height
    screens, assets, chars = [], {}, {}
    for page in renderer.mushaf.pages:
        rec = Recorder()
        renderer.draw_page(rec, page)
        body, used, labels = to_html(rec.ops, is_text_font=lambda family: family.startswith("QCF"))
        stem = f"p{page.number:03d}"
        body = body.replace("{img}", f"../img/{stem}")
        for name, png in labels.items():
            assets[f"img/{stem}{name}.png"] = ("image/png", png)
        for family, cs in used.items():
            chars.setdefault(family, set()).update(cs)
        screens.append(Screen(stem, page.number, True, body=f'<div class="page">{body}</div>'))

    faces = []
    for family, cs in sorted(chars.items()):
        assets[f"fonts/{family}.ttf"] = ("font/ttf", _ttf(renderer.fonts / f"{family}.woff2", cs, font_cache))
        faces.append(f"@font-face{{font-family:'{family}';src:url(fonts/{family}.ttf)}}")
    css = "\n".join(faces) + f"""
html,body{{margin:0;padding:0}}
.page{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:#fff}}
.page span,.page div,.page img{{position:absolute;white-space:nowrap;margin:0;padding:0;box-sizing:border-box}}
"""
    assets["style.css"] = ("text/css", css.encode())
    cover = io.BytesIO()
    renderer.render(renderer.mushaf.pages[0]).save(cover, "PNG", optimize=True)
    assets["img/cover.png"] = ("image/png", cover.getvalue())
    write_epub(screens, tree, None, out, w, h, title, assets=assets, cover="img/cover.png",
               head='<link rel="stylesheet" type="text/css" href="../style.css"/>', comic=False)
