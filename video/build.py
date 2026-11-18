#!/usr/bin/env python3
"""
Build the explainer video.

  video/.venv/bin/python video/build.py script            write VO_SCRIPT.md (read this to record)
  video/.venv/bin/python video/build.py render            render every scene at 1080p60 (about 40 min on 4 cores)
  video/.venv/bin/python video/build.py assemble          join scenes + voice-over -> out/colbert_explainer.mp4
  video/.venv/bin/python video/build.py all               render + assemble + thumbnail
  video/.venv/bin/python video/build.py thumbnail         out/thumbnail.png (1920x1080; YouTube accepts it)
  video/.venv/bin/python video/build.py scratch-vo        synthetic placeholder narration in vo_scratch/

Options:
  --preview             480p15, for checking layout quickly
  --vo DIR              voice-over directory (default video/vo; use vo_scratch for the placeholder)
  --music FILE          optional music bed, ducked under the voice
  --only 03,07          only these scenes (by number)
  -j N                  parallel renders (default: CPU count)

Voice-over: put one file per scene in video/vo/, named after the scene id
(e.g. 02_sierpinski.wav). Optionally add an Audacity label track (02_sierpinski.txt)
with one label at the start of each beat for exact sync. Scenes stretch to fit the
recording, so re-render after adding or changing voice-over.
"""
import argparse, glob, hashlib, json, os, re, shutil, subprocess, sys, textwrap
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from film.script import SCENES, TITLE, SUBTITLE          # noqa: E402
from film import timing as TM                             # noqa: E402

OUT = os.path.join(HERE, "out")
PY = os.path.join(HERE, ".venv", "bin", "python")
MANIM = os.path.join(HERE, ".venv", "bin", "manim")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "")


def scene_classes():
    """scene id -> manim class name, in film order"""
    names = {}
    for mod in ("scenes_a", "scenes_b", "scenes_c"):
        src = open(os.path.join(HERE, "film", mod + ".py")).read()
        for m in re.finditer(r'class (S\d\d\w+)\(Base\):\n\s+SCENE_ID = "([^"]+)"', src):
            names[m.group(2)] = m.group(1)
    return [(s["id"], names[s["id"]]) for s in SCENES]


def quality_dirs(preview):
    return ("media_preview", "480p15") if preview else ("media_final", "1080p60")


def scene_file(cls, preview):
    media, res = quality_dirs(preview)
    return os.path.join(OUT, media, "videos", "scenes", res, cls + ".mp4")


def source_hash(sid, vo_dir, preview):
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(HERE, "film", "*.py")) + glob.glob(os.path.join(HERE, "data", "*.json")) + [os.path.join(HERE, "scenes.py")]):
        h.update(open(f, "rb").read())
    for ext in TM.AUDIO_EXT + (".txt",):
        p = os.path.join(vo_dir, sid + ext)
        if os.path.exists(p):
            st = os.stat(p); h.update(f"{p}{st.st_size}{st.st_mtime}".encode())
    h.update(b"preview" if preview else b"final")
    return h.hexdigest()


def duration(path):
    return TM.audio_duration(path)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit(f"command failed: {' '.join(cmd[:6])} ...")
    return r


# ------------------------------------------------------------------ script
def cmd_script(args):
    lines = [f"# Voice-over script: {TITLE}", "",
             f"*{SUBTITLE}*", "",
             "## How to record", "",
             "* Record **one file per scene**, named exactly as the heading says (e.g. `02_sierpinski.wav`), "
             "and put them in `video/vo/`. WAV or FLAC preferred; MP3 and M4A also work.",
             "* Read at a steady, unhurried pace, roughly 150 words a minute. The total runs about "
             f"{sum(TM.words(b) for s in SCENES for b in s['beats']) / 150:.0f} minutes.",
             "* Leave about half a second of silence at the start and end of each file. Each scene stretches to fit the length of your recording.",
             "* The ▸ marks are **beats**: each one is a group of animations. For exact sync, add a label at the start of each beat in Audacity "
             "(*Edit → Labels → Add Label at Selection*, one per ▸, in order) and export it with *File → Export → Export Labels* as `02_sierpinski.txt` next to the audio. "
             "Without labels, the beats are spread in proportion to their word counts, which is usually close enough.",
             "* Then run `video/.venv/bin/python video/build.py all`.",
             "",
             "Pronunciation: **Sierpiński** sher-PIN-skee · **Wacław** VAHTS-wahf · **Proth** proat · **Gerbicz** GER-beech · "
             "**gwnum** gee-double-you-num · **proth20** proth-twenty · **LLR2** L-L-R-two · **Percival** PER-si-vul · **Gallot** gah-LOH.",
             ""]
    total = 0.0
    for i, s in enumerate(SCENES):
        tm = TM.timing_for(s["id"])
        total += tm.total
        words = sum(TM.words(b) for b in s["beats"])
        lines += [f"## `{s['id']}`  ·  {s['chapter']}", "", f"*{words} words, about {tm.total - TM.LEAD - TM.TAIL:.0f} s*", ""]
        for j, b in enumerate(s["beats"], 1):
            lines += [f"▸ **{j}.** {b}", ""]
    lines += ["---", "", f"Estimated running time at the planning pace: {int(total // 60)} min {int(total % 60)} s.", "",
              "All figures in scene 12 (`12_results`) are projections from `tools/perf_model.py`, "
              "set in `video/film/facts.py`. Replace them with measured values before publishing.", ""]
    path = os.path.join(HERE, "VO_SCRIPT.md")
    open(path, "w").write("\n".join(lines))
    print(f"wrote {path}  (~{total / 60:.1f} min)")


# ------------------------------------------------------------------ scratch VO
def cmd_scratch_vo(args):
    voice = PIPER_VOICE or args.voice
    if not voice or not os.path.exists(voice):
        raise SystemExit("set PIPER_VOICE or --voice to a Piper .onnx voice model")
    d = os.path.join(HERE, "vo_scratch"); os.makedirs(d, exist_ok=True)
    piper = os.path.join(HERE, ".venv", "bin", "piper")
    tmp = os.path.join(OUT, "tmp_tts"); os.makedirs(tmp, exist_ok=True)
    gap = 0.6
    for s in SCENES:
        parts, labels, t = [], [], 0.25
        for j, b in enumerate(s["beats"]):
            w = os.path.join(tmp, f"{s['id']}_{j}.wav")
            subprocess.run([piper, "-m", voice, "-f", w, "--length-scale", "1.05", "--sentence-silence", "0.25"], input=b, text=True, capture_output=True, check=True)
            labels.append(f"{t:.3f}\t{t:.3f}\tbeat {j + 1}")
            parts.append(w); t += duration(w) + gap
        lst = os.path.join(tmp, s["id"] + ".txt")
        with open(lst, "w") as f:
            f.write(f"file '{os.path.join(tmp, 'lead.wav')}'\n")
            for p in parts:
                f.write(f"file '{p}'\nfile '{os.path.join(tmp, 'gap.wav')}'\n")
        sr = "22050"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono", "-t", "0.25", os.path.join(tmp, "lead.wav")])
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono", "-t", str(gap), os.path.join(tmp, "gap.wav")])
        out = os.path.join(d, s["id"] + ".wav")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", out])
        open(os.path.join(d, s["id"] + ".txt"), "w").write("\n".join(labels) + "\n")
        print(f"{s['id']}: {duration(out):.1f} s")


# ------------------------------------------------------------------ render
def cmd_render(args):
    vo_dir = os.path.abspath(args.vo)
    os.makedirs(OUT, exist_ok=True)
    cache_path = os.path.join(OUT, "render_cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    media, _ = quality_dirs(args.preview)
    todo = []
    for sid, cls in scene_classes():
        if args.only and sid[:2] not in args.only:
            continue
        key = source_hash(sid, vo_dir, args.preview)
        if cache.get(f"{media}/{sid}") == key and os.path.exists(scene_file(cls, args.preview)) and not args.force:
            print(f"  {sid}: up to date")
            continue
        todo.append((sid, cls, key))
    todo.sort(key=lambda x: -TM.timing_for(x[0]).total)   # longest first
    env = dict(os.environ, COLBERT_VO_DIR=vo_dir, COLBERT_MASTER="0" if args.preview else "1")
    q = ["-ql"] if args.preview else ["-qh", "--fps", "60"]
    log = os.path.join(OUT, "timing_log.jsonl")
    if os.path.exists(log):
        os.remove(log)

    def one(item):
        sid, cls, key = item
        r = subprocess.run([MANIM, "render", *q, "--disable_caching", "--progress_bar", "none", "--media_dir", os.path.join(OUT, media),
                            os.path.join(HERE, "scenes.py"), cls], capture_output=True, text=True, env=env, cwd=HERE)
        ok = r.returncode == 0 and os.path.exists(scene_file(cls, args.preview))
        if not ok:
            open(os.path.join(OUT, f"error_{sid}.log"), "w").write(r.stdout + r.stderr)
        return sid, key, ok

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for sid, key, ok in ex.map(one, todo):
            print(f"  {sid}: {'rendered' if ok else 'FAILED (see out/error_' + sid + '.log)'}", flush=True)
            if ok:
                cache[f"{media}/{sid}"] = key
                json.dump(cache, open(cache_path, "w"), indent=1)
    if os.path.exists(log):
        for line in open(log):
            d = json.loads(line)
            if d["overruns"]:
                print(f"  note: {d['scene']} animations ran past their beat by {d['overruns']} s")


# ------------------------------------------------------------------ assemble
def fmt_ts(t, srt=False):
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{int(h)}:{int(m):02d}:{int(s):02d}" if h else f"{int(m)}:{int(s):02d}"


def captions(scene_times, vo_dir):
    os.environ["COLBERT_VO_DIR"] = vo_dir
    cues = []
    for (sid, start, dur), s in zip(scene_times, SCENES):
        tm = TM.timing_for(sid)
        for j, text in enumerate(s["beats"]):
            b0 = start + tm.starts[j]
            speak = max(0.5, tm.durs[j] - (TM.GAP if tm.source != "labels" else 0.35))
            sentences = re.split(r"(?<=[.?!])\s+", text)
            chunks = [c for sen in sentences for c in textwrap.wrap(sen, 84, break_long_words=False)]
            total_chars = sum(len(c) for c in chunks)
            t = b0
            for c in chunks:
                d = speak * len(c) / total_chars
                lines = textwrap.wrap(c, 44, break_long_words=False)
                cues.append((t, t + d - 0.04, "\n".join(lines[:2] if len(lines) <= 2 else [" ".join(lines[:len(lines) // 2]), " ".join(lines[len(lines) // 2:])])))
                t += d
    out = []
    for i, (a, b, txt) in enumerate(cues, 1):
        out += [str(i), f"{fmt_ts(a, True)} --> {fmt_ts(b, True)}", txt, ""]
    return "\n".join(out)


def cmd_assemble(args):
    vo_dir = os.path.abspath(args.vo)
    os.environ["COLBERT_VO_DIR"] = vo_dir
    tmp = os.path.join(OUT, "tmp_assemble"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    scenes, t = [], 0.0
    for sid, cls in scene_classes():
        f = scene_file(cls, args.preview)
        if not os.path.exists(f):
            raise SystemExit(f"missing render for {sid}: run `build.py render{' --preview' if args.preview else ''}` first")
        d = duration(f)
        scenes.append((sid, f, t, d)); t += d
    total = t
    # video: identical encoder settings for every scene, so concatenate without re-encoding
    lst = os.path.join(tmp, "video.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for _, f, _, _ in scenes))
    vid = os.path.join(tmp, "video.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-an", "-c", "copy", vid])
    # audio: each scene's voice-over, delayed by the lead-in, padded to the scene's length
    segs, have_vo = [], False
    for sid, f, start, d in scenes:
        seg = os.path.join(tmp, f"a_{sid}.wav")
        vo = TM.find_vo(sid)
        if vo:
            have_vo = True
            ms = int(TM.LEAD * 1000)
            run(["ffmpeg", "-y", "-v", "error", "-i", vo, "-af", f"aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},apad", "-t", f"{d:.3f}", "-ar", "48000", "-ac", "2", seg])
        else:
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{d:.3f}", seg])
        segs.append(seg)
    alst = os.path.join(tmp, "audio.txt")
    open(alst, "w").write("".join(f"file '{s}'\n" for s in segs))
    voice = os.path.join(tmp, "voice.wav")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", alst, "-c", "pcm_s16le", voice])
    mix = voice
    if args.music:
        mix = os.path.join(tmp, "mix.wav")
        fo = max(0.0, total - 4)
        run(["ffmpeg", "-y", "-v", "error", "-i", voice, "-stream_loop", "-1", "-i", args.music, "-filter_complex",
             f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.22,afade=t=in:d=3,afade=t=out:st={fo:.2f}:d=4,atrim=0:{total:.3f}[m];"
             f"[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[md];[v][md]amix=inputs=2:normalize=0[out]",
             "-map", "[out]", "-t", f"{total:.3f}", mix])
    final_audio = os.path.join(tmp, "final.m4a")
    af = "loudnorm=I=-14:TP=-1.0:LRA=11" if (have_vo or args.music) else "anull"
    run(["ffmpeg", "-y", "-v", "error", "-i", mix, "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "256k", final_audio])
    name = args.output or ("colbert_explainer_preview.mp4" if args.preview else "colbert_explainer.mp4")
    out = os.path.join(OUT, name)
    run(["ffmpeg", "-y", "-v", "error", "-i", vid, "-i", final_audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
         "-movflags", "+faststart", "-shortest", out])
    # captions and chapters
    st = [(sid, start, d) for sid, _, start, d in scenes]
    base = os.path.splitext(out)[0]
    open(base + ".srt", "w").write(captions(st, vo_dir))
    desc = [TITLE, "", SUBTITLE, "", "Chapters"]
    for (sid, start, d), s in zip(st, SCENES):
        if d >= 10 and s["chapter"] != "Credits":      # YouTube ignores chapter lists with any chapter under 10 s
            desc.append(f"{fmt_ts(start)} {s['chapter']}")
    open(base + "_youtube_description.txt", "w").write("\n".join(desc) + "\n")
    print(f"wrote {out}  ({fmt_ts(total)}, {os.path.getsize(out) / 1e6:.0f} MB, voice-over: {'yes' if have_vo else 'none'}{', music' if args.music else ''})")
    print(f"      {base}.srt, {base}_youtube_description.txt")


def cmd_thumbnail(args):
    media = os.path.join(OUT, "media_thumb")
    run([MANIM, "render", "-qh", "-s", "--disable_caching", "--progress_bar", "none", "--media_dir", media, os.path.join(HERE, "scenes.py"), "Thumbnail"], cwd=HERE)
    pngs = glob.glob(os.path.join(media, "images", "**", "*.png"), recursive=True)
    shutil.copy(sorted(pngs, key=os.path.getmtime)[-1], os.path.join(OUT, "thumbnail.png"))
    print("wrote", os.path.join(OUT, "thumbnail.png"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["script", "render", "assemble", "all", "thumbnail", "scratch-vo"])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--vo", default=os.path.join(HERE, "vo"))
    ap.add_argument("--music")
    ap.add_argument("--only", type=lambda s: [x.zfill(2) for x in s.split(",")])
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("-o", "--output")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voice", help="Piper voice model for scratch-vo")
    args = ap.parse_args()
    if args.command == "script":
        cmd_script(args)
    elif args.command == "scratch-vo":
        cmd_scratch_vo(args)
    elif args.command == "render":
        cmd_render(args)
    elif args.command == "assemble":
        cmd_assemble(args)
    elif args.command == "thumbnail":
        cmd_thumbnail(args)
    elif args.command == "all":
        cmd_render(args); cmd_assemble(args)
        if not args.preview:
            cmd_thumbnail(args)


if __name__ == "__main__":
    main()
