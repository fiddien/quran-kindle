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
GRID = 512  # === font units per em in the embedded fonts ===


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
            # === from the anchor point to the left end of the baseline, where CSS text starts ===
            left_a, top_a = font.getbbox(text, anchor=anchor, **kw)[:2]
            left_s, top_s = font.getbbox(text, anchor="ls", **kw)[:2]
            x += left_a - left_s
            y += top_a - top_s
            ascent, descent = font.getmetrics()
            family = font_family(font)
            chars.setdefault(family, set()).update(text)
            # === explicit direction: inside the book's RTL pages, English punctuation would flip ===
            dir_attr = ' dir="rtl"' if direction == "rtl" else ' dir="ltr"'
            # === trailing space = word boundary, so highlights don't snap to whole lines ===
            out.append(
                f'<span{dir_attr} style="left:{x:.1f}px;top:{y - ascent:.1f}px;'
                f"font:{font.size}px/{ascent + descent}px '{family}';color:{_gray(fill)}\">"
                f"{escape(text)} </span>"
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


def _ttf(woff2: Path, chars: set, cache: Path) -> Path:
    """Convert a woff2 font to TTF, the format Kindle accepts, keeping only the glyphs used.

    Decoding woff2 in pure Python is slow, so results are cached per font.
    """
    from fontTools import subset
    from fontTools.ttLib import TTFont

    from fontTools.ttLib.scaleUpem import scale_upem

    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1("".join(sorted(chars)).encode()).hexdigest()[:12]
    cached = cache / f"{woff2.stem}-{key}-g{GRID}.ttf"
    if not cached.exists():
        font = TTFont(woff2)
        font.flavor = None
        sub = subset.Subsetter(subset.Options(layout_features=["*"], name_IDs=["*"], notdef_outline=True))
        sub.populate(unicodes={ord(c) for c in chars})
        sub.subset(font)
        # === a coarser outline grid: about 0.1 screen pixel at reading size, 19% smaller ===
        scale_upem(font, GRID)
        tmp = cached.with_suffix(".tmp")
        font.save(tmp)
        tmp.rename(cached)
    return cached


def _prune(tree: list, keep: set) -> list:
    """Drop table-of-contents entries for pages outside a sample build."""
    out = []
    for label, page, children in tree:
        kids = _prune(children, keep)
        if page in keep or kids:
            out.append((label, page if page in keep else kids[0][1], kids))
    return out


def is_text_font(family: str) -> bool:
    """Fonts kept as real text: the mushaf glyphs and the English serif.

    The UI font's Arabic labels need shaping that readers apply unpredictably,
    so they become tiny images instead.
    """
    return family.startswith(("QCF", "Liberation", "DejaVuSerif", "Times", "times"))


def _fonts(screens_ops, font_cache: Path) -> dict:
    """Subset TTF (path) for every text font the screens use."""
    chars, paths = {}, {}
    for _, ops in screens_ops:
        for op in ops:
            if op[0] == "text" and is_text_font(font_family(op[3])):
                family = font_family(op[3])
                chars.setdefault(family, set()).update(op[2])
                paths[family] = Path(op[3].path)
    return {family: _ttf(paths[family], cs, font_cache) for family, cs in sorted(chars.items())}


def build(screens_ops: list, tree: list, out: Path, w: int, h: int, title: str, font_cache: Path,
          cover_png: bytes) -> None:
    """Write a text edition as a fixed-layout EPUB.

    screens_ops is a list of (Screen, recorded ops) in reading order; the
    cover appears only in the library, so page numbering is unaffected.
    """
    from .epub import write_epub

    tree = _prune(tree, {screen.page for screen, _ in screens_ops})
    screens, assets = [], {}
    for screen, ops in screens_ops:
        body, _, labels = to_html(ops, is_text_font=is_text_font)
        body = body.replace("{img}", f"../img/{screen.stem}")
        for name, png in labels.items():
            assets[f"img/{screen.stem}{name}.png"] = ("image/png", png)
        screen.body = f'<div class="page">{body}</div>'
        screens.append(screen)

    faces = []
    for family, path in _fonts(screens_ops, font_cache).items():
        assets[f"fonts/{family}.ttf"] = ("font/ttf", path.read_bytes())
        faces.append(f"@font-face{{font-family:'{family}';src:url(fonts/{family}.ttf)}}")
    css = "\n".join(faces) + f"""
html,body{{margin:0;padding:0}}
.page{{position:relative;width:{w}px;height:{h}px;overflow:hidden;background:#fff}}
.page span,.page div,.page img{{position:absolute;white-space:nowrap;margin:0;padding:0;box-sizing:border-box}}
"""
    assets["style.css"] = ("text/css", css.encode())
    assets["img/cover.png"] = ("image/png", cover_png)
    write_epub(screens, tree, None, out, w, h, title, assets=assets, cover="img/cover.png",
               head='<link rel="stylesheet" type="text/css" href="../style.css"/>', comic=False)


def build_pdf(screens_ops: list, tree: list, out: Path, w: int, h: int, title: str, font_cache: Path) -> None:
    """Write a text edition as a PDF: the same positioned glyphs, with the fonts embedded.

    Kindle's PDF reader allows highlights and notes on real text, and a PDF
    keeps every glyph exactly where it is placed. It starts on the first
    mushaf page; a cover would shift every page by one.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from .pdf import write_pdf

    # === register each subset under its own name: reportlab keeps the first font of a name ===
    names = {}
    for family, path in _fonts(screens_ops, font_cache).items():
        names[family] = path.stem
        if path.stem not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(path.stem, str(path)))
    ops_of = {screen.stem: ops for screen, ops in screens_ops}

    def paint(c, screen, k):
        paint_ops(c, ops_of[screen.stem], h, k, names)

    screens = [screen for screen, _ in screens_ops]
    write_pdf(screens, _prune(tree, {s.page for s in screens}), None, out, w, h, title, paint=paint)


def mushaf_screens(renderer, pages) -> list:
    """(Screen, ops) for each mushaf page."""
    from .epub import Screen

    out = []
    for n in pages:
        rec = Recorder()
        renderer.draw_page(rec, renderer.mushaf.pages[n - 1])
        out.append((Screen(f"p{n:03d}", n, True), rec.ops))
    return out


def paint_ops(c, ops, h: int, k: float, names: dict = None) -> None:
    """Draw recorded ops onto a reportlab canvas; k converts pixels to points.

    names maps a font family to the name its subset was registered under.
    """
    names = names or {}
    from reportlab.lib.utils import ImageReader

    for op in ops:
        if op[0] == "text" and not is_text_font(font_family(op[3])):
            # === header labels: tiny images, as in the EPUB (reportlab can't shape Arabic) ===
            box, png = _label_png(op)
            c.drawImage(ImageReader(io.BytesIO(png)), box[0] * k, (h - box[3]) * k,
                        (box[2] - box[0]) * k, (box[3] - box[1]) * k)
        elif op[0] == "text":
            _, (x, y), text, font, fill, anchor, direction = op
            left_a, top_a = font.getbbox(text, anchor=anchor)[:2]
            left_s, top_s = font.getbbox(text, anchor="ls")[:2]
            c.setFillGray(fill / 255)
            c.setFont(names.get(font_family(font), font_family(font)), font.size * k)
            c.drawString((x + left_a - left_s) * k, (h - (y + top_a - top_s)) * k, text)
        elif op[0] == "line":
            # === filled strips, not strokes: adjacent shadow columns then meet without gaps ===
            _, (x0, y0, x1, y1), fill, width = op
            if y0 == y1:
                box = (min(x0, x1), y0 - width / 2, abs(x1 - x0), width)
            else:
                box = (x0 - width / 2, min(y0, y1), width, abs(y1 - y0))
            c.setFillGray(fill / 255)
            c.rect(box[0] * k, (h - box[1] - box[3]) * k, box[2] * k, box[3] * k, stroke=0, fill=1)
        elif op[0] == "rect":
            _, (x0, y0, x1, y1), outline, width, radius, fill = op
            c.setStrokeGray((outline if outline is not None else 255) / 255)
            c.setLineWidth(width * k)
            c.roundRect(x0 * k, (h - y1) * k, (x1 - x0) * k, (y1 - y0) * k, radius * k,
                        stroke=1 if outline is not None else 0, fill=0)
