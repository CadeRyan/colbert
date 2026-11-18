"""
Synthesised sound: short effects for on-screen events, and an ambient music bed.
Everything is generated from first principles with numpy, so there are no licensing
questions. Replace the bed with a licensed track via `build.py assemble --music FILE`.
"""
import math, wave
import numpy as np

SR = 48000


def _t(dur):
    return np.arange(int(SR * dur)) / SR


def env(n, attack=0.005, decay=0.2, sustain=0.0, hold=0.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.where(t < attack + hold, 1.0, np.exp(-(t - attack - hold) / max(decay, 1e-4)))
    return a * (sustain + (1 - sustain) * d)


def chirp(f0, f1, dur, shape="sine"):
    t = _t(dur)
    f = f0 * (f1 / f0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    if shape == "sine":
        return np.sin(ph)
    if shape == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    return np.sign(np.sin(ph)) * 0.6


def lowpass(x, cutoff):
    """one-pole low-pass; cutoff may be an array"""
    cutoff = np.broadcast_to(cutoff, x.shape)
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = a[i] * acc + (1 - a[i]) * x[i]
        y[i] = acc
    return y


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(SR * dur))


def bell(f, dur=1.2, decay=0.5):
    t = _t(dur)
    s = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / (decay * 0.5)) + 0.15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / (decay * 0.25))
    return s * env(len(t), 0.003, decay)


def place(dst, src, at):
    i = int(at * SR)
    if i >= len(dst) or i + len(src) <= 0:
        return
    j0 = max(0, -i)
    n = min(len(src) - j0, len(dst) - max(0, i))
    dst[max(0, i):max(0, i) + n] += src[j0:j0 + n]


PENTA = [523.25, 587.33, 659.25, 783.99, 880.0, 1046.5]


def make(kind, seed=0):
    rng = np.random.default_rng(seed)
    if kind == "pop":
        x = chirp(900, 320, 0.09) * env(int(SR * 0.09), 0.002, 0.03) + 0.1 * noise(0.09, seed) * env(int(SR * 0.09), 0.001, 0.004)
    elif kind == "hop":
        x = chirp(380, 950, 0.14, "tri") * env(int(SR * 0.14), 0.004, 0.06) * 0.7
    elif kind == "tick":
        x = np.sin(2 * np.pi * 1600 * _t(0.04)) * env(int(SR * 0.04), 0.001, 0.008) * 0.6
    elif kind == "click":
        a = make("tick", seed); x = np.zeros(int(SR * 0.12)); place(x, a, 0); place(x, a * 0.8, 0.06)
    elif kind == "chime":
        x = bell(PENTA[seed % len(PENTA)], 1.4, 0.55) * 0.5
    elif kind == "coin":
        x = (bell(1760, 0.5, 0.18) + 0.6 * bell(2637, 0.5, 0.12)) * 0.3
    elif kind == "twinkle":
        x = np.zeros(int(SR * 1.0))
        for i, f in enumerate((1046.5, 1318.5, 1568.0)):
            place(x, bell(f, 0.6, 0.2) * 0.25, i * 0.08)
    elif kind == "shimmer":
        x = np.zeros(int(SR * 1.6))
        for i in range(22):
            f = rng.choice(PENTA) * rng.choice([1, 2])
            place(x, bell(f, 0.5, 0.15) * 0.09, rng.uniform(0, 1.0))
    elif kind in ("whoosh", "rocket"):
        dur = 0.8 if kind == "whoosh" else 2.6
        n = noise(dur, seed)
        tt = _t(dur)
        shape = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
        cut = 300 + 2500 * shape if kind == "whoosh" else 200 + 900 * shape
        x = lowpass(n, cut) * shape * (0.5 if kind == "whoosh" else 0.7)
    elif kind == "swell":
        dur = 2.4; tt = _t(dur)
        x = sum(np.sin(2 * np.pi * f * tt) for f in (293.66, 369.99, 440.0, 554.37)) / 4
        x *= np.clip(tt / 1.4, 0, 1) ** 2 * np.exp(-np.clip(tt - 1.4, 0, None) / 0.4) * 0.6
    elif kind == "rise":
        dur = 1.4
        x = chirp(220, 880, dur, "tri") * np.clip(_t(dur) / dur, 0, 1) ** 1.5 * env(int(SR * dur), 0.01, 10) * 0.35
    elif kind in ("crash", "crumble"):
        dur = 1.0
        x = lowpass(noise(dur, seed), 1800) * env(int(SR * dur), 0.002, 0.25) * 0.8
        for i in range(8):
            place(x, lowpass(noise(0.08, seed + i), 900) * env(int(SR * 0.08), 0.001, 0.03) * 0.6, rng.uniform(0.05, 0.7))
    elif kind == "boom":
        dur = 1.8
        x = chirp(70, 38, dur) * env(int(SR * dur), 0.004, 0.6) * 0.9 + lowpass(noise(dur, seed), 400) * env(int(SR * dur), 0.002, 0.3) * 0.5
        place(x, bell(1046.5, 1.6, 0.8) * 0.35, 0.05)
    elif kind == "thud":
        x = chirp(120, 60, 0.25) * env(int(SR * 0.25), 0.002, 0.08) * 0.8
    elif kind == "steps":
        x = np.zeros(int(SR * 1.2))
        for i in range(4):
            place(x, chirp(160, 90, 0.07) * env(int(SR * 0.07), 0.002, 0.025) * 0.5, i * 0.26)
    elif kind == "fanfare":
        x = np.zeros(int(SR * 2.2))
        for i, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
            place(x, bell(f, 1.8, 0.7) * 0.35, i * 0.11)
    elif kind in ("flip", "paper"):
        dur = 0.08 if kind == "flip" else 0.45
        x = lowpass(noise(dur, seed), 4000) * env(int(SR * dur), 0.002, dur / 3) * 0.35
    elif kind == "zap":
        x = (chirp(1400, 180, 0.35, "sq") * 0.4 + 0.2 * noise(0.35, seed)) * env(int(SR * 0.35), 0.002, 0.12) * 0.6
    elif kind == "crack":
        x = noise(0.15, seed) * env(int(SR * 0.15), 0.0005, 0.02) * 0.7
    elif kind == "truck":
        dur = 1.4; tt = _t(dur)
        x = lowpass(chirp(48, 52, dur, "sq"), 300) * (0.7 + 0.3 * np.sin(2 * np.pi * 9 * tt)) * np.sin(np.pi * tt / dur) * 0.6
    elif kind == "wobble":
        dur = 0.7; tt = _t(dur)
        f = 500 + 120 * np.sin(2 * np.pi * 9 * tt)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.01, 0.25) * 0.35
    elif kind == "lock":
        x = np.zeros(int(SR * 0.3))
        place(x, np.sin(2 * np.pi * 2400 * _t(0.05)) * env(int(SR * 0.05), 0.001, 0.01) * 0.4, 0)
        place(x, np.sin(2 * np.pi * 1700 * _t(0.08)) * env(int(SR * 0.08), 0.001, 0.02) * 0.4, 0.09)
    elif kind == "wrong":
        x = np.zeros(int(SR * 0.7))
        place(x, chirp(330, 300, 0.22, "tri") * env(int(SR * 0.22), 0.005, 0.12) * 0.5, 0)
        place(x, chirp(250, 210, 0.35, "tri") * env(int(SR * 0.35), 0.005, 0.18) * 0.5, 0.2)
    elif kind == "water":
        x = np.zeros(int(SR * 1.5))
        for i in range(16):
            f = rng.uniform(350, 900)
            place(x, chirp(f, f * 1.6, 0.06) * env(int(SR * 0.06), 0.002, 0.02) * 0.25, rng.uniform(0, 1.3))
    elif kind == "rewind":
        dur = 0.55; tt = _t(dur)
        f = np.linspace(1200, 300, len(tt)) * (1 + 0.05 * np.sin(2 * np.pi * 30 * tt))
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(tt), 0.01, 0.3) * 0.3
    else:
        x = np.zeros(1)
    peak = float(np.abs(x).max()) if len(x) else 0.0
    if peak > 0.85:
        x = x * (0.85 / peak)
    return x.astype(np.float32)


def place2(out, src, at, pan, gain=1.0):
    i = int(at * SR)
    if i >= len(out):
        return
    m = min(len(src), len(out) - i)
    out[i:i + m, 0] += src[:m] * gain * (1 - pan)
    out[i:i + m, 1] += src[:m] * gain * pan


def sfx_track(cues, total, gain=1.0):
    """cues: list of (time_s, kind, gain). Returns a stereo float array."""
    out = np.zeros((int(SR * total) + SR, 2), np.float32)
    cache = {}
    for i, (at, kind, g) in enumerate(cues):
        key = (kind, i % 6)
        if key not in cache:
            cache[key] = make(kind, i % 6)
        pan = 0.5 + 0.25 * math.sin(i * 1.7)
        place2(out, cache[key], max(0.0, at), pan, g * gain * 1.4)
    return out[: int(SR * total)]


def music_bed(total, seed=7):
    """slow, warm pad chords in D with occasional soft bell plucks"""
    rng = np.random.default_rng(seed)
    n = int(SR * total)
    out = np.zeros((n, 2), np.float32)
    chords = [(146.83, 185.0, 220.0, 277.18, 329.63), (123.47, 146.83, 185.0, 220.0, 293.66),
              (98.0, 123.47, 146.83, 185.0, 246.94), (110.0, 138.59, 164.81, 185.0, 220.0)]
    seg = 8.0
    k = 0
    t0 = 0.0
    while t0 < total:
        dur = min(seg + 3.0, total - t0 + 0.01)
        tt = np.arange(int(SR * dur)) / SR
        e = np.clip(tt / 2.5, 0, 1) * np.clip((dur - tt) / 3.0, 0, 1)
        ch = chords[k % 4]
        sl, sr = np.zeros(len(tt)), np.zeros(len(tt))
        for j, f in enumerate(ch):
            for det, pan in ((0.9985, 0.3), (1.0, 0.5), (1.0015, 0.7)):
                v = np.sin(2 * np.pi * f * det * tt + rng.uniform(0, 6.28)) * (0.7 if j else 1.0)
                v += 0.18 * np.sin(2 * np.pi * f * 2 * det * tt)
                sl += v * (1 - pan); sr += v * pan
        lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.11 * tt + k)
        bass = np.sin(2 * np.pi * ch[0] / 2 * tt) * 0.9
        i0 = int(SR * t0)
        m = min(len(tt), n - i0)
        out[i0:i0 + m, 0] += ((sl * lfo + bass) * e)[:m] * 0.035
        out[i0:i0 + m, 1] += ((sr * lfo + bass) * e)[:m] * 0.035
        # plucks
        notes = [x * 4 for x in ch[1:]]
        tp = rng.uniform(1.0, 3.0)
        while tp < seg:
            pl = bell(rng.choice(notes), 2.0, 0.9) * 0.05
            pan = rng.uniform(0.25, 0.75)
            for d, g in ((0, 1.0), (0.33, 0.45), (0.66, 0.2)):
                place2(out, pl, t0 + tp + d, pan, g)
            tp += rng.uniform(1.8, 3.6)
        t0 += seg
        k += 1
    fade = np.clip(np.arange(n) / (SR * 3.0), 0, 1) * np.clip((n - np.arange(n)) / (SR * 4.0), 0, 1)
    return out * fade[:, None]


def write_wav(path, stereo):
    x = np.clip(stereo, -1, 1)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
