"""
A small immediate-mode 2D animation engine on Skia.

Every scene draws a whole frame as a pure function of time t (seconds), in a fixed
1920x1080 coordinate space (origin top-left). No state carries between frames, so a
scene can be rendered in any order, in parallel chunks, or as single stills.
"""
import math, os, sys, functools
import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
sys.path.insert(0, VIDEO)
from film.timing import timing_for  # noqa: E402

W, H = 1920, 1080
FONT_DIR = os.path.join(VIDEO, "assets", "fonts")

# ---------------------------------------------------------------- colour
def hexc(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r, g, b, a)


def mix(c1, c2, u):
    a, b = (hexc(c1) if isinstance(c1, str) else c1), (hexc(c2) if isinstance(c2, str) else c2)
    return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def shade(c, k):
    """k < 0 darker, k > 0 lighter"""
    r, g, b, a = hexc(c) if isinstance(c, str) else c
    if k < 0:
        return (r * (1 + k), g * (1 + k), b * (1 + k), a)
    return (r + (255 - r) * k, g + (255 - g) * k, b + (255 - b) * k, a)


def col(c, alpha=1.0):
    r, g, b, a = hexc(c) if isinstance(c, str) else c
    return skia.Color(int(max(0, min(255, r))), int(max(0, min(255, g))), int(max(0, min(255, b))), int(max(0, min(255, 255 * a * alpha))))


# palette: deep night blues with warm accents
NIGHT0, NIGHT1, NIGHT2 = "#0E0B2A", "#1C1550", "#2E1E6E"
INK = "#F5F1FF"
SOFT = "#B9B0E6"
DIM = "#6E64A8"
GOLD = "#FFC93C"
AMBER = "#FF9F1C"
CORAL = "#FF6B6B"
ROSE = "#FF4F9A"
CYAN = "#3DDCFF"
TEAL = "#2EC4B6"
MINT = "#5BE3A5"
VIOLET = "#9D7BFF"
LILAC = "#C9B6FF"
CREAM = "#FFF4DC"
WOOD = "#C98B5A"
SLATE = "#3B3570"

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, u):
    return a + (b - a) * u


def lin(u):
    return clamp(u)


def smooth(u):
    u = clamp(u); return u * u * (3 - 2 * u)


def io(u):            # ease in-out cubic
    u = clamp(u); return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def out(u):           # ease out cubic
    u = clamp(u); return 1 - (1 - u) ** 3


def inn(u):
    u = clamp(u); return u ** 3


def back(u, s=1.7):   # ease out with overshoot
    u = clamp(u); u -= 1; return u * u * ((s + 1) * u + s) + 1


def elastic(u):
    u = clamp(u)
    if u in (0.0, 1.0):
        return u
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi) / 3) + 1


def prog(t, t0, d, ease=io):
    if d <= 0:
        return 1.0 if t >= t0 else 0.0
    return ease((t - t0) / d)


def pulse(t, t0, d):
    """0 -> 1 -> 0 over [t0, t0+d]"""
    u = clamp((t - t0) / d) if d > 0 else 0
    return math.sin(math.pi * u)


# ---------------------------------------------------------------- fonts & text
@functools.lru_cache(None)
def typeface(name):
    files = {"display": "Fredoka-SemiBold.ttf", "bold": "Fredoka-Bold.ttf", "body": "Fredoka-Medium.ttf", "light": "Fredoka-Regular.ttf"}
    if name in files:
        return skia.Typeface.MakeFromFile(os.path.join(FONT_DIR, files[name]))
    if name == "mono":
        return skia.Typeface.MakeFromName("JetBrains Mono", skia.FontStyle.Bold())
    if name == "monol":
        return skia.Typeface.MakeFromName("JetBrains Mono", skia.FontStyle.Normal())
    for suffix, wt in ((" SemiBold", 600), (" Bold", 700), (" Medium", 500)):
        if name.endswith(suffix):
            return skia.Typeface.MakeFromName(name[: -len(suffix)], skia.FontStyle(wt, 5, skia.FontStyle.kUpright_Slant))
    return skia.Typeface.MakeFromName(name, skia.FontStyle.Normal())


@functools.lru_cache(4096)
def font(name, size):
    f = skia.Font(typeface(name), size)
    f.setSubpixel(True)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    return f


def text_width(s, size, face="body"):
    return _measure(s, size, face)


FALLBACK = {"display": "Inter Display SemiBold", "bold": "Inter Display Bold", "body": "Inter Display Medium", "light": "Inter Display"}


@functools.lru_cache(4096)
def _runs(s, face):
    """split s into runs that the face can draw, and runs that need the fallback face"""
    f = font(face, 20)
    gl = f.textToGlyphs(s)
    runs, cur, curfb = [], "", None
    for ch, g in zip(s, gl):
        fb = (g == 0 and face in FALLBACK)
        if curfb is None or fb == curfb:
            cur += ch
        else:
            runs.append((cur, curfb)); cur = ch
        curfb = fb
    if cur:
        runs.append((cur, curfb))
    return tuple(runs)


def _measure(s, size, face):
    return sum(font(FALLBACK[face] if fb else face, round(size, 1)).measureText(r) for r, fb in _runs(s, face))


def text(c, s, x, y, size, color=INK, face="body", align="center", alpha=1.0, shadow=0.0, valign="middle"):
    """draw single-line text; (x, y) is the anchor; returns width"""
    if alpha <= 0.003 or not s:
        return 0
    runs = _runs(s, face)
    if len(runs) > 1 or runs[0][1]:
        w = _measure(s, size, face)
        x0 = x + {"center": -w / 2, "left": 0, "right": -w}[align]
        for r, fb in runs:
            x0 += _text1(c, r, x0, y, size, color, FALLBACK[face] if fb else face, "left", alpha, shadow, valign, base_face=face)
        return w
    return _text1(c, s, x, y, size, color, face, align, alpha, shadow, valign)


def _text1(c, s, x, y, size, color, face, align, alpha, shadow, valign, base_face=None):
    f = font(face, round(size, 1))
    w = f.measureText(s)
    dx = {"center": -w / 2, "left": 0, "right": -w}[align]
    m = font(base_face or face, round(size, 1)).getMetrics()
    dy = {"middle": -(m.fAscent + m.fDescent) / 2, "baseline": 0, "top": -m.fAscent}[valign]
    if shadow > 0:
        p = skia.Paint(AntiAlias=True, Color=col("#05031A", 0.55 * alpha * shadow), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, size * 0.06))
        c.drawString(s, x + dx + size * 0.03, y + dy + size * 0.06, f, p)
    c.drawString(s, x + dx, y + dy, f, skia.Paint(AntiAlias=True, Color=col(color, alpha)))
    return w


def rich(c, runs, x, y, size, align="center", alpha=1.0, face="body", shadow=0.0):
    """runs: list of (string, colour) where a string starting with '^' is a superscript"""
    parts = []
    for s, colr in runs:
        sup = s.startswith("^")
        ss = s[1:] if sup else s
        sz = size * (0.58 if sup else 1.0)
        parts.append((ss, colr, sz, sup, text_width(ss, sz, face)))
    total = sum(p[4] for p in parts)
    cx = {"center": x - total / 2, "left": x, "right": x - total}[align]
    for ss, colr, sz, sup, w in parts:
        text(c, ss, cx, y - (size * 0.42 if sup else 0), sz, colr, face, "left", alpha, shadow)
        cx += w
    return total


def fmt(n):
    return f"{n:,}"


# ---------------------------------------------------------------- shapes
def paint(color, alpha=1.0, stroke=0.0, cap=skia.Paint.kRound_Cap, blur=0.0):
    p = skia.Paint(AntiAlias=True, Color=col(color, alpha))
    if stroke:
        p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(stroke); p.setStrokeCap(cap); p.setStrokeJoin(skia.Paint.kRound_Join)
    if blur:
        p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
    return p


def glow(c, x, y, r, color, alpha=0.6):
    """soft radial glow (cheap: a radial gradient, no blur)"""
    if alpha <= 0.003 or r <= 0:
        return
    col0 = col(color, alpha)
    p = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial(
        (x, y), r, [col0, col(color, alpha * 0.35), col(color, 0)], [0.0, 0.35, 1.0]))
    c.drawCircle(x, y, r, p)


def circle(c, x, y, r, color, alpha=1.0):
    c.drawCircle(x, y, r, paint(color, alpha))


def ring(c, x, y, r, color, width, alpha=1.0):
    c.drawCircle(x, y, r, paint(color, alpha, stroke=width))


def rrect(c, x, y, w, h, r, color, alpha=1.0, stroke=0.0):
    c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r), paint(color, alpha, stroke=stroke))


def line(c, x1, y1, x2, y2, color, width, alpha=1.0):
    c.drawLine(x1, y1, x2, y2, paint(color, alpha, stroke=width))


def soft_shadow(c, x, y, rx, ry, alpha=0.35):
    p = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeRadial((0, 0), 1, [col("#03020F", alpha), col("#03020F", 0)]))
    c.save(); c.translate(x, y); c.scale(rx, ry); c.drawCircle(0, 0, 1, p); c.restore()


def poly(c, pts, color, alpha=1.0, stroke=0.0, close=True):
    path = skia.Path()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    if close:
        path.close()
    c.drawPath(path, paint(color, alpha, stroke=stroke))


def arc(c, x, y, r, a0, sweep, color, width, alpha=1.0):
    """angles in degrees, clockwise from 3 o'clock"""
    rect = skia.Rect.MakeXYWH(x - r, y - r, 2 * r, 2 * r)
    path = skia.Path(); path.addArc(rect, a0, sweep)
    c.drawPath(path, paint(color, alpha, stroke=width))


def curve(c, pts, color, width, alpha=1.0, dash=None):
    path = skia.Path(); path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    p = paint(color, alpha, stroke=width)
    if dash:
        p.setPathEffect(skia.DashPathEffect.Make(dash, 0))
    c.drawPath(path, p)


def bezier(c, p0, p1, p2, color, width, alpha=1.0, upto=1.0, dash=None):
    """quadratic curve from p0 to p2 via control p1, drawn up to fraction `upto`"""
    n = max(2, int(40 * upto))
    pts = []
    for i in range(n + 1):
        u = upto * i / n
        pts.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
    curve(c, pts, color, width, alpha, dash)
    return pts[-1]


def qpoint(p0, p1, p2, u):
    return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1])


# ---------------------------------------------------------------- backgrounds
class Sky:
    """layered night sky: gradient, drifting nebulae, three parallax star layers"""
    def __init__(self, seed=1, top=NIGHT0, bottom=NIGHT2, nebulae=(VIOLET, ROSE, CYAN), stars=420, horizon=None):
        rng = np.random.default_rng(seed)
        self.top, self.bottom, self.horizon = top, bottom, horizon
        self.neb = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(380, 720), nebulae[i % len(nebulae)], rng.uniform(0, 6.28), rng.uniform(0.06, 0.14))
                    for i in range(5)]
        self.layers = []
        for depth, n, rmax in ((0.15, int(stars * 0.6), 1.6), (0.35, int(stars * 0.3), 2.3), (0.7, int(stars * 0.1), 3.2)):
            xs, ys = rng.uniform(-200, W + 200, n), rng.uniform(-200, H + 200, n)
            rs, ph = rng.uniform(0.6, rmax, n), rng.uniform(0, 6.28, n)
            sp = rng.uniform(0.6, 2.2, n)
            self.layers.append((depth, xs, ys, rs, ph, sp))

    def draw(self, c, t, cam=(0, 0), alpha=1.0, star_alpha=1.0):
        g = skia.GradientShader.MakeLinear([(0, 0), (0, H)], [col(self.top), col(self.bottom)])
        c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=g))
        for x, y, r, colr, ph, a in self.neb:
            glow(c, x + 40 * math.sin(t * 0.05 + ph) - cam[0] * 0.05, y + 30 * math.cos(t * 0.04 + ph) - cam[1] * 0.05, r, colr, a * alpha)
        for depth, xs, ys, rs, ph, sp in self.layers:
            ox = (-cam[0] * depth + t * 6 * depth) % (W + 400)
            oy = -cam[1] * depth
            tw = 0.55 + 0.45 * np.sin(t * sp + ph)
            px = (xs + ox) % (W + 400) - 200
            py = ys + oy
            for i in range(0, len(xs)):
                a = tw[i] * star_alpha
                if a < 0.05:
                    continue
                c.drawCircle(float(px[i]), float(py[i]), float(rs[i]), paint(INK, a * 0.9))
                if rs[i] > 2.4:
                    glow(c, float(px[i]), float(py[i]), float(rs[i]) * 6, LILAC, a * 0.35)
        if self.horizon:
            g = skia.GradientShader.MakeLinear([(0, H * 0.55), (0, H)], [col(self.horizon, 0), col(self.horizon, 0.55)])
            c.drawRect(skia.Rect(0, H * 0.55, W, H), skia.Paint(Shader=g))


@functools.lru_cache(None)
def _grain(i):
    rng = np.random.default_rng(100 + i)
    n = rng.normal(128, 40, (512, 512)).clip(0, 255).astype(np.uint8)
    rgba = np.dstack([n, n, n, np.full_like(n, 255)])
    return skia.Image.fromarray(rgba, colorType=skia.ColorType.kRGBA_8888_ColorType)


def grain(c, t, fps=60, amount=0.045):
    # a static texture: animated grain is incompressible and YouTube would smear it anyway
    img = _grain(0)
    sh = img.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat)
    p = skia.Paint(Shader=sh, BlendMode=skia.BlendMode.kOverlay)
    p.setAlphaf(amount * 4)
    c.drawRect(skia.Rect(0, 0, W, H), p)


def vignette(c, amount=0.55):
    p = skia.Paint(Shader=skia.GradientShader.MakeRadial((W / 2, H / 2), W * 0.72, [col("#000000", 0), col("#000000", 0), col("#05031A", amount)], [0, 0.55, 1.0]))
    c.drawRect(skia.Rect(0, 0, W, H), p)


# ---------------------------------------------------------------- scene base
class Scene:
    ID = ""
    CHAPTER = ""
    NUMBER = ""

    def __init__(self):
        self.tm = timing_for(self.ID)
        self.dur = self.tm.total
        self.cues = []
        self.setup()

    # timing
    def b(self, i, f=0.0):
        return self.tm.starts[i] + f * self.tm.durs[i]

    def d(self, i, f=1.0):
        return f * self.tm.durs[i]

    def P(self, t, i, f0, f1, ease=io):
        """progress through beat i between fractions f0 and f1"""
        return prog(t, self.b(i, f0), self.d(i, f1 - f0), ease)

    def sfx(self, at, kind, gain=1.0):
        self.cues.append((round(at, 3), kind, gain))

    def setup(self):
        pass

    def draw(self, c, t):
        raise NotImplementedError

    def camera(self, t):
        """(cx, cy, zoom): the point at the centre of the frame, and the zoom"""
        return (W / 2, H / 2, 1.0)

    def frame(self, c, t):
        cx, cy, z = self.camera(t)
        breathe = 1.0 + 0.012 * (t / max(1.0, self.dur))
        self.background(c, t, (cx, cy))
        c.save()
        c.translate(W / 2, H / 2); c.scale(z * breathe, z * breathe); c.translate(-cx, -cy)
        self.draw(c, t)
        c.restore()
        self.overlay(c, t)
        grain(c, t)
        vignette(c)
        if self.CHAPTER:
            self.chapter_tag(c, t)
        fin = clamp(t / 0.45)
        fout = clamp((self.dur - t) / 0.55)
        a = 1 - min(fin, fout)
        if a > 0.002:
            c.drawRect(skia.Rect(0, 0, W, H), paint("#05031A", a))

    STAR_ALPHA = 0.6

    def background(self, c, t, cam):
        """screen-space layer drawn below the camera (the sky never zooms)"""
        sky = getattr(self, "sky", None)
        if sky is not None:
            sky.draw(c, t, cam=(cam[0] - W / 2, cam[1] - H / 2), star_alpha=self.STAR_ALPHA)

    def overlay(self, c, t):
        """screen-space layer drawn above the camera (labels that must not move)"""
        pass

    def chapter_tag(self, c, t):
        a = prog(t, 0.5, 0.8) * (1 - prog(t, self.dur - 1.2, 0.6))
        if a <= 0:
            return
        x, y = 70, 70
        circle(c, x, y, 25, GOLD, 0.95 * a)
        text(c, self.NUMBER, x, y + 1, 26, NIGHT0, "bold", alpha=a)
        text(c, self.CHAPTER, x + 44, y + 1, 30, INK, "display", "left", alpha=0.85 * a, shadow=1)
