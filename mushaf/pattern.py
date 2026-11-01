"""The woven 12-fold rosette pattern on the covers.

Each rosette is a {12/5} star ringed by twelve petals and twelve outer
points; the petals' straight edges run on past the points and close into a
larger twelve-pointed star. A smaller rosette sits inside the central star,
its points on the star's inner corners. Every line is one of the rosette's
own lines, so lines meet at shared points instead of crossing at random.

Rosettes stand on a checkerboard, turned so that a star point lies on each
diagonal: neighbours touch tip to tip, and each one's lines run straight on
through the shared tip as its neighbour's lines. The lines left over carry
on until they meet another line or the edge of the page; between four
rosettes they close into a four-pointed star.

The lines are drawn as bands that weave over and under at crossings, and
thin towards the title.
"""
import math
from collections import defaultdict

from PIL import Image, ImageDraw

N = 12
R0 = math.cos(5 * math.pi / N) / math.cos(4 * math.pi / N)  # === inner corners of the {12/5} star ===
R1 = 1.0  # === its points ===
R2 = 1.42  # === where neighbouring petals part ===
R = 2.2  # === the outer points ===
LEVELS = 2  # === crossings past the outer points before the lines close into the large star ===
NESTED = 0.42  # === band width of the nested rosette, relative to the main bands ===
SS = 3  # === supersampling: drawn at three times the size, then reduced ===


def _pol(r, deg):
    """A point at radius r, `deg` degrees clockwise from straight up (y grows downward)."""
    a = math.radians(deg - 90)
    return (r * math.cos(a), r * math.sin(a))


def _turn(p, deg, s=1.0):
    a = math.radians(deg)
    return (s * (p[0] * math.cos(a) - p[1] * math.sin(a)), s * (p[0] * math.sin(a) + p[1] * math.cos(a)))


def _hit(p, d, a, b):
    """Distance t along the ray p + t*d (|d| = 1) to segment ab, or None if it misses."""
    ex, ey = b[0] - a[0], b[1] - a[1]
    den = d[0] * ey - d[1] * ex
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / den
    u = ((a[0] - p[0]) * d[1] - (a[1] - p[1]) * d[0]) / den
    return t if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9 else None


def _family():
    """The 24 lines through each outer point: from the petal corner on one side, through the point."""
    lines = []
    for k in range(N):
        f = 30 * k
        lines.append((_pol(R2, f + 30), _pol(R, f)))
        lines.append((_pol(R2, f - 30), _pol(R, f)))
    return lines


def _reach(lines, levels):
    """How far along each line (as a multiple of petal corner -> outer point) it runs before stopping."""
    if not levels:
        return 1.0
    (ax, ay), (bx, by) = lines[0]
    ts = []
    for c, d in lines[2:]:
        dx, dy = d[0] - c[0], d[1] - c[1]
        den = (ax - bx) * dy - (ay - by) * dx
        if abs(den) < 1e-12:
            continue
        t = ((ax - c[0]) * dy - (ay - c[1]) * dx) / den
        if t > 1.0001:
            ts.append(t)
    return sorted(set(round(t, 9) for t in ts))[levels - 1]


def rosette(levels=LEVELS):
    """One rosette's segments (in units of the central star's radius), their band widths, and its lines.

    Returns (segments, widths, rays, radius): `rays` are (tip, direction) where the lines end,
    for carrying them further; `radius` is how far the figure reaches.
    """
    lines = _family()
    end = _reach(lines, levels)
    segs = []
    star = []
    for k in range(N):
        f = 30 * k
        star += [_pol(R1, f), _pol(R0, f + 15)]
        segs.append((_pol(R1, f), _pol(R2, f)))  # === the side two petals share ===
    segs += [(star[i], star[(i + 1) % (2 * N)]) for i in range(2 * N)]
    rays = []
    for a, b in lines:
        e = (a[0] + (b[0] - a[0]) * end, a[1] + (b[1] - a[1]) * end)
        segs.append((a, e))
        length = math.dist(a, b)
        rays.append((e, ((b[0] - a[0]) / length, (b[1] - a[1]) / length)))
    widths = [1.0] * len(segs)
    # === the nested rosette: its outer points on the central star's inner corners ===
    if levels:
        inner, _, _, _ = rosette(0)
        s = R0 / R
        segs += [(_turn(a, 15, s), _turn(b, 15, s)) for a, b in inner]
        widths += [NESTED] * len(inner)
    radius = math.hypot(*rays[0][0])
    return segs, widths, rays, radius


def field(w, h, cx, cy, tip, cells):
    """Segments and band widths for rosettes at checkerboard `cells` around (cx, cy), in pixels.

    `tip` is the radius of each rosette's outer star; neighbours on the diagonals touch tip to tip.
    """
    base, base_w, base_rays, radius = rosette()
    sc = tip / radius
    step = math.sqrt(2) * tip
    centres = [(cx + i * step, cy + j * step) for i, j in cells if (i + j) % 2 == 0]

    def place(p, o):
        q = _turn(p, 15)  # === a star point on each diagonal ===
        return (o[0] + q[0] * sc, o[1] + q[1] * sc)

    segs, widths, owner = [], [], []
    for n, o in enumerate(centres):
        segs += [(place(a, o), place(b, o)) for a, b in base]
        widths += base_w
        owner += [n] * len(base)
    main = [i for i, f in enumerate(widths) if f == 1.0]
    edges = [((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))]

    # === carry each line on from its tip, unless the tip touches a neighbour's ===
    starts = []
    for n, o in enumerate(centres):
        for e, d in base_rays:
            p = place(e, o)
            d = _turn(d, 15)
            shared = any(m != n and abs(math.dist(p, c) - tip) < 1e-6 * tip for m, c in enumerate(centres))
            if shared or not (0 <= p[0] <= w and 0 <= p[1] <= h):
                continue
            far = min(t for t in (_hit(p, d, *e) for e in edges) if t is not None)
            for i in main:
                if owner[i] != n:
                    t = _hit(p, d, *segs[i])
                    if t is not None and t < far:
                        far = t
            starts.append((p, d, far))
    # === where two carried lines meet, the one that arrives later stops there ===
    for k, (p, d, far) in enumerate(starts):
        stop = far
        for j, (q, e, far2) in enumerate(starts):
            if j == k:
                continue
            t = _hit(p, d, q, (q[0] + e[0] * far2, q[1] + e[1] * far2))
            if t is not None and t < stop:
                u = _hit(q, e, p, (p[0] + d[0] * stop, p[1] + d[1] * stop))
                if u is not None and u <= t + 1e-6:
                    stop = t
        if stop > 1e-3:
            segs.append((p, (p[0] + d[0] * stop, p[1] + d[1] * stop)))
            widths.append(1.0)
    return segs, widths


def _crossings(segs):
    """Points where two segments cross inside both: the places where one band passes over the other."""
    out = []
    for i in range(len(segs)):
        (x1, y1), (x2, y2) = segs[i]
        lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
        for j in range(i + 1, len(segs)):
            (x3, y3), (x4, y4) = segs[j]
            if max(x3, x4) < lo_x or min(x3, x4) > hi_x or max(y3, y4) < lo_y or min(y3, y4) > hi_y:
                continue
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(den) < 1e-12:
                continue
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
            if 1e-6 < t < 1 - 1e-6 and 1e-6 < u < 1 - 1e-6:
                out.append((i, j, t, u, (x1 + t * (x2 - x1), y1 + t * (y2 - y1))))
    return out


def _weave(cross):
    """For each crossing, the segment that passes over: alternating along every segment where it can."""
    along = defaultdict(list)
    for c, (i, j, t, u, _) in enumerate(cross):
        along[i].append((t, c, 0))
        along[j].append((u, c, 1))
    links = defaultdict(list)
    for marks in along.values():
        marks.sort()
        for (_, c1, r1), (_, c2, r2) in zip(marks, marks[1:]):
            links[c1].append((c2, 1 ^ r1 ^ r2))
            links[c2].append((c1, 1 ^ r1 ^ r2))
    first_over = {}
    for start in range(len(cross)):
        if start in first_over:
            continue
        first_over[start] = True
        todo = [start]
        while todo:
            c = todo.pop()
            for nxt, flip in links[c]:
                if nxt not in first_over:
                    first_over[nxt] = first_over[c] ^ bool(flip)
                    todo.append(nxt)
    return [(cross[c][0] if first_over[c] else cross[c][1], cross[c][4]) for c in range(len(cross))]


def draw(w, h, centre, tip, cells, taper=None, band=0.0089, channel=0.5):
    """The pattern as a w x h grayscale image.

    centre and tip are fractions of the width and height (tip of the width); `taper` is
    (top, bottom) as fractions of the height: bands keep their width above `top` and thin
    to a hairline at `bottom`. `band` is the band width as a share of the width, and
    `channel` the white channel inside it as a share of the band.
    """
    W, H = w * SS, h * SS
    segs, widths = field(W, H, centre[0] * W, centre[1] * H, tip * W, cells)
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    outer = band * W
    inner = outer * channel
    hair = max(1.0, W / 1100)

    def scale(y):
        if not taper or y <= taper[0] * H:
            return 1.0
        t = min(1.0, (y - taper[0] * H) / ((taper[1] - taper[0]) * H))
        return (1 - t) ** 1.6

    def width(y, f, layer):
        s = scale(y) * f
        return max(round(hair), round(outer * s)) if layer == 0 else round(inner * s)

    def stretch(a, b, f, layer):
        """One band from a to b, as wide as the taper allows at each height.

        The band is cut into short pieces only where its width changes; pieces of one width
        are drawn as a single stroke, so no seams show inside the channel.
        """
        n = max(1, int(math.dist(a, b) / (2 * SS)))
        at = lambda k: (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
        run, run_w = 0, None
        for k in range(n + 1):
            wk = width((at(k)[1] + at(min(k + 1, n))[1]) / 2, f, layer) if k < n else None
            if wk != run_w:
                if run_w is not None and (layer == 0 or run_w >= 2):
                    d.line((*at(run), *at(k)), fill=0 if layer == 0 else 255, width=run_w)
                run, run_w = k, wk
        # === round ends: corners close without notches, and channels meet cleanly ===
        for p in (a, b):
            r = width(p[1], f, layer) / 2
            if r >= 1:
                d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=0 if layer == 0 else 255)

    for (a, b), f in zip(segs, widths):
        stretch(a, b, f, 0)
    for (a, b), f in zip(segs, widths):
        stretch(a, b, f, 1)
    # === over-crossings: the upper band, redrawn across the lower one ===
    for i, x in _weave(_crossings(segs)):
        (a, b), f = segs[i], widths[i]
        s = scale(x[1]) * f
        if inner * s < 2:
            continue  # === too fine for over and under to show: leave the hairlines crossing ===
        reach = outer * 1.6 * s / math.dist(a, b)
        ux, uy = b[0] - a[0], b[1] - a[1]
        p, q = (x[0] - ux * reach, x[1] - uy * reach), (x[0] + ux * reach, x[1] + uy * reach)
        d.line((*p, *q), fill=0, width=round(outer * s))
        d.line((*p, *q), fill=255, width=round(inner * s))
    return img.resize((w, h), Image.LANCZOS)
