"""
Beat timing. Each scene's narration is a list of beats (film/script.py). This module decides
when each beat starts, from the best information available:

  1. vo/<scene>.wav + vo/<scene>.txt   Audacity label track: one label at the start of each
                                       beat, in order. Exact sync.
  2. vo/<scene>.wav                    the scene's recording alone: nominal beat lengths
                                       (from word counts) are scaled to fit it.
  3. nothing                           nominal beat lengths from word counts.

Any of .wav .flac .mp3 .m4a works. The directory is $COLBERT_VO_DIR, default video/vo.
"""
import os, json, subprocess
from dataclasses import dataclass, field
from .script import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
WPS = 2.6            # words per second: 156 words per minute, a measured documentary pace
GAP = 0.55           # pause after each beat (s)
LEAD = 0.7           # picture before the first word (s)
TAIL = 1.1           # picture after the last word (s)
AUDIO_EXT = (".wav", ".flac", ".mp3", ".m4a")


def vo_dir():
    return os.environ.get("COLBERT_VO_DIR", os.path.join(VIDEO, "vo"))


def scene(scene_id):
    for s in SCENES:
        if s["id"] == scene_id:
            return s
    raise KeyError(scene_id)


def words(text):
    return len(text.split())


def audio_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def find_vo(scene_id):
    for ext in AUDIO_EXT:
        p = os.path.join(vo_dir(), scene_id + ext)
        if os.path.exists(p):
            return p
    return None


def read_labels(path):
    starts = []
    for line in open(path):
        parts = line.strip().split("\t")
        if len(parts) >= 2 and parts[0].replace(".", "", 1).isdigit():
            starts.append(float(parts[0]))
    return starts


@dataclass
class Timing:
    scene_id: str
    starts: list
    durs: list
    total: float
    vo_path: str = None
    vo_offset: float = LEAD
    source: str = "nominal"
    texts: list = field(default_factory=list)


def timing_for(scene_id):
    beats = scene(scene_id)["beats"]
    nominal = [words(b) / WPS + GAP for b in beats]
    vo = find_vo(scene_id)
    lab = os.path.join(vo_dir(), scene_id + ".txt")
    if vo and os.path.exists(lab):
        rel = read_labels(lab)
        if len(rel) != len(beats):
            raise SystemExit(f"{lab}: {len(rel)} labels for {len(beats)} beats")
        vd = audio_duration(vo)
        ends = rel[1:] + [vd]
        starts = [LEAD + r for r in rel]
        durs = [e - r for r, e in zip(rel, ends)]
        source = "labels"
    elif vo:
        vd = audio_duration(vo)
        scale = vd / sum(nominal)
        durs = [d * scale for d in nominal]
        starts, t = [], LEAD
        for d in durs:
            starts.append(t); t += d
        source = f"vo (x{scale:.2f})"
    else:
        durs = nominal
        starts, t = [], LEAD
        for d in durs:
            starts.append(t); t += d
        source = "nominal"
    total = starts[-1] + durs[-1] + TAIL
    return Timing(scene_id, starts, durs, total, vo, LEAD, source, beats)
