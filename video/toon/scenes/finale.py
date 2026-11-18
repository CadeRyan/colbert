"""14–17: what it buys, how it stays right, what it means."""
from .common import *
import skia


def board(c, x, y, w, h, alpha):
    rrect(c, x, y, w, h, 50, "#1B3A2E", alpha)
    rrect(c, x + 18, y + 18, w - 36, h - 36, 40, "#1F4A38", alpha)
    for k in range(int(w / 110)):
        rrect(c, x + 60 + k * 110, y + h, 56, 38, 6, GOLD, alpha * 0.9)


def coin(c, x, y, r, alpha, colr=GOLD):
    c.drawOval(skia.Rect(x - r, y - r * 0.35 + 6, x + r, y + r * 0.35 + 6), paint(shade(colr, -0.35), alpha))
    c.drawOval(skia.Rect(x - r, y - r * 0.35, x + r, y + r * 0.35), paint(colr, alpha))
    c.drawOval(skia.Rect(x - r * 0.6, y - r * 0.2, x + r * 0.6, y + r * 0.2), paint(shade(colr, 0.3), alpha * 0.6))


# ======================================================================================
class Results(Scene):
    ID = "14_results"
    NUMBER, CHAPTER = "13", "What it buys"

    def setup(self):
        self.sky = Sky(seed=41)
        self.sfx(self.b(0, 0.05), "whoosh", 0.5)
        for i in range(3):
            self.sfx(self.b(1, 0.1 + i * 0.25), "truck", 0.6)
        self.sfx(self.b(2, 0.1), "rocket", 0.8)
        self.sfx(self.b(2, 0.1) + self.race_time() * F.HOURS_PER_TEST["colbert"] / F.HOURS_PER_TEST["proth20"], "chime", 0.9)
        self.sfx(self.b(2, 0.1) + self.race_time(), "thud", 0.6)
        for i in range(9):
            self.sfx(self.b(3, 0.15 + i * 0.04), "coin", 0.4)

    def race_time(self):
        return self.d(2, 0.55)

    def draw(self, c, t):
        # b0: memory -> compute: the data has to travel
        if t < self.b(1, 0.12):
            fa = prog(t, self.b(0, 0.03), 0.5) * (1 - prog(t, self.b(1, 0.0), self.d(1, 0.12)))
            board(c, 160, 230, 1600, 600, fa)
            rrect(c, 260, 330, 480, 400, 30, "#2A6FDB", fa)
            for r in range(4):
                for k in range(5):
                    rrect(c, 290 + k * 88, 360 + r * 90, 70, 70, 10, GOLD if (r + k) % 2 else shade(GOLD, -0.15), fa)
            text(c, "memory", 500, 770, 40, CYAN, "display", alpha=fa, shadow=1)
            rrect(c, 1300, 420, 300, 220, 30, CYAN, fa)
            rrect(c, 1320, 440, 260, 180, 24, shade(CYAN, -0.3), fa)
            for i in range(3):
                critter(c, 1360 + i * 90, 560, 28, MINT, t, seed=i, mood="sleepy", alpha=fa)
            text(c, "compute", 1450, 690, 40, MINT, "display", alpha=fa, shadow=1)
            rrect(c, 760, 515, 520, 40, 20, "#14301F", fa)
            for i in range(7):
                u = ((t * 0.35) + i / 7) % 1.0
                rrect(c, 770 + u * 470, 470, 46, 46, 8, GOLD, fa * smooth(u / 0.08) * smooth((1 - u) / 0.08))
            for z in range(3):
                zt = (t * 0.5 + z * 0.33) % 1
                text(c, "z", 1560 + zt * 40, 470 - zt * 70, 24 + z * 5, LILAC, "display", alpha=fa * (1 - zt))
        # b1: three trucks, three loads (one crate = 2 MB)
        if self.b(1, 0.0) < t < self.b(2, 0.12):
            fa = prog(t, self.b(1, 0.05), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.12)))
            rows = [("padded (proth20)", 64.0, CORAL), ("decimal weights (LLR2)", 33.8, VIOLET), ("colbert", 24.0, CYAN)]
            for i, (lab, mb, colr) in enumerate(rows):
                u = prog(t, self.b(1, 0.1 + i * 0.25), 1.2, out)
                if u <= 0:
                    continue
                y = 440 + i * 235
                x = lerp(-300, 900, u)
                truck(c, x, y, 430, int(round(mb / 2)), t if u < 1 else 0, colr, GOLD, fa)
                text(c, lab, 140, y - 120, 34, INK if colr != CYAN else CYAN, "display", "left", fa, shadow=1)
                text(c, f"{mb:g} MB", 1260, y - 70, 56, colr, "display", "left", fa * prog(t, self.b(1, 0.1 + i * 0.25) + 1.0, 0.5), shadow=1)
        # b2: the race to one finished test
        if self.b(2, 0.0) < t < self.b(3, 0.12):
            fa = prog(t, self.b(2, 0.04), 0.5) * (1 - prog(t, self.b(3, 0.0), self.d(3, 0.12)))
            x0, x1 = 230, 1600
            planet(c, 1780, 560, 150, t, alpha=fa)
            flag(c, x1 + 20, 820, 140, GOLD, fa, t)
            rt = self.race_time()
            hp, hc = F.HOURS_PER_TEST["proth20"], F.HOURS_PER_TEST["colbert"]
            el = max(0.0, (t - self.b(2, 0.1)) / rt) * hp
            for k, (nm, hh, colr, y) in enumerate((("proth20", hp, CORAL, 430), ("colbert", hc, CYAN, 680))):
                u = clamp(el / hh)
                curve(c, [(x0, y), (x1, y)], colr, 4, 0.25 * fa, dash=[16, 14])
                rocket(c, lerp(x0, x1, io(u)), y, 150, t, colr, fa, flame=1.0 if u < 1 else 0.0)
                text(c, nm, x0 - 30, y - 70, 34, colr, "display", "left", fa, shadow=1)
                if u >= 1:
                    text(c, f"{hh:.1f} hours", x1 - 40, y - 80, 40, colr, "display", "right", fa, shadow=1)
        # b3: tests per kilowatt-hour, as coins
        if t > self.b(3, 0.0):
            fa = prog(t, self.b(3, 0.05), 0.5)
            cols = [("CPU · LLR2", 0.30, SOFT), ("GPU · proth20", 0.38, CORAL), ("GPU · colbert", 0.85, CYAN)]
            k = 0
            for i, (nm, v, colr) in enumerate(cols):
                x = 520 + i * 440
                n = int(round(v * 10))
                for j in range(n):
                    u = prog(t, self.b(3, 0.15 + k * 0.04), 0.4, back)
                    k += 1
                    if u > 0:
                        coin(c, x, 820 - j * 42 - (1 - u) * 80, 70, fa * clamp(u))
                text(c, nm, x, 920, 34, colr if colr != SOFT else INK, "display", alpha=fa, shadow=1)
                va = prog(t, self.b(3, 0.15 + k * 0.04), 0.5)
                text(c, f"{v:.2f}", x, 820 - n * 42 - 60, 44, colr if colr != SOFT else INK, "display", alpha=fa * va, shadow=1)

    def overlay(self, c, t):
        caption(c, "a squaring this size spends its time moving data", 985, prog(t, self.b(0, 0.2), 0.5) * (1 - prog(t, self.b(1, 0.0), 0.4)), 34)
        caption(c, "data moved per squaring, at the search frontier", 120, prog(t, self.b(1, 0.05), 0.5) * (1 - prog(t, self.b(2, 0.0), 0.4)), 32)
        a = prog(t, self.b(2, 0.05), 0.5) * (1 - prog(t, self.b(3, 0.0), 0.4))
        if a > 0:
            caption(c, "one full test at the frontier  ·  GeForce RTX 4090", 130, a, 32)
            rt = self.race_time()
            el = min(F.HOURS_PER_TEST["proth20"], max(0.0, (t - self.b(2, 0.1)) / rt) * F.HOURS_PER_TEST["proth20"])
            counter_pill(c, "hours:", f"{el:.1f}", W / 2, 985, a, INK, 40, align="center")
            ba = prog(t, self.b(2, 0.1) + rt + 0.2, 0.6, back)
            if ba > 0:
                c.save(); c.translate(1600, 985); c.scale(ba, ba)
                label_tag(c, f"{F.SPEEDUP:.1f}× faster", 0, 0, 44, "#1A1240", CYAN, a, "bold", 0.5)
                c.restore()
        a = prog(t, self.b(3, 0.05), 0.5)
        if a > 0:
            caption(c, "tests per kilowatt-hour", 130, a, 34)
            r = F.TESTS_PER_KWH["GPU · colbert"] / F.TESTS_PER_KWH["CPU · LLR2"]
            ba = prog(t, self.b(3, 0.62), 0.6, back)
            if ba > 0:
                c.save(); c.translate(W / 2, 230); c.scale(ba, ba)
                label_tag(c, f"≈ {r:.1f}× the tests per kWh of a CPU", 0, 0, 40, "#1A1240", CYAN, a, "bold", 0.5)
                c.restore()


# ======================================================================================
class Trust(Scene):
    ID = "15_trust"
    NUMBER, CHAPTER = "14", "Making sure it's right"

    def setup(self):
        self.sky = Sky(seed=43, nebulae=(CYAN, VIOLET, MINT))
        self.sfx(self.b(0, 0.05), "steps", 0.4)
        self.sfx(self.b(0, 0.32), "zap", 0.8)
        self.sfx(self.b(0, 0.75), "wrong", 0.7)
        self.sfx(self.b(1, 0.2), "water", 0.6)
        self.sfx(self.b(1, 0.7), "chime", 0.7)
        self.sfx(self.b(2, 0.35), "zap", 0.6)
        self.sfx(self.b(2, 0.5), "wrong", 0.6)
        self.sfx(self.b(2, 0.58), "rewind", 0.7)
        self.sfx(self.b(2, 0.82), "chime", 0.8)

    def draw(self, c, t):
        # b0: a cosmic ray flips one bit
        if t < self.b(1, 0.1):
            fa = prog(t, self.b(0, 0.03), 0.5) * (1 - prog(t, self.b(1, 0.0), self.d(1, 0.1)))
            y = 640
            rrect(c, 160, y - 20, 1600, 40, 20, "#2A2270", fa)
            u = prog(t, self.b(0, 0.05), self.d(0, 0.65), lin)
            rrect(c, 160, y - 20, max(40, 1600 * u), 40, 20, GOLD, fa * 0.9)
            for i in range(32):
                x = 190 + i * 49
                bit = "1" if (i * 7 + 3) % 5 < 2 else "0"
                flipped = i == 14 and t > self.b(0, 0.34)
                text(c, "1" if flipped else bit, x, y + 60, 26, CORAL if flipped else DIM, "mono", alpha=fa)
            hx = 160 + 1600 * u
            hiker(c, hx, y - 22, 80, t, GOLD, u < 0.999, fa, seed=2)
            ru = prog(t, self.b(0, 0.28), 0.35, inn)
            if 0 < ru < 1.0 or (t < self.b(0, 0.4) and ru >= 1):
                px, py = 190 + 14 * 49, y + 40
                sx, sy = px + 700, py - 700
                x2, y2 = lerp(sx, px, ru), lerp(sy, py, ru)
                line(c, lerp(sx, px, max(0, ru - 0.3)), lerp(sy, py, max(0, ru - 0.3)), x2, y2, CORAL, 6, fa)
                glow(c, x2, y2, 50, CORAL, 0.8 * fa)
            burst(c, 190 + 14 * 49, y + 60, prog(t, self.b(0, 0.34), 0.8, lin), CORAL, 10, 80, fa)
            wa = prog(t, self.b(0, 0.75), 0.6, back)
            if wa > 0:
                critter(c, 1700, y - 150, 60 * wa, "#8C86B8", t, label="×", seed=5, mood="worried", alpha=fa, label_color=CORAL)
        # b1: the tank never overflows
        if self.b(1, 0.0) < t < self.b(2, 0.1):
            fa = prog(t, self.b(1, 0.05), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.1)))
            lvl = 80 / 91 * prog(t, self.b(1, 0.2), self.d(1, 0.4), io)
            tank(c, 700, 860, 360, 560, lvl, 1.0, t, CYAN, fa)
            text(c, "room in the arithmetic: 91 bits", 980, 300, 36, CORAL, "display", "left", fa, shadow=1)
            text(c, "the largest value any input", 980, 860 - 560 * 80 / 91 - 10, 34, CYAN, "display", "left", fa * prog(t, self.b(1, 0.5), 0.5), shadow=1)
            text(c, "could ever produce: 80 bits", 980, 860 - 560 * 80 / 91 + 38, 34, CYAN, "display", "left", fa * prog(t, self.b(1, 0.5), 0.5), shadow=1)
            sa = prog(t, self.b(1, 0.7), 0.6, back)
            if sa > 0:
                c.save(); c.translate(1300, 720); c.scale(sa, sa)
                label_tag(c, "✓  proved before every run", 0, 0, 40, "#1A1240", MINT, fa, "bold", 0.5)
                c.restore()
        # b2: two walkers, checkpoints, a rewind
        if t > self.b(2, 0.0):
            fa = prog(t, self.b(2, 0.05), 0.5)
            x0, x1 = 240, 1700
            flags = [x0 + i * (x1 - x0) / 4 for i in range(5)]
            for yy, nm, colr in ((520, "calculation", GOLD), (760, "checksum", VIOLET)):
                curve(c, [(x0, yy), (x1, yy)], colr, 5, 0.35 * fa)
                text(c, nm, x0, yy + 50, 28, colr, "display", "left", fa)
            for fx in flags[1:]:
                curve(c, [(fx, 450), (fx, 800)], MINT, 3, 0.45 * fa, dash=[10, 10])
                flag(c, fx, 450, 90, MINT, fa, t)
            # path of the walkers: 0 -> f2 (flip near 1.5) -> back to f1 -> f2 -> f4
            T0 = self.b(2, 0.12)
            segs = [(0.0, 0.42, flags[0], flags[2]), (0.46, 0.56, flags[2], flags[1]), (0.58, 0.8, flags[1], flags[2]), (0.82, 0.98, flags[2], flags[4])]
            pos = flags[0]
            for f0, f1, a, b in segs:
                u = prog(t, self.b(2, f0), self.d(2, f1 - f0), io)
                if t >= self.b(2, f0):
                    pos = lerp(a, b, u)
            walking = any(self.b(2, f0) < t < self.b(2, f1) for f0, f1, _, _ in segs)
            hiker(c, pos, 520 - 6, 70, t, GOLD, walking, fa, seed=1)
            hiker(c, pos, 760 - 6, 70, t, VIOLET, walking, fa, seed=2)
            sp = (flags[1] + flags[2]) / 2
            if self.b(2, 0.32) < t < self.b(2, 0.58):
                burst(c, sp, 520, prog(t, self.b(2, 0.35), 0.8, lin), CORAL, 10, 70, fa)
                glow(c, sp, 520, 40, CORAL, 0.7 * fa)
            ne = prog(t, self.b(2, 0.44), 0.4, back) * (1 - prog(t, self.b(2, 0.58), 0.3))
            text(c, "≠", flags[2], 640, 70 * max(0.01, ne), CORAL, "display", alpha=fa * clamp(ne))
            if self.b(2, 0.46) < t < self.b(2, 0.6):
                bezier(c, (flags[2], 420), ((flags[1] + flags[2]) / 2, 330), (flags[1], 420), CYAN, 5, fa, upto=prog(t, self.b(2, 0.46), 0.5))
                text(c, "rewind", (flags[1] + flags[2]) / 2, 300, 34, CYAN, "display", alpha=fa)
            eq = prog(t, self.b(2, 0.8), 0.4, back)
            if eq > 0:
                text(c, "=", flags[2], 640, 70, MINT, "display", alpha=fa)
            for i in (3, 4):
                if t > self.b(2, 0.82) + (i - 2) * self.d(2, 0.16) / 2:
                    text(c, "=", flags[i], 640, 70, MINT, "display", alpha=fa)
            text(c, "=", flags[1], 640, 70, MINT, "display", alpha=fa * prog(t, self.b(2, 0.25), 0.3))

    def overlay(self, c, t):
        caption(c, "one flipped bit: a wrong answer, and nothing to show it", 985, prog(t, self.b(0, 0.6), 0.5) * (1 - prog(t, self.b(1, 0.0), 0.4)), 32, CORAL)
        caption(c, "the Gerbicz–Li check: compare, and rewind on any mismatch", 985, prog(t, self.b(2, 0.1), 0.5), 32)


# ======================================================================================
class Impact(Scene):
    ID = "16_impact"
    NUMBER, CHAPTER = "15", "What it means for the search"

    def setup(self):
        self.sky = Sky(seed=45)
        self.sfx(self.b(0, 0.1), "rise", 0.6)
        self.sfx(self.b(1, 0.05), "shimmer", 0.6)
        self.sfx(self.b(1, 0.35), "whoosh", 0.7)
        for i in range(10):
            self.sfx(self.b(2, 0.2 + i * 0.06), "tick", 0.35)
        self.sfx(self.b(3, 0.25), "twinkle", 0.8)
        self.sfx(self.b(3, 0.6), "swell", 0.8)
        W_, H_ = 1036, 500
        self.gw, self.gh = W_, H_
        self.gold = (H_ // 2) * W_ + W_ // 2 + 7
        rng = np.random.default_rng(3)
        b = rng.uniform(0.35, 0.8, (H_, W_))
        img = np.zeros((H_, W_, 4), np.uint8)
        img[..., 0] = (150 * b).astype(np.uint8); img[..., 1] = (140 * b).astype(np.uint8); img[..., 2] = (220 * b).astype(np.uint8)
        img[..., 3] = (255 * b).astype(np.uint8)
        g = self.gold
        img.reshape(-1, 4)[g] = (255, 210, 80, 255)
        self.field = skia.Image.fromarray(img, colorType=skia.ColorType.kRGBA_8888_ColorType)
        rng = np.random.default_rng(8)
        self.houses = [(a, rng.choice([CORAL, VIOLET, TEAL, AMBER, ROSE]), rng.uniform(24, 36)) for a in np.linspace(-50, 50, 30) if abs(a) > 5]

    def draw(self, c, t):
        # b0: the odds
        if t < self.b(1, 0.1):
            fa = prog(t, self.b(0, 0.03), 0.5) * (1 - prog(t, self.b(1, 0.0), self.d(1, 0.1)))
            x, y, R = 640, 560, 250
            ring(c, x, y, R, "#2A2270", 46, fa)
            fr = F.EXPECTED_PRIMES * prog(t, self.b(0, 0.1), self.d(0, 0.4), out)
            if fr > 0:
                arc(c, x, y, R, -90, 360 * fr, GOLD, 46, fa)
                glow(c, x + R * math.cos(math.radians(-90 + 360 * fr)), y + R * math.sin(math.radians(-90 + 360 * fr)), 80, GOLD, 0.6 * fa)
            text(c, f"{fr:.2f}", x, y - 10, 110, GOLD, "display", alpha=fa, shadow=1)
            text(c, "expected primes", x, y + 80, 34, SOFT, "body", alpha=fa)
            ta = prog(t, self.b(0, 0.5), 0.6)
            text(c, "about a one-in-five chance", 1350, 470, 48, INK, "display", alpha=fa * ta, shadow=1)
            text(c, "of even one prime", 1350, 540, 48, INK, "display", alpha=fa * ta, shadow=1)
            text(c, "n from 47.9 M to 57.5 M  ·  all five k", 1350, 640, 32, SOFT, "body", alpha=fa * ta)
        # b1: half a million tests per prime: from close-up to the whole field
        if self.b(1, 0.0) < t < self.b(2, 0.1):
            fa = prog(t, self.b(1, 0.03), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.1)))
            fw = 1500.0
            fh = fw * self.gh / self.gw
            fx, fy = W / 2 - fw / 2, 560 - fh / 2
            z = lerp(28.0, 1.0, prog(t, self.b(1, 0.3), self.d(1, 0.35), io))
            gx = fx + (self.gold % self.gw + 0.5) * fw / self.gw
            gy = fy + (self.gold // self.gw + 0.5) * fh / self.gh
            c.save()
            c.translate(gx, gy); c.scale(z, z); c.translate(-gx, -gy)
            if z > 6:
                # close-up: draw the neighbourhood as distinct dots
                cw = int(40 * 28 / z) + 4
                ch = int(18 * 28 / z) + 4
                gi, gj = self.gold % self.gw, self.gold // self.gw
                step = fw / self.gw
                for i in range(gi - cw // 2, gi + cw // 2 + 1):
                    for j in range(gj - ch // 2, gj + ch // 2 + 1):
                        px, py = fx + (i + 0.5) * step, fy + (j + 0.5) * step
                        isg = (i == gi and j == gj)
                        rr = step * 0.32
                        if isg:
                            glow(c, px, py, step * 1.6, GOLD, 0.7 * fa)
                        c.drawCircle(px, py, rr, paint(GOLD if isg else "#8C84D8", fa * (1 if isg else 0.8)))
            else:
                c.drawImageRect(self.field, skia.Rect.MakeXYWH(fx, fy, fw, fh), skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(Alphaf=fa))
                glow(c, gx, gy, 30, GOLD, 0.9 * fa)
                ring(c, gx, gy, 18, GOLD, 3, fa)
            c.restore()
        # b2: volunteers' graphics cards joining
        if self.b(2, 0.0) < t < self.b(3, 0.12):
            fa = prog(t, self.b(2, 0.03), 0.5) * (1 - prog(t, self.b(3, 0.0), self.d(3, 0.12)))
            PX, PY, PR = 960, 1650, 850
            planet(c, PX, PY, PR, t, alpha=fa)
            gx, gy = PX, PY - PR
            tower(c, gx, gy, 220, t, GOLD, fa)
            for i, (a, colr, s) in enumerate(self.houses):
                u = prog(t, self.b(2, 0.1 + i * 0.022), 0.5, back)
                if u <= 0:
                    continue
                ar = math.radians(a)
                x, y = PX + PR * math.sin(ar), PY - PR * math.cos(ar)
                house(c, x, y, s * u, t, ang=a, lit=1.0, color=colr, seed=i)
                if u >= 1 and i % 2 == 0:
                    beam(c, x, y - 30, gx, gy - 230, t, CYAN, 0.45 * fa, 2, 1.0, 0.7, seed=i)
        # b3: five dark stars
        if t > self.b(3, 0.0):
            fa = prog(t, self.b(3, 0.05), 0.8)
            for i, k in enumerate(F.REMAINING_K):
                x, y = FIVE_POS[k]
                y += 200
                lit = 0.0
                if i == 0:
                    lit = 0.25 * prog(t, self.b(3, 0.25), 1.5) * (0.6 + 0.4 * math.sin(t * 2))
                star(c, x, y, 18, GOLD, t, lit=lit, seed=i, alpha=fa)
                text(c, str(k), x, y + 60, 34, CORAL, "display", alpha=fa, shadow=1)
            qa = prog(t, self.b(3, 0.3), 0.8)
            x, y = FIVE_POS[F.REMAINING_K[0]]
            text(c, "?", x + 50, y + 120 + 8 * math.sin(t * 2), 70, GOLD, "display", alpha=fa * qa, shadow=1)
            for i in range(4):
                (x1, y1), (x2, y2) = FIVE_POS[F.REMAINING_K[i]], FIVE_POS[F.REMAINING_K[i + 1]]
                line(c, x1, y1 + 200, x2, y2 + 200, LILAC, 2, 0.4 * fa)

    def overlay(self, c, t):
        a = prog(t, self.b(1, 0.05), 0.5) * (1 - prog(t, self.b(2, 0.0), 0.4))
        if a > 0:
            caption(c, "each dot: one 14-million-digit test", 120, a, 32)
            v = prog(t, self.b(1, 0.62), 0.6, back)
            if v > 0:
                c.save(); c.translate(W / 2, 985); c.scale(v, v)
                label_tag(c, "≈ 518,000 tests per prime, on average", 0, 0, 40, "#1A1240", GOLD, a, "bold", 0.5)
                c.restore()
        caption(c, "every graphics card that can join widens the circle", 985, prog(t, self.b(2, 0.4), 0.5) * (1 - prog(t, self.b(3, 0.0), 0.4)), 34)
        a = prog(t, self.b(3, 0.55), 0.8)
        if a > 0:
            big_title(c, "five dark stars", W / 2, 230, 80, INK, a)


# ======================================================================================
class Credits(Scene):
    ID = "17_credits"

    def setup(self):
        self.sky = Sky(seed=47)
        self.sfx(self.b(0, 0.05), "swell", 0.7)

    def draw(self, c, t):
        a = prog(t, self.b(0, 0.02), 0.8)
        for i, k in enumerate(F.REMAINING_K):
            x, y = FIVE_POS[k]
            star(c, x, y - 120, 12, GOLD, t, lit=0, seed=i, alpha=a)
        big_title(c, "colbert", W / 2, 400, 130, CYAN, a, CYAN)
        text(c, F.REPO_URL, W / 2, 510, 40, INK, "mono", alpha=prog(t, self.b(0, 0.12), 0.6))
        b = prog(t, self.b(0, 0.25), 0.6)
        text(c, "built on the work of", W / 2, 640, 30, SOFT, "body", alpha=b)
        text(c, "Richard Crandall · Barry Fagin · Colin Percival · George Woltman · Yves Gallot · Robert Gerbicz · Darren Li", W / 2, 695, 30, INK, "body", alpha=b)
        text(c, "and the volunteers of Seventeen or Bust and PrimeGrid", W / 2, 790, 36, GOLD, "display", alpha=prog(t, self.b(0, 0.4), 0.6), shadow=1)


# ======================================================================================
class Thumbnail(Scene):
    """not part of the film: the YouTube thumbnail (render with build.py thumbnail)"""
    ID = "17_credits"

    def setup(self):
        self.sky = Sky(seed=51, nebulae=(VIOLET, ROSE, AMBER))

    def frame(self, c, t):
        self.background(c, 2.0, (W / 2, H / 2))
        glow(c, 1420, 600, 620, AMBER, 0.35)
        critter(c, 1420, 620, 250, GOLD, 2.0, label="?", seed=2, mood="wow", glowing=True, look=(-0.5, -0.3), label_scale=1.3)
        for i, k in enumerate(F.REMAINING_K):
            x, y = 120 + i * 170, 170 + 30 * math.sin(i * 1.3)
            star(c, x, y, 20, GOLD, 2.0, lit=1.0 if i == 2 else 0.0, seed=i)
        for i in range(4):
            line(c, 120 + i * 170, 170 + 30 * math.sin(i * 1.3), 120 + (i + 1) * 170, 170 + 30 * math.sin((i + 1) * 1.3), LILAC, 3, 0.45)
        glow(c, 560, 520, 700, VIOLET, 0.45)
        text(c, "THE LAST", 560, 450, 190, INK, "display", shadow=1.5)
        text(c, "FIVE", 560, 640, 230, GOLD, "display", shadow=1.5)
        label_tag(c, "14.4-million-digit primes", 560, 830, 50, "#1A1240", CREAM, 1.0, "bold", 0.5)
        grain(c, 0); vignette(c, 0.45)
