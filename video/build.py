#!/usr/bin/env python3
"""
Build the explainer video.

  video/.venv/bin/python video/build.py script        write VO_SCRIPT.md (read this to record)
  video/.venv/bin/python video/build.py render        render every scene at 1080p60
  video/.venv/bin/python video/build.py assemble      join scenes + voice + effects + music -> out/colbert_explainer.mp4
  video/.venv/bin/python video/build.py all           render + assemble + thumbnail
  video/.venv/bin/python video/build.py thumbnail     out/thumbnail.png (1920x1080)
  video/.venv/bin/python video/build.py scratch-vo    synthetic placeholder narration in vo_scratch/
  video/.venv/bin/python video/build.py stills        contact sheet of every scene, for checking layout

Options:
  --preview             960x540 at 30 fps, for checking timing quickly
  --vo DIR              voice-over directory (default video/vo; use video/vo_scratch for the placeholder)
  --music FILE          use this music bed instead of the generated one
  --no-music            no music bed
  --only 03,07          only these scenes (by number)
  -j N                  parallel render processes (default: CPU count)

Voice-over: one file per scene in video/vo/, named after the scene id (e.g.
02_sierpinski.wav). An optional Audacity label track (02_sierpinski.txt) with one label
at the start of each beat gives exact sync. Scenes stretch to fit the recording, so
re-render after adding or changing voice-over.
"""
import argparse, glob, hashlib, json, os, re, shutil, subprocess, sys, textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from film.script import SCENES, TITLE, SUBTITLE          # noqa: E402
from film import timing as TM                             # noqa: E402

OUT = os.path.join(HERE, "out")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
        raise SystemExit(f"command failed: {' '.join(map(str, cmd[:6]))} ...")
    return r


def duration(path):
    return TM.audio_duration(path)


def scenes():
    from toon import scenes as S
    return [(cls.ID, cls.__name__) for cls in S.ORDER]


def qdir(preview):
    return os.path.join(OUT, "toon_preview" if preview else "toon_final")


def scene_file(sid, preview):
    return os.path.join(qdir(preview), sid + ".mp4")


def source_hash(sid, vo_dir, preview):
    h = hashlib.sha256()
    files = sorted(glob.glob(os.path.join(HERE, "toon", "**", "*.py"), recursive=True) + glob.glob(os.path.join(HERE, "film", "*.py")) +
                   glob.glob(os.path.join(HERE, "data", "*.json")))
    for f in files:
        h.update(open(f, "rb").read())
    for ext in TM.AUDIO_EXT + (".txt",):
        p = os.path.join(vo_dir, sid + ext)
        if os.path.exists(p):
            st = os.stat(p); h.update(f"{p}{st.st_size}{st.st_mtime}".encode())
    h.update(b"preview" if preview else b"final")
    return h.hexdigest()


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
    for s in SCENES:
        tm = TM.timing_for(s["id"])
        total += tm.total
        words = sum(TM.words(b) for b in s["beats"])
        lines += [f"## `{s['id']}`  ·  {s['chapter']}", "", f"*{words} words, about {tm.total - TM.LEAD - TM.TAIL:.0f} s*", ""]
        for j, b in enumerate(s["beats"], 1):
            lines += [f"▸ **{j}.** {b}", ""]
    lines += ["---", "", f"Estimated running time at the planning pace: {int(total // 60)} min {int(total % 60)} s.", "",
              "All figures in scene 14 (`14_results`) are projections from `tools/perf_model.py`, "
              "set in `video/film/facts.py`. Replace them with measured values before publishing.", ""]
    path = os.path.join(HERE, "VO_SCRIPT.md")
    open(path, "w").write("\n".join(lines))
    print(f"wrote {path}  (~{total / 60:.1f} min)")


# ------------------------------------------------------------------ scratch VO
def cmd_scratch_vo(args):
    voice = os.environ.get("PIPER_VOICE") or args.voice
    if not voice or not os.path.exists(voice):
        raise SystemExit("set PIPER_VOICE or --voice to a Piper .onnx voice model")
    d = os.path.join(HERE, "vo_scratch"); os.makedirs(d, exist_ok=True)
    piper = os.path.join(HERE, ".venv", "bin", "piper")
    tmp = os.path.join(OUT, "tmp_tts"); os.makedirs(tmp, exist_ok=True)
    gap = 0.6
    sr = "22050"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono", "-t", "0.25", os.path.join(tmp, "lead.wav")])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl=mono", "-t", str(gap), os.path.join(tmp, "gap.wav")])
    for s in SCENES:
        if args.only and s["id"][:2] not in args.only:
            continue
        parts, labels, t = [], [], 0.25
        for j, b in enumerate(s["beats"]):
            w = os.path.join(tmp, f"{s['id']}_{j}.wav")
            spoken = b.replace("proth20", "proth twenty").replace("LLR2", "L L R two").replace("gwnum", "G W num")
            subprocess.run([piper, "-m", voice, "-f", w, "--length-scale", "1.05", "--sentence-silence", "0.25"], input=spoken, text=True, capture_output=True, check=True)
            labels.append(f"{t:.3f}\t{t:.3f}\tbeat {j + 1}")
            parts.append(w); t += duration(w) + gap
        lst = os.path.join(tmp, s["id"] + ".txt")
        with open(lst, "w") as f:
            f.write(f"file '{os.path.join(tmp, 'lead.wav')}'\n")
            for p in parts:
                f.write(f"file '{p}'\nfile '{os.path.join(tmp, 'gap.wav')}'\n")
        out = os.path.join(d, s["id"] + ".wav")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "48000", out])
        open(os.path.join(d, s["id"] + ".txt"), "w").write("\n".join(labels) + "\n")
        print(f"{s['id']}: {duration(out):.1f} s")


# ------------------------------------------------------------------ render
def cmd_render(args):
    from toon.render import render_scene
    vo_dir = os.path.abspath(args.vo)
    os.environ["COLBERT_VO_DIR"] = vo_dir
    os.makedirs(qdir(args.preview), exist_ok=True)
    cache_path = os.path.join(OUT, "render_cache.json")
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    q = "preview" if args.preview else "final"
    for sid, name in scenes():
        if args.only and sid[:2] not in args.only:
            continue
        key = source_hash(sid, vo_dir, args.preview)
        out = scene_file(sid, args.preview)
        if cache.get(f"{q}/{sid}") == key and os.path.exists(out) and os.path.exists(out + ".json") and not args.force:
            print(f"  {sid}: up to date", flush=True)
            continue
        fps, scale = (30, 0.5) if args.preview else (60, 1.0)
        render_scene(name, out, fps=fps, scale=scale, workers=args.jobs, crf=20 if args.preview else 16,
                     preset="veryfast" if args.preview else "medium", vo_dir=vo_dir)
        cache[f"{q}/{sid}"] = key
        json.dump(cache, open(cache_path, "w"), indent=1)
        print(f"  {sid}: rendered ({duration(out):.1f} s)", flush=True)


# ------------------------------------------------------------------ assemble
def fmt_ts(t, srt=False):
    h, rem = divmod(t, 3600); m, s = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)) % 1000:03d}"
    return f"{int(h)}:{int(m):02d}:{int(s):02d}" if h else f"{int(m)}:{int(s):02d}"


def captions(scene_times):
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
                if len(lines) > 2:
                    lines = [" ".join(lines[:len(lines) // 2]), " ".join(lines[len(lines) // 2:])]
                cues.append((t, t + d - 0.04, "\n".join(lines)))
                t += d
    out = []
    for i, (a, b, txt) in enumerate(cues, 1):
        out += [str(i), f"{fmt_ts(a, True)} --> {fmt_ts(b, True)}", txt, ""]
    return "\n".join(out)


def cmd_assemble(args):
    from toon import sfx
    import numpy as np
    vo_dir = os.path.abspath(args.vo)
    os.environ["COLBERT_VO_DIR"] = vo_dir
    tmp = os.path.join(OUT, "tmp_assemble"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    items, t = [], 0.0
    for sid, name in scenes():
        f = scene_file(sid, args.preview)
        if not os.path.exists(f):
            raise SystemExit(f"missing render for {sid}: run `build.py render{' --preview' if args.preview else ''}` first")
        d = duration(f)
        items.append((sid, f, t, d)); t += d
    total = t
    lst = os.path.join(tmp, "video.txt")
    open(lst, "w").write("".join(f"file '{f}'\n" for _, f, _, _ in items))
    vid = os.path.join(tmp, "video.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-an", "-c", "copy", vid])
    # voice
    segs, have_vo = [], False
    for sid, f, start, d in items:
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
    # effects, from each scene's cue list
    cues = []
    for sid, f, start, d in items:
        info = json.load(open(f + ".json"))
        cues += [(start + at, kind, g) for at, kind, g in info["cues"] if at < d]
    fx = os.path.join(tmp, "fx.wav")
    sfx.write_wav(fx, sfx.sfx_track(cues, total, 0.55))
    # music
    inputs = ["-i", voice, "-i", fx]
    if not args.no_music:
        if args.music:
            inputs += ["-stream_loop", "-1", "-i", args.music]
        else:
            mus = os.path.join(tmp, "music.wav")
            sfx.write_wav(mus, sfx.music_bed(total))
            inputs += ["-i", mus]
        fo = max(0.0, total - 4)
        mvol = 0.22 if args.music else 1.0
        graph = (f"[2:a]aresample=48000,aformat=channel_layouts=stereo,volume={mvol},afade=t=in:d=3,afade=t=out:st={fo:.2f}:d=4,atrim=0:{total:.3f}[m];"
                 f"[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[md];"
                 f"[v][1:a][md]amix=inputs=3:normalize=0[mix]")
    else:
        graph = "[0:a][1:a]amix=inputs=2:normalize=0[mix]"
    mix = os.path.join(tmp, "mix.wav")
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[mix]", "-t", f"{total:.3f}", mix])
    final_audio = os.path.join(tmp, "final.m4a")
    run(["ffmpeg", "-y", "-v", "error", "-i", mix, "-af", "loudnorm=I=-14:TP=-1.0:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", final_audio])
    name = args.output or ("colbert_explainer_preview.mp4" if args.preview else "colbert_explainer.mp4")
    out = os.path.join(OUT, name)
    run(["ffmpeg", "-y", "-v", "error", "-i", vid, "-i", final_audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
         "-movflags", "+faststart", "-shortest", out])
    if not args.preview:
        web = os.path.splitext(out)[0] + "_web.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", out, "-vf", "hqdn3d=1.5:1.5:6:6", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", web])
        print(f"wrote {web}  ({os.path.getsize(web) / 1e6:.0f} MB, for sharing; upload the full-quality file to YouTube)")
    st = [(sid, start, d) for sid, _, start, d in items]
    base = os.path.splitext(out)[0]
    open(base + ".srt", "w").write(captions(st))
    desc = [TITLE, "", SUBTITLE, "", "Chapters"]
    for (sid, start, d), s in zip(st, SCENES):
        if d >= 10 and s["chapter"] != "Credits":      # YouTube ignores chapter lists with any chapter under 10 s
            desc.append(f"{fmt_ts(start)} {s['chapter']}")
    open(base + "_youtube_description.txt", "w").write("\n".join(desc) + "\n")
    print(f"wrote {out}  ({fmt_ts(total)}, {os.path.getsize(out) / 1e6:.0f} MB, voice-over: {'yes' if have_vo else 'none'})")
    print(f"      {base}.srt, {base}_youtube_description.txt")


def cmd_thumbnail(args):
    from toon.render import still
    from toon import scenes as S
    os.environ["COLBERT_VO_DIR"] = os.path.abspath(args.vo)
    path = os.path.join(OUT, "thumbnail.png")
    still("Thumbnail", 0.0, path, scale=1.0)
    print("wrote", path)


def cmd_stills(args):
    from toon.render import still
    os.environ["COLBERT_VO_DIR"] = os.path.abspath(args.vo)
    d = os.path.join(OUT, "stills"); os.makedirs(d, exist_ok=True)
    from toon import scenes as S
    files = []
    for cls in S.ORDER:
        sc = cls()
        for i in range(len(sc.tm.starts)):
            p = os.path.join(d, f"{cls.ID}_b{i}.png")
            still(cls.__name__, sc.b(i, 0.8), p, scale=0.25)
            files.append(p)
    print(f"{len(files)} stills in {d}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["script", "render", "assemble", "all", "thumbnail", "scratch-vo", "stills"])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--vo", default=os.path.join(HERE, "vo"))
    ap.add_argument("--music")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--only", type=lambda s: [x.zfill(2) for x in s.split(",")])
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("-o", "--output")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voice", help="Piper voice model for scratch-vo")
    args = ap.parse_args()
    {"script": cmd_script, "scratch-vo": cmd_scratch_vo, "render": cmd_render, "assemble": cmd_assemble,
     "thumbnail": cmd_thumbnail, "stills": cmd_stills}.get(args.command, lambda a: None)(args)
    if args.command == "all":
        cmd_render(args); cmd_assemble(args)
        if not args.preview:
            cmd_thumbnail(args)


if __name__ == "__main__":
    main()
