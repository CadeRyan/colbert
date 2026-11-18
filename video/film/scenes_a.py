"""Scenes 01–05: the background story."""
from .style import *
from . import facts as F
import math


def vignette():
    h, w = 270, 480
    y, x = np.mgrid[0:h, 0:w]
    r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / 1.25
    t = np.clip(1 - r, 0, 1) ** 1.6
    c0, c1 = np.array([11, 16, 32]), np.array([20, 29, 54])
    rgb = (c0 + (c1 - c0) * t[..., None]).astype(np.uint8)
    img = np.dstack([rgb, np.full((h, w), 255, np.uint8)])
    m = ImageMobject(img)
    m.height = config.frame_height
    m.width = config.frame_width
    return m


class Base(BeatScene):
    def setup(self):
        super().setup()
        self.vig = vignette()
        self.add(self.vig)
        self.bring_to_back(self.vig)
        if hasattr(self, "tag"):
            self.bring_to_front(self.tag)

    def finish(self, fade=0.6):
        self.until(self.tm.total - fade)
        mobs = [m for m in self.mobjects if m is not self.vig]
        if mobs:
            self.play(*[FadeOut(m) for m in mobs], run_time=fade)
        self.until(self.tm.total)
        super_finish_log(self)

    def five_chips(self, size=34, highlight=None, gap=0.3):
        g = VGroup(*[chip(k, CORAL if k == highlight else INK, size=size, stroke=CORAL if k == highlight else LINE)
                     for k in F.REMAINING_K]).arrange(RIGHT, buff=gap)
        return g


def super_finish_log(scene):
    info = dict(scene=scene.SCENE_ID, total=round(scene.tm.total, 2), source=scene.tm.source, overruns=scene._overruns)
    log = os.path.join(VIDEO, "out", "timing_log.jsonl")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a") as f:
        f.write(json.dumps(info) + "\n")


def counter(tracker, fmt_fn, size=28, color=INK, font=MONO, pos=None, edge=None):
    def make():
        t = Text(fmt_fn(tracker.get_value()), font=font, font_size=size, color=color)
        if pos is not None:
            t.move_to(pos)
        if edge is not None:
            t.move_to(edge[0], aligned_edge=edge[1])
        return t
    return always_redraw(make)


# ======================================================================================
class S01ColdOpen(Base):
    SCENE_ID = "01_cold_open"

    def construct(self):
        cand = load("candidate.json")
        lead = cand["leading"]
        rows, cols = 18, 60
        lines = VGroup(*[M(lead[r * cols:(r + 1) * cols], 22, INK) for r in range(rows)]).arrange(DOWN, buff=0.16, aligned_edge=LEFT)
        lines.scale_to_fit_height(5.9).move_to(UP * 0.45)
        if lines.width > 12.6:
            lines.scale_to_fit_width(12.6).move_to(UP * 0.45)
        for i, ln in enumerate(lines):
            ln.set_opacity(0.92 - 0.035 * i)
        shown = rows * cols
        count = VGroup(M(fmt(shown), 24, GOLD), T("digits on screen", 22, MUTED),
                       T("of", 22, MUTED), M(fmt(cand["digits"]), 24, INK)).arrange(RIGHT, buff=0.18)
        count.to_edge(DOWN, buff=0.42)

        self.beat(0)
        self.play(LaggedStart(*[FadeIn(l, shift=UP * 0.15) for l in lines], lag_ratio=0.12), run_time=self.D(0, 0.75))
        self.play(FadeIn(count, shift=UP * 0.1), run_time=self.D(0, 0.2))

        self.beat(1)
        expr = kexpr(F.CANDIDATE[0], fmt(F.CANDIDATE[1]), 64, kcolor=CORAL).move_to(UP * 0.9)
        q = H("prime?", 54, GOLD, weight=MEDIUM).next_to(expr, DOWN, buff=0.45)
        self.play(lines.animate.set_opacity(0.10), FadeOut(count), run_time=self.D(1, 0.12))
        self.play(FadeIn(expr, scale=0.96), run_time=self.D(1, 0.12))
        self.play(FadeIn(q, shift=UP * 0.1), run_time=self.D(1, 0.1))
        five = self.five_chips(30, highlight=F.CANDIDATE[0]).next_to(q, DOWN, buff=0.75)
        lab = T("one of the last five", 24, MUTED).next_to(five, DOWN, buff=0.25)
        self.wait(self.D(1, 0.15))
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.1) for c in five], lag_ratio=0.15), FadeIn(lab), run_time=self.D(1, 0.3))

        self.beat(2)
        title = H(TITLE_TEXT, 104).move_to(UP * 0.75)
        sub = T(SUBTITLE_TEXT, 28, MUTED).next_to(title, DOWN, buff=0.35)
        self.play(FadeOut(VGroup(expr, q, lab), shift=UP * 0.2), lines.animate.set_opacity(0.05), run_time=self.D(2, 0.15))
        self.play(FadeIn(title, shift=UP * 0.15), five.animate.scale(0.9).next_to(sub, DOWN, buff=0.9), run_time=self.D(2, 0.2))
        self.play(FadeIn(sub), run_time=self.D(2, 0.15))
        self.finish(0.8)


from .script import TITLE as TITLE_TEXT, SUBTITLE as SUBTITLE_TEXT


# ======================================================================================
class S02Sierpinski(Base):
    SCENE_ID = "02_sierpinski"
    NUMBER, CHAPTER = "01", "Sierpiński's question"

    def construct(self):
        seqs = load("sequences.json")
        cov = load("covering.json")

        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        form = P('<span foreground="#F06E5A">k</span> × 2<sup>n</sup> + 1', 72, font=DISPLAY).move_to(UP * 2.3)
        self.play(FadeIn(form, shift=DOWN * 0.15), run_time=self.D(0, 0.15))
        steps = VGroup(*[P(f'<span foreground="#F06E5A">k</span>·{m} + 1', 34, font=MONO) for m in (2, 4, 8, 16, 32)],
                       T("…", 34, MUTED)).arrange(RIGHT, buff=0.55).move_to(UP * 0.6)
        self.play(LaggedStart(*[FadeIn(s, shift=RIGHT * 0.15) for s in steps], lag_ratio=0.35), run_time=self.D(0, 0.6))

        self.beat(1)
        klab = P('<span foreground="#F06E5A">k</span> = 3', 40, font=MONO).move_to(LEFT * 5.6 + DOWN * 0.9)
        terms = seqs["3"][:9]
        row = VGroup(*[chip(v, GOLD if pr else MUTED, size=30, stroke=GOLD if pr else LINE) for _, v, pr in terms]).arrange(RIGHT, buff=0.22)
        row.next_to(klab, RIGHT, buff=0.5)
        legend = VGroup(VGroup(Dot(color=GOLD, radius=0.07), T("prime", 22, GOLD)).arrange(RIGHT, buff=0.12),
                        VGroup(Dot(color=MUTED, radius=0.07), T("composite", 22, MUTED)).arrange(RIGHT, buff=0.12)).arrange(RIGHT, buff=0.5)
        legend.next_to(row, DOWN, buff=0.45).align_to(row, LEFT)
        self.play(FadeOut(steps), FadeIn(klab), run_time=self.D(1, 0.08))
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.12) for c in row], lag_ratio=0.25), run_time=self.D(1, 0.55))
        self.play(FadeIn(legend), run_time=self.D(1, 0.1))

        self.beat(2)
        card = VGroup(M("1960", 30, TEAL), T("Wacław Sierpiński", 34, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.3).move_to(UP * 2.3)
        claim = T("Some values of k never give a prime. Ever.", 38, INK).move_to(UP * 0.9)
        self.play(FadeOut(form, shift=UP * 0.2), FadeOut(VGroup(klab, row, legend)), run_time=self.D(2, 0.12))
        self.play(FadeIn(card, shift=DOWN * 0.1), run_time=self.D(2, 0.12))
        self.play(FadeIn(claim), run_time=self.D(2, 0.15))
        never = VGroup(*[chip("composite", MUTED, size=20) for _ in range(5)], T("…  forever", 24, MUTED)).arrange(RIGHT, buff=0.16).move_to(DOWN * 0.6)
        never.scale_to_fit_width(min(never.width, 12.0))
        self.play(LaggedStart(*[FadeIn(c) for c in never], lag_ratio=0.2), run_time=self.D(2, 0.4))

        self.beat(3)
        card2 = VGroup(M("1962", 30, TEAL), T("John Selfridge", 34, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.3).move_to(UP * 2.3)
        big = M("k = 78,557", 48, CORAL, weight=MEDIUM).move_to(UP * 1.2)
        self.play(FadeOut(VGroup(claim, never)), Transform(card, card2), run_time=self.D(3, 0.06))
        self.play(FadeIn(big, scale=0.95), run_time=self.D(3, 0.06))
        # covering wheel: 36 slots, one per n mod 36, coloured by the prime that divides 78557*2^n+1
        R, r = 1.75, 1.05
        center = RIGHT * 3.4 + DOWN * 1.35
        slots = VGroup()
        for n in range(36):
            p = cov["slot_prime"][n]
            a0 = PI / 2 - n * TAU / 36
            s = AnnularSector(inner_radius=r, outer_radius=R, angle=-TAU / 36 * 0.9, start_angle=a0 - TAU / 36 * 0.05,
                              fill_color=COVER_COLORS[p], fill_opacity=0.9, stroke_width=0, arc_center=center)
            slots.add(s)
        hub = VGroup(T("n mod 36", 22, MUTED)).move_to(center)
        legend = VGroup(*[VGroup(Square(0.22, fill_color=COVER_COLORS[p], fill_opacity=1, stroke_width=0), M(str(p), 26, INK)).arrange(RIGHT, buff=0.15)
                          for p in cov["primes"]]).arrange(DOWN, buff=0.16, aligned_edge=LEFT)
        legend.next_to(center + RIGHT * R, RIGHT, buff=0.45)
        # list of first terms with their divisor
        rows = VGroup()
        for n, v, p in cov["first_terms"][:6]:
            rows.add(VGroup(P(f'78557·2<sup>{n}</sup>+1', 26, font=MONO), T("÷", 26, MUTED), M(str(p), 26, COVER_COLORS[p], weight=BOLD)).arrange(RIGHT, buff=0.22))
        rows.arrange(DOWN, buff=0.22, aligned_edge=LEFT).move_to(LEFT * 3.6 + DOWN * 1.35)
        self.play(LaggedStart(*[FadeIn(x, shift=RIGHT * 0.1) for x in rows], lag_ratio=0.3), run_time=self.D(3, 0.25))
        self.play(LaggedStart(*[FadeIn(s, scale=0.8) for s in slots], lag_ratio=0.04), FadeIn(hub), run_time=self.D(3, 0.3))
        self.play(LaggedStart(*[FadeIn(l, shift=LEFT * 0.1) for l in legend], lag_ratio=0.1), run_time=self.D(3, 0.12))
        self.play(Rotate(slots, angle=-TAU, about_point=center), run_time=self.D(3, 0.15), rate_func=smooth)

        self.beat(4)
        name = H("Sierpiński numbers", 44, INK).move_to(UP * 1.0)
        qn = T("Is 78,557 the smallest one?", 52, GOLD, weight=MEDIUM).move_to(DOWN * 0.6)
        self.play(FadeOut(VGroup(rows, slots, hub, legend, card)), big.animate.move_to(UP * 2.3).scale(0.8), run_time=self.D(4, 0.15))
        self.play(FadeIn(name), run_time=self.D(4, 0.15))
        self.play(FadeIn(qn, shift=UP * 0.1), run_time=self.D(4, 0.2))
        self.finish()


# ======================================================================================
class S03Elimination(Base):
    SCENE_ID = "03_elimination"
    NUMBER, CHAPTER = "02", "Crossing off candidates"
    W, CELL, GAP = 286, 5, 1

    def construct(self):
        fp = load("first_prime.json")
        ks = np.arange(1, 78557, 2)
        first = np.array([fp["first_n"][str(k)] if fp["first_n"][str(k)] is not None else -1 for k in ks], dtype=float)
        sob = set(F.SEVENTEEN)
        is17 = np.array([k in sob for k in ks])
        W = self.W
        Hn = int(math.ceil(len(ks) / W))
        cells = W * Hn
        firstp = np.full(cells, -2.0); firstp[:len(ks)] = first
        s17 = np.zeros(cells, bool); s17[:len(ks)] = is17
        valid = np.zeros(cells, bool); valid[:len(ks)] = True
        cs, gp = self.CELL, self.GAP
        mask = np.zeros((cs + gp, cs + gp), bool); mask[:cs, :cs] = True
        tile = np.tile(mask, (Hn, W))
        ink = np.array([150, 160, 185]); gold = np.array([242, 181, 68]); coral = np.array([240, 110, 90]); bg = np.array([14, 20, 38])

        state = {"t": 0.0, "fade_rest": 0.0, "hl": 0.0}

        def frame():
            t = state["t"]
            col = np.tile(ink, (cells, 1)).astype(float)
            alpha = np.where(valid, 0.85, 0.0)
            gone = (firstp >= 0) & (firstp <= t)
            age = np.clip((t - firstp) / max(1.0, 0.25 * t + 0.5), 0, 1)  # flash gold then fade
            g = gone[:, None]
            flash = np.clip(1 - age, 0, 1)[:, None]
            col = np.where(g, gold * flash + bg * (1 - flash), col)
            alpha = np.where(gone, 0.95 * np.clip(1 - age, 0.0, 1), alpha)
            rest = valid & (firstp == -1) & ~s17
            alpha = np.where(rest, 0.85 * (1 - state["fade_rest"]), alpha)
            col = np.where(s17[:, None], ink * (1 - state["hl"]) + coral * state["hl"], col)
            grid = col.reshape(Hn, W, 3)
            a = alpha.reshape(Hn, W)
            big = np.repeat(np.repeat(grid, cs + gp, 0), cs + gp, 1)
            ab = np.repeat(np.repeat(a, cs + gp, 0), cs + gp, 1) * tile
            return np.dstack([big.astype(np.uint8), (ab * 255).astype(np.uint8)])

        img = ImageMobject(frame())
        img.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        img.height = 4.75
        img.move_to(DOWN * 0.6)

        def upd(m):
            m.pixel_array = frame()
        img.add_updater(upd)

        head = T("Every odd k below 78,557", 34, INK, weight=MEDIUM).to_edge(UP, buff=1.0)
        sub = T("39,278 lists. Each needs one prime.", 26, MUTED).next_to(head, DOWN, buff=0.18)
        tn = ValueTracker(0)
        remaining = ValueTracker(len(ks))

        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        self.play(FadeIn(head), FadeIn(img), run_time=self.D(0, 0.3))
        self.play(FadeIn(sub), run_time=self.D(0, 0.15))

        self.beat(1)
        lab = VGroup(T("first prime found at n =", 24, MUTED), M("0", 26, GOLD)).arrange(RIGHT, buff=0.2)
        cnt_l = T("still open:", 24, MUTED)
        lab.to_corner(DL, buff=0.5)

        def ncount():
            v = tn.get_value()
            return M(fmt(int(v)), 26, GOLD).next_to(lab[0], RIGHT, buff=0.2)

        def opencount():
            t = state["t"]
            n_open = int(np.sum(valid & ~((firstp >= 0) & (firstp <= t))))
            n_open = int(n_open - (np.sum(valid & (firstp == -1) & ~s17) * state["fade_rest"]))
            return VGroup(cnt_l.copy(), M(fmt(n_open), 26, INK)).arrange(RIGHT, buff=0.2).to_corner(DR, buff=0.5)
        nc = always_redraw(ncount)
        oc = always_redraw(opencount)
        self.play(FadeIn(lab[0]), FadeIn(nc), FadeIn(oc), run_time=0.4)
        tn.add_updater(lambda m: state.__setitem__("t", m.get_value()))
        self.add(tn)
        # sweep n logarithmically 1 -> 1200
        sweep = ValueTracker(0)
        def sw(m):
            u = sweep.get_value()
            tn.set_value(math.expm1(u * math.log1p(1200)))
        sweep.add_updater(sw); self.add(sweep)
        self.play(sweep.animate.set_value(1), run_time=self.D(1, 0.6), rate_func=rate_functions.ease_in_out_sine)
        dec = T("…and decades of larger searches", 24, MUTED).next_to(head, DOWN, buff=0.18)
        fr = ValueTracker(0)
        fr.add_updater(lambda m: state.__setitem__("fade_rest", m.get_value())); self.add(fr)
        self.play(FadeOut(sub), FadeIn(dec), fr.animate.set_value(1), run_time=self.D(1, 0.3))

        self.beat(2)
        hl = ValueTracker(0)
        hl.add_updater(lambda m: state.__setitem__("hl", m.get_value())); self.add(hl)
        self.play(hl.animate.set_value(1), run_time=self.D(2, 0.1))
        # markers on the 17 surviving cells, then gather them into a row of chips
        idx = {k: (k - 1) // 2 for k in F.SEVENTEEN}
        px_w = img.width / (W * (cs + gp))
        tl = img.get_corner(UL)
        dots = VGroup()
        for k in F.SEVENTEEN:
            i = idx[k]; r_, c_ = divmod(i, W)
            p = tl + RIGHT * (c_ * (cs + gp) + cs / 2) * px_w + DOWN * (r_ * (cs + gp) + cs / 2) * px_w
            dots.add(Circle(radius=0.13, color=CORAL, stroke_width=3).move_to(p))
        self.play(LaggedStart(*[Create(d) for d in dots], lag_ratio=0.05), run_time=self.D(2, 0.15))
        chips = seventeen_grid().move_to(DOWN * 0.2)
        title = VGroup(M("2002", 30, TEAL), T("seventeen left", 34, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.3).to_edge(UP, buff=1.0)
        img.clear_updaters()
        self.play(FadeOut(img), FadeOut(VGroup(lab[0], nc, oc, head, dec)), FadeIn(title),
                  LaggedStart(*[ReplacementTransform(d, c) for d, c in zip(dots, chips)], lag_ratio=0.03), run_time=self.D(2, 0.3))
        self.finish()


# ======================================================================================
def seventeen_grid():
    return VGroup(*[chip(k, CORAL, size=20, stroke=CORAL) for k in F.SEVENTEEN]).arrange_in_grid(2, 9, buff=(0.15, 0.28))


class S04SeventeenOrBust(Base):
    SCENE_ID = "04_seventeen_or_bust"
    NUMBER, CHAPTER = "03", "Seventeen or Bust"

    def construct(self):
        grid = seventeen_grid().move_to(DOWN * 0.2)
        chips = {k: c for k, c in zip(F.SEVENTEEN, grid)}
        title = VGroup(M("2002", 30, TEAL), T("Seventeen or Bust", 34, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.3).to_edge(UP, buff=1.0)

        self.beat(0)
        self.add(grid)
        self.play(self.show_tag(), FadeIn(title), grid.animate.move_to(UP * 1.75), run_time=0.8)
        # volunteers: a field of small machines feeding a hub
        hub = VGroup(Circle(0.42, color=TEAL, fill_color=PANEL, fill_opacity=1, stroke_width=2.5), T("server", 20, TEAL)).move_to(DOWN * 1.7)
        hub[1].move_to(hub[0])
        rng = np.random.default_rng(3)
        machines = VGroup(); links = VGroup()
        for i in range(46):
            ang = rng.uniform(0, TAU); rad = rng.uniform(1.6, 3.6)
            p = hub.get_center() + np.array([1.9 * rad * math.cos(ang), 0.45 * rad * math.sin(ang), 0])
            mch = RoundedRectangle(width=0.32, height=0.22, corner_radius=0.04, stroke_color=MUTED, stroke_width=1.5, fill_color=PANEL, fill_opacity=1).move_to(p)
            machines.add(mch)
            links.add(Line(p, hub.get_center(), stroke_width=1, color=FAINT).set_z_index(-1))
        self.play(FadeIn(hub), run_time=self.D(0, 0.1))
        self.play(LaggedStart(*[AnimationGroup(FadeIn(m), Create(l)) for m, l in zip(machines, links)], lag_ratio=0.03), run_time=self.D(0, 0.55))
        pulses = [ShowPassingFlash(l.copy().set_color(TEAL).set_stroke(width=2.5), time_width=0.4) for l in links[::2]]
        self.play(LaggedStart(*pulses, lag_ratio=0.02), run_time=self.D(0, 0.25))

        self.beat(1)
        # timeline
        x0, x1 = -6.0, 6.0
        y = -2.9
        axis = Line([x0, y, 0], [x1, y, 0], color=LINE, stroke_width=2)
        def X(year):
            return x0 + (year - 2001.5) / (2017.5 - 2001.5) * (x1 - x0)
        ticks = VGroup(*[VGroup(Line([X(yr), y - 0.07, 0], [X(yr), y + 0.07, 0], color=LINE), M(str(yr), 18, MUTED).move_to([X(yr), y - 0.32, 0]))
                         for yr in range(2002, 2018, 2)])
        self.play(FadeOut(VGroup(machines, links)), hub.animate.scale(0.6).to_corner(UR, buff=0.5).shift(DOWN * 0.1),
                  Create(axis), FadeIn(ticks), run_time=self.D(1, 0.15))
        found = [p for p in F.SOB_PRIMES if p[2] <= 2007]
        stack = {}
        anims = []
        marks = VGroup()
        for k, n, yr in found:
            c = chips[k]
            stack[yr] = stack.get(yr, 0) + 1
            target = np.array([X(yr), y + 0.3 + 0.32 * (stack[yr] - 1), 0])
            new = chip(k, BG, fill=GOLD, size=13, stroke=GOLD, pad=0.07, radius=0.06).move_to(target)
            anims.append(Transform(c, new))
        cnt = VGroup(M("11", 40, GOLD, weight=BOLD), T("primes found, 2002–2007", 26, MUTED)).arrange(RIGHT, buff=0.25).move_to(DOWN * 0.15)
        self.play(LaggedStart(*anims, lag_ratio=0.18), run_time=self.D(1, 0.6))
        left = [k for k in F.SEVENTEEN if k not in {p[0] for p in found}]
        row = VGroup(*[chips[k].copy() for k in left]).arrange(RIGHT, buff=0.2).move_to(UP * 2.05)
        self.play(FadeIn(cnt, shift=UP * 0.1), *[chips[k].animate.move_to(r) for k, r in zip(left, row)], run_time=self.D(1, 0.15))

        self.beat(2)
        cross = VGroup(Line(UL, DR), Line(UR, DL)).set_stroke(CORAL, 4).scale(0.25).move_to(hub)
        pg = T("PrimeGrid", 22, TEAL, weight=SEMIBOLD).next_to(hub, DOWN, buff=0.15)
        self.play(Create(cross), FadeOut(cnt), run_time=self.D(2, 0.08))
        self.play(FadeIn(pg, shift=UP * 0.05), run_time=self.D(2, 0.08))
        k, n, yr = F.SOB_PRIMES[-1]
        c = chips[k]
        new = chip(k, BG, fill=GOLD, size=13, stroke=GOLD, pad=0.07, radius=0.06).move_to([X(2016.8), y + 0.3, 0])
        big = VGroup(kexpr(k, fmt(n), 44, kcolor=GOLD),
                     VGroup(M(fmt(F.TWELFTH_DIGITS), 28, INK), T("digits  ·  31 October 2016", 26, MUTED)).arrange(RIGHT, buff=0.2),
                     T(f"tested on a home PC in {F.TWELFTH_DAYS}", 24, MUTED)).arrange(DOWN, buff=0.28).move_to(DOWN * 0.55)
        self.play(c.animate.scale(1.5).move_to(UP * 0.95).set_color(GOLD), run_time=self.D(2, 0.12))
        self.play(FadeIn(big[0], shift=UP * 0.1), run_time=self.D(2, 0.15))
        self.play(FadeIn(big[1]), run_time=self.D(2, 0.12))
        self.play(FadeIn(big[2]), run_time=self.D(2, 0.12))
        self.play(Transform(c, new), FadeOut(big), run_time=self.D(2, 0.15))

        self.beat(3)
        # Colbert numbers: >1M digits and eliminating a k
        lab = H("Colbert numbers", 44, GOLD).move_to(UP * 0.55)
        rule = T("more than a million digits  ·  eliminates a remaining k", 26, MUTED).next_to(lab, DOWN, buff=0.25)
        rings, dim = VGroup(), []
        for k, n, yr in F.SOB_PRIMES:
            d = int(n * math.log10(2) + math.log10(k)) + 1
            if d > 1_000_000:
                rings.add(SurroundingRectangle(chips[k], color=GOLD, buff=0.06, corner_radius=0.1, stroke_width=2.5))
            else:
                dim.append(chips[k].animate.set_opacity(0.35))
        self.play(FadeIn(lab, shift=UP * 0.1), FadeIn(rule), *dim, run_time=self.D(3, 0.2))
        self.play(LaggedStart(*[Create(r) for r in rings], lag_ratio=0.15), run_time=self.D(3, 0.4))

        self.beat(4)
        rest = VGroup(*[chips[k] for k in F.REMAINING_K])
        others = VGroup(*[chips[k] for k, _, _ in F.SOB_PRIMES])
        five = VGroup(*[chip(k, CORAL, size=40, stroke=CORAL) for k in F.REMAINING_K]).arrange(RIGHT, buff=0.35).move_to(UP * 0.4)
        h5 = H("Five remain", 50, INK).next_to(five, UP, buff=0.6)
        goal = T("Find a prime for each, and 78,557 is the smallest Sierpiński number.", 28, MUTED).next_to(five, DOWN, buff=0.6)
        self.play(FadeOut(VGroup(lab, rule, rings, others, axis, ticks, hub, cross, pg, title)), run_time=self.D(4, 0.15))
        self.play(*[Transform(a, b) for a, b in zip(rest, five)], FadeIn(h5), run_time=self.D(4, 0.25))
        self.play(FadeIn(goal), run_time=self.D(4, 0.2))
        self.finish()


# ======================================================================================
class S05Scale(Base):
    SCENE_ID = "05_scale"
    NUMBER, CHAPTER = "04", "How big is enormous?"

    def construct(self):
        cand = load("candidate.json")
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        x0, x1, y = -5.5, 5.5, 0.9
        track = RoundedRectangle(width=x1 - x0, height=0.32, corner_radius=0.16, stroke_color=LINE, stroke_width=2, fill_color=PANEL, fill_opacity=1).move_to([0, y, 0])
        frac = ValueTracker(0.0)
        fill = always_redraw(lambda: RoundedRectangle(width=max(0.32, (x1 - x0) * frac.get_value()), height=0.32, corner_radius=0.16,
                                                      fill_color=TEAL, fill_opacity=0.9, stroke_width=0).move_to([x0, y, 0], aligned_edge=LEFT))
        l0 = M("n = 0", 22, MUTED).next_to(track, DOWN, buff=0.25).align_to(track, LEFT)
        lab = T("exponents already searched", 26, MUTED).next_to(track, UP, buff=0.3).align_to(track, LEFT)
        nval = always_redraw(lambda: M(f"n ≈ {frac.get_value() * 47.9:4.1f} million", 28, TEAL).next_to(track, DOWN, buff=0.25).align_to(track, RIGHT))
        self.play(FadeIn(track), FadeIn(lab), FadeIn(l0), run_time=self.D(0, 0.12))
        self.add(fill, nval)
        self.play(frac.animate.set_value(1.0), run_time=self.D(0, 0.45), rate_func=rate_functions.ease_out_cubic)
        dg = VGroup(T("next candidates:", 30, MUTED), M("≈ 14.4 million digits", 40, GOLD, weight=MEDIUM)).arrange(RIGHT, buff=0.3).move_to(DOWN * 1.3)
        self.play(FadeIn(dg, shift=UP * 0.1), run_time=self.D(0, 0.2))

        self.beat(1)
        self.play(FadeOut(VGroup(track, lab, l0, dg)), FadeOut(fill), FadeOut(nval), run_time=self.D(1, 0.1))
        digits = cand["leading"]
        def page(i):
            body = VGroup(*[M(digits[(i * 7 + r) * 40 % 2000:(i * 7 + r) * 40 % 2000 + 40], 9, "#3A4562") for r in range(26)]).arrange(DOWN, buff=0.055)
            sheet = Rectangle(width=2.3, height=3.1, fill_color="#E9EDF5", fill_opacity=1, stroke_width=0)
            body.scale_to_fit_width(sheet.width - 0.3).move_to(sheet)
            return VGroup(sheet, body)
        p0 = page(0).move_to(LEFT * 3.2)
        self.play(FadeIn(p0, shift=UP * 0.2), run_time=self.D(1, 0.12))
        stack = VGroup(*[Rectangle(width=2.3, height=3.1, fill_color="#E9EDF5", fill_opacity=1, stroke_color="#AEB6C8", stroke_width=1)
                         for _ in range(28)])
        for i, s in enumerate(stack):
            s.move_to(RIGHT * 2.6 + UP * (-0.9 + 0.0) + RIGHT * 0.012 * i + UP * 0.05 * i)
        pages = ValueTracker(1)
        pc = always_redraw(lambda: VGroup(M(fmt(int(pages.get_value())), 46, INK, weight=MEDIUM), T("pages", 30, MUTED)).arrange(RIGHT, buff=0.22).move_to(RIGHT * 2.75 + DOWN * 3.05))
        self.add(pc)
        self.play(LaggedStart(*[FadeIn(s, shift=DOWN * 0.3) for s in stack], lag_ratio=0.12), pages.animate.set_value(F.PAGES),
                  run_time=self.D(1, 0.6), rate_func=rate_functions.ease_in_out_sine)

        self.beat(2)
        self.play(FadeOut(VGroup(p0, stack)), FadeOut(pc), run_time=self.D(2, 0.1))
        half = (cand["digits"]) // 2
        trial = VGroup(T("Trial division would need about", 30, MUTED),
                       P(f'10<sup>{fmt(half)}</sup> divisions', 50, GOLD, font=MONO)).arrange(DOWN, buff=0.4).move_to(UP * 0.6)
        uni = VGroup(T("Age of the universe:", 26, MUTED), P('≈ 4 × 10<sup>17</sup> seconds', 30, INK, font=MONO)).arrange(RIGHT, buff=0.25).next_to(trial, DOWN, buff=0.8)
        self.play(FadeIn(trial[0]), run_time=self.D(2, 0.1))
        self.play(FadeIn(trial[1], scale=0.95), run_time=self.D(2, 0.2))
        self.play(FadeIn(uni), run_time=self.D(2, 0.2))
        self.finish()
