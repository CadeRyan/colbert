"""Visual language: palette, type, and the shared scene base class."""
import json, os, sys
import numpy as np
from manim import *
from .timing import timing_for, VIDEO

# ---- palette ---------------------------------------------------------------------------
BG = "#0B1020"        # deep navy
PANEL = "#141B2E"
LINE = "#26304A"
GRIDC = "#1A2238"
INK = "#E8ECF4"       # primary text
MUTED = "#8A94AD"     # secondary text
FAINT = "#4A5470"
GOLD = "#F2B544"      # primes, discoveries
TEAL = "#3CC8C8"      # transforms, colbert
CORAL = "#F06E5A"     # obstacles, errors, k
VIOLET = "#9B8CFF"    # fields, the mathematics
GREEN = "#6BD48A"     # verified
BLUE = "#5B8DEF"      # data, memory

SANS = "Inter"
DISPLAY = "Inter Display"
MONO = "JetBrains Mono"

COVER_COLORS = {3: "#5B8DEF", 5: "#3CC8C8", 7: "#6BD48A", 13: "#F2B544", 19: "#F06E5A", 37: "#9B8CFF", 73: "#E879B9"}

DATA = os.path.join(VIDEO, "data")


def load(name):
    return json.load(open(os.path.join(DATA, name)))


def T(s, size=36, color=INK, weight=NORMAL, font=SANS, **kw):
    return Text(s, font=font, font_size=size, color=color, weight=weight, **kw)


def M(s, size=36, color=INK, weight=NORMAL, **kw):
    return Text(s, font=MONO, font_size=size, color=color, weight=weight, **kw)


def H(s, size=60, color=INK, weight=SEMIBOLD, **kw):
    return Text(s, font=DISPLAY, font_size=size, color=color, weight=weight, **kw)


def P(markup, size=36, color=INK, font=SANS, **kw):
    """Pango markup, for mixed styles and superscripts: P('k·2<sup>n</sup>+1')."""
    return MarkupText(markup, font=font, font_size=size, color=color, **kw)


def kexpr(k, n, size=40, color=INK, kcolor=None, mono=True):
    kc = kcolor or color
    f = MONO if mono else SANS
    return MarkupText(f'<span foreground="{kc}">{k}</span> × 2<sup>{n}</sup> + 1', font=f, font_size=size, color=color)


def chip(label, color=INK, fill=PANEL, size=30, pad=0.22, font=MONO, stroke=None, radius=0.12):
    t = Text(str(label), font=font, font_size=size, color=color)
    box = RoundedRectangle(width=t.width + 2 * pad, height=t.height + 1.5 * pad, corner_radius=radius,
                           fill_color=fill, fill_opacity=1, stroke_color=stroke or LINE, stroke_width=1.5)
    t.move_to(box)
    return VGroup(box, t)


def bar(width, height, color, opacity=1.0):
    return Rectangle(width=max(width, 1e-3), height=height, fill_color=color, fill_opacity=opacity, stroke_width=0)


def fmt(n):
    return f"{n:,}"


class BeatScene(Scene):
    """A scene whose animations are pinned to narration beats (see film/timing.py)."""
    SCENE_ID = ""
    NUMBER = ""
    CHAPTER = ""

    def setup(self):
        self.camera.background_color = BG
        self.tm = timing_for(self.SCENE_ID)
        self._overruns = []
        if self.CHAPTER:
            self.add_chapter_tag()

    # --- time ---
    def now(self):
        return self.renderer.time

    def until(self, t):
        dt = t - self.now()
        if dt > 1 / 120:
            self.wait(dt)
        elif dt < -0.25:
            self._overruns.append(round(-dt, 2))

    def beat(self, i, frac=0.0):
        self.until(self.tm.starts[i] + frac * self.tm.durs[i])

    def D(self, i, frac=1.0, lo=0.2):
        return max(lo, frac * self.tm.durs[i])

    def finish(self, fade=0.6):
        self.until(self.tm.total - fade)
        mobs = [m for m in self.mobjects]
        if mobs:
            self.play(*[FadeOut(m) for m in mobs], run_time=fade)
        self.until(self.tm.total)
        info = dict(scene=self.SCENE_ID, total=self.tm.total, source=self.tm.source, overruns=self._overruns)
        log = os.path.join(VIDEO, "out", "timing_log.jsonl")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps(info) + "\n")

    # --- furniture ---
    def add_chapter_tag(self):
        num = T(self.NUMBER, 20, TEAL, weight=SEMIBOLD, font=MONO)
        name = T(self.CHAPTER.upper(), 20, MUTED, weight=MEDIUM)
        name.next_to(num, RIGHT, buff=0.22)
        tag = VGroup(num, name).to_corner(UL, buff=0.45)
        rule = Line(LEFT, RIGHT, stroke_width=2, color=TEAL).set_width(0.5).next_to(tag, DOWN, buff=0.12, aligned_edge=LEFT)
        self.tag = VGroup(tag, rule)
        self.add(self.tag)
        self.tag.set_opacity(0)
        self.tag_on = True

    def show_tag(self):
        return self.tag.animate.set_opacity(1)

    def caption(self, text, color=MUTED, size=28):
        """a short on-screen key phrase at the bottom of the frame"""
        c = T(text, size, color)
        c.to_edge(DOWN, buff=0.6)
        return c
