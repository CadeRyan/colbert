"""11–13: the key observation, and why a root always exists."""
from .common import *
import skia

Q = 7


def pmul(a, b):
    return ((a[0] * b[0] - a[1] * b[1]) % Q, (a[0] * b[1] + a[1] * b[0]) % Q)


def powers(h, n):
    out = [(1, 0)]
    for _ in range(n):
        out.append(pmul(out[-1], h))
    return out


H31 = (3, 1)
PATH = powers(H31, 8)                     # (1,0) (3,1) (1,6) (4,5) (0,5) (2,1) (5,5) (3,6) (3,0)
ROOTS = {1: (0, 1), 2: (1, 1), 3: (3, 1), 4: (0, 2), 5: (1, 2), 6: (2, 3)}   # each r with r^8 = c (mod 7)
assert all(powers(r, 8)[-1] == (c, 0) for c, r in ROOTS.items())
assert PATH[7] == (3, 6) and PATH[8] == (3, 0)

GX, GY, ST = 640, 905, 92


def gpos(i, j):
    return GX + i * ST, GY - j * ST


def lattice(c, t, alpha, rows=1.0, hl=None, dim_pairs=1.0):
    """the 7x7 world of pairs; bottom row = ordinary numbers"""
    if alpha <= 0:
        return
    for j in range(Q):
        ra = clamp(rows * Q - j) if j > 0 else 1.0
        for i in range(Q):
            x, y = gpos(i, j)
            if j == 0:
                critter(c, x, y, 30, GOLD, t, label=i, seed=i, mood="calm", alpha=alpha, eyes=False, bob=False)
            elif ra > 0:
                a = alpha * ra * dim_pairs
                glow(c, x, y, 26, VIOLET, 0.35 * a)
                c.drawCircle(x, y, 9, paint(LILAC, a))
    if hl:
        for (i, j), colr in hl.items():
            x, y = gpos(i, j)
            ring(c, x, y, 24, colr, 4, alpha)


def axes_labels(c, alpha):
    if alpha <= 0:
        return
    text(c, "ordinary numbers", GX + 3 * ST, GY + 70, 30, GOLD, "display", alpha=alpha)
    c.save(); c.translate(GX - 80, GY - 3.5 * ST); c.rotate(-90)
    text(c, "the  i  part", 0, 0, 30, LILAC, "display", alpha=alpha)
    c.restore()
    for j in range(1, Q):
        x, y = gpos(-0.55, j)
        text(c, str(j), x + 20, y, 22, DIM, "bold", alpha=alpha)


def pair_token(c, x, y, s, a, b, alpha=1.0, la="a", lb="b"):
    if alpha <= 0:
        return
    w, h = s * 2.2, s
    soft_shadow(c, x, y + h * 0.65, w * 0.5, h * 0.12, 0.35 * alpha)
    rrect(c, x - w / 2, y - h / 2, w / 2, h, h * 0.45, GOLD, alpha)
    rrect(c, x, y - h / 2, w / 2, h, h * 0.45, VIOLET, alpha)
    c.drawRect(skia.Rect(x - h * 0.45, y - h / 2, x, y + h / 2), paint(GOLD, alpha))
    c.drawRect(skia.Rect(x, y - h / 2, x + h * 0.45, y + h / 2), paint(VIOLET, alpha))
    text(c, la, x - w / 4, y, s * 0.55, "#1A1240", "bold", alpha=alpha)
    text(c, lb, x + w / 4, y, s * 0.55, "#FFFFFF", "bold", alpha=alpha)


def hopper(c, t, t0, step, alpha=1.0, upto=8, show_trail=True, seed=7, highlight=None):
    """the pair (3,1) multiplying itself: hops along PATH, one hop per `step` seconds"""
    k = (t - t0) / step
    if k < 0:
        x, y = gpos(*PATH[0])
        critter(c, x, y - 34, 26, VIOLET, t, seed=seed, mood="happy", alpha=alpha)
        return 0
    n = min(upto, int(k))
    frac = clamp(k - n) if n < upto else 1.0
    if show_trail:
        for m in range(1, n + 1):
            p0, p1 = gpos(*PATH[m - 1]), gpos(*PATH[m])
            ctrl = ((p0[0] + p1[0]) / 2, min(p0[1], p1[1]) - 80)
            bezier(c, p0, ctrl, p1, LILAC, 3, 0.35 * alpha, dash=[8, 8])
    if n < upto:
        p0, p1 = gpos(*PATH[n]), gpos(*PATH[n + 1])
        ctrl = ((p0[0] + p1[0]) / 2, min(p0[1], p1[1]) - 80)
        u = out(frac)
        x, y = qpoint(p0, ctrl, p1, u)
        squash = 1 + 0.15 * math.sin(math.pi * u)
    else:
        x, y = gpos(*PATH[upto]); squash = 1.0
    critter(c, x, y - 34, 26, VIOLET, t, seed=seed, mood="happy", alpha=alpha, squash=squash, bob=False)
    for m in range(1, n + 1):
        px, py = gpos(*PATH[m])
        colr = GOLD if (highlight and m in highlight) else LILAC
        text(c, str(m), px + 26, py - 26, 20, colr, "bold", alpha=alpha * 0.85)
    return n


# ======================================================================================
class PairWorld(Scene):
    ID = "11_pair_world"
    NUMBER, CHAPTER = "10", "A clock made of pairs"

    def setup(self):
        self.sky = Sky(seed=31, nebulae=(VIOLET, CYAN, ROSE))
        self.sfx(self.b(0, 0.05), "swell", 0.7)
        self.sfx(self.b(1, 0.1), "pop", 0.7)
        self.sfx(self.b(2, 0.1), "whoosh", 0.6)
        for j in range(1, 7):
            self.sfx(self.b(2, 0.35 + j * 0.06), "tick", 0.4)
        step = self.hop_step()
        for m in range(8):
            self.sfx(self.b(3, 0.12) + m * step + step * 0.5, "hop", 0.55)
        self.sfx(self.b(3, 0.12) + 8 * step, "chime", 0.9)

    def hop_step(self):
        return self.d(3, 0.62) / 8

    def draw(self, c, t):
        # b0: a clock with 2^61 - 1 hours
        if t < self.b(2, 0.25):
            fa = prog(t, self.b(0, 0.02), 0.6) * (1 - prog(t, self.b(2, 0.05), self.d(2, 0.2)))
            x, y, R = 560, 560, 330
            sh = prog(t, self.b(2, 0.05), self.d(2, 0.2))
            R *= 1 - 0.5 * sh
            soft_shadow(c, x, y + R * 1.05, R * 0.9, R * 0.15, 0.4 * fa)
            c.drawCircle(x, y, R * 1.06, paint(shade(VIOLET, -0.25), fa))
            c.drawCircle(x, y, R * 1.02, paint(VIOLET, fa))
            c.drawCircle(x, y, R, paint(CREAM, fa))
            for i in range(240):
                a = -math.pi / 2 + i * 2 * math.pi / 240
                line(c, x + math.cos(a) * R * 0.9, y + math.sin(a) * R * 0.9, x + math.cos(a) * R * 0.97, y + math.sin(a) * R * 0.97, "#3B2E7A", 2, fa * 0.6)
            text(c, "0", x, y - R * 0.74, R * 0.13, "#3B2E7A", "bold", alpha=fa)
            a = -math.pi / 2 + t * 2.5
            line(c, x, y, x + math.cos(a) * R * 0.65, y + math.sin(a) * R * 0.65, CORAL, R * 0.04, fa)
            c.drawCircle(x, y, R * 0.05, paint(CORAL, fa))
            ta = prog(t, self.b(0, 0.15), 0.6) * (1 - prog(t, self.b(2, 0.0), 0.5))
            rich(c, [("2", INK), ("^61", INK), (" − 1  hours", INK)], 1340, 400, 70, alpha=ta, face="display", shadow=1)
            text(c, "2,305,843,009,213,693,951", 1340, 490, 40, SOFT, "mono", alpha=ta)
            la = prog(t, self.b(0, 0.4), 0.6, back) * (1 - prog(t, self.b(2, 0.0), 0.5))
            if la > 0:
                c.save(); c.translate(1340, 590); c.scale(la, la)
                label_tag(c, "a Mersenne prime", 0, 0, 40, "#1A1240", GOLD, 1.0, "bold", 0.5)
                c.restore()
        # b1: pairs
        if self.b(1, 0.0) < t < self.b(2, 0.25):
            fa = prog(t, self.b(1, 0.05), 0.6) * (1 - prog(t, self.b(2, 0.05), self.d(2, 0.15)))
            pu = prog(t, self.b(1, 0.08), 0.7, back)
            c.save(); c.translate(1340, 760); c.scale(pu, pu)
            pair_token(c, 0, 0, 90, 0, 0, fa)
            c.restore()
            ia = prog(t, self.b(1, 0.45), 0.6)
            critter(c, 1240, 930, 34, VIOLET, t, label="i", seed=3, mood="happy", alpha=fa * ia)
            text(c, "×", 1300, 930, 40, SOFT, "display", alpha=fa * ia)
            critter(c, 1360, 930, 34, VIOLET, t, label="i", seed=4, mood="happy", alpha=fa * ia)
            text(c, "=  −1", 1460, 930, 44, INK, "display", alpha=fa * ia)
            ma = prog(t, self.b(1, 0.7), 0.6)
            text(c, "multiplied like complex numbers", 1340, 660, 32, SOFT, "body", alpha=fa * ma)
        # b2/b3: the 7-hour world of pairs
        if t > self.b(2, 0.1):
            fa = prog(t, self.b(2, 0.12), 0.6)
            rows = prog(t, self.b(2, 0.35), self.d(2, 0.45), lin)
            lattice(c, t, fa, rows)
            axes_labels(c, fa * prog(t, self.b(2, 0.6), 0.6))
            if t > self.b(3, 0.0):
                n = hopper(c, t, self.b(3, 0.12), self.hop_step(), prog(t, self.b(3, 0.02), 0.4))
                if n >= 8:
                    x, y = gpos(3, 0)
                    burst(c, x, y, prog(t, self.b(3, 0.12) + 8 * self.hop_step(), 1.0, lin), GOLD, 14, 160)
                    glow(c, x, y, 120, GOLD, 0.6 * pulse((t - self.b(3, 0.12) - 8 * self.hop_step()) % 2.0, 0, 2.0))

    def overlay(self, c, t):
        a = prog(t, self.b(2, 0.2), 0.6) * (1 - prog(t, self.b(3, 0.0), 0.4))
        if a > 0:
            text(c, "shrink it to", 1560, 380, 36, SOFT, "body", alpha=a)
            text(c, "7 hours", 1560, 450, 64, GOLD, "display", alpha=a, shadow=1)
            rich(c, [("7 = 2", INK), ("^3", INK), (" − 1", INK)], 1560, 540, 44, alpha=a, face="display")
            text(c, "also a Mersenne prime", 1560, 600, 30, SOFT, "body", alpha=a)
        a = prog(t, self.b(3, 0.02), 0.5)
        if a > 0:
            n = max(0, min(8, int((t - self.b(3, 0.12)) / self.hop_step()))) if t > self.b(3, 0.12) else 0
            label_tag(c, "multiply by  (3, 1)", 1560, 300, 38, INK, "#3A2C86", a)
            counter_pill(c, "hops:", str(n), 1560, 400, a, LILAC, 40, align="center")
            fa = prog(t, self.b(3, 0.12) + 8 * self.hop_step(), 0.6)
            if fa > 0:
                rich(c, [("(3, 1)", LILAC), ("^8", LILAC), ("  =  3", GOLD)], 1560, 540, 64, alpha=fa, face="display", shadow=1)
                text(c, "an eighth root of 3", 1560, 630, 36, INK, "display", alpha=fa)
                text(c, "whole numbers, nothing left over", 1560, 690, 30, SOFT, "body", alpha=fa)


# ======================================================================================
class WhyRoots(Scene):
    ID = "12_why_roots"
    NUMBER, CHAPTER = "11", "Why a root always exists"
    CX, CY, CR = 560, 580, 280

    def setup(self):
        self.sky = Sky(seed=33, nebulae=(VIOLET, CYAN, MINT))
        self.squares = [0, 1, 2, 4]
        self.sq_of = {0: 0, 1: 1, 2: 3, 4: 2}           # hour: a number whose square it is
        self.minus = [(3 - s) % Q for s in self.squares]  # 3, 2, 1, 6
        self.sfx(self.b(0, 0.1), "pop", 0.7)
        self.sfx(self.b(0, 0.35), "pop", 0.7)
        for i in range(4):
            self.sfx(self.b(1, 0.12 + i * 0.05) + 0.6, "tick", 0.5)
            self.sfx(self.b(1, 0.38 + i * 0.05) + 0.6, "tick" if self.minus[i] not in self.squares else "chime", 0.6)
        self.sfx(self.b(1, 0.8), "chime", 0.8)
        self.sfx(self.b(2, 0.3), "shimmer", 0.7)
        st = self.hop_step()
        for m in range(8):
            self.sfx(self.b(3, 0.1) + m * st + st * 0.5, "hop", 0.5)
        self.sfx(self.b(3, 0.1) + 7 * st, "chime", 0.7)
        self.sfx(self.b(3, 0.1) + 8 * st, "chime", 0.9)
        self.sfx(self.b(4, 0.1), "swell", 0.7)
        self.sfx(self.b(5, 0.1), "shimmer", 0.9)

    def hop_step(self):
        return self.d(3, 0.7) / 8

    def token(self, c, x, y, s, label, colr, alpha):
        critter(c, x, y, s, colr, 0, label=label, mood="calm", alpha=alpha, eyes=False, bob=False)

    def draw(self, c, t):
        # b0: two steps
        if t < self.b(1, 0.1):
            fa = 1 - prog(t, self.b(1, 0.0), self.d(1, 0.1))
            u1 = prog(t, self.b(0, 0.1), 0.6, back)
            u2 = prog(t, self.b(0, 0.35), 0.6, back)
            big_title(c, "Lucky?  No.", W / 2, 330, 96, INK, fa * prog(t, self.b(0, 0.02), 0.5))
            for k, (u, s) in enumerate(((u1, "1   every number is  pair × mirror"), (u2, "2   on a Mersenne clock, that's a power of two"))):
                c.save(); c.translate(W / 2, 560 + k * 130); c.scale(u, u)
                label_tag(c, s, 0, 0, 42, INK, "#3A2C86", fa)
                c.restore()
        # b1: step one, the pigeonhole: squares and (3 - squares) on a 7-hour clock
        if self.b(1, 0.0) < t < self.b(2, 0.15):
            fa = prog(t, self.b(1, 0.03), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.12)))
            clock(c, self.CX, self.CY, self.CR, 7, t, alpha=fa)
            for i, s in enumerate(self.squares):
                t0 = self.b(1, 0.12 + i * 0.05)
                u = prog(t, t0, 0.6, out)
                if u <= 0:
                    continue
                x1, y1 = clock_pos(self.CX, self.CY, self.CR, 7, s, 0.76)
                x0, y0 = 1250 + i * 130, 260
                x, y = lerp(x0, x1, u), lerp(y0, y1, u) - 120 * math.sin(math.pi * u)
                glow(c, x, y, 60, GOLD, 0.4 * fa)
                c.drawCircle(x, y, 30, paint(GOLD, fa))
                text(c, str(s), x, y, 30, "#1A1240", "bold", alpha=fa)
                if u >= 1:
                    px, py = clock_pos(self.CX, self.CY, self.CR, 7, s, 1.2)
                    text(c, f"{self.sq_of[s]}²", px, py, 28, GOLD, "display", alpha=fa)
            for i, m in enumerate(self.minus):
                t0 = self.b(1, 0.38 + i * 0.05)
                u = prog(t, t0, 0.6, out)
                if u <= 0:
                    continue
                x1, y1 = clock_pos(self.CX, self.CY, self.CR, 7, m, 0.76)
                x0, y0 = 1250 + i * 130, 470
                x, y = lerp(x0, x1, u), lerp(y0, y1, u) - 120 * math.sin(math.pi * u)
                ring(c, x, y, 40, CYAN, 7, fa)
                if u >= 1 and m in self.squares:
                    burst(c, x, y, prog(t, t0 + 0.6, 0.9, lin), CYAN, 10, 90, fa)
                    glow(c, x, y, 90, CYAN, 0.45 * fa)
        # b2: pair x mirror on the lattice
        if self.b(2, 0.05) < t < self.b(4, 0.1):
            fa = prog(t, self.b(2, 0.08), 0.6) * (1 - prog(t, self.b(4, 0.0), self.d(4, 0.1)))
            lattice(c, t, fa, 1.0, dim_pairs=0.6)
            axes_labels(c, fa * 0.7)
            if t < self.b(3, 0.05):
                ma = prog(t, self.b(2, 0.15), 0.6)
                y_m = GY - 3.5 * ST
                curve(c, [(GX - 40, y_m), (GX + 6 * ST + 40, y_m)], CYAN, 3, fa * ma * 0.8, dash=[14, 10])
                text(c, "mirror", GX + 6 * ST + 90, y_m, 28, CYAN, "display", alpha=fa * ma)
                p, q = gpos(3, 1), gpos(3, 6)
                critter(c, p[0], p[1] - 30, 26, VIOLET, t, label=None, seed=5, mood="happy", alpha=fa * ma)
                text(c, "(3, 1)", p[0] + 64, p[1] - 30, 26, LILAC, "display", "left", fa * ma)
                ru = prog(t, self.b(2, 0.25), 0.7, back)
                critter(c, q[0], q[1] - 30, 26 * ru, VIOLET, t, seed=6, mood="happy", alpha=fa * ma)
                text(c, "(3, −1) = (3, 6)", q[0] + 64, q[1] - 30, 26, LILAC, "display", "left", fa * ma * ru)
                pu = prog(t, self.b(2, 0.45), 0.8)
                if pu > 0:
                    dst = gpos(3, 0)
                    beam(c, p[0], p[1], dst[0], dst[1], t, GOLD, fa, 4, pu)
                    beam(c, q[0], q[1], dst[0], dst[1], t, GOLD, fa, 4, pu)
                    burst(c, dst[0], dst[1], prog(t, self.b(2, 0.45) + 0.8, 0.9, lin), GOLD, 12, 120, fa)
            else:
                st = self.hop_step()
                hopper(c, t, self.b(3, 0.1), st, fa, highlight={7, 8})
                m7 = prog(t, self.b(3, 0.1) + 7 * st, 0.5)
                if m7 > 0:
                    x, y = gpos(3, 6)
                    ring(c, x, y, 34 + 6 * math.sin(t * 5), CYAN, 4, fa * m7)
        # b4: the real clock
        if t > self.b(4, 0.0) and t < self.b(5, 0.15):
            fa = prog(t, self.b(4, 0.05), 0.6) * (1 - prog(t, self.b(5, 0.0), self.d(5, 0.12)))
            clock(c, 380, 560, 220, 12, t, labels=[""] * 12, hand=(t * 0.8) % 12, alpha=fa)
            rich(c, [("2", "#3B2E7A"), ("^61", "#3B2E7A"), (" − 1", "#3B2E7A")], 380, 660, 44, alpha=fa, face="display")
            lines = [
                ([("pair", LILAC), ("^2⁶¹", LILAC), ("  =  ", INK), ("−k·2", CORAL), ("^n", CORAL)], 0.12),
                ([("θ  =  pair", LILAC), ("^2⁴⁰", LILAC)], 0.42),
                ([("θ", GOLD), ("^2²¹", GOLD), ("  =  ", INK), ("−k·2", CORAL), ("^n", CORAL)], 0.62),
            ]
            for k, (runs, f0) in enumerate(lines):
                u = prog(t, self.b(4, f0), 0.6, back)
                if u <= 0:
                    continue
                c.save(); c.translate(1220, 330 + k * 170); c.scale(u, u)
                rich(c, runs, 0, 0, 72, alpha=fa, face="display", shadow=1)
                c.restore()
            la = prog(t, self.b(4, 0.75), 0.6)
            text(c, "2²¹ = 2,097,152:  θ is a two-millionth root", 1220, 830, 36, GOLD, "display", alpha=fa * la, shadow=1)
        # b5: every number has its root pair
        if t > self.b(5, 0.0):
            fa = prog(t, self.b(5, 0.05), 0.6)
            lattice(c, t, fa, 1.0, dim_pairs=0.45)
            axes_labels(c, fa * 0.6)
            for k, (cc, r) in enumerate(sorted(ROOTS.items())):
                u = prog(t, self.b(5, 0.15 + k * 0.08), 0.7)
                if u <= 0:
                    continue
                p, q = gpos(cc, 0), gpos(*r)
                beam(c, p[0], p[1] - 30, q[0], q[1], t, GOLD, fa, 3, u, seed=k)
                if u >= 1:
                    glow(c, q[0], q[1], 40, GOLD, 0.6 * fa)
                    c.drawCircle(q[0], q[1], 12, paint(GOLD, fa))

    def overlay(self, c, t):
        # step one text
        a = prog(t, self.b(1, 0.1), 0.5) * (1 - prog(t, self.b(2, 0.0), 0.4))
        if a > 0:
            text(c, "squares", 1450, 190, 34, GOLD, "display", alpha=a, shadow=1)
            text(c, "3 − each square", 1450, 400, 34, CYAN, "display", alpha=a * prog(t, self.b(1, 0.35), 0.5), shadow=1)
            u = prog(t, self.b(1, 0.62), 0.6)
            text(c, "4 + 4 hours won't fit on a 7-hour clock", 1450, 640, 34, INK, "display", alpha=a * u)
            text(c, "without sharing one", 1450, 690, 34, INK, "display", alpha=a * u)
            v = prog(t, self.b(1, 0.8), 0.6, back)
            if v > 0:
                c.save(); c.translate(1450, 830); c.scale(v, v)
                rrect(c, -330, -62, 660, 124, 62, "#140F3A", 0.85 * a)
                rich(c, [("3  =  3", INK), ("^2", INK), ("  +  1", INK), ("^2", INK)], 0, 4, 64, alpha=a, face="display")
                c.restore()
        a = prog(t, self.b(2, 0.2), 0.5) * (1 - prog(t, self.b(3, 0.0), 0.4))
        if a > 0:
            rich(c, [("a", GOLD), ("^2", GOLD), (" + b", LILAC), ("^2", LILAC)], 1560, 360, 64, alpha=a, face="display", shadow=1)
            text(c, "=", 1560, 440, 50, SOFT, "display", alpha=a)
            text(c, "pair × its mirror", 1560, 515, 52, INK, "display", alpha=a, shadow=1)
            text(c, "(3, 1) × (3, −1) = 9 + 1 = 3", 1560, 610, 32, SOFT, "body", alpha=a * prog(t, self.b(2, 0.45), 0.5))
        a = prog(t, self.b(3, 0.02), 0.5) * (1 - prog(t, self.b(4, 0.0), 0.4))
        if a > 0:
            st = self.hop_step()
            n = max(0, min(8, int((t - self.b(3, 0.1)) / st))) if t > self.b(3, 0.1) else 0
            counter_pill(c, "hops:", str(n), 1560, 300, a, LILAC, 40, align="center")
            u7 = prog(t, self.b(3, 0.1) + 7 * st, 0.5)
            rich(c, [("2", INK), ("^3", INK), (" − 1 = 7 hops", INK)], 1560, 430, 48, alpha=a * u7, face="display", shadow=1)
            text(c, "→ its mirror image", 1560, 495, 40, CYAN, "display", alpha=a * u7)
            u8 = prog(t, self.b(3, 0.1) + 8 * st, 0.5)
            rich(c, [("2", INK), ("^3", INK), (" = 8 hops", INK)], 1560, 630, 48, alpha=a * u8, face="display", shadow=1)
            text(c, "→ pair × mirror = 3", 1560, 695, 40, GOLD, "display", alpha=a * u8)
        a = prog(t, self.b(5, 0.1), 0.6)
        if a > 0:
            text(c, "every number has its root pair", 1560, 420, 44, INK, "display", alpha=a, shadow=1)
            text(c, "every k, every n", 1560, 500, 38, GOLD, "display", alpha=a * prog(t, self.b(5, 0.35), 0.5))
            text(c, "found in a fraction of a second", 1560, 580, 32, SOFT, "body", alpha=a * prog(t, self.b(5, 0.5), 0.5))
            text(c, "before the test begins", 1560, 625, 32, SOFT, "body", alpha=a * prog(t, self.b(5, 0.5), 0.5))


# ======================================================================================
def piece(c, x, y, w, h, colr, label, sub, alpha, knob=True, notch=True):
    soft_shadow(c, x, y + h * 0.6, w * 0.5, h * 0.1, 0.35 * alpha)
    rrect(c, x - w / 2, y - h / 2, w, h, 26, colr, alpha)
    if knob:
        c.drawCircle(x + w / 2 + 14, y, 34, paint(colr, alpha))
    if notch:
        c.drawCircle(x - w / 2 + 14, y, 34, paint(BG_PIECE, alpha))
    text(c, label, x, y - 18, 40, "#1A1240", "display", alpha=alpha)
    text(c, sub, x, y + 30, 26, shade(colr, -0.6), "body", alpha=alpha)


BG_PIECE = "#1C1550"


class TheFit(Scene):
    ID = "13_the_fit"
    NUMBER, CHAPTER = "12", "The pieces fit"

    def setup(self):
        self.sky = Sky(seed=35)
        for i in range(3):
            self.sfx(self.b(0, 0.1 + i * 0.12), "whoosh", 0.5)
        self.sfx(self.b(0, 0.55), "click", 0.9)
        self.sfx(self.b(0, 0.62), "swell", 0.8)
        for i in range(6):
            self.sfx(self.b(1, 0.1 + i * 0.07), "twinkle", 0.4)
        self.sfx(self.b(1, 0.62), "chime", 0.9)

    def draw(self, c, t):
        cx, cy = W / 2, 520
        fa0 = 1 - prog(t, self.b(1, 0.0), self.d(1, 0.15))
        if fa0 > 0:
            specs = [("no padding", "Percival's method", BLUE_ := "#5B8DEF", (-700, -300)),
                     ("exact", "clock arithmetic", MINT, (0, -420)),
                     ("fast", "whole numbers on GPUs", CYAN, (700, -300))]
            for i, (lab, sub, colr, (dx, dy)) in enumerate(specs):
                u = prog(t, self.b(0, 0.1 + i * 0.12), 0.8, out)
                x = cx + (i - 1) * 470 + dx * (1 - u) * 0.6
                y = cy - 40 + dy * (1 - u)
                piece(c, x, y, 420, 180, colr, lab, sub, fa0 * u, knob=i < 2, notch=i > 0)
            ku = prog(t, self.b(0, 0.45), 0.6, back)
            if ku > 0:
                c.save(); c.translate(cx, cy + 210); c.scale(ku, ku)
                glow(c, 0, 0, 260, GOLD, 0.5 * fa0)
                rrect(c, -420, -60, 840, 120, 60, GOLD, fa0)
                text(c, "the roots always exist", 0, 0, 46, "#1A1240", "display", alpha=fa0)
                c.restore()
            sa = prog(t, self.b(0, 0.62), 0.8)
            if sa > 0:
                glow(c, cx, cy + 40, 900, GOLD, 0.25 * sa * fa0)
                big_title(c, "colbert", cx, 170, 110, CYAN, sa * fa0, CYAN)
        # b1: who built what
        if t > self.b(1, 0.0):
            fa = prog(t, self.b(1, 0.05), 0.6)
            people = [("Crandall & Fagin", "weights, 1994"), ("Crandall", "pair arithmetic, 1999"), ("Percival", "any k, no padding, 2002"),
                      ("Woltman", "gwnum and the 1/k trick"), ("Gallot", "GPU transforms"), ("Gerbicz & Li", "error checking")]
            for i, (who, what) in enumerate(people):
                ang = -math.pi / 2 + (i + 0.5) * 2 * math.pi / 6
                x, y = cx + math.cos(ang) * 640, 540 + math.sin(ang) * 330
                u = prog(t, self.b(1, 0.1 + i * 0.07), 0.6, back)
                if u <= 0:
                    continue
                beam(c, x, y, cx, 540, t, LILAC, 0.5 * fa, 2, u, seed=i)
                star(c, x, y, 11 * u, LILAC, t, lit=1, seed=i, alpha=fa)
                text(c, who, x, y + 48, 34, INK, "display", alpha=fa * u, shadow=1)
                text(c, what, x, y + 90, 26, SOFT, "body", alpha=fa * u)
            star(c, cx, 540, 22, CYAN, t, lit=1, seed=9, alpha=fa)
            text(c, "colbert", cx, 610, 44, CYAN, "display", alpha=fa, shadow=1)
            nu = prog(t, self.b(1, 0.62), 0.7, back)
            if nu > 0:
                c.save(); c.translate(cx, 700); c.scale(nu, nu)
                label_tag(c, "new: the roots always exist", 0, 0, 36, "#1A1240", GOLD, fa, "bold", 0.5)
                c.restore()
