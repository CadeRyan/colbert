"""01–05: the story of the Sierpiński problem."""
from .common import *
import skia


# ======================================================================================
class ColdOpen(Scene):
    ID = "01_cold_open"
    STAR_ALPHA = 0.6

    def setup(self):
        self.sky = Sky(seed=3, top="#07051A", bottom="#1A1248")
        self.digits = load("candidate.json")["leading"]
        self.cand = load("candidate.json")
        self.sfx(0.2, "whoosh", 0.8)
        self.sfx(self.b(1, 0.12), "pop")
        for i in range(5):
            self.sfx(self.b(1, 0.42 + i * 0.06), "twinkle", 0.6)
        self.sfx(self.b(2, 0.12), "swell")

    def draw(self, c, t):
        # b0: a highway of the number's real digits flying past
        hw = 1 - prog(t, self.b(1, 0.0), self.d(1, 0.25))
        if hw > 0:
            yh = 420
            glow(c, W / 2, yh, 700, VIOLET, 0.35 * hw)
            rows = 15
            for k in range(rows):
                z = 4.0 - ((k * 0.26 + t * 0.75) % 3.9)
                if z < 0.12:
                    continue
                y = yh + 300 / z
                size = 30 / z
                a = hw * smooth((4.0 - z) / 1.8) * smooth((z - 0.12) / 0.5)
                s = self.digits[(k * 47) % 1900:(k * 47) % 1900 + 64]
                colr = mix(LILAC, GOLD, clamp(1.4 - z / 3))
                text(c, s, W / 2, y, size, colr, "mono", alpha=a)
            ca = prog(t, self.b(0, 0.35), 0.8) * hw
            caption(c, f"{fmt(self.cand['digits'])} digits", 980, ca, 36, GOLD)
        # b1: the number as a creature, five dark stars
        ap = prog(t, self.b(1, 0.1), 0.7, back)
        fa = 1 - prog(t, self.b(2, 0.0), self.d(2, 0.15))
        if ap > 0 and fa > 0:
            r = 115 * ap
            critter(c, W / 2, 600, r, "#8E86C9", t, mood="wow", look=(0, -0.6), alpha=fa, seed=2)
            qa = prog(t, self.b(1, 0.25), 0.5)
            text(c, "?", W / 2 + 120, 470 + 10 * math.sin(t * 2), 110, GOLD, "display", alpha=qa * fa, shadow=1)
            ra = prog(t, self.b(1, 0.2), 0.6)
            rich(c, [("21181", CORAL), (" × 2", INK), ("^47,856,068", INK), (" + 1", INK)], W / 2, 810, 58, alpha=ra * fa, face="display", shadow=1)
        for i, k in enumerate(F.REMAINING_K):
            sa = prog(t, self.b(1, 0.42 + i * 0.06), 0.5, back)
            if sa <= 0:
                continue
            x, y = FIVE_POS[k]
            x2, y2 = x, y - 90
            u = prog(t, self.b(2, 0.05), self.d(2, 0.25))
            px, py = lerp(x2, x, u), lerp(y2 - 40, y + 10, u)
            star(c, px, py, 13 * sa, GOLD, t, lit=0, seed=i)
            if i == 0 and fa > 0:
                pr = pulse((t - self.b(1, 0.7)) % 1.6, 0, 1.6) if t > self.b(1, 0.7) else 0
                ring(c, px, py, 26 + 18 * pr, CORAL, 3, 0.8 * pr * fa)
        # b2: title, constellation lines
        ta = prog(t, self.b(2, 0.12), self.d(2, 0.25))
        if ta > 0:
            ks = F.REMAINING_K
            for i in range(4):
                lu = prog(t, self.b(2, 0.2 + i * 0.07), 0.6)
                (x1, y1), (x2, y2) = FIVE_POS[ks[i]], FIVE_POS[ks[i + 1]]
                y1 += 10; y2 += 10
                line(c, x1, y1, lerp(x1, x2, lu), lerp(y1, y2, lu), LILAC, 2, 0.45 * lu)
            big_title(c, "THE LAST FIVE", W / 2, 560, 150 * (0.92 + 0.08 * back(prog(t, self.b(2, 0.12), 0.8))), INK, ta)
            text(c, "the hunt for the final Colbert primes", W / 2, 690, 40, SOFT, "body", alpha=prog(t, self.b(2, 0.3), 0.8))

    def camera(self, t):
        return (W / 2 + 20 * math.sin(t * 0.2), H / 2, 1.0)


# ======================================================================================
class Sierpinski(Scene):
    ID = "02_sierpinski"
    STAR_ALPHA = 0.7
    NUMBER, CHAPTER = "1", "Sierpiński's question"

    def setup(self):
        self.sky = Sky(seed=5, horizon=ROSE)
        self.seq = load("sequences.json")["3"][:7]
        self.cov = load("covering.json")
        self.fac = {25: [5, 5], 49: [7, 7], 385: [5, 7, 11]}
        for i in range(5):
            self.sfx(self.b(0, 0.2 + i * 0.13), "pop", 0.6)
        for i in range(7):
            self.sfx(self.b(1, 0.05 + i * 0.08), "pop" if not self.seq[i][2] else "chime", 0.7)
        self.sfx(self.b(2, 0.05), "whoosh", 0.6)
        self.sfx(self.b(3, 0.05), "swell", 0.7)
        self.sfx(self.b(4, 0.1), "chime", 0.8)

    def draw(self, c, t):
        far_hills(c, t)
        hill(c, t)
        # the k creature
        kx, ky, kr = 250, 800, 82
        kfade = 1 - prog(t, self.b(3, 0.0), self.d(3, 0.08))
        if kfade > 0:
            lab = "k" if t < self.b(1, 0.03) else ("3" if t < self.b(2, 0.05) else "k")
            colr = CORAL if lab == "k" else LILAC
            critter(c, kx, ky, kr * back(prog(t, 0.3, 0.8)), colr, t, label=lab, seed=1, mood="happy", look=(1, -0.3), alpha=kfade)
        # b0: the recipe, as floating bubbles
        if t < self.b(1, 0.12):
            fa = 1 - prog(t, self.b(1, 0.0), self.d(1, 0.1))
            mults = [2, 4, 8, 16, 32]
            for i, m in enumerate(mults):
                u = prog(t, self.b(0, 0.2 + i * 0.13), 0.6, back)
                if u <= 0:
                    continue
                x = 520 + i * 260
                y = 600 - 60 * math.sin(i * 0.8) + 8 * math.sin(t * 1.5 + i)
                c.save(); c.translate(x, y); c.scale(u, u)
                label_tag(c, f"k × {m} + 1", 0, 0, 34, INK, SLATE, fa)
                c.restore()
                if i > 0:
                    px = 520 + (i - 1) * 260
                    bezier(c, (px + 95, 600 - 60 * math.sin((i - 1) * 0.8)), (x - 130, y - 90), (x - 95, y), GOLD, 3, 0.5 * fa * u, dash=[8, 8])
            if t > self.b(0, 0.85):
                text(c, "…", 520 + 5 * 260, 580, 60, SOFT, "display", alpha=fa * prog(t, self.b(0, 0.85), 0.4))
        # b1: k = 3, the sequence as creatures; composites crack into factors
        if self.b(1, 0.0) < t < self.b(2, 0.25):
            fa = 1 - prog(t, self.b(2, 0.05), self.d(2, 0.18))
            for i, (n, v, pr) in enumerate(self.seq):
                t0 = self.b(1, 0.05 + i * 0.08)
                u = prog(t, t0, 0.55, back)
                if u <= 0:
                    continue
                x = 470 + i * 205
                y = 820
                v = int(v)
                if pr:
                    critter(c, x, y, 62 * u, GOLD, t, label=v, seed=10 + i, mood="happy", glowing=True, alpha=fa, look=(-0.4, -0.2))
                    burst(c, x, y, prog(t, t0, 0.8, linear_u), GOLD, 10, 110, fa)
                else:
                    cu = prog(t, t0 + 0.6, 1.0, io)
                    if cu <= 0:
                        critter(c, x, y, 62 * u, "#8C86B8", t, label=v, seed=10 + i, mood="calm", alpha=fa)
                    else:
                        cracked(c, x, y, 62, "#8C86B8", cu, self.fac[v], t, seed=10 + i, alpha=fa, fcolor="#A9A3D3")
            la = prog(t, self.b(1, 0.7), 0.6) * fa
            if la > 0:
                for i, (n, v, pr) in enumerate(self.seq):
                    if pr:
                        text(c, "prime", 470 + i * 205, 935, 24, GOLD, "display", alpha=la)
        # b2: Sierpiński, 1960: an endless march of composites
        if self.b(2, 0.0) < t < self.b(3, 0.15):
            fa = 1 - prog(t, self.b(3, 0.0), self.d(3, 0.12))
            pa = prog(t, self.b(2, 0.05), 0.6, back)
            c.save(); c.translate(W / 2, 170); c.scale(pa, pa)
            label_tag(c, "1960  ·  Wacław Sierpiński", 0, 0, 40, INK, "#3A2C86", fa)
            c.restore()
            ma = prog(t, self.b(2, 0.2), 1.0) * fa
            if ma > 0:
                t0 = self.b(2, 0.2)
                for i in range(12):
                    x = 2150 - ((t - t0) * 140 + i * 205) % 2300 + 0
                    if x < 380 or x > 2000:
                        continue
                    edge = smooth((x - 380) / 150) * smooth((2000 - x) / 200)
                    critter(c, x, 830, 56, "#7D78A8", t, label=None, seed=40 + i, mood="worried", alpha=ma * edge)
                    curve(c, [(x - 4, 778), (x + 8, 800), (x - 2, 818), (x + 6, 840)], "#1A1240", 3.5, ma * edge * 0.9)
                caption(c, "never a prime", 985, ma, 34, CORAL)
        # b3: Selfridge, 1962: 78557 and its seven guards
        if t > self.b(3, 0.0) and t < self.b(4, 0.3):
            fa = 1 - prog(t, self.b(4, 0.0), self.d(4, 0.25))
            pa = prog(t, self.b(3, 0.02), 0.6, back)
            c.save(); c.translate(W / 2, 170); c.scale(pa, pa)
            label_tag(c, "1962  ·  John Selfridge", 0, 0, 40, INK, "#3A2C86", fa)
            c.restore()
            mx, my = 560, 600
            u = prog(t, self.b(3, 0.05), 0.7, back)
            critter(c, mx, my, 120 * u, CORAL, t, label="78557", seed=3, mood="calm", alpha=fa, look=(0.6, 0))
            primes = self.cov["primes"]
            spin = (t - self.b(3, 0.0)) * 0.35
            for i, p in enumerate(primes):
                mu = prog(t, self.b(3, 0.12 + i * 0.03), 0.6, back)
                if mu <= 0:
                    continue
                ang = spin + i * 2 * math.pi / 7
                px, py = mx + math.cos(ang) * 245, my + math.sin(ang) * 175
                critter(c, px, py, 38 * mu, COVER_COL[p], t, label=p, seed=60 + i, mood="happy", alpha=fa, look=(math.cos(ang + math.pi) * 0.6, 0))
            # the 36-slot wheel
            wx, wy, R1, R0 = 1400, 590, 250, 165
            wa = prog(t, self.b(3, 0.3), 0.8) * fa
            if wa > 0:
                step_t0 = self.b(3, 0.45)
                rate = 36 / max(1.0, self.d(3, 0.5))
                nstep = max(0.0, (t - step_t0) * rate)
                rot = -nstep * 10.0
                for n in range(36):
                    p = self.cov["slot_prime"][n]
                    a0 = -90 + n * 10 + rot
                    path = skia.Path()
                    path.addArc(skia.Rect.MakeXYWH(wx - R1, wy - R1, 2 * R1, 2 * R1), a0 + 0.6, 8.8)
                    path.arcTo(skia.Rect.MakeXYWH(wx - R0, wy - R0, 2 * R0, 2 * R0), a0 + 9.4, -8.8, False)
                    path.close()
                    c.drawPath(path, paint(COVER_COL[p], wa * 0.92))
                c.drawCircle(wx, wy, R0 - 8, paint("#1A1248", wa))
                cur = int(nstep) % 36 if nstep > 0 else 0
                cp = self.cov["slot_prime"][cur]
                text(c, "every n", wx, wy - 22, 30, SOFT, "body", alpha=wa)
                text(c, f"÷ {cp}", wx, wy + 24, 46, COVER_COL[cp], "display", alpha=wa)
                poly(c, [(wx - 18, wy - R1 - 34), (wx + 18, wy - R1 - 34), (wx, wy - R1 - 4)], INK, wa)
                if nstep > 0:
                    i = primes.index(cp)
                    ang = spin + i * 2 * math.pi / 7
                    px, py = mx + math.cos(ang) * 245, my + math.sin(ang) * 175
                    beam(c, px, py, wx, wy - R1 - 20, t, COVER_COL[cp], 0.8 * wa, 3, 1.0, 2.0)
                caption(c, "the same pattern, every 36 steps, forever", 985, prog(t, self.b(3, 0.75), 0.6) * fa, 32)
        # b4: is 78,557 the smallest?
        if t > self.b(4, 0.1):
            qa = prog(t, self.b(4, 0.1), 0.8)
            u = prog(t, self.b(4, 0.12), 0.8, back)
            critter(c, W / 2, 700, 110 * u, CORAL, t, label="78557", seed=3, mood="happy", glowing=True)
            rng = np.random.default_rng(9)
            for i in range(14):
                side = -1 if i % 2 == 0 else 1
                x = W / 2 + side * (230 + (i // 2) * 105) + rng.uniform(-20, 20)
                sa = prog(t, self.b(4, 0.25 + i * 0.025), 0.5, back)
                if 0 < x < W and sa > 0:
                    critter(c, x, 845 - (i // 2) * 6, 40 * sa, "#8E86C9", t, seed=80 + i, mood="wow", look=(-side * 0.7, -0.8))
            big_title(c, "Is 78,557 the smallest?", W / 2, 260, 84, GOLD, qa, glow_col=AMBER)


def linear_u(u):
    return clamp(u)


# ======================================================================================
class Elimination(Scene):
    ID = "03_elimination"
    STAR_ALPHA = 0.5
    NUMBER, CHAPTER = "2", "A sky of candidates"
    GW, GH = 286, 138

    def setup(self):
        self.sky = Sky(seed=7, stars=180)
        fp = load("first_prime.json")["first_n"]
        ks = np.arange(1, 78557, 2)
        self.first = np.array([fp[str(k)] if fp[str(k)] is not None else -1 for k in ks], dtype=float)
        sev = set(F.SEVENTEEN)
        self.is17 = np.array([k in sev for k in ks])
        n = len(ks)
        self.n = n
        rng = np.random.default_rng(3)
        cells = rng.permutation(self.GW * self.GH)[:n]
        col_, row = cells % self.GW, cells // self.GW
        self.x = 20 + (col_ + rng.uniform(0, 1, n)) * (1880 / self.GW)
        self.y = 30 + (row + rng.uniform(0, 1, n)) * (1020 / self.GH)
        ex = np.abs(self.x - W / 2) / (W / 2); ey = np.abs(self.y - H / 2) / (H / 2)
        self.edge = np.clip(1.25 - np.sqrt(ex ** 2 + ey ** 2) * 0.55, 0.25, 1.0)
        self.ph = rng.uniform(0, 6.28, n)
        self.sp = rng.uniform(1.0, 3.0, n)
        self.pos17 = {k: (float(self.x[(k - 1) // 2]), float(self.y[(k - 1) // 2])) for k in F.SEVENTEEN}
        self.sfx(self.b(0, 0.05), "shimmer", 0.7)
        self.sfx(self.b(1, 0.02), "rise", 0.8)
        self.sfx(self.b(2, 0.05), "twinkle", 0.8)
        self.sfx(self.b(2, 0.45), "whoosh", 0.6)

    def nval(self, t):
        u = prog(t, self.b(1, 0.02), self.d(1, 0.62), io)
        return math.expm1(u * math.log1p(1200))

    def field(self, c, t, alpha):
        n_now = self.nval(t)
        rest_fade = prog(t, self.b(1, 0.66), self.d(1, 0.3))
        lit = (self.first >= 0) & (self.first <= n_now)
        age = np.where(lit, (n_now - self.first) / (0.2 * n_now + 1.5), 0)
        flash = np.clip(1 - age, 0, 1) * lit
        rest = (self.first < 0) & ~self.is17
        litf = np.where(lit, 1.0, 0.0) + np.where(rest, rest_fade, 0.0)
        tw = 0.7 + 0.3 * np.sin(t * self.sp + self.ph)
        # draw into a 2x-resolution buffer then upscale (soft dots), plus a blurred glow pass
        sc = 0.5
        w, h = int(W * sc), int(H * sc)
        buf = np.zeros((h, w, 4), np.float32)
        xi = np.clip((self.x * sc).astype(int), 0, w - 1)
        yi = np.clip((self.y * sc).astype(int), 0, h - 1)
        dim = np.array([150, 140, 215], np.float32)
        warm = np.array([255, 210, 110], np.float32)
        white = np.array([255, 255, 255], np.float32)
        c3 = dim[None, :] * (1 - litf[:, None]) + warm[None, :] * litf[:, None]
        c3 = c3 * (1 - flash[:, None]) + white[None, :] * flash[:, None]
        a = np.clip(np.where(self.is17, 0.0, (0.62 + 0.6 * litf) * tw) * alpha * self.edge, 0, 1)
        buf[yi, xi, :3] = c3
        buf[yi, xi, 3] = a
        rgba = np.dstack([buf[..., :3] * buf[..., 3:4], buf[..., 3:4] * 255]).clip(0, 255).astype(np.uint8)
        img = skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.ColorType.kRGBA_8888_ColorType, alphaType=skia.AlphaType.kPremul_AlphaType)
        c.save(); c.scale(1 / sc, 1 / sc)
        gp = skia.Paint(ImageFilter=skia.ImageFilters.Blur(3.0, 3.0), BlendMode=skia.BlendMode.kPlus)
        c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), gp)
        c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), gp)
        c.drawImage(img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear), skia.Paint(BlendMode=skia.BlendMode.kPlus))
        c.restore()

    def draw(self, c, t):
        fa = prog(t, self.b(0, 0.02), self.d(0, 0.3)) * (1 - prog(t, self.b(2, 0.4), self.d(2, 0.3)))
        if fa > 0:
            self.field(c, t, fa)
        # the 17 dark stars
        for i, k in enumerate(F.SEVENTEEN):
            x0, y0 = self.pos17[k]
            x1, y1 = SEV_POS[k]
            u = prog(t, self.b(2, 0.42 + i * 0.012), self.d(2, 0.35))
            hl = prog(t, self.b(2, 0.05), 0.8, back)
            x, y = lerp(x0, x1, u), lerp(y0, y1, u)
            star(c, x, y, (5 + 9 * hl) * (1 + 0.4 * u * 0), GOLD, t, lit=0, seed=i, alpha=max(0.35, hl) * prog(t, self.b(0, 0.1), 1.0))

    def overlay(self, c, t):
        a0 = prog(t, self.b(0, 0.25), 0.8) * (1 - prog(t, self.b(1, 0.0), 0.6))
        caption(c, "every odd number below 78,557  =  one star", 985, a0, 34)
        a1 = prog(t, self.b(1, 0.0), 0.5) * (1 - prog(t, self.b(2, 0.3), 0.6))
        if a1 > 0:
            counter_pill(c, "first prime found by n =", fmt(int(self.nval(t))), W - 60, 120, a1)
            n_now = self.nval(t)
            dark = int(np.sum(~((self.first >= 0) & (self.first <= n_now))) - np.sum((self.first < 0) & ~self.is17) * prog(t, self.b(1, 0.66), self.d(1, 0.3)))
            counter_pill(c, "still dark:", fmt(dark), W - 60, 985, a1, INK)
        a2 = prog(t, self.b(1, 0.66), 0.6) * (1 - prog(t, self.b(2, 0.0), 0.5))
        caption(c, "…and decades of bigger searches", 985, a2 * 0, 32)
        a3 = prog(t, self.b(2, 0.6), 0.8)
        if a3 > 0:
            big_title(c, "2002: seventeen still dark", W / 2, 640, 64, INK, a3)


# ======================================================================================
class SeventeenOrBust(Scene):
    ID = "04_seventeen_or_bust"
    STAR_ALPHA = 1.0
    NUMBER, CHAPTER = "3", "Seventeen or Bust"
    PX, PY, PR = 960, 1730, 900

    def setup(self):
        self.sky = Sky(seed=11)
        rng = np.random.default_rng(5)
        self.houses = [(a, rng.choice([CORAL, VIOLET, TEAL, AMBER, ROSE]), rng.uniform(26, 40)) for a in np.linspace(-48, 48, 23) if abs(a) > 4]
        self.found = [p for p in F.SOB_PRIMES if p[2] <= 2007]
        for i in range(len(self.houses)):
            self.sfx(self.b(0, 0.15 + i * 0.022), "tick", 0.35)
        for i in range(len(self.found)):
            self.sfx(self.b(1, 0.12 + i * 0.065) + 0.25, "chime", 0.6)
        self.sfx(self.b(2, 0.04), "crash", 0.8)
        self.sfx(self.b(2, 0.18), "rise", 0.7)
        self.sfx(self.b(2, 0.3), "boom", 0.9)
        self.sfx(self.b(3, 0.1), "shimmer", 0.8)
        self.sfx(self.b(4, 0.1), "whoosh", 0.6)

    def surface(self, a_deg, h=0.0):
        a = math.radians(a_deg)
        return self.PX + (self.PR + h) * math.sin(a), self.PY - (self.PR + h) * math.cos(a)

    def star_state(self, t, k):
        """lit amount for star k"""
        for i, (kk, n, yr) in enumerate(self.found):
            if kk == k:
                return prog(t, self.b(1, 0.12 + i * 0.065) + 0.25, 0.4)
        if k == 10223:
            return prog(t, self.b(2, 0.3), 0.4)
        return 0.0

    def draw(self, c, t):
        rot = t * 1.2
        planet(c, self.PX, self.PY, self.PR, t, rot=math.radians(rot) * 0.2)
        # houses with computers
        for i, (a, colr, s) in enumerate(self.houses):
            u = prog(t, self.b(0, 0.15 + i * 0.022), 0.5, back)
            if u <= 0:
                continue
            x, y = self.surface(a)
            house(c, x, y, s * u, t, ang=a, lit=1.0, color=colr, seed=i)
        # server tower, then PrimeGrid
        tx, ty = self.surface(0)
        brk = prog(t, self.b(2, 0.04), 0.9, inn)
        ta = prog(t, self.b(0, 0.05), 0.6)
        tower(c, tx, ty, 220, t, TEAL, ta * (1 - brk * 0.8), broken=brk)
        rise = prog(t, self.b(2, 0.16), 0.9, back)
        gx, gy = self.surface(9)
        if rise > 0:
            c.save(); c.translate(gx, gy); c.rotate(9); c.translate(-gx, -gy)
            tower(c, gx, gy, 240 * rise, t, GOLD)
            c.restore()
        hub = (tx, ty - 230) if t < self.b(2, 0.1) else (gx + 30, gy - 250)
        # volunteer beams to the hub
        ba = prog(t, self.b(0, 0.55), 1.0) * (1 - 0.8 * brk * (1 - rise))
        for i, (a, colr, s) in enumerate(self.houses[::2]):
            x, y = self.surface(a, 30)
            beam(c, x, y, hub[0], hub[1], t, GOLD, 0.35 * ba, 2, 1.0, 0.6, seed=i)
        # stars
        for i, k in enumerate(F.SEVENTEEN):
            x, y = SEV_POS[k]
            lit = self.star_state(t, k)
            five = k in F.REMAINING_K
            if five:
                u = prog(t, self.b(4, 0.1), self.d(4, 0.4))
                x, y = lerp(x, FIVE_POS[k][0], u), lerp(y, FIVE_POS[k][1] + 80, u)
            dim = 1 - 0.85 * prog(t, self.b(4, 0.1), self.d(4, 0.3)) if not five else 1
            colb = prog(t, self.b(3, 0.1), 0.8) * (1 - prog(t, self.b(4, 0.05), 0.6))
            star(c, x, y, 12 + (4 if five and t > self.b(4, 0.1) else 0), GOLD, t, lit=lit, seed=i, alpha=dim)
            for j, (kk, n, yr) in enumerate(self.found + [(10223, 31172165, 2016)]):
                if kk == k and lit > 0:
                    bt = self.b(1, 0.12 + j * 0.065) if kk != 10223 else self.b(2, 0.3) - 0.25
                    bu = prog(t, bt, 0.3)
                    if bu < 1 or t < bt + 0.6:
                        beam(c, hub[0], hub[1], x, y, t, GOLD, 0.9 * (1 - prog(t, bt + 0.4, 0.4)), 3, bu)
                    burst(c, x, y, prog(t, bt + 0.25, 0.9, clamp), GOLD, 10, 70 if kk != 10223 else 160)
                    text(c, str(yr), x, y + 42, 22, SOFT, "body", alpha=lit * dim * (1 - colb * 0.6) * (1 - prog(t, self.b(4, 0.0), 0.5)))
                    digits = int(n * math.log10(2) + math.log10(k)) + 1
                    if digits > 1_000_000 and colb > 0:
                        ring(c, x, y, 30 + 4 * math.sin(t * 3 + j), GOLD, 3, colb * dim)
                        pass
            if five:
                la = prog(t, self.b(4, 0.4), 0.6)
                text(c, str(k), x, y + 46, 30, CORAL, "display", alpha=la, shadow=1)

    def overlay(self, c, t):
        a = prog(t, self.b(0, 0.05), 0.6) * (1 - prog(t, self.b(2, 0.02), 0.4))
        if a > 0:
            label_tag(c, "Seventeen or Bust  ·  2002", W / 2, 1010, 34, INK, "#2A1E6A", a)
        a = prog(t, self.b(2, 0.18), 0.5) * (1 - prog(t, self.b(3, 0.0), 0.4))
        if a > 0:
            label_tag(c, "PrimeGrid  ·  2016", W / 2, 1010, 34, GOLD, "#2A1E6A", a)
        nlit = sum(1 for i in range(len(self.found)) if t >= self.b(1, 0.12 + i * 0.065) + 0.25)
        a = prog(t, self.b(1, 0.1), 0.5) * (1 - prog(t, self.b(2, 0.25), 0.5))
        counter_pill(c, "primes found:", str(nlit), W - 60, 120, a)
        # the twelfth prime
        ca = prog(t, self.b(2, 0.38), 0.7, back) * (1 - prog(t, self.b(3, 0.0), 0.5))
        if ca > 0:
            x, y = 540, 640
            c.save(); c.translate(x, y); c.scale(0.8 + 0.1 * ca, 0.8 + 0.1 * ca)
            rrect(c, -470, -120, 940, 240, 40, "#150F40", 0.88 * ca)
            rich(c, [("10223", GOLD), (" × 2", INK), ("^31,172,165", INK), (" + 1", INK)], 0, -50, 56, alpha=ca, face="display")
            text(c, "9,383,761 digits  ·  31 October 2016", 0, 22, 32, SOFT, "body", alpha=ca)
            text(c, "tested on a home PC in 8 days, 22 hours", 0, 72, 28, LILAC, "body", alpha=ca * prog(t, self.b(2, 0.6), 0.6))
            c.restore()
        a = prog(t, self.b(3, 0.15), 0.6) * (1 - prog(t, self.b(4, 0.0), 0.5))
        if a > 0:
            label_tag(c, "Colbert numbers: over a million digits, and a star lit", W / 2, 1010, 32, GOLD, "#2A1E6A", a)
        a = prog(t, self.b(4, 0.5), 0.7)
        if a > 0:
            big_title(c, "five stars still dark", W / 2, 175, 66, INK, a)


# ======================================================================================
class Scale(Scene):
    ID = "05_scale"
    NUMBER, CHAPTER = "4", "How big is enormous?"

    def setup(self):
        self.sky = Sky(seed=13, horizon=AMBER)
        self.sfx(self.b(0, 0.05), "steps", 0.5)
        self.sfx(self.b(0, 0.62), "chime", 0.7)
        for i in range(10):
            self.sfx(self.b(1, 0.1 + i * 0.07), "thud", 0.5)
        self.sfx(self.b(2, 0.1), "whoosh", 0.5)
        self.digits = load("candidate.json")["leading"]

    def road_pt(self, u):
        x = -100 + u * 3000
        y = 900 - 120 * math.sin(u * 3.2) - u * 80
        return x, y

    def camera(self, t):
        u = prog(t, self.b(0, 0.0), self.d(0, 0.62), io)
        cx = lerp(800, 2150, u)
        z = 1.0
        if t > self.b(1, 0.0):
            cx = W / 2
        return (cx, H / 2, z)

    def draw(self, c, t):
        cx = self.camera(t)[0]
        c.save(); c.translate(cx - W / 2, 0)
        c.restore()
        if t < self.b(1, 0.15):
            fa = 1 - prog(t, self.b(1, 0.0), self.d(1, 0.12))
            c.save(); c.translate((cx - W / 2) * 0.6, 0)
            far_hills(c, t, cx, fa)
            c.restore()
            pts = [self.road_pt(u) for u in np.linspace(0, 1, 120)]
            poly(c, [(-200, H + 200)] + [(x, y + 40) for x, y in pts] + [(3100, H + 200)], "#20185A", fa)
            curve(c, pts, "#4A3A9A", 46, fa)
            curve(c, pts, CREAM, 4, 0.5 * fa, dash=[30, 26])
            marks = [(0.08, "n = 0"), (0.22, "10 M"), (0.36, "20 M"), (0.5, "30 M"), (0.64, "40 M")]
            for u, lab in marks:
                x, y = self.road_pt(u)
                line(c, x, y - 30, x, y - 130, WOOD, 8, fa)
                label_tag(c, lab, x, y - 140, 26, "#1A1240", CREAM, fa, "bold", 0.4)
            fu = 0.75
            fx, fy = self.road_pt(fu)
            flag(c, fx, fy - 20, 170, MINT, fa, t)
            label_tag(c, "47.9 M: the frontier", fx, fy - 230, 30, "#1A1240", MINT, fa * prog(t, self.b(0, 0.55), 0.6), "bold", 0.4)
            walk = prog(t, self.b(0, 0.0), self.d(0, 0.62), io)
            hx, hy = self.road_pt(0.08 + (fu - 0.1 - 0.08) * walk)
            hiker(c, hx, hy - 10, 90, t, GOLD, walking=walk < 0.999, alpha=fa, seed=3)
            glow(c, self.road_pt(0.92)[0], self.road_pt(0.92)[1] - 100, 500, "#FFFFFF", 0.08 * fa)
        # b1: a bookshelf of one number
        if t > self.b(1, 0.0) and t < self.b(2, 0.2):
            fa = prog(t, self.b(1, 0.0), 0.5) * (1 - prog(t, self.b(2, 0.0), self.d(2, 0.15)))
            hill(c, t, 880, "#241A5E", VIOLET, alpha=fa)
            sx0, sy = 600, 790
            rrect(c, sx0 - 30, sy, 900, 28, 8, WOOD, fa)
            rrect(c, sx0 - 30, sy - 380, 900, 22, 8, shade(WOOD, -0.15), fa)
            cols = [CORAL, TEAL, AMBER, VIOLET, ROSE, MINT, CYAN, GOLD, LILAC, CORAL]
            for i in range(10):
                u = prog(t, self.b(1, 0.1 + i * 0.07), 0.45, back)
                if u <= 0:
                    continue
                bx = sx0 + 30 + i * 84
                book(c, bx, sy - 330 * (1 - u) * 0 , 70, 330 * u, cols[i], fa, self.digits[i * 9:i * 9 + 9])
            person(c, sx0 - 110, sy + 95, 250, LILAC, fa)
            pages = int(3000 * prog(t, self.b(1, 0.1), self.d(1, 0.72), io))
            counter_pill(c, "pages:", fmt(pages), sx0 + 410, sy - 470, fa, GOLD, 44, align="center")
        # b2: trial division vs the age of the universe
        if t > self.b(2, 0.0):
            fa = prog(t, self.b(2, 0.1), 0.6)
            fill = prog(t, self.b(2, 0.2), self.d(2, 0.7), io)
            hourglass(c, 1350, 560, 420, fill, t, CREAM, GOLD, fa)
            text(c, "the age of the universe", 1350, 830, 30, SOFT, "body", alpha=fa)
            rich(c, [("10", GOLD), ("^7,203,058", GOLD)], 620, 470, 110, alpha=fa, face="display", shadow=1)
            text(c, "divisions to try", 620, 590, 40, INK, "body", alpha=fa)
            critter(c, 620, 790, 70, LILAC, t, seed=5, mood="worried", alpha=prog(t, self.b(2, 0.3), 0.6), look=(0.8, -0.4))
