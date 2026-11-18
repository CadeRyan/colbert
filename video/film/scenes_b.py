"""Scenes 06–09: how a test works, and why k is the problem."""
from .style import *
from .scenes_a import Base, counter
from . import facts as F
import math


PANEL_X = 0.35      # left edge of the right-hand text panel
PANEL_W = 6.4


def panel(m, y=None, maxw=PANEL_W):
    """place m in the right-hand panel, left-aligned, shrunk to fit"""
    if m.width > maxw:
        m.scale_to_fit_width(maxw)
    m.move_to([PANEL_X + m.width / 2, m.get_y() if y is None else y, 0])
    return m


def arrow(a, b, color=FAINT, w=2.5):
    return Arrow(a, b, buff=0.08, color=color, stroke_width=w, max_tip_length_to_length_ratio=0.25, tip_length=0.14)


# ======================================================================================
class S06Proth(Base):
    SCENE_ID = "06_proth"
    NUMBER, CHAPTER = "05", "One long calculation"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        card = VGroup(M("1878", 30, TEAL), T("François Proth", 34, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.3).move_to(UP * 2.4)
        N = VGroup(T("N =", 32, MUTED), kexpr(F.CANDIDATE[0], fmt(F.CANDIDATE[1]), 40, kcolor=CORAL)).arrange(RIGHT, buff=0.25).move_to(UP * 1.2)
        claim = T("one long calculation decides whether N is prime", 28, MUTED).next_to(N, DOWN, buff=0.4)
        self.play(FadeIn(card, shift=DOWN * 0.1), run_time=self.D(0, 0.2))
        self.play(FadeIn(N), run_time=self.D(0, 0.2))
        self.play(FadeIn(claim), run_time=self.D(0, 0.2))

        self.beat(1)
        vals = ["3", "9", "81", "6,561", "43,046,721", "1,853,020,188,851,841"]
        boxes = VGroup(*[chip(v, GOLD if i == 0 else INK, size=26) for i, v in enumerate(vals)])
        boxes.arrange(RIGHT, buff=0.5).scale_to_fit_width(12.6).move_to(DOWN * 0.6)
        arrows = VGroup(*[arrow(boxes[i].get_right(), boxes[i + 1].get_left()) for i in range(len(boxes) - 1)])
        sq = VGroup(*[T("²", 22, TEAL).next_to(a, UP, buff=0.05) for a in arrows])
        self.play(FadeOut(claim), N.animate.scale(0.75).move_to(UP * 1.5), card.animate.scale(0.85).move_to(UP * 2.45), run_time=self.D(1, 0.08))
        self.play(FadeIn(boxes[0]), run_time=self.D(1, 0.05))
        for i in range(1, len(boxes)):
            self.play(GrowArrow(arrows[i - 1]), FadeIn(sq[i - 1]), FadeIn(boxes[i], shift=RIGHT * 0.1), run_time=self.D(1, 0.05))
        note = T("…and once the numbers outgrow N, keep only the remainder after dividing by N", 24, MUTED).next_to(boxes, DOWN, buff=0.55)
        self.play(FadeIn(note), run_time=self.D(1, 0.12))
        prog = ValueTracker(6)
        track = RoundedRectangle(width=11, height=0.2, corner_radius=0.1, fill_color=PANEL, fill_opacity=1, stroke_color=LINE, stroke_width=1.5).move_to(DOWN * 2.6)
        fill = always_redraw(lambda: RoundedRectangle(width=max(0.2, 11 * prog.get_value() / 47_856_067), height=0.2, corner_radius=0.1,
                                                      fill_color=GOLD, fill_opacity=1, stroke_width=0).move_to(track.get_left(), aligned_edge=LEFT))
        cnt = always_redraw(lambda: VGroup(T("squarings:", 24, MUTED), M(fmt(int(prog.get_value())), 26, GOLD), T("of 47,856,067", 24, MUTED))
                            .arrange(RIGHT, buff=0.18).next_to(track, UP, buff=0.22))
        self.play(FadeIn(track), FadeIn(fill), FadeIn(cnt), run_time=self.D(1, 0.06))
        self.play(prog.animate.set_value(47_856_067), run_time=self.D(1, 0.3), rate_func=rate_functions.ease_in_quad)

        self.beat(2)
        self.play(FadeOut(VGroup(boxes, arrows, sq, note, track, cnt)), FadeOut(fill), run_time=self.D(2, 0.1))
        last = VGroup(T("final remainder", 26, MUTED), chip("N − 1", GOLD, size=40, stroke=GOLD, font=SANS)).arrange(RIGHT, buff=0.35).move_to(UP * 0.05)
        means = VGroup(T("(the remainder that stands for −1)", 24, MUTED)).next_to(last, DOWN, buff=0.25)
        verdict = H("PRIME", 52, GOLD).next_to(means, DOWN, buff=0.45)
        other = T("anything else → not prime", 26, MUTED).next_to(verdict, DOWN, buff=0.3)
        self.play(FadeIn(last, shift=UP * 0.1), run_time=self.D(2, 0.15))
        self.play(FadeIn(means), run_time=self.D(2, 0.15))
        self.play(FadeIn(verdict, scale=0.9), run_time=self.D(2, 0.15))
        self.play(FadeIn(other), run_time=self.D(2, 0.15))

        self.beat(3)
        self.play(FadeOut(VGroup(last, means, verdict, other, N, card)), run_time=self.D(3, 0.08))
        lanes = VGroup()
        labels = VGroup()
        for i in range(4):
            y = 1.3 - i * 1.0
            row = VGroup(*[Square(0.42, stroke_color=LINE, stroke_width=1.5, fill_color=PANEL, fill_opacity=1) for _ in range(14)]).arrange(RIGHT, buff=0.14)
            row.move_to([0.9, y, 0])
            lanes.add(row)
            labels.add(T(f"computer {i + 1}", 22, MUTED).next_to(row, LEFT, buff=0.35))
        self.play(FadeIn(lanes), FadeIn(labels), run_time=self.D(3, 0.1))
        waits = VGroup(*[T("waiting for the previous result", 20, FAINT).move_to(lanes[i]) for i in (1, 2, 3)])
        self.play(*[lanes[i].animate.set_opacity(0.25) for i in (1, 2, 3)], FadeIn(waits), run_time=self.D(3, 0.1))
        self.play(LaggedStart(*[lanes[0][j].animate.set_fill(GOLD, 0.95).set_stroke(GOLD) for j in range(14)], lag_ratio=0.5),
                  run_time=self.D(3, 0.42))
        take = T("A faster squaring is the only way to a faster test.", 30, INK, weight=MEDIUM).to_edge(DOWN, buff=0.75)
        self.play(FadeIn(take, shift=UP * 0.1), run_time=self.D(3, 0.12))
        self.finish()


# ======================================================================================
def conv(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


class S07FFT(Base):
    SCENE_ID = "07_fft"
    NUMBER, CHAPTER = "06", "Multiplying giants"

    def construct(self):
        a = [3, 1, 4, 1, 5]
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        top = VGroup(*[M(str(d), 36, INK) for d in a]).arrange(RIGHT, buff=0.55)
        left = VGroup(*[M(str(d), 36, INK) for d in a]).arrange(DOWN, buff=0.32)
        cells = VGroup()
        for i, x in enumerate(a):
            for j, y in enumerate(a):
                c = VGroup(Square(0.72, stroke_color=LINE, stroke_width=1.5, fill_color=PANEL, fill_opacity=1), M(str(x * y), 26, GOLD))
                c[1].move_to(c[0])
                cells.add(c)
        grid = VGroup(*cells).arrange_in_grid(5, 5, buff=0.06)
        grid.move_to(LEFT * 2.2 + DOWN * 0.35)
        for j, t in enumerate(top):
            t.move_to([grid[j].get_x(), grid.get_top()[1] + 0.45, 0])
        for i, t in enumerate(left):
            t.move_to([grid.get_left()[0] - 0.45, grid[i * 5].get_y(), 0])
        times = T("×", 36, MUTED).move_to([grid.get_left()[0] - 0.45, grid.get_top()[1] + 0.45, 0])
        self.play(FadeIn(top), FadeIn(left), FadeIn(times), run_time=self.D(0, 0.1))
        self.play(LaggedStart(*[FadeIn(c, scale=0.8) for c in cells], lag_ratio=0.06), run_time=self.D(0, 0.35))
        side = VGroup(T("5 digits:", 26, MUTED), M("25 products", 30, INK),
                      T("14.4 million digits:", 26, MUTED), P('≈ 2 × 10<sup>14</sup> products', 30, GOLD, font=MONO),
                      T("per squaring", 24, MUTED)).arrange(DOWN, buff=0.22, aligned_edge=LEFT).move_to(RIGHT * 3.6 + DOWN * 0.2)
        self.play(FadeIn(side[:2]), run_time=self.D(0, 0.15))
        self.play(FadeIn(side[2:]), run_time=self.D(0, 0.2))

        self.beat(1)
        tot = VGroup(T("× 48 million squarings", 30, MUTED), P('≈ 10<sup>22</sup> operations', 44, INK, font=MONO),
                     T("thousands of years, even on a fast computer", 30, CORAL)).arrange(DOWN, buff=0.35).move_to(DOWN * 0.1)
        self.play(FadeOut(VGroup(top, left, times, cells, side)), run_time=self.D(1, 0.12))
        self.play(LaggedStart(*[FadeIn(t, shift=UP * 0.1) for t in tot], lag_ratio=0.4), run_time=self.D(1, 0.6))

        self.beat(2)
        self.play(FadeOut(tot), run_time=self.D(2, 0.06))
        head = H("Fast Fourier Transform", 40, TEAL).to_edge(UP, buff=1.0)
        self.play(FadeIn(head), run_time=self.D(2, 0.1))
        unit = 0.11
        def bars(vals, color, w=0.42, gap=0.14, scale=unit):
            g = VGroup(*[bar(w, max(0.02, v * scale), color) for v in vals]).arrange(RIGHT, buff=gap, aligned_edge=DOWN)
            return g
        digits = bars(a, BLUE, scale=0.28).move_to(LEFT * 4.2 + DOWN * 0.3)
        dl = VGroup(*[M(str(d), 24, MUTED).next_to(b, DOWN, buff=0.12) for d, b in zip(a, digits)])
        cap1 = T("a number as a list of digits", 22, MUTED).next_to(dl, DOWN, buff=0.3)
        self.play(FadeIn(digits, shift=UP * 0.1), FadeIn(dl), FadeIn(cap1), run_time=self.D(2, 0.15))
        # the smear: each digit times the whole list, one row per digit, shifted one column each time
        c = conv(a, a)
        colw = 0.44
        res = bars(c, GOLD, w=0.32, gap=colw - 0.32, scale=0.035).move_to(RIGHT * 2.7 + DOWN * 1.9, aligned_edge=DOWN)
        x_first = res[0].get_center()[0]
        layers = VGroup()
        for i, d in enumerate(a):
            row = VGroup()
            for j, x in enumerate(a):
                b = bar(0.32, max(0.03, d * x * 0.035), BLUE, 0.75)
                b.move_to([x_first + (i + j) * colw, res.get_bottom()[1] + 3.0 - i * 0.62, 0], aligned_edge=DOWN)
                row.add(b)
            layers.add(row)
        rowlab = VGroup(*[M(f"{d}×", 20, MUTED).next_to(layers[i][0], LEFT, buff=0.15 + 0.0) for i, d in enumerate(a)])
        for i, rl in enumerate(rowlab):
            rl.move_to([x_first - 0.55, layers[i][0].get_bottom()[1] + 0.1, 0])
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.15) for r in layers], lag_ratio=0.3), FadeIn(rowlab), run_time=self.D(2, 0.3))
        cl = VGroup(*[M(str(v), 20, GOLD).next_to(b, UP, buff=0.08) for v, b in zip(c, res)])
        cols = [VGroup(*[layers[i][k - i] for i in range(len(a)) if 0 <= k - i < len(a)]) for k in range(len(c))]
        self.play(*[ReplacementTransform(cols[k], res[k]) for k in range(len(c))], FadeOut(rowlab), FadeIn(cl), run_time=self.D(2, 0.25))
        add = T("overlapping columns add up", 22, MUTED).next_to(res, DOWN, buff=0.25)
        self.play(FadeIn(add), run_time=self.D(2, 0.08))
        self.res, self.cl = res, cl

        self.beat(3)
        # frequency view: magnitudes of the 16-point DFT of the digit list
        A = np.fft.fft(np.array(a[::-1] + [0] * 11, dtype=float))
        mag = np.abs(A[:9])
        freq = bars(mag, TEAL, w=0.3, gap=0.1, scale=0.15).move_to(LEFT * 4.85 + DOWN * 0.3)
        self.play(FadeOut(VGroup(res, cl, add)), Transform(digits, freq), FadeOut(dl), FadeOut(cap1), run_time=self.D(3, 0.15))
        eq = VGroup(T("bass", 20, MUTED), T("mid", 20, MUTED), T("treble", 20, MUTED)).arrange(RIGHT, buff=0.55).next_to(freq, DOWN, buff=0.25)
        fl = T("frequencies", 24, TEAL).next_to(eq, DOWN, buff=0.2)
        self.play(FadeIn(eq), FadeIn(fl), run_time=self.D(3, 0.1))
        sqm = bars(mag ** 2, TEAL, w=0.3, gap=0.1, scale=0.012).move_to([-0.45, freq.get_bottom()[1], 0], aligned_edge=DOWN)
        back = bars(c, GOLD, w=0.3, gap=0.1, scale=0.035).move_to([4.4, freq.get_bottom()[1], 0], aligned_edge=DOWN)
        a1 = arrow(freq.get_right() + RIGHT * 0.1 + UP * 0.6, sqm.get_left() + LEFT * 0.1 + UP * 0.6, color=MUTED)
        a2 = arrow(sqm.get_right() + RIGHT * 0.1 + UP * 0.6, back.get_left() + LEFT * 0.1 + UP * 0.6, color=MUTED)
        l1 = T("multiply pair by pair", 20, MUTED).next_to(sqm, DOWN, buff=0.3)
        l2 = T("convert back", 20, MUTED).next_to(back, DOWN, buff=0.3)
        self.play(GrowArrow(a1), TransformFromCopy(digits, sqm), FadeIn(l1), run_time=self.D(3, 0.2))
        bl = VGroup(*[M(str(v), 18, GOLD).next_to(b, UP, buff=0.08) for v, b in zip(c, back)])
        self.play(GrowArrow(a2), TransformFromCopy(sqm, back), FadeIn(bl), FadeIn(l2), run_time=self.D(3, 0.2))
        xlab, inv = VGroup(a1, l1), VGroup(a2, l2)
        prod = VGroup(T("carries →", 24, MUTED), M(fmt(31415 * 31415), 40, GOLD, weight=MEDIUM)).arrange(RIGHT, buff=0.3).move_to(DOWN * 2.6)
        chk = T("= 31,415²", 24, MUTED).next_to(prod, RIGHT, buff=0.3)
        self.play(FadeIn(prod, shift=UP * 0.1), FadeIn(chk), run_time=self.D(3, 0.15))

        self.beat(4)
        self.play(FadeOut(VGroup(digits, eq, fl, sqm, xlab, back, bl, inv, prod, chk, head)), run_time=self.D(4, 0.08))
        ax = VGroup(Line([-5, -2.3, 0], [5, -2.3, 0], color=LINE, stroke_width=2), Line([-5, -2.3, 0], [-5, 2.3, 0], color=LINE, stroke_width=2))
        xl = T("number of digits", 22, MUTED).next_to(ax[0], DOWN, buff=0.2)
        yl = T("work", 22, MUTED).rotate(PI / 2).next_to(ax[1], LEFT, buff=0.2)
        def curve(f, color):
            us = [u for u in np.linspace(0, 1, 160) if f(u) <= 4.6]
            pts = [np.array([-5 + 10 * u, -2.3 + f(u), 0]) for u in us]
            return VMobject(stroke_color=color, stroke_width=4).set_points_smoothly(pts)
        quad = curve(lambda u: 4.6 * (u * 3.0) ** 2, CORAL)
        fft = curve(lambda u: 0.55 * u * (1 + math.log2(1 + 7 * u)) / 4 * 4, TEAL)
        ql = T("long multiplication", 24, CORAL).move_to([1.1, 1.6, 0])
        flb = T("FFT", 24, TEAL).move_to([4.3, -0.05, 0])
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), run_time=self.D(4, 0.12))
        self.play(Create(quad), FadeIn(ql), run_time=self.D(4, 0.2))
        self.play(Create(fft), FadeIn(flb), run_time=self.D(4, 0.2))
        take = VGroup(T("each squaring:", 26, MUTED), T("many minutes", 28, CORAL), T("→", 28, MUTED), T("a fraction of a millisecond", 28, TEAL)).arrange(RIGHT, buff=0.2)
        take.move_to(UP * 2.7)
        self.play(FadeIn(take), run_time=self.D(4, 0.2))
        self.finish()


# ======================================================================================
def ring(nseats=12, radius=2.0, center=ORIGIN, seat_r=0.36, color=LINE, start=PI / 2):
    seats = VGroup()
    for i in range(nseats):
        ang = start - i * TAU / nseats
        p = center + radius * np.array([math.cos(ang), math.sin(ang), 0])
        seats.add(Circle(seat_r, stroke_color=color, stroke_width=2, fill_color=PANEL, fill_opacity=1).move_to(p))
    return seats


class S08RoundTable(Base):
    SCENE_ID = "08_round_table"
    NUMBER, CHAPTER = "07", "The round table"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        prod = VGroup(*[chip(d, INK, size=30) for d in "4718205936147"]).arrange(RIGHT, buff=0.1).move_to(UP * 0.6)
        brace = Brace(prod, DOWN, color=FAINT)
        need = T("we only need the remainder after dividing by N", 28, MUTED).next_to(brace, DOWN, buff=0.25)
        self.play(LaggedStart(*[FadeIn(c) for c in prod], lag_ratio=0.05), run_time=self.D(0, 0.35))
        self.play(GrowFromCenter(brace), FadeIn(need), run_time=self.D(0, 0.25))

        self.beat(1)
        center = LEFT * 3.5 + DOWN * 0.3
        seats = ring(12, 2.1, center)
        digs = VGroup(*[M(d, 28, INK).move_to(s) for d, s in zip("471820593614", seats)])
        self.play(FadeOut(VGroup(brace, need)), ReplacementTransform(prod[:12], VGroup(*[VGroup(s, d) for s, d in zip(seats, digs)])),
                  FadeOut(prod[12:]), run_time=self.D(1, 0.25))
        over = chip("7", GOLD, size=28, stroke=GOLD).move_to(seats[11].get_center() + LEFT * 0.0 + UP * 0.0)
        over.move_to(center + 2.1 * np.array([math.cos(PI / 2 + 0.55), math.sin(PI / 2 + 0.55), 0]) + LEFT * 0.0)
        path = ArcBetweenPoints(seats[11].get_center() + UL * 0.15, seats[0].get_center() + UR * 0.15, angle=-TAU / 12)
        lab = panel(T("overflow past the last seat…", 28, MUTED), y=1.2)
        lab2 = panel(T("…arrives at the first", 28, MUTED), y=0.6)
        self.play(FadeIn(over, scale=0.8), FadeIn(lab), run_time=self.D(1, 0.15))
        self.play(MoveAlongPath(over, path), run_time=self.D(1, 0.25))
        self.play(over.animate.move_to(seats[0]).set_opacity(0), seats[0].animate.set_stroke(GOLD, 3), FadeIn(lab2), run_time=self.D(1, 0.15))

        self.beat(2)
        mers = VGroup(P('Mersenne numbers: 2<sup>p</sup> − 1', 30, INK), T("overflow wraps around unchanged  ✓", 26, GREEN)).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        panel(mers, y=1.2)
        self.play(FadeOut(VGroup(lab, lab2)), FadeIn(mers, shift=LEFT * 0.1), run_time=self.D(2, 0.15))
        # weights: unequal seats
        sizes = [0.42, 0.3, 0.38, 0.27, 0.41, 0.33, 0.29, 0.4, 0.31, 0.37, 0.28, 0.39]
        new = VGroup(*[Circle(r, stroke_color=TEAL, stroke_width=2, fill_color=PANEL, fill_opacity=1).move_to(s) for r, s in zip(sizes, seats)])
        wl = panel(VGroup(T("weights", 28, TEAL, weight=MEDIUM), T("Crandall & Fagin, 1994", 24, MUTED)).arrange(DOWN, buff=0.12, aligned_edge=LEFT), y=-0.15)
        self.play(*[Transform(s, n) for s, n in zip(seats, new)], FadeIn(wl), run_time=self.D(2, 0.25))
        gimps = panel(VGroup(T("a big part of why the hunt for", 24, MUTED), T("Mersenne primes is so efficient", 24, MUTED)).arrange(DOWN, buff=0.1, aligned_edge=LEFT), y=-1.35)
        self.play(FadeIn(gimps), run_time=self.D(2, 0.2))
        self.finish()


# ======================================================================================
class S09KProblem(Base):
    SCENE_ID = "09_the_k_problem"
    NUMBER, CHAPTER = "08", "Why k makes it hard"

    def construct(self):
        center = LEFT * 3.45 + DOWN * 0.3
        seats = ring(12, 2.1, center)
        digs = VGroup(*[M(d, 28, INK).move_to(s) for d, s in zip("471820593614", seats)])
        table = VGroup(seats, digs)

        self.beat(0)
        self.add(table)
        self.play(self.show_tag(), FadeIn(table), run_time=0.6)
        form = panel(P('<span foreground="#F06E5A">k</span> × 2<sup>n</sup> + 1', 40, font=MONO), y=2.1)
        rule = VGroup(T("overflow should come back", 26, MUTED), VGroup(T("divided by", 28, INK), M("k", 30, CORAL), T("and sign-flipped", 28, INK)).arrange(RIGHT, buff=0.16)).arrange(DOWN, buff=0.15, aligned_edge=LEFT)
        panel(rule, y=1.0)
        self.play(FadeIn(form), run_time=self.D(0, 0.2))
        self.play(FadeIn(rule), run_time=self.D(0, 0.3))

        self.beat(1)
        frac = 1 / 21181
        div = panel(VGroup(M("1 ÷ 21,181 =", 30, INK), M(f"{frac:.10f}…", 32, CORAL)).arrange(RIGHT, buff=0.25), y=-0.2)
        self.play(FadeIn(div), run_time=self.D(1, 0.25))
        bad = VGroup(*[DashedVMobject(Circle(0.36, color=CORAL, stroke_width=2).move_to(s), num_dashes=10) for s in seats])
        nofit = panel(T("not a whole number: the table no longer fits", 26, CORAL), y=-0.9)
        self.play(*[FadeIn(b) for b in bad], seats.animate.set_stroke(opacity=0.2), FadeIn(nofit), run_time=self.D(1, 0.35))

        self.beat(2)
        self.play(FadeOut(VGroup(form, rule, div, nofit, bad)), seats.animate.set_stroke(LINE, opacity=1), run_time=self.D(2, 0.08))
        big = ring(24, 2.6, center, seat_r=0.27)
        empties = VGroup(*[DashedVMobject(Circle(0.27, color=FAINT, stroke_width=1.5).move_to(big[i]), num_dashes=8) for i in range(12, 24)])
        newd = VGroup(*[M(d, 22, INK).move_to(big[i]) for i, d in enumerate("471820593614")])
        h1 = VGroup(M("1", 28, TEAL), T("Make the table twice as big", 30, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.25)
        panel(h1, y=2.1)
        pros = panel(VGroup(T("✓  exact", 26, GREEN), T("✕  every squaring moves twice the data", 26, CORAL), T("proth20, the existing GPU tester", 24, MUTED)).arrange(DOWN, buff=0.22, aligned_edge=LEFT), y=0.9)
        self.play(FadeIn(h1), run_time=self.D(2, 0.1))
        self.play(Transform(seats, VGroup(*[big[i] for i in range(12)])), Transform(digs, newd), FadeIn(empties), run_time=self.D(2, 0.25))
        self.play(LaggedStart(*[FadeIn(p, shift=RIGHT * 0.1) for p in pros], lag_ratio=0.4), run_time=self.D(2, 0.35))

        self.beat(3)
        small = ring(12, 2.1, center)
        sd = VGroup(*[M(d, 28, INK).move_to(s) for d, s in zip("471820593614", small)])
        self.play(FadeOut(VGroup(h1, pros, empties)), Transform(seats, small), Transform(digs, sd), run_time=self.D(3, 0.12))
        h2 = panel(VGroup(M("2", 28, TEAL), T("Build k into the weights", 30, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.25), y=2.4)
        w = 21181 ** (1 / 1048576)
        wts = VGroup(*[M(f"{21181 ** (j / 1048576):.7f}", 16, VIOLET).move_to(center + 2.8 * np.array([math.cos(PI / 2 - j * TAU / 12), math.sin(PI / 2 - j * TAU / 12), 0])) for j in range(12)])
        self.play(FadeIn(h2), LaggedStart(*[FadeIn(x) for x in wts], lag_ratio=0.06), run_time=self.D(3, 0.2))
        # precision budget of one double
        x0 = PANEL_X
        total_w = 5.6
        segs = [(32.0, BLUE, "the number's digits"), (15.0, CORAL, "lost to k"), (6.0, FAINT, "rounding margin")]
        budget = VGroup(); labs = VGroup()
        cx = x0
        for bits, col, name in segs:
            wdt = total_w * bits / 53
            r = Rectangle(width=wdt, height=0.42, fill_color=col, fill_opacity=0.9, stroke_width=0).move_to([cx + wdt / 2, 0.55, 0])
            budget.add(r)
            labs.add(T(name, 20, col if col != FAINT else MUTED).next_to(r, DOWN, buff=0.15))
            cx += wdt
        btitle = T("one double-precision number: 53 bits", 22, MUTED).next_to(budget, UP, buff=0.2, aligned_edge=LEFT)
        labs[1].shift(DOWN * 0.35); labs[2].shift(DOWN * 0.0)
        self.play(FadeIn(btitle), LaggedStart(*[GrowFromEdge(b, LEFT) for b in budget], lag_ratio=0.3), FadeIn(labs), run_time=self.D(3, 0.3))
        who = VGroup(T("Percival, 2002  ·  Woltman's gwnum", 24, MUTED), T("LLR2: PrimeGrid's tester on ordinary processors", 24, MUTED)).arrange(DOWN, buff=0.18, aligned_edge=LEFT)
        panel(who, y=-1.75)
        self.play(FadeIn(who), run_time=self.D(3, 0.15))
        self.finish()
