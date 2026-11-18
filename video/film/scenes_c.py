"""Scenes 10–15: the idea, what it buys, and what it means."""
from .style import *
from .scenes_a import Base, counter
from .scenes_b import panel, arrow, PANEL_X
from . import facts as F
import math


def clock_face(n, radius=1.9, center=ORIGIN, labels=None, size=26, start_label=None):
    face = Circle(radius, stroke_color=LINE, stroke_width=2.5, fill_color=PANEL, fill_opacity=1).move_to(center)
    nums = VGroup()
    pos = []
    for i in range(n):
        ang = PI / 2 - i * TAU / n
        p = center + (radius - 0.42) * np.array([math.cos(ang), math.sin(ang), 0])
        pos.append(p)
        lab = labels[i] if labels else str(i)
        nums.add(M(lab, size, INK).move_to(p))
    return face, nums, pos


class S10Exact(Base):
    SCENE_ID = "10_exact"
    NUMBER, CHAPTER = "09", "Exact arithmetic"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        screen = RoundedRectangle(width=8.6, height=1.7, corner_radius=0.18, fill_color="#0E1628", fill_opacity=1, stroke_color=LINE, stroke_width=2).move_to(UP * 0.9)
        q = M("0.1 + 0.2 =", 34, MUTED)
        q.move_to(screen.get_corner(UL) + RIGHT * 0.45 + DOWN * 0.45, aligned_edge=UL)
        ans = VGroup(M("0.3000000000000000", 46, INK), M("4", 46, CORAL)).arrange(RIGHT, buff=0.02)
        ans.move_to(screen.get_corner(DR) + LEFT * 0.45 + UP * 0.3, aligned_edge=DR)
        lab = T("a computer's decimals keep a fixed number of significant digits", 26, MUTED).next_to(screen, DOWN, buff=0.45)
        self.play(FadeIn(screen), FadeIn(q), run_time=self.D(0, 0.15))
        self.play(FadeIn(ans[0]), run_time=self.D(0, 0.15))
        self.play(FadeIn(ans[1], scale=1.3), FadeIn(lab), run_time=self.D(0, 0.15))
        marg = T("tiny rounding errors → programs keep a safety margin", 26, CORAL).next_to(lab, DOWN, buff=0.3)
        self.play(FadeIn(marg), run_time=self.D(0, 0.2))

        self.beat(1)
        self.play(FadeOut(VGroup(screen, q, ans, lab, marg)), run_time=self.D(1, 0.08))
        head = T("A gaming graphics card's arithmetic throughput", 28, MUTED).move_to(UP * 2.3)
        base_y = -1.9
        b1 = bar(1.6, 3.6, TEAL).move_to([-2.0, base_y, 0], aligned_edge=DOWN)
        b2 = bar(1.6, 3.6 / 32, CORAL).move_to([2.0, base_y, 0], aligned_edge=DOWN)
        l1 = T("whole numbers", 26, TEAL).next_to(b1, DOWN, buff=0.25)
        l2 = T("double precision", 26, CORAL).next_to(b2, DOWN, buff=0.25)
        x = T("32–64× slower", 34, CORAL, weight=MEDIUM).next_to(b2, UP, buff=0.4)
        self.play(FadeIn(head), run_time=self.D(1, 0.1))
        self.play(GrowFromEdge(b1, DOWN), FadeIn(l1), run_time=self.D(1, 0.2))
        self.play(GrowFromEdge(b2, DOWN), FadeIn(l2), run_time=self.D(1, 0.15))
        self.play(FadeIn(x, shift=UP * 0.1), run_time=self.D(1, 0.15))

        self.beat(2)
        self.play(FadeOut(VGroup(head, b1, b2, l1, l2, x)), run_time=self.D(2, 0.08))
        c = LEFT * 3.4 + DOWN * 0.2
        face, nums, pos = clock_face(12, 2.0, c, labels=["12"] + [str(i) for i in range(1, 12)])
        hand = Line(c, pos[9], color=GOLD, stroke_width=5)
        dot = Dot(c, radius=0.08, color=GOLD)
        title = panel(H("Clock arithmetic", 40, INK), y=1.9)
        eq = panel(VGroup(M("9 + 7 = 4", 40, GOLD), T("on a 12-hour clock", 24, MUTED)).arrange(DOWN, buff=0.15, aligned_edge=LEFT), y=0.6)
        props = panel(VGroup(T("no fractions", 28, INK), T("no rounding", 28, INK), T("every result exact", 28, GREEN)).arrange(DOWN, buff=0.2, aligned_edge=LEFT), y=-1.2)
        self.play(FadeIn(face), FadeIn(nums), FadeIn(title), run_time=self.D(2, 0.15))
        self.play(Create(hand), FadeIn(dot), run_time=self.D(2, 0.08))
        self.play(Rotate(hand, angle=-7 * TAU / 12, about_point=c), run_time=self.D(2, 0.25), rate_func=smooth)
        self.play(FadeIn(eq), run_time=self.D(2, 0.1))
        self.play(LaggedStart(*[FadeIn(p, shift=RIGHT * 0.1) for p in props], lag_ratio=0.3), run_time=self.D(2, 0.2))

        self.beat(3)
        self.play(FadeOut(VGroup(face, nums, hand, dot, title, eq, props)), run_time=self.D(3, 0.08))
        face, nums, pos = clock_face(13, 2.2, c, size=24)
        squares = {(x * x) % 13 for x in range(1, 13)}
        self.play(FadeIn(face), FadeIn(nums), run_time=self.D(3, 0.1))
        t2 = panel(VGroup(T("Square roots on a 13-hour clock", 30, INK, weight=MEDIUM)), y=2.1)
        self.play(FadeIn(t2), run_time=self.D(3, 0.06))
        sq_lines = VGroup(*[M(f"{xv}² = {xv * xv} → {xv * xv % 13}", 24, INK) for xv in range(1, 7)]).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        panel(sq_lines, y=0.45)
        for xv, ln in zip(range(1, 7), sq_lines):
            self.play(FadeIn(ln, shift=RIGHT * 0.08), nums[xv * xv % 13].animate.set_color(GOLD), run_time=self.D(3, 0.035))
        arcs = VGroup()
        res = panel(VGroup(VGroup(T("have a square root:", 22, MUTED), M("1 3 4 9 10 12", 24, GOLD)).arrange(RIGHT, buff=0.2),
                           VGroup(T("have none:", 22, MUTED), M("2 5 6 7 8 11", 24, CORAL)).arrange(RIGHT, buff=0.2)).arrange(DOWN, buff=0.15, aligned_edge=LEFT), y=-1.35)
        self.play(*[nums[i].animate.set_color(CORAL).set_opacity(0.7) for i in range(1, 13) if i not in squares], FadeIn(res), run_time=self.D(3, 0.12))
        self.play(FadeOut(sq_lines), res.animate.move_to([PANEL_X + res.width / 2, 1.2, 0]), run_time=self.D(3, 0.06))
        need = panel(VGroup(T("colbert's weights need a", 26, INK), P('millionth root of <span foreground="#F06E5A">−k·2<sup>n</sup></span>', 30, INK)).arrange(DOWN, buff=0.15, aligned_edge=LEFT), y=-0.3)
        rare = panel(T("In most clocks, most numbers have none.", 26, CORAL), y=-1.4)
        self.play(FadeIn(need), run_time=self.D(3, 0.15))
        self.play(FadeIn(rare), run_time=self.D(3, 0.12))

        self.beat(4)
        self.play(FadeOut(VGroup(face, nums, arcs, t2, res, need, rare)), run_time=self.D(4, 0.1))
        mark = T("“", 140, TEAL, font=DISPLAY).move_to(LEFT * 5.0 + UP * 1.6)
        quote = VGroup(T("Surprisingly no fast algorithm exists", 44, INK, font=DISPLAY, weight=MEDIUM),
                       P('for k·b<sup>n</sup> ± 1 …', 44, INK, font=DISPLAY)).arrange(DOWN, buff=0.2, aligned_edge=LEFT).move_to(UP * 0.7)
        who = T("Yves Gallot, PrimeGrid forum, February 2024", 26, MUTED).next_to(quote, DOWN, buff=0.6, aligned_edge=LEFT)
        ctx = T("on number-theoretic transforms for numbers like ours", 24, FAINT).next_to(who, DOWN, buff=0.15, aligned_edge=LEFT)
        self.play(FadeIn(mark), FadeIn(quote, shift=UP * 0.1), run_time=self.D(4, 0.3))
        self.play(FadeIn(who), FadeIn(ctx), run_time=self.D(4, 0.25))
        self.finish()


# ======================================================================================
class S11KeyIdea(Base):
    SCENE_ID = "11_key_idea"
    NUMBER, CHAPTER = "10", "The key observation"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        q = VGroup(P('a clock of size  2<sup>61</sup> − 1', 40, INK, font=DISPLAY), M("= 2,305,843,009,213,693,951", 28, MUTED)).arrange(DOWN, buff=0.25).move_to(UP * 2.0)
        self.play(FadeIn(q[0]), run_time=self.D(0, 0.12))
        self.play(FadeIn(q[1]), run_time=self.D(0, 0.1))
        plane_c = LEFT * 3.4 + DOWN * 1.0
        axes = VGroup(Line(plane_c + LEFT * 2.2, plane_c + RIGHT * 2.2, color=LINE, stroke_width=2), Line(plane_c + DOWN * 1.6, plane_c + UP * 1.6, color=LINE, stroke_width=2))
        pt = Dot(plane_c + RIGHT * 1.2 + UP * 0.9, color=VIOLET, radius=0.09)
        ptl = M("(a, b)", 26, VIOLET).next_to(pt, UR, buff=0.1)
        rule = panel(VGroup(T("numbers are pairs, multiplied like complex numbers", 24, MUTED),
                            M("(a, b) × (c, d) = (ac − bd, ad + bc)", 26, INK)).arrange(DOWN, buff=0.18, aligned_edge=LEFT), y=-0.2)
        cred = panel(VGroup(T("Crandall, 1999", 24, MUTED), T("wrapping around = one shift and one addition", 24, TEAL)).arrange(DOWN, buff=0.15, aligned_edge=LEFT), y=-1.6)
        self.play(Create(axes), FadeIn(pt), FadeIn(ptl), run_time=self.D(0, 0.2))
        self.play(FadeIn(rule), run_time=self.D(0, 0.2))
        self.play(FadeIn(cred), run_time=self.D(0, 0.2))

        self.beat(1)
        self.play(FadeOut(VGroup(q, rule, cred, pt, ptl)), run_time=self.D(1, 0.08))
        stmt = VGroup(T("In this clock, every ordinary number", 34, INK, weight=MEDIUM),
                      T("has every root colbert needs.", 34, GOLD, weight=MEDIUM)).arrange(DOWN, buff=0.15).move_to(UP * 2.2)
        self.play(FadeIn(stmt, shift=UP * 0.1), run_time=self.D(1, 0.2))
        # illustration: powers of a root spiral round to land on -k*2^n
        Nst, R = 16, 4.0
        target = plane_c + LEFT * 1.9
        scale = 1.9 / R
        pts = [plane_c + scale * (R ** (j / Nst)) * np.array([math.cos(PI * j / Nst), math.sin(PI * j / Nst), 0]) for j in range(Nst + 1)]
        tdot = Dot(target, color=CORAL, radius=0.1)
        tlab = P('−k·2<sup>n</sup>', 26, CORAL, font=MONO).next_to(tdot, DOWN, buff=0.15)
        one = Dot(pts[0], color=INK, radius=0.06)
        self.play(FadeIn(tdot), FadeIn(tlab), FadeIn(one), run_time=self.D(1, 0.1))
        dots = VGroup(*[Dot(p, radius=0.055, color=VIOLET) for p in pts[1:]])
        path = VMobject(stroke_color=VIOLET, stroke_width=2, stroke_opacity=0.6).set_points_smoothly(pts)
        self.play(Create(path), LaggedStart(*[FadeIn(d, scale=0.5) for d in dots], lag_ratio=0.15), run_time=self.D(1, 0.35), rate_func=linear)
        expl = panel(VGroup(P('θ, θ<sup>2</sup>, θ<sup>3</sup>, … θ<sup>N</sup> = −k·2<sup>n</sup>', 28, INK, font=MONO),
                            T("whatever k is, whatever n is: the root θ exists", 24, MUTED),
                            T("and is computed once, before the test starts", 24, MUTED)).arrange(DOWN, buff=0.2, aligned_edge=LEFT), y=-0.6)
        self.play(FadeIn(expl), run_time=self.D(1, 0.2))

        self.beat(2)
        self.play(FadeOut(VGroup(path, dots, one, tdot, tlab, expl)), stmt.animate.set_opacity(0.35), run_time=self.D(2, 0.08))
        h = Dot(plane_c + RIGHT * 1.3 + UP * 1.0, color=VIOLET, radius=0.09)
        hb = Dot(plane_c + RIGHT * 1.3 + DOWN * 1.0, color=VIOLET, radius=0.09)
        hl = M("pair", 24, VIOLET).next_to(h, RIGHT, buff=0.12)
        hbl = M("mirror", 24, VIOLET).next_to(hb, RIGHT, buff=0.12)
        mirror = DashedLine(h.get_center(), hb.get_center(), color=FAINT, dash_length=0.08)
        prod = Dot(plane_c + LEFT * 1.6, color=GOLD, radius=0.1)
        pl = T("ordinary number", 22, GOLD).next_to(prod, DOWN, buff=0.15)
        self.play(FadeIn(h), FadeIn(hl), run_time=self.D(2, 0.1))
        self.play(Create(mirror), TransformFromCopy(h, hb), FadeIn(hbl), run_time=self.D(2, 0.12))
        self.play(TransformFromCopy(VGroup(h, hb), prod), FadeIn(pl), run_time=self.D(2, 0.15))
        eq = panel(VGroup(T("every ordinary number =", 26, MUTED), T("a pair × its own mirror image", 30, INK, weight=MEDIUM),
                          T("that extra room is what guarantees the roots", 24, MUTED)).arrange(DOWN, buff=0.18, aligned_edge=LEFT), y=0.2)
        self.play(FadeIn(eq), run_time=self.D(2, 0.15))
        ana = panel(VGroup(T("like allowing  i  so that", 26, MUTED), P('i × i = −1', 30, TEAL, font=MONO)).arrange(RIGHT, buff=0.25), y=-1.6)
        self.play(FadeIn(ana), run_time=self.D(2, 0.15))

        self.beat(3)
        self.play(FadeOut(VGroup(axes, h, hb, hl, hbl, mirror, prod, pl, eq, ana, stmt)), run_time=self.D(3, 0.1))
        cards = VGroup(
            self.card("small table", "Percival's no-padding method", BLUE),
            self.card("exact", "clock arithmetic: no rounding", GREEN),
            self.card("fast on GPUs", "whole numbers, not decimals", TEAL)).arrange(RIGHT, buff=0.45).move_to(UP * 0.9)
        self.play(LaggedStart(*[FadeIn(cd, shift=UP * 0.15) for cd in cards], lag_ratio=0.3), run_time=self.D(3, 0.35))
        core = VGroup(RoundedRectangle(width=4.0, height=1.1, corner_radius=0.2, fill_color=PANEL, fill_opacity=1, stroke_color=TEAL, stroke_width=3),
                      H("colbert", 46, TEAL)).move_to(DOWN * 1.6)
        core[1].move_to(core[0])
        links = VGroup(*[Line(cd.get_bottom(), core.get_top(), color=FAINT, stroke_width=2) for cd in cards])
        self.play(Create(links), FadeIn(core, scale=0.9), run_time=self.D(3, 0.3))

        self.beat(4)
        self.play(FadeOut(VGroup(cards, links)), core.animate.move_to(DOWN * 0.2), run_time=self.D(4, 0.1))
        people = [("Crandall & Fagin, 1994", "weights"), ("Crandall, 1999", "pair arithmetic"), ("Percival, 2002", "any k, no padding"),
                  ("Woltman · gwnum", "the 1/k trick"), ("Gallot · genefer, proth20", "GPU transforms"), ("Gerbicz & Li", "error checking")]
        nodes = VGroup()
        for i, (who, what) in enumerate(people):
            ang = PI / 2 + i * TAU / 6 + TAU / 12
            p = core.get_center() + np.array([4.6 * math.cos(ang), 2.6 * math.sin(ang), 0])
            nd = VGroup(T(who, 22, INK, weight=MEDIUM), T(what, 19, MUTED)).arrange(DOWN, buff=0.08).move_to(p)
            nodes.add(nd)
        edges = VGroup(*[Line(nd.get_center(), core.get_center(), color=FAINT, stroke_width=1.5).set_z_index(-1) for nd in nodes])
        for e, nd in zip(edges, nodes):
            e.put_start_and_end_on(nd.get_center() + (core.get_center() - nd.get_center()) * 0.28, core.get_center() + (nd.get_center() - core.get_center()) * 0.3)
        self.play(LaggedStart(*[AnimationGroup(FadeIn(nd), Create(e)) for nd, e in zip(nodes, edges)], lag_ratio=0.2), run_time=self.D(4, 0.4))
        new = VGroup(T("new here:", 22, GOLD, weight=MEDIUM), T("the roots always exist, so the pieces fit", 22, GOLD)).arrange(RIGHT, buff=0.15).next_to(core, DOWN, buff=0.35)
        self.play(FadeIn(new), core[0].animate.set_stroke(GOLD, 3), run_time=self.D(4, 0.2))
        self.finish()

    def card(self, title, sub, color):
        box = RoundedRectangle(width=4.1, height=1.6, corner_radius=0.18, fill_color=PANEL, fill_opacity=1, stroke_color=color, stroke_width=2.5)
        t = T(title, 32, color, weight=SEMIBOLD)
        s = T(sub, 19, MUTED)
        if s.width > box.width - 0.4:
            s.scale_to_fit_width(box.width - 0.4)
        g = VGroup(t, s).arrange(DOWN, buff=0.18).move_to(box)
        return VGroup(box, g)


# ======================================================================================
class S12Results(Base):
    SCENE_ID = "12_results"
    NUMBER, CHAPTER = "11", "What it buys"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        mem = VGroup(RoundedRectangle(width=3.4, height=3.0, corner_radius=0.2, fill_color=PANEL, fill_opacity=1, stroke_color=BLUE, stroke_width=2.5),
                     T("memory", 30, BLUE, weight=MEDIUM)).move_to(LEFT * 4.2 + DOWN * 0.2)
        mem[1].move_to(mem[0])
        cpu = VGroup(RoundedRectangle(width=1.8, height=1.5, corner_radius=0.2, fill_color=PANEL, fill_opacity=1, stroke_color=TEAL, stroke_width=2.5),
                     T("compute", 26, TEAL, weight=MEDIUM)).move_to(RIGHT * 4.4 + DOWN * 0.2)
        cpu[1].move_to(cpu[0])
        pipe = RoundedRectangle(width=5.8, height=0.55, corner_radius=0.27, fill_color="#0E1628", fill_opacity=1, stroke_color=LINE, stroke_width=2).move_to(DOWN * 0.2 + RIGHT * 0.5)
        self.play(FadeIn(mem), FadeIn(cpu), FadeIn(pipe), run_time=self.D(0, 0.15))
        rng = np.random.default_rng(5)
        flow = ValueTracker(0)
        starts = rng.uniform(0, 1, 70)
        ys = rng.uniform(-0.16, 0.16, 70)
        def particles():
            g = VGroup()
            t = flow.get_value()
            for s0, yy in zip(starts, ys):
                u = (s0 + t) % 1.0
                g.add(Dot(pipe.get_left() + RIGHT * (0.2 + 5.4 * u) + UP * yy, radius=0.045, color=BLUE).set_opacity(0.9))
            return g
        parts = always_redraw(particles)
        self.add(parts)
        lab = T("a squaring this size spends most of its time moving data", 26, MUTED).to_edge(UP, buff=1.2)
        self.play(flow.animate.set_value(3.0), FadeIn(lab), run_time=self.D(0, 0.7), rate_func=linear)

        self.beat(1)
        self.play(FadeOut(VGroup(mem, cpu, pipe, lab)), FadeOut(parts), run_time=self.D(1, 0.08))
        head = T("data moved per squaring, at the search frontier", 28, MUTED).move_to(UP * 2.4)
        self.play(FadeIn(head), run_time=self.D(1, 0.08))
        rows = VGroup()
        maxw = 7.5
        colors = [CORAL, VIOLET, TEAL]
        for (name, mib), col in zip(F.DATA_MIB.items(), colors):
            b = bar(maxw * mib / 64.0, 0.55, col)
            nm = T(name, 24, INK if col == TEAL else MUTED, weight=MEDIUM if col == TEAL else NORMAL)
            val = M(f"{mib:g} MB", 26, col)
            rows.add(VGroup(nm, b, val))
        for i, r in enumerate(rows):
            y = 1.1 - i * 1.25
            r[0].move_to([-6.3 + r[0].width / 2, y + 0.45, 0])
            r[1].move_to([-6.3 + r[1].width / 2, y - 0.05, 0])
            r[2].next_to(r[1], RIGHT, buff=0.25)
        for r in rows:
            self.play(FadeIn(r[0]), GrowFromEdge(r[1], LEFT), FadeIn(r[2]), run_time=self.D(1, 0.25))

        self.beat(2)
        self.play(FadeOut(VGroup(head, rows)), run_time=self.D(2, 0.08))
        head = VGroup(T("one full test at the frontier", 30, INK, weight=MEDIUM), T("GeForce RTX 4090", 24, MUTED)).arrange(DOWN, buff=0.12).move_to(UP * 2.3)
        self.play(FadeIn(head), run_time=self.D(2, 0.08))
        hrs = F.HOURS_PER_TEST
        tmax = hrs["proth20"]
        clock = ValueTracker(0)
        track_w = 9.0
        names = [("proth20", CORAL), ("colbert", TEAL)]
        tracks = VGroup(); fills = []; labs = VGroup()
        for i, (nm, col) in enumerate(names):
            y = 0.6 - i * 1.4
            tr = RoundedRectangle(width=track_w, height=0.5, corner_radius=0.25, fill_color=PANEL, fill_opacity=1, stroke_color=LINE, stroke_width=1.5).move_to([0.8, y, 0])
            tracks.add(tr)
            labs.add(T(nm, 28, col, weight=MEDIUM).next_to(tr, LEFT, buff=0.35))
            def mk(tr=tr, nm=nm, col=col):
                frac = min(1.0, clock.get_value() / hrs[nm])
                return RoundedRectangle(width=max(0.5, track_w * frac), height=0.5, corner_radius=0.25, fill_color=col, fill_opacity=0.95, stroke_width=0).move_to(tr.get_left(), aligned_edge=LEFT)
            fills.append(always_redraw(mk))
        tlab = always_redraw(lambda: VGroup(M(f"{clock.get_value():4.1f}", 30, INK), T("hours", 24, MUTED)).arrange(RIGHT, buff=0.15).move_to(DOWN * 2.2))
        self.play(FadeIn(tracks), FadeIn(labs), *[FadeIn(f) for f in fills], FadeIn(tlab), run_time=self.D(2, 0.08))
        tc = hrs["colbert"]
        self.play(clock.animate.set_value(tc), run_time=self.D(2, 0.45 * tc / tmax), rate_func=linear)
        lc = M(f"{tc:.1f} h  ✓", 26, TEAL).next_to(tracks[1], RIGHT, buff=0.2)
        self.add(lc)
        self.play(clock.animate.set_value(tmax), run_time=self.D(2, 0.45 * (1 - tc / tmax)), rate_func=linear)
        lp = M(f"{tmax:.1f} h", 26, CORAL).next_to(tracks[0], RIGHT, buff=0.2)
        done = VGroup(lc, lp)
        badge = VGroup(RoundedRectangle(width=3.3, height=0.9, corner_radius=0.45, fill_color=TEAL, fill_opacity=1, stroke_width=0),
                       T(f"{F.SPEEDUP:.1f}× faster", 32, BG, weight=BOLD))
        badge[1].move_to(badge[0]); badge.move_to(RIGHT * 4.2 + DOWN * 2.2)
        self.play(FadeIn(lp), FadeIn(badge, scale=0.9), run_time=self.D(2, 0.15))

        self.beat(3)
        self.play(FadeOut(VGroup(head, tracks, labs, done, badge, tlab)), *[FadeOut(f) for f in fills], run_time=self.D(3, 0.08))
        head = T("tests per kilowatt-hour", 30, INK, weight=MEDIUM).move_to(UP * 2.4)
        self.play(FadeIn(head), run_time=self.D(3, 0.08))
        base = -1.9
        cols = [MUTED, CORAL, TEAL]
        grp = VGroup()
        for i, ((nm, v), col) in enumerate(zip(F.TESTS_PER_KWH.items(), cols)):
            b = bar(1.7, 3.0 * v / max(F.TESTS_PER_KWH.values()), col).move_to([-3.6 + i * 3.6, base, 0], aligned_edge=DOWN)
            grp.add(VGroup(b, T(nm, 24, col if col != MUTED else INK).next_to(b, DOWN, buff=0.25), M(f"{v:.2f}", 26, col if col != MUTED else INK).next_to(b, UP, buff=0.15)))
        for g_ in grp:
            self.play(GrowFromEdge(g_[0], DOWN), FadeIn(g_[1]), FadeIn(g_[2]), run_time=self.D(3, 0.15))
        ratio = list(F.TESTS_PER_KWH.values())[2] / list(F.TESTS_PER_KWH.values())[0]
        note = T(f"≈ {ratio:.1f}× the tests per kWh of a high-end CPU", 26, TEAL).next_to(head, DOWN, buff=0.3)
        self.play(FadeIn(note), run_time=self.D(3, 0.15))
        self.finish()


# ======================================================================================
class S13Trust(Base):
    SCENE_ID = "13_trust"
    NUMBER, CHAPTER = "12", "Making sure it's right"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        tr = RoundedRectangle(width=11, height=0.4, corner_radius=0.2, fill_color=PANEL, fill_opacity=1, stroke_color=LINE, stroke_width=1.5).move_to(UP * 0.3)
        p = ValueTracker(0)
        fill = always_redraw(lambda: RoundedRectangle(width=max(0.4, 11 * p.get_value()), height=0.4, corner_radius=0.2, fill_color=GOLD, fill_opacity=0.9, stroke_width=0).move_to(tr.get_left(), aligned_edge=LEFT))
        lab = T("a test: hours of squarings", 24, MUTED).next_to(tr, UP, buff=0.3).align_to(tr, LEFT)
        self.add(tr, fill)
        self.play(FadeIn(lab), FadeIn(tr), run_time=self.D(0, 0.08))
        self.play(p.animate.set_value(0.45), run_time=self.D(0, 0.25), rate_func=linear)
        hit = tr.get_left() + RIGHT * 11 * 0.45
        ray = Line(hit + UP * 3 + LEFT * 1.6, hit, color=CORAL, stroke_width=4)
        flip = VGroup(M("0", 30, INK), T("→", 26, MUTED), M("1", 30, CORAL)).arrange(RIGHT, buff=0.15).next_to(hit, DOWN, buff=0.45)
        self.play(ShowPassingFlash(ray, time_width=0.6), run_time=self.D(0, 0.1))
        self.play(FadeIn(flip, scale=1.2), Flash(hit, color=CORAL, line_length=0.25), run_time=self.D(0, 0.12))
        self.play(p.animate.set_value(1.0), run_time=self.D(0, 0.2), rate_func=linear)
        wrong = T("a wrong answer, and nothing to show it", 28, CORAL).next_to(tr, DOWN, buff=1.4)
        self.play(FadeIn(wrong), run_time=self.D(0, 0.15))

        self.beat(1)
        self.play(FadeOut(VGroup(tr, lab, flip, wrong)), FadeOut(fill), run_time=self.D(1, 0.08))
        head = VGroup(M("1", 30, TEAL), T("Exactness is proven, not hoped for", 32, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.25).move_to(UP * 2.3)
        self.play(FadeIn(head), run_time=self.D(1, 0.1))
        cap = RoundedRectangle(width=10, height=0.7, corner_radius=0.1, fill_color=PANEL, fill_opacity=1, stroke_color=LINE, stroke_width=2).move_to(UP * 0.4)
        worst = bar(10 * 80 / 91, 0.7, BLUE).move_to(cap.get_left(), aligned_edge=LEFT)
        l_cap = T("room in the arithmetic: 91 bits", 24, MUTED).next_to(cap, UP, buff=0.2).align_to(cap, RIGHT)
        l_w = T("largest value any input could ever produce: 80 bits", 24, BLUE).next_to(cap, DOWN, buff=0.2).align_to(cap, LEFT)
        self.play(FadeIn(cap), FadeIn(l_cap), run_time=self.D(1, 0.12))
        self.play(GrowFromEdge(worst, LEFT), FadeIn(l_w), run_time=self.D(1, 0.25))
        ok = T("✓  checked before every run; if it fails, colbert won't start", 26, GREEN).move_to(DOWN * 1.5)
        self.play(FadeIn(ok), run_time=self.D(1, 0.2))

        self.beat(2)
        self.play(FadeOut(VGroup(head, cap, worst, l_cap, l_w, ok)), run_time=self.D(2, 0.06))
        head = VGroup(M("2", 30, TEAL), T("A running checksum: the Gerbicz–Li check", 32, INK, weight=MEDIUM)).arrange(RIGHT, buff=0.25).move_to(UP * 2.4)
        self.play(FadeIn(head), run_time=self.D(2, 0.06))
        x0, x1 = -4.6, 5.8
        main = Line([x0, 0.7, 0], [x1, 0.7, 0], color=LINE, stroke_width=6)
        chk = Line([x0, -0.5, 0], [x1, -0.5, 0], color=LINE, stroke_width=6)
        ml = T("calculation", 22, MUTED).next_to(main, LEFT, buff=0.2)
        cl = T("checksum", 22, MUTED).next_to(chk, LEFT, buff=0.2)
        flags = VGroup(*[VGroup(Line([x, -0.75, 0], [x, 0.95, 0], color=FAINT, stroke_width=1.5)) for x in np.linspace(x0, x1, 5)])
        self.play(Create(main), Create(chk), FadeIn(ml), FadeIn(cl), FadeIn(flags), run_time=self.D(2, 0.1))
        pos = ValueTracker(x0)
        prog_m = always_redraw(lambda: Line([x0, 0.7, 0], [pos.get_value(), 0.7, 0], color=GOLD, stroke_width=6))
        prog_c = always_redraw(lambda: Line([x0, -0.5, 0], [pos.get_value(), -0.5, 0], color=VIOLET, stroke_width=6))
        self.add(prog_m, prog_c)
        xs = np.linspace(x0, x1, 5)
        ticks = VGroup()
        self.play(pos.animate.set_value(xs[1]), run_time=self.D(2, 0.08), rate_func=linear)
        ticks.add(T("=", 30, GREEN).move_to([xs[1], 0.1, 0]))
        self.play(FadeIn(ticks[-1]), run_time=self.D(2, 0.03))
        self.play(pos.animate.set_value((xs[1] + xs[2]) / 2), run_time=self.D(2, 0.05), rate_func=linear)
        spark = Dot([(xs[1] + xs[2]) / 2, 0.7, 0], color=CORAL, radius=0.12)
        self.play(Flash(spark, color=CORAL), FadeIn(spark), run_time=self.D(2, 0.05))
        self.play(pos.animate.set_value(xs[2]), run_time=self.D(2, 0.05), rate_func=linear)
        ne = T("≠", 34, CORAL).move_to([xs[2], 0.1, 0])
        self.play(FadeIn(ne, scale=1.3), run_time=self.D(2, 0.05))
        back = CurvedArrow([xs[2], 1.2, 0], [xs[1], 1.2, 0], angle=PI / 3, color=TEAL, stroke_width=3)
        rw = T("rewind to the last verified point", 22, TEAL).next_to(back, UP, buff=0.1)
        self.play(Create(back), FadeIn(rw), run_time=self.D(2, 0.08))
        self.play(pos.animate.set_value(xs[1]), FadeOut(spark), FadeOut(ne), run_time=self.D(2, 0.06))
        self.play(pos.animate.set_value(xs[2]), run_time=self.D(2, 0.07), rate_func=linear)
        eq2 = T("=", 30, GREEN).move_to([xs[2], 0.1, 0])
        self.play(FadeIn(eq2), FadeOut(back), FadeOut(rw), run_time=self.D(2, 0.04))
        self.play(pos.animate.set_value(x1), run_time=self.D(2, 0.1), rate_func=linear)
        more = VGroup(*[T("=", 30, GREEN).move_to([x, 0.1, 0]) for x in xs[3:]])
        self.play(FadeIn(more), run_time=self.D(2, 0.04))
        self.finish()


# ======================================================================================
class S14Impact(Base):
    SCENE_ID = "14_impact"
    NUMBER, CHAPTER = "13", "What it means for the search"

    def construct(self):
        self.beat(0)
        self.play(self.show_tag(), run_time=0.6)
        rng_lab = VGroup(T("n from", 26, MUTED), M("47.9 M", 28, INK), T("to", 26, MUTED), M("57.5 M", 28, INK), T("· all five k", 26, MUTED)).arrange(RIGHT, buff=0.2).move_to(UP * 2.3)
        self.play(FadeIn(rng_lab), run_time=self.D(0, 0.12))
        c = LEFT * 2.6 + DOWN * 0.4
        base_r = Circle(1.6, stroke_color=PANEL, stroke_width=22).move_to(c)
        frac = ValueTracker(0)
        arc = always_redraw(lambda: Arc(radius=1.6, start_angle=PI / 2, angle=-TAU * max(0.001, frac.get_value()), stroke_color=GOLD, stroke_width=22).move_arc_center_to(c))
        val = always_redraw(lambda: M(f"{frac.get_value():.2f}", 52, GOLD, weight=MEDIUM).move_to(c))
        self.add(base_r)
        self.play(FadeIn(base_r), run_time=self.D(0, 0.06))
        self.add(arc, val)
        self.play(frac.animate.set_value(F.EXPECTED_PRIMES), run_time=self.D(0, 0.35), rate_func=rate_functions.ease_out_cubic)
        txt = panel(VGroup(T("expected primes", 30, INK, weight=MEDIUM), T("about a one-in-five chance", 26, MUTED), T("that there's even one", 26, MUTED)).arrange(DOWN, buff=0.18, aligned_edge=LEFT), y=-0.4)
        self.play(FadeIn(txt), run_time=self.D(0, 0.2))

        self.beat(1)
        self.play(FadeOut(VGroup(rng_lab, base_r, txt)), FadeOut(arc), FadeOut(val), run_time=self.D(1, 0.08))
        W, Hh = 1036, 500
        gold_at = (Hh // 2) * W + W // 2 + 7
        big = np.zeros((Hh, W, 4), np.uint8)
        big[..., :3] = (70, 84, 112); big[..., 3] = 170
        big.reshape(-1, 4)[gold_at] = (242, 181, 68, 255)
        im = ImageMobject(big)
        im.set_resampling_algorithm(RESAMPLING_ALGORITHMS["nearest"])
        im.width = 11.0
        im.move_to(DOWN * 0.3)
        # close-up: a 40 x 18 patch around the gold test, drawn as visible dots
        cw, ch = 40, 18
        r0, c0 = gold_at // W - ch // 2, gold_at % W - cw // 2
        cells = VGroup()
        for r in range(ch):
            for c in range(cw):
                isg = (r0 + r) * W + (c0 + c) == gold_at
                cells.add(Square(0.2, stroke_width=0, fill_color=GOLD if isg else "#46546F", fill_opacity=1 if isg else 0.9))
        cells.arrange_in_grid(ch, cw, buff=0.07).move_to(DOWN * 0.3)
        cap = VGroup(T("each square: one 14-million-digit test", 24, MUTED)).to_edge(UP, buff=1.0)
        self.play(FadeIn(cap), LaggedStart(*[FadeIn(c) for c in cells], lag_ratio=0.0008), run_time=self.D(1, 0.22))
        # zoom out: the patch shrinks to its true size inside the full field
        patch_w = im.width * cw / W
        target = im.get_corner(UL) + RIGHT * (c0 + cw / 2) * im.width / W + DOWN * (r0 + ch / 2) * im.height / Hh
        self.play(cells.animate.scale(patch_w / cells.width).move_to(target), FadeIn(im), run_time=self.D(1, 0.25), rate_func=rate_functions.ease_in_out_cubic)
        self.remove(cells)
        gp = im.get_corner(UL) + RIGHT * (gold_at % W + 0.5) * im.width / W + DOWN * (gold_at // W + 0.5) * im.height / Hh
        ringg = Circle(0.25, color=GOLD, stroke_width=3).move_to(gp)
        tot = VGroup(M("≈ 518,000", 40, GOLD, weight=MEDIUM), T("tests per prime, on average", 26, MUTED)).arrange(RIGHT, buff=0.25).to_edge(DOWN, buff=0.5)
        self.play(Create(ringg), FadeIn(tot), run_time=self.D(1, 0.15))
        im.clear_updaters()
        shrink = T("What a faster transform shrinks: the cost of every one of them.", 26, TEAL).move_to(cap)
        self.play(FadeOut(cap), FadeIn(shrink), run_time=self.D(1, 0.2))

        self.beat(2)
        self.play(FadeOut(Group(im, ringg, tot, shrink)), run_time=self.D(2, 0.08))
        hub = VGroup(Circle(0.95, fill_color=PANEL, fill_opacity=1, stroke_color=TEAL, stroke_width=3), T("PrimeGrid", 24, TEAL, weight=MEDIUM)).move_to(DOWN * 0.2)
        hub[1].move_to(hub[0])
        rng = np.random.default_rng(11)
        nodes, links = VGroup(), VGroup()
        for i in range(70):
            ang = rng.uniform(0, TAU); rad = rng.uniform(1.6, 3.3)
            p = hub.get_center() + np.array([1.85 * rad * math.cos(ang), 0.82 * rad * math.sin(ang), 0])
            isgpu = i % 3 != 0
            nd = RoundedRectangle(width=0.34 if isgpu else 0.26, height=0.2, corner_radius=0.04, fill_color=PANEL, fill_opacity=1,
                                  stroke_color=TEAL if isgpu else MUTED, stroke_width=1.5).move_to(p)
            nodes.add(nd)
            links.add(Line(p, hub.get_center(), color=FAINT, stroke_width=1).set_z_index(-1))
        self.play(FadeIn(hub), run_time=self.D(2, 0.1))
        self.play(LaggedStart(*[AnimationGroup(FadeIn(n_), Create(l_)) for n_, l_ in zip(nodes, links)], lag_ratio=0.02), run_time=self.D(2, 0.45))
        self.play(LaggedStart(*[n_.animate.set_fill(TEAL, 0.6) for i, n_ in enumerate(nodes) if i % 3 != 0], lag_ratio=0.02), run_time=self.D(2, 0.25))

        self.beat(3)
        self.play(FadeOut(VGroup(hub, nodes, links)), run_time=self.D(3, 0.1))
        five = VGroup(*[chip(k, CORAL, size=44, stroke=CORAL) for k in F.REMAINING_K]).arrange(RIGHT, buff=0.4).move_to(UP * 0.3)
        self.play(LaggedStart(*[FadeIn(c_, shift=UP * 0.15) for c_ in five], lag_ratio=0.15), run_time=self.D(3, 0.3))
        q = M("?", 60, GOLD, weight=BOLD).next_to(five[0], UP, buff=0.3)
        glow = SurroundingRectangle(five[0], color=GOLD, buff=0.08, corner_radius=0.14, stroke_width=3)
        self.play(FadeIn(q, shift=DOWN * 0.1), Create(glow), run_time=self.D(3, 0.25))
        self.finish(1.0)


# ======================================================================================
class S15Credits(Base):
    SCENE_ID = "15_credits"

    def construct(self):
        self.beat(0)
        word = H("colbert", 96, TEAL).move_to(UP * 1.9)
        url = M(F.REPO_URL, 30, INK).next_to(word, DOWN, buff=0.35)
        built = T("Built on the work of", 24, MUTED).move_to(DOWN * 0.15)
        names = T("Richard Crandall · Barry Fagin · Colin Percival · George Woltman · Yves Gallot · Robert Gerbicz · Darren Li", 22, INK).next_to(built, DOWN, buff=0.2)
        names.scale_to_fit_width(min(names.width, 12.5))
        thanks = T("and the volunteers of Seventeen or Bust and PrimeGrid", 24, GOLD).next_to(names, DOWN, buff=0.55)
        self.play(FadeIn(word, shift=UP * 0.1), run_time=self.D(0, 0.15))
        self.play(FadeIn(url), run_time=self.D(0, 0.12))
        self.play(FadeIn(built), FadeIn(names), run_time=self.D(0, 0.15))
        self.play(FadeIn(thanks), run_time=self.D(0, 0.15))
        self.finish(1.0)


# ======================================================================================
class Thumbnail(Base):
    SCENE_ID = "01_cold_open"   # timing unused; rendered as a still with -s

    def construct(self):
        cand = load("candidate.json")
        lines = VGroup(*[M(cand["leading"][r * 64:(r + 1) * 64], 22, INK) for r in range(16)]).arrange(DOWN, buff=0.16).scale_to_fit_height(7.6)
        lines.set_opacity(0.08)
        title = H("THE LAST FIVE", 120, INK, weight=BOLD).move_to(UP * 1.2)
        five = VGroup(*[chip(k, CORAL, size=46, stroke=CORAL) for k in F.REMAINING_K]).arrange(RIGHT, buff=0.35).next_to(title, DOWN, buff=0.6)
        sub = T("14.4-million-digit primes · exact arithmetic on GPUs", 34, GOLD, weight=MEDIUM).next_to(five, DOWN, buff=0.55)
        self.add(lines, title, five, sub)
