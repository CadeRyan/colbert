"""Illustrated characters and props. Everything takes (canvas, x, y, size, ..., t)."""
import math
import numpy as np
import skia
from .core import *


def _blink(t, seed):
    """1 = open, 0 = closed; blinks every few seconds, offset per seed"""
    period = 3.1 + (seed % 7) * 0.37
    ph = (t + seed * 0.913) % period
    return 1.0 - pulse(ph, period - 0.16, 0.16)


def critter(c, x, y, r, color, t=0.0, label=None, seed=0, mood="happy", look=(0.0, 0.0), alpha=1.0,
            glowing=False, squash=1.0, label_color=None, label_scale=1.0, bob=True, eyes=True, label_face="bold"):
    """a round number-creature. mood: happy, calm, worried, sleepy, wow"""
    if alpha <= 0.003 or r <= 0.5:
        return
    by = y + (math.sin(t * 2.1 + seed) * r * 0.06 if bob else 0)
    sx, sy = 1 / math.sqrt(squash), squash
    soft_shadow(c, x, y + r * 1.02, r * 0.9, r * 0.22, 0.35 * alpha)
    if glowing:
        glow(c, x, by, r * 2.6, color, 0.55 * alpha * (0.85 + 0.15 * math.sin(t * 3 + seed)))
    c.save()
    c.translate(x, by + r); c.scale(sx, sy); c.translate(-x, -(by + r))
    body = skia.Path(); body.addCircle(x, by, r)
    c.save(); c.clipPath(body, doAntiAlias=True)
    c.drawCircle(x, by, r, paint(shade(color, -0.28), alpha))
    c.drawCircle(x - r * 0.1, by - r * 0.12, r * 0.97, paint(color, alpha))
    c.drawCircle(x - r * 0.42, by - r * 0.48, r * 0.22, paint("#FFFFFF", 0.22 * alpha))
    c.restore()
    if eyes:
        ey = by - (r * 0.28 if label else r * 0.12)
        es = r * (0.17 if label else 0.2)
        op = _blink(t, seed) if mood != "sleepy" else 0.12
        for sgn in (-1, 1):
            ex = x + sgn * r * 0.32
            c.save(); c.translate(ex, ey); c.scale(1, max(0.08, op))
            c.drawOval(skia.Rect(-es, -es * 1.15, es, es * 1.15), paint("#FFFFFF", alpha))
            px, py = look[0] * es * 0.45, look[1] * es * 0.45
            c.drawCircle(px, py + es * 0.1, es * 0.55, paint("#1A1240", alpha))
            c.drawCircle(px - es * 0.18, py - es * 0.15, es * 0.17, paint("#FFFFFF", alpha))
            c.restore()
        my = ey + es * 1.55
        if mood == "happy":
            arc(c, x, my - es * 0.55, es * 0.75, 25, 130, "#1A1240", r * 0.06, alpha)
        elif mood == "wow":
            c.drawOval(skia.Rect(x - es * 0.32, my - es * 0.2, x + es * 0.32, my + es * 0.45), paint("#1A1240", alpha))
        elif mood == "worried":
            arc(c, x, my + es * 0.35, es * 0.6, 205, 130, "#1A1240", r * 0.055, alpha)
        elif mood == "calm":
            line(c, x - es * 0.4, my, x + es * 0.4, my, "#1A1240", r * 0.05, alpha)
    if label is not None:
        s = str(label)
        size = r * 0.62 * label_scale
        w = text_width(s, size, label_face)
        if w > r * 1.55:
            size *= r * 1.55 / w
        text(c, s, x, by + (r * 0.32 if eyes else 0), size, label_color or "#1A1240", label_face, alpha=alpha)
    c.restore()


def cracked(c, x, y, r, color, u, factors, t, seed=0, alpha=1.0, fcolor=None):
    """a composite critter splitting into its factor critters as u goes 0 -> 1"""
    if u < 0.35:
        critter(c, x, y, r, color, t, label=None, seed=seed, mood="worried", alpha=alpha, squash=1 - 0.1 * pulse(u, 0, 0.35))
        if u > 0.12:
            k = (u - 0.12) / 0.23
            curve(c, [(x - r * 0.1, y - r * 0.9), (x + r * 0.08, y - r * 0.35), (x - r * 0.06, y + r * 0.1), (x + r * 0.1, y + r * 0.6)][:2 + int(k * 2)], "#1A1240", r * 0.06, alpha)
        return
    k = out((u - 0.35) / 0.65)
    n = len(factors)
    for i, f in enumerate(factors):
        ang = math.pi + (i + 0.5) * math.pi / n
        fr = r * (0.62 if n <= 2 else 0.52)
        spread = (i - (n - 1) / 2) * fr * 2.25
        fx = x + spread * k
        fy = y + r - fr - abs(spread) * 0.08 * k
        critter(c, fx, fy, fr, fcolor or color, t, label=f, seed=seed + i + 1, mood="calm", alpha=alpha)


def star(c, x, y, r, color=GOLD, t=0.0, lit=1.0, seed=0, alpha=1.0):
    """a star that is dark (lit=0) or blazing (lit=1)"""
    if alpha <= 0.003:
        return
    tw = 0.85 + 0.15 * math.sin(t * 2.3 + seed * 1.7)
    if lit > 0.01:
        glow(c, x, y, r * 7 * lit * tw, color, 0.5 * alpha * lit)
        L = r * (2.6 + 0.8 * tw) * lit
        for ang in (0, 90):
            c.save(); c.translate(x, y); c.rotate(ang + 8 * math.sin(t * 0.5 + seed))
            poly(c, [(-L, 0), (0, -r * 0.28), (L, 0), (0, r * 0.28)], "#FFFFFF", 0.8 * alpha * lit)
            c.restore()
    core = mix(SLATE, color, lit)
    c.drawCircle(x, y, r, paint(core, alpha))
    if lit < 0.99:
        ring(c, x, y, r * 1.05, CORAL, max(1.0, r * 0.12), alpha * (1 - lit) * 0.8)
    if lit > 0.01:
        c.drawCircle(x, y, r * 0.55, paint("#FFFFFF", 0.85 * alpha * lit))


def burst(c, x, y, u, color=GOLD, n=10, R=80, alpha=1.0, seed=0):
    """celebration sparkle burst, u in [0, 1]"""
    if u <= 0 or u >= 1:
        return
    k = out(u)
    for i in range(n):
        ang = i * 2 * math.pi / n + seed
        d = R * k
        px, py = x + math.cos(ang) * d, y + math.sin(ang) * d
        s = (1 - u) * R * 0.09
        c.save(); c.translate(px, py); c.rotate(math.degrees(ang) + 45)
        poly(c, [(-s, 0), (0, -s * 0.35), (s, 0), (0, s * 0.35)], color, alpha * (1 - u))
        c.restore()
    ring(c, x, y, R * 0.7 * k, color, 3 * (1 - u), alpha * (1 - u) * 0.6)


def gear(c, x, y, r, teeth, angle, color, alpha=1.0, hole=0.35):
    path = skia.Path()
    n = teeth * 2
    for i in range(n * 2 + 1):
        a = math.radians(angle) + i * math.pi / n
        rr = r if (i // 2) % 2 == 0 else r * 0.8
        px, py = x + rr * math.cos(a), y + rr * math.sin(a)
        path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
    path.close()
    c.drawPath(path, paint(color, alpha))
    c.drawCircle(x, y, r * 0.62, paint(shade(color, 0.15), alpha))
    c.drawCircle(x, y, r * hole * 0.6, paint(shade(color, -0.4), alpha))


def clock(c, x, y, R, n, t=0.0, labels=None, hand=None, lit=None, locked=None, face=CREAM, alpha=1.0, num_size=None, rim=VIOLET, dim=None):
    """a friendly clock with n hours (0 at the top). lit: {hour: colour}. hand: hour (float)."""
    soft_shadow(c, x, y + R * 1.05, R * 0.9, R * 0.15, 0.4 * alpha)
    c.drawCircle(x, y, R * 1.08, paint(shade(rim, -0.25), alpha))
    c.drawCircle(x, y, R * 1.04, paint(rim, alpha))
    c.drawCircle(x, y, R, paint(face, alpha))
    c.drawCircle(x - R * 0.05, y - R * 0.06, R * 0.93, paint(shade(face, 0.3), alpha * 0.6))
    ns = num_size or R * 0.2
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        px, py = x + math.cos(a) * R * 0.76, y + math.sin(a) * R * 0.76
        lab = labels[i] if labels else str(i)
        if lit and i in lit:
            glow(c, px, py, ns * 1.6, lit[i], 0.7 * alpha)
            c.drawCircle(px, py, ns * 0.78, paint(lit[i], alpha))
            text(c, lab, px, py, ns, "#1A1240", "bold", alpha=alpha)
        else:
            a2 = alpha * (0.35 if dim and i in dim else 1.0)
            text(c, lab, px, py, ns, "#3B2E7A", "bold", alpha=a2)
        if locked and i in locked:
            padlock(c, px + ns * 0.75, py - ns * 0.6, ns * 0.5, CORAL, alpha * locked[i])
        tx1, ty1 = x + math.cos(a) * R * 0.93, y + math.sin(a) * R * 0.93
        tx2, ty2 = x + math.cos(a) * R * 0.98, y + math.sin(a) * R * 0.98
        line(c, tx1, ty1, tx2, ty2, "#3B2E7A", R * 0.02, alpha * 0.5)
    if hand is not None:
        a = -math.pi / 2 + hand * 2 * math.pi / n
        line(c, x, y, x + math.cos(a) * R * 0.58, y + math.sin(a) * R * 0.58, CORAL, R * 0.06, alpha)
        c.drawCircle(x, y, R * 0.07, paint(CORAL, alpha))
        c.drawCircle(x, y, R * 0.03, paint(CREAM, alpha))


def clock_pos(x, y, R, n, i, k=0.76):
    a = -math.pi / 2 + i * 2 * math.pi / n
    return x + math.cos(a) * R * k, y + math.sin(a) * R * k


def padlock(c, x, y, s, color=CORAL, alpha=1.0):
    if alpha <= 0.003:
        return
    arc(c, x, y - s * 0.35, s * 0.42, 180, 180, shade(color, -0.2), s * 0.16, alpha)
    rrect(c, x - s * 0.55, y - s * 0.35, s * 1.1, s * 0.9, s * 0.18, color, alpha)
    c.drawCircle(x, y + s * 0.05, s * 0.13, paint("#1A1240", alpha))


def label_tag(c, s, x, y, size=30, color=INK, bg=SLATE, alpha=1.0, face="display", pad=0.55):
    w = text_width(s, size, face)
    rrect(c, x - w / 2 - size * pad, y - size * 0.8, w + 2 * size * pad, size * 1.6, size * 0.8, bg, alpha * 0.92)
    text(c, s, x, y, size, color, face, alpha=alpha)


def speech(c, x, y, w, h, alpha=1.0, color=CREAM, tail=(-0.3, 1)):
    if alpha <= 0.003:
        return
    soft_shadow(c, x, y + h * 0.6, w * 0.5, h * 0.12, 0.3 * alpha)
    rrect(c, x - w / 2, y - h / 2, w, h, h * 0.25, color, alpha)
    tx = x + tail[0] * w / 2
    poly(c, [(tx - 20, y + h / 2 - 2), (tx + 24, y + h / 2 - 2), (tx - 30, y + h / 2 + 38)], color, alpha)


def machine(c, x, y, s, t, run=0.0, color=VIOLET, light=None, alpha=1.0, label=None):
    """a squaring machine: body, funnel, gears, chute. (x, y) = centre of body; s = body width"""
    w, h = s, s * 0.72
    soft_shadow(c, x, y + h * 0.62, w * 0.6, h * 0.1, 0.45 * alpha)
    poly(c, [(x - w * 0.22, y - h * 0.5), (x - w * 0.32, y - h * 0.82), (x + w * 0.02, y - h * 0.82), (x - w * 0.06, y - h * 0.5)], shade(color, -0.15), alpha)
    rrect(c, x - w / 2, y - h / 2, w, h, s * 0.08, color, alpha)
    rrect(c, x - w / 2, y - h / 2, w, h * 0.18, s * 0.08, shade(color, 0.18), alpha)
    rrect(c, x + w * 0.42, y + h * 0.12, w * 0.22, h * 0.16, s * 0.03, shade(color, -0.25), alpha)
    ang = t * 90 * run
    gear(c, x - w * 0.18, y + h * 0.08, s * 0.14, 9, ang, shade(color, 0.35), alpha)
    gear(c, x + w * 0.1, y + h * 0.13, s * 0.1, 7, -ang * 1.3 + 12, shade(color, 0.25), alpha)
    gear(c, x + w * 0.27, y - h * 0.08, s * 0.07, 6, ang * 1.8, shade(color, 0.45), alpha)
    lc = light or (MINT if run > 0.1 else DIM)
    glow(c, x + w * 0.36, y - h * 0.32, s * 0.12, lc, 0.6 * alpha * (0.6 + 0.4 * math.sin(t * 8 * max(run, 0.2))))
    c.drawCircle(x + w * 0.36, y - h * 0.32, s * 0.035, paint(lc, alpha))
    if label:
        text(c, label, x - w * 0.05, y - h * 0.32, s * 0.08, "#1A1240", "bold", alpha=alpha * 0.85)


def planet(c, x, y, R, t, rot=0.0, alpha=1.0, seed=4):
    glow(c, x, y, R * 1.5, CYAN, 0.35 * alpha)
    body = skia.Path(); body.addCircle(x, y, R)
    c.save(); c.clipPath(body, doAntiAlias=True)
    c.drawCircle(x, y, R, paint("#2A6FDB", alpha))
    rng = np.random.default_rng(seed)
    for i in range(9):
        ang = rng.uniform(0, 6.28) + rot
        dist = rng.uniform(0.1, 0.85) * R
        cx = x + math.cos(ang) * dist
        cy = y + math.sin(ang) * dist * 0.8
        rr = rng.uniform(0.18, 0.4) * R
        c.drawOval(skia.Rect(cx - rr, cy - rr * 0.6, cx + rr, cy + rr * 0.6), paint(MINT, 0.85 * alpha))
    c.drawCircle(x + R * 0.35, y + R * 0.4, R * 1.05, paint("#05031A", 0.25 * alpha))
    c.drawCircle(x - R * 0.35, y - R * 0.4, R * 0.5, paint("#FFFFFF", 0.08 * alpha))
    c.restore()


def house(c, x, y, s, t, ang=0.0, lit=1.0, color=CORAL, seed=0, alpha=1.0, computer=True):
    """a little house standing on a surface; (x, y) = base centre; rotated by ang degrees"""
    c.save(); c.translate(x, y); c.rotate(ang)
    rrect(c, -s * 0.5, -s * 0.7, s, s * 0.7, s * 0.06, color, alpha)
    poly(c, [(-s * 0.62, -s * 0.66), (0, -s * 1.15), (s * 0.62, -s * 0.66)], shade(color, -0.3), alpha)
    flick = 0.8 + 0.2 * math.sin(t * 5 + seed * 2.1)
    wc = mix("#2A1E5C", GOLD, lit * flick)
    rrect(c, -s * 0.28, -s * 0.52, s * 0.3, s * 0.26, s * 0.04, wc, alpha)
    if computer and lit > 0.05:
        glow(c, -s * 0.13, -s * 0.39, s * 0.6, GOLD, 0.35 * lit * alpha)
    rrect(c, s * 0.12, -s * 0.42, s * 0.22, s * 0.42, s * 0.03, shade(color, -0.45), alpha)
    c.restore()


def tower(c, x, y, h, t, color=TEAL, alpha=1.0, broken=0.0, label=None):
    """an antenna tower standing at (x, y)"""
    if alpha <= 0.003:
        return
    w = h * 0.32
    c.save()
    if broken > 0:
        c.translate(x, y); c.rotate(28 * broken); c.translate(-x, -y)
        alpha *= 1 - broken * 0.6
    for side in (-1, 1):
        line(c, x + side * w / 2, y, x + side * w * 0.12, y - h, shade(color, -0.1), h * 0.05, alpha)
    for k in range(1, 5):
        yy = y - h * k / 5
        ww = w / 2 - (w / 2 - w * 0.12) * k / 5
        line(c, x - ww, yy, x + ww, yy, shade(color, 0.1), h * 0.03, alpha)
    blink = 0.5 + 0.5 * math.sin(t * 4)
    glow(c, x, y - h * 1.04, h * 0.35, CORAL if broken else color, 0.7 * alpha * blink)
    c.drawCircle(x, y - h * 1.04, h * 0.05, paint(CORAL if broken else INK, alpha))
    c.restore()
    if label:
        label_tag(c, label, x, y + h * 0.2, h * 0.14, INK, SLATE, alpha)


def beam(c, x1, y1, x2, y2, t, color=GOLD, alpha=1.0, width=4, upto=1.0, speed=1.0, seed=0):
    if alpha <= 0.003 or upto <= 0:
        return
    xe, ye = x1 + (x2 - x1) * upto, y1 + (y2 - y1) * upto
    line(c, x1, y1, xe, ye, color, width * 3, alpha * 0.18)
    line(c, x1, y1, xe, ye, color, width, alpha * 0.6)
    u = (t * 0.8 * speed + seed * 0.31) % 1.0
    if u <= upto:
        px, py = x1 + (x2 - x1) * u, y1 + (y2 - y1) * u
        glow(c, px, py, width * 6, color, alpha * 0.9)


def book(c, x, y, w, h, color, alpha=1.0, title=None):
    rrect(c, x - w / 2, y - h, w, h, w * 0.12, color, alpha)
    rrect(c, x - w / 2, y - h, w * 0.18, h, w * 0.06, shade(color, -0.25), alpha)
    for k in (0.2, 0.8):
        line(c, x - w * 0.25, y - h * k, x + w * 0.4, y - h * k, shade(color, 0.35), w * 0.06, alpha)
    if title:
        c.save(); c.translate(x + w * 0.08, y - h / 2); c.rotate(-90)
        text(c, title, 0, 0, w * 0.32, shade(color, 0.6), "bold", alpha=alpha)
        c.restore()


def person(c, x, y, h, color=LILAC, alpha=1.0):
    """a simple figure for scale; (x, y) = feet"""
    c.drawCircle(x, y - h * 0.86, h * 0.12, paint(color, alpha))
    rrect(c, x - h * 0.13, y - h * 0.72, h * 0.26, h * 0.42, h * 0.1, color, alpha)
    line(c, x - h * 0.06, y - h * 0.32, x - h * 0.08, y, color, h * 0.08, alpha)
    line(c, x + h * 0.06, y - h * 0.32, x + h * 0.08, y, color, h * 0.08, alpha)


def hourglass(c, x, y, h, fill, t, color=CREAM, sand=GOLD, alpha=1.0):
    w = h * 0.55
    rrect(c, x - w * 0.6, y - h / 2 - h * 0.06, w * 1.2, h * 0.08, h * 0.03, WOOD, alpha)
    rrect(c, x - w * 0.6, y + h / 2 - h * 0.02, w * 1.2, h * 0.08, h * 0.03, WOOD, alpha)
    top = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w * 0.06, y), (x - w * 0.06, y)]
    bot = [(x - w * 0.06, y), (x + w * 0.06, y), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)]
    poly(c, top, color, alpha * 0.35); poly(c, bot, color, alpha * 0.35)
    ft = 1 - fill
    if ft > 0.02:
        yy = y - h / 2 * ft
        ww = w * 0.06 + (w / 2 - w * 0.06) * ft
        poly(c, [(x - ww, yy), (x + ww, yy), (x + w * 0.06, y), (x - w * 0.06, y)], sand, alpha)
    if fill > 0.02:
        yy = y + h / 2 - h / 2 * fill * 0.9
        poly(c, [(x - w / 2, y + h / 2), (x + w / 2, y + h / 2), (x + w * 0.2, yy), (x - w * 0.2, yy)], sand, alpha)
    if 0.02 < fill < 0.98:
        line(c, x, y, x, y + h / 2 - h / 2 * fill * 0.9, sand, h * 0.015, alpha)
    poly(c, top, INK, alpha * 0.5, stroke=h * 0.012); poly(c, bot, INK, alpha * 0.5, stroke=h * 0.012)


def prism(c, x, y, s, alpha=1.0, color=LILAC):
    pts = [(x, y - s * 0.6), (x + s * 0.55, y + s * 0.4), (x - s * 0.55, y + s * 0.4)]
    glow(c, x, y, s * 1.1, color, 0.25 * alpha)
    poly(c, pts, color, 0.35 * alpha)
    poly(c, pts, "#FFFFFF", 0.7 * alpha, stroke=s * 0.03)
    poly(c, [(x, y - s * 0.6), (x + s * 0.18, y + s * 0.4), (x - s * 0.1, y + s * 0.4)], "#FFFFFF", 0.12 * alpha)


RAINBOW = ["#FF5D73", "#FF9F1C", "#FFD23F", "#5BE3A5", "#3DDCFF", "#5B8DEF", "#9D7BFF", "#FF4F9A", "#FF5D73"]


def truck(c, x, y, s, crates, t, color=CORAL, crate=GOLD, alpha=1.0, max_cols=8):
    """side-view truck; (x, y) = ground under the middle; crates stacked in the bed"""
    bounce = math.sin(t * 12) * s * 0.01
    yy = y + bounce
    for wx in (-0.38, 0.12, 0.42):
        c.drawCircle(x + wx * s, y - s * 0.07, s * 0.075, paint("#1A1240", alpha))
        c.drawCircle(x + wx * s, y - s * 0.07, s * 0.035, paint(SOFT, alpha))
    rrect(c, x - s * 0.5, yy - s * 0.2, s * 0.74, s * 0.08, s * 0.02, shade(color, -0.2), alpha)
    rrect(c, x + s * 0.26, yy - s * 0.36, s * 0.26, s * 0.25, s * 0.05, color, alpha)
    rrect(c, x + s * 0.33, yy - s * 0.33, s * 0.14, s * 0.1, s * 0.02, CYAN, alpha * 0.8)
    cw = s * 0.09
    for i in range(crates):
        col_, row = i % max_cols, i // max_cols
        cx = x - s * 0.47 + col_ * cw * 0.98
        cy = yy - s * 0.2 - (row + 1) * cw * 0.98
        rrect(c, cx, cy, cw * 0.92, cw * 0.92, cw * 0.15, crate if (i + row) % 2 else shade(crate, -0.12), alpha)


def rocket(c, x, y, s, t, color=CORAL, alpha=1.0, flame=1.0, angle=0.0):
    c.save(); c.translate(x, y); c.rotate(angle)
    if flame > 0:
        fl = s * (0.35 + 0.1 * math.sin(t * 30))
        glow(c, -s * 0.55 - fl * 0.5, 0, fl * 1.5, AMBER, 0.6 * alpha * flame)
        poly(c, [(-s * 0.5, -s * 0.12), (-s * 0.5 - fl, 0), (-s * 0.5, s * 0.12)], GOLD, alpha * flame)
    c.drawOval(skia.Rect(-s * 0.55, -s * 0.18, s * 0.45, s * 0.18), paint(CREAM, alpha))
    poly(c, [(s * 0.3, -s * 0.16), (s * 0.62, 0), (s * 0.3, s * 0.16)], color, alpha)
    poly(c, [(-s * 0.45, -s * 0.15), (-s * 0.6, -s * 0.34), (-s * 0.2, -s * 0.15)], color, alpha)
    poly(c, [(-s * 0.45, s * 0.15), (-s * 0.6, s * 0.34), (-s * 0.2, s * 0.15)], color, alpha)
    c.drawCircle(s * 0.08, 0, s * 0.08, paint(CYAN, alpha))
    c.restore()


def tank(c, x, y, w, h, level, mark, t, color=CYAN, alpha=1.0):
    """a glass tank; level and mark in [0, 1]"""
    rrect(c, x - w / 2, y - h, w, h, w * 0.08, "#FFFFFF", 0.08 * alpha)
    lh = h * level
    wave = [(x - w / 2 + 6 + i * (w - 12) / 30, y - lh + math.sin(t * 2.5 + i * 0.6) * 4) for i in range(31)]
    poly(c, [(x - w / 2 + 6, y - 6)] + wave + [(x + w / 2 - 6, y - 6)], color, 0.75 * alpha)
    rrect(c, x - w / 2, y - h, w, h, w * 0.08, INK, 0.8 * alpha, stroke=4)
    yy = y - h * mark
    curve(c, [(x - w / 2 - 30, yy), (x + w / 2 + 30, yy)], CORAL, 4, alpha, dash=[14, 10])


def hiker(c, x, y, s, t, color=GOLD, walking=True, alpha=1.0, seed=0, trip=0.0):
    """a small walking critter (legs swing)"""
    ph = t * 9 + seed if walking else 0
    for k, sgn in ((0, 1), (1, -1)):
        a = math.sin(ph) * 0.5 * sgn
        line(c, x + (k - 0.5) * s * 0.3, y - s * 0.3, x + (k - 0.5) * s * 0.3 + math.sin(a) * s * 0.35, y, shade(color, -0.35), s * 0.1, alpha)
    critter(c, x, y - s * 0.65, s * 0.42, color, t, seed=seed, mood="wow" if trip > 0.3 else "happy", alpha=alpha, bob=walking, squash=1 - 0.15 * trip)


def flag(c, x, y, h, color=MINT, alpha=1.0, t=0.0):
    line(c, x, y, x, y - h, INK, h * 0.04, alpha)
    wv = math.sin(t * 4) * h * 0.04
    poly(c, [(x, y - h), (x + h * 0.45, y - h * 0.86 + wv), (x, y - h * 0.7)], color, alpha)


def calculator(c, x, y, w, t, alpha=1.0, sweat=1.0):
    h = w * 1.35
    soft_shadow(c, x, y + h * 0.55, w * 0.55, w * 0.08, 0.4 * alpha)
    rrect(c, x - w / 2, y - h / 2, w, h, w * 0.12, "#4B3F9E", alpha)
    rrect(c, x - w * 0.42, y - h * 0.42, w * 0.84, h * 0.3, w * 0.06, "#BFE3C9", alpha)
    for r_ in range(3):
        for c_ in range(3):
            rrect(c, x - w * 0.38 + c_ * w * 0.27, y + r_ * h * 0.14 - h * 0.04, w * 0.2, h * 0.1, w * 0.04, shade("#4B3F9E", 0.25), alpha)
    if sweat > 0:
        dy = (t * 40) % 60
        c.drawOval(skia.Rect(x + w * 0.52, y - h * 0.4 + dy, x + w * 0.6, y - h * 0.28 + dy), paint(CYAN, alpha * sweat * (1 - dy / 60)))


def grid_dots(c, x0, y0, n, step, t, colorf, rf, alpha=1.0):
    """an n x n lattice; colorf(i, j) -> colour or None; rf(i, j) -> radius. (i: column, j: row from bottom)"""
    for i in range(n):
        for j in range(n):
            colr = colorf(i, j)
            if colr is None:
                continue
            x, y = x0 + i * step, y0 - j * step
            r = rf(i, j)
            c.drawCircle(x, y, r, paint(colr, alpha))
