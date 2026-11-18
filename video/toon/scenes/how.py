"""06–10: how a test works, and why k is the problem."""
from .common import *
import skia


# ======================================================================================
class Proth(Scene):
    ID = "06_proth"
    NUMBER, CHAPTER = "5", "One long calculation"

    def setup(self):
        self.sky = Sky(seed=21)
        self.vals = ["3", "9", "81", "6,561", "43,046,721"]
        self.sfx(self.b(0, 0.05), "pop", 0.7)
        self.sfx(self.b(1, 0.05), "hop", 0.6)
        for i in range(1, 5):
            self.sfx(self.b(1, 0.1 + i * 0.1), "pop", 0.5)
        self.sfx(self.b(1, 0.6), "rise", 0.7)
        self.sfx(self.b(2, 0.12), "fanfare", 0.9)
        self.sfx(self.b(3, 0.05), "whoosh", 0.5)

    def draw(self, c, t):
        hill(c, t, 840, "#241A5E", VIOLET)
        mx, my, ms = 960, 560, 520
        fa = 1 - prog(t, self.b(3, 0.0), self.d(3, 0.1))
        if fa > 0:
            run = prog(t, self.b(1, 0.05), 1.0) + 4 * prog(t, self.b(1, 0.55), self.d(1, 0.3), inn)
            run *= 1 - prog(t, self.b(2, 0.05), 0.4)
            u = prog(t, self.b(0, 0.05), 0.7, back)
            c.save(); c.translate(mx, my + 190); c.scale(u, u); c.translate(-mx, -(my + 190))
            light = GOLD if t > self.b(2, 0.1) else None
            machine(c, mx, my, ms, t, run, VIOLET, light, fa, "SQUARE IT")
            c.restore()
            # b1: in through the funnel, out through the chute, bigger each time
            if self.b(1, 0.0) < t < self.b(2, 0.1):
                hu = prog(t, self.b(1, 0.02), 0.9)
                if hu < 1:
                    x = lerp(300, mx - 90, hu); y = lerp(760, my - 240, hu) - 140 * math.sin(math.pi * hu)
                    critter(c, x, y, 46, LILAC, t, label="3", seed=1, mood="happy", alpha=fa)
                for i in range(1, 5):
                    t0 = self.b(1, 0.1 + i * 0.1)
                    k = prog(t, t0, 1.6, lin)
                    if 0 < k < 1:
                        x = lerp(mx + 320, 1820, k); y = 770
                        r = 30 + i * 8
                        critter(c, x, y - r + 10, r, LILAC if i < 4 else GOLD, t, label=self.vals[i], seed=i + 3, mood="happy", alpha=fa * (1 - smooth((k - 0.8) / 0.2)))
                loop = prog(t, self.b(1, 0.55), 0.8)
                if loop > 0:
                    bezier(c, (mx + 330, my + 120), (mx + 600, my - 420), (mx - 40, my - 300), GOLD, 5, 0.7 * fa, upto=loop, dash=[16, 12])
                    text(c, "again, and again", mx + 470, my - 330, 30, GOLD, "display", alpha=fa * loop)
        # b2: the verdict
        if self.b(2, 0.0) < t < self.b(3, 0.15):
            fa2 = 1 - prog(t, self.b(3, 0.0), self.d(3, 0.12))
            u = prog(t, self.b(2, 0.08), 0.7, back)
            critter(c, mx + 420, 700, 80 * u, GOLD, t, label="N − 1", seed=9, mood="wow", glowing=True, alpha=fa2)
            burst(c, mx + 420, 700, prog(t, self.b(2, 0.12), 1.2, lin), GOLD, 14, 220, fa2)
            pa = prog(t, self.b(2, 0.15), 0.6, back)
            c.save(); c.translate(mx, 170); c.scale(pa, pa)
            big_title(c, "PRIME!", 0, 0, 110, GOLD, fa2, AMBER)
            c.restore()
        # b3: one squaring at a time: the other machines wait
        if t > self.b(3, 0.0):
            a = prog(t, self.b(3, 0.05), 0.7)
            for i in range(4):
                x = 330 + i * 420
                working = i == int(((t - self.b(3, 0.1)) / max(0.8, self.d(3, 0.18))) % 4) if t > self.b(3, 0.1) else i == 0
                machine(c, x, 600, 300, t, 1.0 if working else 0.0, VIOLET if working else SLATE, None, a)
                if not working:
                    for z in range(3):
                        zt = (t * 0.6 + z * 0.33 + i * 0.2) % 1.0
                        text(c, "z", x + 90 + zt * 60, 470 - zt * 110, 26 + z * 6, LILAC, "display", alpha=a * (1 - zt))
                if i < 3:
                    bezier(c, (x + 160, 560), (x + 210, 500), (x + 260, 560), GOLD, 4, 0.6 * a, dash=[10, 8])

    def overlay(self, c, t):
        a = prog(t, self.b(0, 0.15), 0.6) * (1 - prog(t, self.b(1, 0.0), 0.5))
        if a > 0:
            label_tag(c, "1878  ·  François Proth", W / 2, 120, 40, INK, "#3A2C86", a)
            rrect(c, W / 2 - 440, 905, 880, 110, 55, "#140F3A", 0.75 * a)
            rich(c, [("N  =  ", SOFT), ("21181", CORAL), (" × 2", INK), ("^47,856,068", INK), (" + 1", INK)], W / 2, 962, 52, alpha=a, face="display")
        a = prog(t, self.b(1, 0.25), 0.6) * (1 - prog(t, self.b(2, 0.0), 0.5))
        if a > 0:
            n = int(47_856_067 * prog(t, self.b(1, 0.55), self.d(1, 0.4), inn))
            n = max(n, min(4, int((t - self.b(1, 0.1)) / max(0.01, self.d(1, 0.1)))))
            counter_pill(c, "squarings:", fmt(n), W - 60, 120, a)
            caption(c, "keep only the remainder after dividing by N", 985, a, 32)
        a = prog(t, self.b(2, 0.3), 0.6) * (1 - prog(t, self.b(3, 0.0), 0.4))
        caption(c, "last remainder = N − 1, the one that stands for −1", 985, a, 32, GOLD)
        a = prog(t, self.b(3, 0.15), 0.6)
        caption(c, "each squaring needs the one before", 985, a * (1 - prog(t, self.b(3, 0.55), 0.4)), 32)
        caption(c, "a faster squaring is the only way to a faster test", 985, prog(t, self.b(3, 0.6), 0.5), 32, GOLD)


# ======================================================================================
class FFT(Scene):
    ID = "07_fft"
    NUMBER, CHAPTER = "6", "Multiplying giants"

    def setup(self):
        self.sky = Sky(seed=23)
        self.a = [3, 1, 4, 1, 5]
        self.cv = [0] * 9
        for i, x in enumerate(self.a):
            for j, y in enumerate(self.a):
                self.cv[i + j] += x * y
        A = np.fft.fft(np.array(self.a[::-1] + [0] * 11, dtype=float))
        self.mag = np.abs(A[:9])
        rng = np.random.default_rng(2)
        self.tile = rng.integers(0, 81, (60, 100))
        for i in range(25):
            self.sfx(self.b(0, 0.05 + i * 0.012), "tick", 0.25)
        self.sfx(self.b(0, 0.45), "whoosh", 0.7)
        self.sfx(self.b(1, 0.05), "flip", 0.6)
        self.sfx(self.b(3, 0.1), "shimmer", 0.8)
        self.sfx(self.b(3, 0.6), "shimmer", 0.6)
        self.sfx(self.b(3, 0.85), "chime", 0.8)
        self.sfx(self.b(4, 0.1), "steps", 0.5)

    def camera(self, t):
        z = 1.0
        if self.b(0, 0.45) < t < self.b(2, 0.0):
            z = lerp(1.0, 0.18, prog(t, self.b(0, 0.45), self.d(0, 0.4), io))
        return (W / 2, H / 2 - 20, z)

    def bars(self, c, vals, x0, y0, w, gap, scale, colors, alpha=1.0, labels=None, lab_col=None, glow_on=True, grow=1.0):
        x = x0
        for i, v in enumerate(vals):
            h = max(4, v * scale * grow)
            colr = colors[i % len(colors)] if isinstance(colors, list) else colors
            if glow_on:
                glow(c, x + w / 2, y0 - h / 2, w * 1.6, colr, 0.25 * alpha)
            rrect(c, x, y0 - h, w, h, min(w / 2, 8), colr, alpha)
            if labels:
                text(c, str(labels[i]), x + w / 2, y0 + 30, 26, lab_col or SOFT, "bold", alpha=alpha)
            x += w + gap

    def draw(self, c, t):
        # b0: long multiplication, then the camera pulls back over an endless grid
        if t < self.b(2, 0.0):
            fa = 1 - 0.85 * prog(t, self.b(1, 0.05), self.d(1, 0.2))
            gx, gy, s = 760, 340, 92
            for i in range(-30, 31):
                for j in range(-18, 19):
                    if 0 <= i < 5 and 0 <= j < 5:
                        continue
                    k = prog(t, self.b(0, 0.45) + (abs(i) + abs(j)) * 0.02, 0.3)
                    if k <= 0:
                        continue
                    x, y = gx + i * s, gy + j * s
                    rrect(c, x + 4, y + 4, s - 8, s - 8, 14, "#2E2470", 0.9 * k * fa)
                    text(c, str(self.tile[(j + 30) % 60, (i + 50) % 100]), x + s / 2, y + s / 2, 30, LILAC, "bold", alpha=0.6 * k * fa)
            for i, x_ in enumerate(self.a):
                text(c, str(x_), gx + i * s + s / 2, gy - 50, 48, INK, "display", alpha=fa)
                text(c, str(x_), gx - 50, gy + i * s + s / 2, 48, INK, "display", alpha=fa)
                for j, y_ in enumerate(self.a):
                    k = prog(t, self.b(0, 0.05 + (i * 5 + j) * 0.012), 0.4, back)
                    if k <= 0:
                        continue
                    x, y = gx + j * s, gy + i * s
                    c.save(); c.translate(x + s / 2, y + s / 2); c.scale(k, k)
                    rrect(c, -s / 2 + 4, -s / 2 + 4, s - 8, s - 8, 14, VIOLET, fa)
                    text(c, str(x_ * y_), 0, 0, 36, INK, "bold", alpha=fa)
                    c.restore()
            text(c, "×", gx - 50, gy - 50, 48, SOFT, "display", alpha=fa)
        # b2: digits as bars, smeared across each other
        if self.b(2, 0.0) < t < self.b(3, 0.15):
            fa = prog(t, self.b(2, 0.05), 0.5) * (1 - prog(t, self.b(3, 0.0), self.d(3, 0.12)))
            self.bars(c, self.a, 260, 700, 70, 26, 70, CYAN, fa, self.a, INK)
            text(c, "a number, as a row of digits", 260 + 230, 790, 28, SOFT, "body", alpha=fa)
            colw = 74
            x0 = 900
            for i, d in enumerate(self.a):
                k = prog(t, self.b(2, 0.3 + i * 0.07), 0.5, back)
                if k <= 0:
                    continue
                mergek = prog(t, self.b(2, 0.72), self.d(2, 0.2), io)
                for j, x_ in enumerate(self.a):
                    h = d * x_ * 5.5
                    xx = x0 + (i + j) * colw
                    yy = lerp(300 + i * 92, 700, mergek)
                    off = sum(self.a[ii] * self.a[i + j - ii] * 5.5 for ii in range(i) if 0 <= i + j - ii < 5) * mergek
                    rrect(c, xx, yy - h - off, 56, h, 8, CYAN if (i % 2 == 0) else TEAL, fa * k * (0.85))
                text(c, f"{d}×", x0 - 60, lerp(300 + i * 92, 700, mergek) - 20, 26, SOFT, "bold", alpha=fa * k * (1 - mergek))
            la = prog(t, self.b(2, 0.85), 0.5)
            if la > 0:
                for i, v in enumerate(self.cv):
                    text(c, str(v), x0 + i * colw + 28, 735, 26, GOLD, "bold", alpha=fa * la)
                text(c, "overlapping columns add up", x0 + 4 * colw + 28, 800, 28, SOFT, "body", alpha=fa * la)
        # b3: the prism
        if t > self.b(3, 0.0) and t < self.b(4, 0.12):
            fa = prog(t, self.b(3, 0.05), 0.5) * (1 - prog(t, self.b(4, 0.0), self.d(4, 0.1)))
            py = 520
            self.bars(c, self.a, 90, py + 120, 34, 10, 40, CYAN, fa)
            bu = prog(t, self.b(3, 0.08), 0.6)
            line(c, 320, py, lerp(320, 520, bu), py, "#FFFFFF", 10, 0.8 * fa)
            glow(c, 500, py, 60, "#FFFFFF", 0.4 * fa * bu)
            prism(c, 600, py, 220, fa)
            su = prog(t, self.b(3, 0.15), 0.8)
            sq = prog(t, self.b(3, 0.45), self.d(3, 0.15))
            for i in range(9):
                yy = py - 160 + i * 40
                colr = RAINBOW[i]
                line(c, 680, py + (i - 4) * 6, lerp(680, 900, su), lerp(py + (i - 4) * 6, yy, su), colr, 8, fa * su * 0.9)
                mm = self.mag[i] / self.mag.max()
                L = 300 * su * ((1 - sq) * mm + sq * mm * mm) + 8
                rrect(c, 920, yy - 12, max(6, L), 24, 12, colr, fa * su)
                if sq > 0:
                    glow(c, 920 + L, yy, 40, colr, 0.5 * fa * pulse(sq, 0, 1))
            text(c, "frequencies", 1060, py - 210, 30, INK, "display", alpha=fa * su)
            if sq > 0:
                text(c, "× pair by pair", 1060, py + 220, 30, GOLD, "display", alpha=fa * sq)
            ru = prog(t, self.b(3, 0.6), self.d(3, 0.2))
            if ru > 0:
                prism(c, 1440, py, 180, fa * ru)
                for i in range(9):
                    yy = py - 160 + i * 40
                    line(c, 1250, yy, lerp(1250, 1380, ru), lerp(yy, py + (i - 4) * 5, ru), RAINBOW[i], 6, fa * ru * 0.7)
                self.bars(c, self.cv, 1530, py + 160, 30, 8, 5, GOLD, fa * ru, glow_on=True, grow=ru)
            pu = prog(t, self.b(3, 0.82), 0.6, back)
            if pu > 0:
                c.save(); c.translate(W / 2, 880); c.scale(pu, pu)
                rrect(c, -330, -60, 660, 120, 60, "#140F3A", 0.8 * fa)
                text(c, "31415²  =  986,902,225", 0, 0, 52, GOLD, "display", alpha=fa)
                c.restore()
        # b4: two climbs
        if t > self.b(4, 0.0):
            fa = prog(t, self.b(4, 0.05), 0.6)
            base = 900
            steep = [(200 + x, base - 0.0028 * x * x) for x in range(0, 540, 10)]
            gentle = [(1000 + x, base - 0.38 * x) for x in range(0, 760, 10)]
            poly(c, [(200, base)] + steep + [(740, base)], "#3A2066", fa)
            poly(c, [(1000, base)] + gentle + [(1760, base)], "#1E4A66", fa)
            curve(c, steep, CORAL, 6, fa)
            curve(c, gentle, CYAN, 6, fa)
            text(c, "long multiplication", 520, 960, 32, CORAL, "display", alpha=fa)
            text(c, "Fast Fourier Transform", 1380, 960, 32, CYAN, "display", alpha=fa)
            u1 = 0.35 * prog(t, self.b(4, 0.1), self.d(4, 0.85), lin)
            u2 = prog(t, self.b(4, 0.1), self.d(4, 0.55), io)
            x1 = 200 + u1 * 640; y1 = base - 0.0028 * (x1 - 200) ** 2
            x2 = 1000 + u2 * 740; y2 = base - 0.38 * (x2 - 1000)
            hiker(c, x1, y1, 80, t * 0.5, CORAL, True, fa, seed=1)
            hiker(c, x2, y2, 80, t * 1.4, CYAN, u2 < 0.99, fa, seed=2)
            if u2 >= 0.99:
                flag(c, x2 + 30, y2, 120, GOLD, fa, t)

    def overlay(self, c, t):
        # b1: thousands of years (screen space, over the zoomed-out grid)
        if self.b(1, 0.0) < t < self.b(2, 0.1):
            fa = prog(t, self.b(1, 0.15), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.08)))
            cx, cy = W / 2, 520
            years = int(2026 + 3000 * inn(prog(t, self.b(1, 0.15), self.d(1, 0.75), lin)))
            rrect(c, cx - 210, cy - 200, 420, 420, 40, CREAM, fa)
            rrect(c, cx - 210, cy - 200, 420, 110, 40, CORAL, fa)
            for k in (-120, 120):
                rrect(c, cx + k - 14, cy - 230, 28, 70, 14, SLATE, fa)
            text(c, "YEAR", cx, cy - 145, 44, CREAM, "bold", alpha=fa)
            text(c, str(years), cx, cy + 50, 120, "#2E2470", "display", alpha=fa)
            flip = (t * 5) % 1.0
            c.save(); c.translate(cx, cy - 90); c.scale(1, max(0.02, 1 - flip))
            rrect(c, -205, 0, 410, 300 * (1 - flip) * 0 + 300, 30, shade(CREAM, -0.08), fa * (1 - flip) * 0.8)
            c.restore()
        a = prog(t, self.b(0, 0.55), 0.6) * (1 - prog(t, self.b(1, 0.1), 0.5))
        if a > 0:
            rrect(c, W / 2 - 520, 860, 1040, 160, 50, "#140F3A", 0.8 * a)
            text(c, "14.4 million digits × 14.4 million digits", W / 2, 905, 36, INK, "display", alpha=a)
            rich(c, [("≈ 2 × 10", GOLD), ("^14", GOLD), (" small multiplications, per squaring", GOLD)], W / 2, 970, 36, alpha=a, face="display")
        a = prog(t, self.b(1, 0.2), 0.5) * (1 - prog(t, self.b(2, 0.0), 0.4))
        caption(c, "× 48 million squarings  =  thousands of years", 985, a, 36, CORAL)
        a = prog(t, self.b(4, 0.6), 0.5)
        caption(c, "each squaring: many minutes  →  a fraction of a millisecond", 1035, a, 32, GOLD)


# ======================================================================================
def table(c, x, y, R, n, t, sizes=None, alpha=1.0, chair_col=WOOD, empty=None, crack=0.0):
    soft_shadow(c, x, y + R * 0.15, R * 1.35, R * 1.0, 0.35 * alpha)
    for i in range(n):
        a = -math.pi / 2 + i * 2 * math.pi / n
        s = (sizes[i] if sizes else 1.0)
        cx, cy = x + math.cos(a) * R * 1.32, y + math.sin(a) * R * 1.32
        if empty and i in empty:
            ring(c, cx, cy, R * 0.16 * s, LILAC, 3, 0.5 * alpha)
        else:
            c.drawCircle(cx, cy, R * 0.17 * s, paint(shade(chair_col, -0.25), alpha))
            c.drawCircle(cx, cy, R * 0.14 * s, paint(chair_col, alpha))
    c.drawCircle(x, y, R * 1.04, paint(shade(WOOD, -0.35), alpha))
    c.drawCircle(x, y, R, paint(WOOD, alpha))
    for k in (0.75, 0.5, 0.25):
        ring(c, x, y, R * k, shade(WOOD, -0.12), 3, 0.5 * alpha)
    if crack > 0:
        pts = [(x - R * 0.9, y - R * 0.2), (x - R * 0.4, y - R * 0.05), (x - R * 0.1, y - R * 0.3), (x + R * 0.3, y + R * 0.1), (x + R * 0.85, y - R * 0.05)]
        m = max(2, int(len(pts) * crack))
        curve(c, pts[:m], "#2A1408", 7, alpha)


def seat_pos(x, y, R, n, i, k=1.32):
    a = -math.pi / 2 + i * 2 * math.pi / n
    return x + math.cos(a) * R * k, y + math.sin(a) * R * k


class RoundTable(Scene):
    ID = "08_round_table"
    NUMBER, CHAPTER = "7", "The round table"
    DIG = "471820593614"

    def setup(self):
        self.sky = Sky(seed=25)
        self.sfx(self.b(0, 0.05), "steps", 0.5)
        for i in range(12):
            self.sfx(self.b(1, 0.05 + i * 0.025), "tick", 0.3)
        self.sfx(self.b(1, 0.4), "steps", 0.5)
        self.sfx(self.b(1, 0.85), "pop", 0.8)
        self.sfx(self.b(2, 0.1), "chime", 0.8)
        self.sfx(self.b(2, 0.4), "whoosh", 0.5)

    def draw(self, c, t):
        tx, ty, R = 760, 560, 230
        cols = [CORAL, TEAL, AMBER, VIOLET, ROSE, MINT, CYAN, GOLD, LILAC, CORAL, TEAL, AMBER, ROSE]
        # b0: the full product queues up
        if t < self.b(1, 0.3):
            fa = 1 - prog(t, self.b(1, 0.1), self.d(1, 0.2))
            hill(c, t, 840, "#241A5E", VIOLET, alpha=fa)
            for i, d in enumerate(self.DIG + "7"):
                k = prog(t, self.b(0, 0.05) + i * 0.08, 0.8, out)
                x = lerp(-100, 220 + i * 115, k)
                critter(c, x, 780, 46, cols[i], t * (1.5 if k < 1 else 1), label=d, seed=i, mood="happy", alpha=fa)
            a = prog(t, self.b(0, 0.5), 0.5) * fa
            if a > 0:
                for x in (180, 1740):
                    line(c, x, 860, x, 660, GOLD, 10, a)
                    c.drawCircle(x, 650, 16, paint(GOLD, a))
                bezier(c, (180, 690), (960, 760), (1740, 690), CORAL, 12, a)
                label_tag(c, "only the remainder gets in", W / 2, 560, 40, "#1A1240", GOLD, a, "bold", 0.45)
        # b1/b2: the round table
        if t > self.b(1, 0.0):
            fa = prog(t, self.b(1, 0.05), 0.6)
            grow = prog(t, self.b(2, 0.35), self.d(2, 0.25), io)
            sizes = [1 + grow * s for s in (0.35, -0.2, 0.2, -0.25, 0.3, 0.0, -0.15, 0.32, -0.22, 0.15, -0.1, 0.25)]
            table(c, tx, ty, R, 12, t, sizes, fa)
            for i, d in enumerate(self.DIG):
                k = prog(t, self.b(1, 0.05 + i * 0.025), 0.5, back)
                if k <= 0:
                    continue
                x, y = seat_pos(tx, ty, R, 12, i)
                merged = i == 0 and t > self.b(1, 0.85)
                lab = "11" if merged else d   # 4 + 7 = 11: the carry is tidied up later
                critter(c, x, y - 6, 38 * k * sizes[i], cols[i], t, label=lab, seed=i, mood="wow" if merged and t < self.b(1, 0.95) else "happy", look=((tx - x) / R * 0.5, (ty - y) / R * 0.5))
            # the 13th guest walks round to the first seat
            wk = prog(t, self.b(1, 0.4), self.d(1, 0.45), io)
            if 0 < wk < 1:
                a0 = -math.pi / 2 - 2 * math.pi / 12 * 1.0
                ang = a0 + wk * 2 * math.pi / 12
                rr = R * (1.75 - 0.43 * smooth((wk - 0.7) / 0.3))
                x, y = tx + math.cos(ang) * rr, ty + math.sin(ang) * rr
                critter(c, x, y, 38, cols[12], t * 2, label="7", seed=12, mood="happy")
            if t > self.b(1, 0.85):
                x, y = seat_pos(tx, ty, R, 12, 0)
                burst(c, x, y, prog(t, self.b(1, 0.85), 0.8, lin), GOLD, 10, 90)

    def overlay(self, c, t):
        a = prog(t, self.b(1, 0.3), 0.6) * (1 - prog(t, self.b(2, 0.0), 0.4))
        if a > 0:
            text(c, "overflow past the last seat…", 1180, 420, 40, INK, "display", "left", a, shadow=1)
            text(c, "…walks round to the first", 1180, 490, 40, GOLD, "display", "left", a * prog(t, self.b(1, 0.7), 0.5), shadow=1)
        a = prog(t, self.b(2, 0.05), 0.6)
        if a > 0:
            rich(c, [("Mersenne numbers:  2", INK), ("^p", INK), (" − 1", INK)], 1180, 380, 44, "left", a, "display", 1)
            text(c, "the wrap is exactly right  ✓", 1180, 450, 36, MINT, "display", "left", a, shadow=1)
        a = prog(t, self.b(2, 0.4), 0.6)
        if a > 0:
            text(c, "weights", 1180, 580, 44, GOLD, "display", "left", a, shadow=1)
            text(c, "Crandall & Fagin, 1994", 1180, 640, 30, SOFT, "body", "left", a)
            text(c, "a big reason the hunt for", 1180, 740, 30, SOFT, "body", "left", a * prog(t, self.b(2, 0.6), 0.5))
            text(c, "Mersenne primes is so fast", 1180, 785, 30, SOFT, "body", "left", a * prog(t, self.b(2, 0.6), 0.5))


# ======================================================================================
class KProblem(Scene):
    ID = "09_the_k_problem"
    NUMBER, CHAPTER = "8", "Why k makes it hard"
    DIG = "471820593614"

    def setup(self):
        self.sky = Sky(seed=27, nebulae=(CORAL, VIOLET, ROSE))
        rng = np.random.default_rng(4)
        self.dust = rng.uniform(-1, 1, (40, 2))
        self.sfx(self.b(0, 0.3), "steps", 0.5)
        self.sfx(self.b(1, 0.05), "zap", 0.8)
        self.sfx(self.b(1, 0.2), "crumble", 0.8)
        self.sfx(self.b(1, 0.45), "crack", 0.8)
        self.sfx(self.b(2, 0.1), "whoosh", 0.6)
        self.sfx(self.b(2, 0.45), "truck", 0.6)
        self.sfx(self.b(3, 0.1), "whoosh", 0.6)

    def draw(self, c, t):
        tx, ty, R = 700, 560, 230
        cols = [CORAL, TEAL, AMBER, VIOLET, ROSE, MINT, CYAN, GOLD, LILAC, CORAL, TEAL, AMBER, ROSE]
        big = prog(t, self.b(2, 0.1), self.d(2, 0.25), io) * (1 - prog(t, self.b(3, 0.0), self.d(3, 0.15), io))
        n = 12 if big < 0.5 else 24
        RR = R * (1 + 0.36 * big)
        crack = prog(t, self.b(1, 0.45), 0.8) * (1 - prog(t, self.b(2, 0.05), 0.4))
        fuzzy = prog(t, self.b(3, 0.15), self.d(3, 0.25))
        table(c, tx, ty, RR, n, t, None, 1.0, empty=set(range(12, 24)) if n == 24 else None, crack=crack)
        for i, d in enumerate(self.DIG):
            k = prog(t, 0.2 + i * 0.04, 0.5, back)
            x, y = seat_pos(tx, ty, RR, n, i)
            worried = crack > 0.2
            if fuzzy > 0:
                lp = skia.Paint(ImageFilter=skia.ImageFilters.Blur(5 * fuzzy, 5 * fuzzy))
                c.saveLayer(skia.Rect(x - 90, y - 110, x + 90, y + 90), lp)   # blur only this creature's box
            critter(c, x, y - 6, 38 * k, cols[i], t, label=d if fuzzy < 0.5 else "≈" + d, seed=i, mood="worried" if worried else "happy", look=((tx - x) / RR * 0.5, (ty - y) / RR * 0.5))
            if fuzzy > 0:
                c.restore()
        # the overflow guest meets the ÷k gate and crumbles
        if t < self.b(2, 0.1):
            gx, gy = seat_pos(tx, ty, R, 12, -0.7, 1.72)
            ga = prog(t, self.b(0, 0.2), 0.5) * (1 - prog(t, self.b(2, 0.0), 0.4))
            ring(c, gx, gy, 56, CORAL, 10, ga)
            glow(c, gx, gy, 130, CORAL, 0.35 * ga)
            text(c, "÷ k", gx - 110, gy, 44, CORAL, "display", alpha=ga, shadow=1)
            wk = prog(t, self.b(0, 0.3), self.d(0, 0.6), io)
            if wk > 0 and t < self.b(1, 0.2):
                ang = -math.pi / 2 - 2 * math.pi / 12 * (0.7 + (1 - wk) * 1.4)
                x, y = tx + math.cos(ang) * R * 1.72, ty + math.sin(ang) * R * 1.72
                shrink = 1 - 0.85 * prog(t, self.b(1, 0.02), 0.4)
                critter(c, x, y, 40 * shrink, cols[12], t * 2, label="7", seed=12, mood="wow" if shrink < 0.9 else "happy")
            du = prog(t, self.b(1, 0.2), 1.6, out)
            if 0 < du < 1:
                for i, (dx, dy) in enumerate(self.dust):
                    c.drawCircle(gx + dx * 90 * du, gy + dy * 60 * du + 140 * du * du, 4 * (1 - du), paint(cols[12], 1 - du))
                text(c, "0.0000472…", gx, gy + 110, 34, CORAL, "mono", alpha=pulse(du, 0, 1) * 1.2)
        # option 1: twice the table, twice the data
        if big > 0.02:
            truck(c, 1500 + 60 * math.sin(t * 0.8), 930, 320, 16, t, CORAL, GOLD, big)
            truck(c, 1500 + 60 * math.sin(t * 0.8 + 1), 760, 320, 16, t, CORAL, GOLD, big * prog(t, self.b(2, 0.45), 0.6, back))
        # option 2: the precision budget of one decimal
        if fuzzy > 0:
            x0, y0, w = 1150, 760, 620
            segs = [(32, CYAN, "the number"), (15, CORAL, "eaten by k"), (6, DIM, "margin")]
            text(c, "one double-precision number: 53 bits", x0, y0 - 70, 28, SOFT, "body", "left", fuzzy)
            x = x0
            for bits, colr, lab in segs:
                ww = w * bits / 53 * prog(t, self.b(3, 0.3), self.d(3, 0.3))
                rrect(c, x, y0 - 22, max(1, ww - 6), 44, 14, colr, fuzzy)
                if ww > 40:
                    text(c, lab, x + ww / 2, y0 + 50, 24, colr if colr != DIM else SOFT, "display", alpha=fuzzy)
                x += ww

    def overlay(self, c, t):
        a = prog(t, self.b(0, 0.05), 0.6) * (1 - prog(t, self.b(2, 0.05), 0.4))
        if a > 0:
            rich(c, [("k", CORAL), (" × 2", INK), ("^n", INK), (" + 1", INK)], 1500, 300, 64, alpha=a, face="display", shadow=1)
            text(c, "overflow must come back", 1500, 400, 34, SOFT, "body", alpha=a)
            text(c, "divided by k, sign flipped", 1500, 450, 34, CORAL, "display", alpha=a)
            ua = prog(t, self.b(1, 0.3), 0.6)
            text(c, "not a whole number: it doesn't fit", 1500, 560, 32, CORAL, "body", alpha=a * ua)
        a = prog(t, self.b(2, 0.15), 0.6) * (1 - prog(t, self.b(3, 0.0), 0.4))
        if a > 0:
            label_tag(c, "1   twice the table", 1500, 300, 40, INK, "#3A2C86", a)
            text(c, "exact, but twice the data", 1500, 390, 32, SOFT, "body", alpha=a)
            text(c, "proth20 (graphics cards)", 1500, 440, 30, CORAL, "display", alpha=a)
        a = prog(t, self.b(3, 0.1), 0.6)
        if a > 0:
            label_tag(c, "2   k inside the weights", 1460, 300, 40, INK, "#3A2C86", a)
            text(c, "small table, but decimals", 1460, 390, 32, SOFT, "body", alpha=a)
            text(c, "Percival · Woltman's gwnum · LLR2", 1460, 440, 30, CYAN, "display", alpha=a)


# ======================================================================================
class Exact(Scene):
    ID = "10_exact"
    NUMBER, CHAPTER = "9", "Exact arithmetic"

    def setup(self):
        self.sky = Sky(seed=29)
        self.sfx(self.b(0, 0.1), "pop", 0.7)
        self.sfx(self.b(0, 0.35), "wobble", 0.7)
        self.sfx(self.b(1, 0.05), "whoosh", 0.5)
        for i in range(7):
            self.sfx(self.b(2, 0.3) + i * self.d(2, 0.4) / 7, "tick", 0.5)
        self.sfx(self.b(3, 0.15), "chime", 0.6)
        self.sfx(self.b(3, 0.45), "lock", 0.7)
        self.sfx(self.b(4, 0.05), "paper", 0.6)

    def draw(self, c, t):
        # b0: the sweating calculator
        if t < self.b(1, 0.1):
            fa = prog(t, self.b(0, 0.05), 0.5) * (1 - prog(t, self.b(1, 0.0), self.d(1, 0.1)))
            x, y, w = 960, 540, 460
            hh = w * 1.35
            sw = prog(t, self.b(0, 0.35), 0.5)
            soft_shadow(c, x, y + hh * 0.55, w * 0.55, w * 0.08, 0.4 * fa)
            rrect(c, x - w / 2, y - hh / 2, w, hh, w * 0.12, "#4B3F9E", fa)
            rrect(c, x - w * 0.43, y - hh * 0.43, w * 0.86, hh * 0.27, w * 0.06, "#BFE3C9", fa)
            text(c, "0.1 + 0.2 =", x + w * 0.38, y - hh * 0.36, 38, "#2E5A3A", "mono", "right", fa)
            jit = math.sin(t * 40) * 5 * sw
            text(c, "0.3000000000000000", x + w * 0.39 - 20, y - hh * 0.23, 29, "#1A3A24", "mono", "right", fa)
            text(c, "4", x + w * 0.39 - 9 + jit, y - hh * 0.23, 29, CORAL, "mono", "center", fa)
            ey = y - hh * 0.04
            for sgn in (-1, 1):
                c.drawCircle(x + sgn * 62, ey, 22, paint("#FFFFFF", fa))
                c.drawCircle(x + sgn * 62 + 4 * math.sin(t * 6) * sw, ey + 5, 11, paint("#1A1240", fa))
            arc(c, x, ey + 75, 32, 205, 130, "#FFFFFF", 7, fa)
            for r_ in range(2):
                for c_ in range(4):
                    rrect(c, x - w * 0.42 + c_ * w * 0.215, y + hh * 0.17 + r_ * hh * 0.13, w * 0.17, hh * 0.1, w * 0.04, shade("#4B3F9E", 0.25), fa)
            if sw > 0:
                dy = (t * 50) % 80
                c.drawOval(skia.Rect(x + w * 0.52, y - hh * 0.36 + dy, x + w * 0.6, y - hh * 0.26 + dy), paint(CYAN, fa * sw * (1 - dy / 80)))
        # b1: a graphics card's two lanes
        if self.b(1, 0.0) < t < self.b(2, 0.1):
            fa = prog(t, self.b(1, 0.05), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.1)))
            rrect(c, 180, 230, 1560, 640, 60, "#1B3A2E", fa)
            rrect(c, 200, 250, 1520, 600, 50, "#1F4A38", fa)
            for k in range(14):
                rrect(c, 260 + k * 104, 870, 56, 40, 6, GOLD, fa * 0.9)
            line(c, 260, 560, 1660, 560, "#2E6A50", 4, fa)
            text(c, "whole numbers", 300, 300, 36, MINT, "display", "left", fa, shadow=1)
            text(c, "double precision", 300, 610, 36, CORAL, "display", "left", fa, shadow=1)
            for i in range(18):
                ph = (t * 0.55 + i / 18) % 1.0
                hiker(c, 280 + ph * 1400, 520 - (i % 3) * 22, 60, t * 2.2, MINT, True, fa, seed=i)
            ph = (t * 0.02) % 1.0
            hiker(c, 300 + ph * 1400, 800, 60, t * 0.35, CORAL, True, fa, seed=99)
            text(c, "32–64× slower", 1500, 700, 40, CORAL, "display", alpha=fa * prog(t, self.b(1, 0.5), 0.5), shadow=1)
        # b2: clock arithmetic
        if self.b(2, 0.0) < t < self.b(3, 0.1):
            fa = prog(t, self.b(2, 0.05), 0.5) * (1 - prog(t, self.b(3, 0.0), self.d(3, 0.1)))
            hand = 9 + 7 * prog(t, self.b(2, 0.3), self.d(2, 0.4), io)
            clock(c, 700, 540, 300, 12, t, labels=["12"] + [str(i) for i in range(1, 12)], hand=hand % 12, alpha=fa)
            text(c, "9 + 7 = 4", 1300, 440, 96, GOLD, "display", alpha=fa * prog(t, self.b(2, 0.7), 0.5), shadow=1)
            for i, s in enumerate(("no fractions", "no rounding", "every result exact")):
                text(c, s, 1300, 580 + i * 62, 38, MINT if i == 2 else INK, "display", alpha=fa * prog(t, self.b(2, 0.78 + i * 0.05), 0.5))
        # b3: square roots on a 7-hour clock
        if t > self.b(3, 0.0) and t < self.b(4, 0.12):
            fa = prog(t, self.b(3, 0.05), 0.5) * (1 - prog(t, self.b(4, 0.0), self.d(4, 0.1)))
            lu = prog(t, self.b(3, 0.15), 0.6)
            lk = prog(t, self.b(3, 0.42), 0.6, back)
            lit = {1: GOLD, 2: GOLD, 4: GOLD} if lu > 0.5 else None
            locked = {3: lk, 5: lk, 6: lk}
            clock(c, 640, 560, 300, 7, t, lit=lit, locked=locked, alpha=fa, dim={3, 5, 6} if lk > 0.5 else None)
            for i, (root, sq) in enumerate(((1, 1), (3, 2), (2, 4))):
                px, py = clock_pos(640, 560, 300, 7, sq, 1.18)
                text(c, f"{root}²", px, py, 34, GOLD, "display", alpha=fa * lu, shadow=1)
            text(c, "square roots on a 7-hour clock", 640, 160, 40, INK, "display", alpha=fa, shadow=1)
            ra = prog(t, self.b(3, 0.6), 0.6)
            text(c, "our weights need a", 1350, 470, 40, INK, "display", alpha=fa * ra, shadow=1)
            rich(c, [("millionth root of ", INK), ("−k·2", CORAL), ("^n", CORAL)], 1350, 545, 48, alpha=fa * ra, face="display", shadow=1)
            text(c, "usually, there isn't one", 1350, 640, 36, CORAL, "body", alpha=fa * prog(t, self.b(3, 0.78), 0.5))
        # b4: the quote
        if t > self.b(4, 0.0):
            fa = prog(t, self.b(4, 0.05), 0.6, back)
            speech(c, 960, 480, 1300, 330, fa, CREAM, (-0.55, 1))
            text(c, "“Surprisingly no fast algorithm", 960, 420, 58, "#2E2470", "display", alpha=fa)
            rich(c, [("exists for k·b", "#2E2470"), ("^n", "#2E2470"), (" ± 1 …”", "#2E2470")], 960, 500, 58, alpha=fa, face="display")
            text(c, "Yves Gallot, PrimeGrid forum, February 2024", 960, 760, 32, SOFT, "body", alpha=prog(t, self.b(4, 0.3), 0.6))
            text(c, "on fast whole-number transforms for numbers like ours", 960, 815, 28, DIM, "body", alpha=prog(t, self.b(4, 0.4), 0.6))

    def overlay(self, c, t):
        a = prog(t, self.b(0, 0.4), 0.5) * (1 - prog(t, self.b(1, 0.0), 0.4))
        caption(c, "tiny rounding errors creep in, so programs keep a safety margin", 985, a, 32)
