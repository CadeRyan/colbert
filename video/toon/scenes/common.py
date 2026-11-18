"""Shared layout and data for the scenes."""
import json, math, os
import numpy as np
from ..core import *
from ..art import *
from film import facts as F

DATA = os.path.join(VIDEO, "data")


def load(name):
    return json.load(open(os.path.join(DATA, name)))


COVER_COL = {3: "#5B8DEF", 5: "#3DDCFF", 7: "#5BE3A5", 13: "#FFC93C", 19: "#FF6B6B", 37: "#9D7BFF", 73: "#FF4F9A"}


def _sev_positions():
    rng = np.random.default_rng(17)
    pos = {}
    ks = F.SEVENTEEN
    for i, k in enumerate(ks):
        x = 230 + i * (1460 / (len(ks) - 1))
        y = 300 + 110 * math.sin(i * 0.9) + rng.uniform(-40, 40)
        pos[k] = (x, y)
    return pos


SEV_POS = _sev_positions()
FIVE_POS = {k: (560 + i * 200, 330 - 70 * math.sin(math.pi * i / 4)) for i, k in enumerate(F.REMAINING_K)}


def hill(c, t, y_top=890, color="#241A5E", rim=VIOLET, cx=960, rx=1500, ry=560, alpha=1.0):
    cy = y_top + ry
    c.save(); c.translate(cx, cy); c.scale(rx, ry)
    c.drawCircle(0, 0, 1, paint(color, alpha))
    c.restore()
    arcpts = [(cx + rx * math.cos(a), cy - ry * math.sin(a)) for a in np.linspace(0.35, math.pi - 0.35, 60)]
    curve(c, arcpts, rim, 3, 0.35 * alpha)


def far_hills(c, t, camx=0.0, alpha=1.0):
    for k, (y, colr, amp, depth) in enumerate(((760, "#1E1652", 60, 0.2), (820, "#211858", 45, 0.4))):
        pts = [(x, y - amp * (0.5 + 0.5 * math.sin(x * 0.004 + k * 2))) for x in range(-2400, W + 3200, 40)]
        poly(c, [(-2400, H + 400)] + pts + [(W + 3200, H + 400)], colr, alpha)


def big_title(c, s, x, y, size, color=INK, alpha=1.0, glow_col=VIOLET):
    glow(c, x, y, size * 3.2, glow_col, 0.35 * alpha)
    text(c, s, x, y, size, color, "display", alpha=alpha, shadow=1.2)


def caption(c, s, y=985, alpha=1.0, size=34, color=INK):
    if alpha <= 0.003:
        return
    w = text_width(s, size, "body")
    rrect(c, W / 2 - w / 2 - 28, y - size * 0.85, w + 56, size * 1.7, size * 0.85, "#140F3A", 0.72 * alpha)
    text(c, s, W / 2, y, size, color, "body", alpha=alpha)


def counter_pill(c, label, value, x, y, alpha=1.0, color=GOLD, size=30, align="right"):
    if alpha <= 0.003:
        return
    lw = text_width(label, size * 0.8, "body")
    vw = text_width(value, size, "mono")
    w = lw + vw + size * 1.6
    x0 = x - w if align == "right" else (x - w / 2 if align == "center" else x)
    rrect(c, x0, y - size * 0.9, w, size * 1.8, size * 0.9, "#140F3A", 0.75 * alpha)
    text(c, label, x0 + size * 0.6, y, size * 0.8, SOFT, "body", "left", alpha)
    text(c, value, x0 + size * 0.6 + lw + size * 0.4, y, size, color, "mono", "left", alpha)
