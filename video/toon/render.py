"""Render toon scenes to video (parallel chunks through ffmpeg) or to still frames."""
import json, math, os, subprocess, sys, importlib
import multiprocessing as mp
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
sys.path.insert(0, VIDEO)


def scene_class(name):
    from toon import scenes
    return scenes.BY_NAME[name]


def _render_chunk(args):
    name, f0, f1, fps, scale, out, crf, preset, vo_dir = args
    os.environ["COLBERT_VO_DIR"] = vo_dir
    import skia
    from toon.core import W, H
    sc = scene_class(name)()
    w, h = int(W * scale), int(H * scale)
    surf = skia.Surface(w, h)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-g", str(fps * 2), out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(f0, f1):
        t = f / fps
        c = surf.getCanvas()
        c.clear(skia.ColorBLACK)
        c.save(); c.scale(scale, scale)
        sc.frame(c, t)
        c.restore()
        p.stdin.write(surf.makeImageSnapshot().tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f"ffmpeg failed for {name} frames {f0}-{f1}")
    return out


def render_scene(name, out, fps=60, scale=1.0, workers=4, crf=16, preset="medium", vo_dir=None):
    vo_dir = vo_dir or os.environ.get("COLBERT_VO_DIR", os.path.join(VIDEO, "vo"))
    os.environ["COLBERT_VO_DIR"] = vo_dir
    sc = scene_class(name)()
    n = int(math.ceil(sc.dur * fps))
    chunks = max(1, min(workers, n // (fps * 2)))
    bounds = [round(i * n / chunks) for i in range(chunks + 1)]
    tmpdir = out + ".parts"
    os.makedirs(tmpdir, exist_ok=True)
    jobs = [(name, bounds[i], bounds[i + 1], fps, scale, os.path.join(tmpdir, f"{i:03d}.mp4"), crf, preset, vo_dir) for i in range(chunks)]
    ctx = mp.get_context("spawn")
    with ctx.Pool(min(workers, chunks)) as pool:
        parts = pool.map(_render_chunk, jobs)
    lst = os.path.join(tmpdir, "list.txt")
    open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out], check=True)
    for p in parts:
        os.remove(p)
    os.remove(lst); os.rmdir(tmpdir)
    json.dump({"scene": sc.ID, "duration": n / fps, "cues": sc.cues}, open(out + ".json", "w"))
    return out


def still(name, t, path, scale=0.5, vo_dir=None):
    if vo_dir:
        os.environ["COLBERT_VO_DIR"] = vo_dir
    import skia
    from toon.core import W, H
    sc = scene_class(name)()
    surf = skia.Surface(int(W * scale), int(H * scale))
    c = surf.getCanvas(); c.clear(skia.ColorBLACK)
    c.save(); c.scale(scale, scale); sc.frame(c, t); c.restore()
    surf.makeImageSnapshot().save(path, skia.kPNG)
    return sc


if __name__ == "__main__":
    # python -m toon.render still SceneName t1,t2,... outdir  [scale]
    if sys.argv[1] == "still":
        name, ts, outdir = sys.argv[2], sys.argv[3], sys.argv[4]
        scale = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
        os.makedirs(outdir, exist_ok=True)
        for t in ts.split(","):
            if t.startswith("b"):         # b<beat>.<fraction>, e.g. b2.5 = halfway through beat 2
                sc = scene_class(name)()
                bi, frac = t[1:].split(".") if "." in t else (t[1:], "0")
                tt = sc.b(int(bi), float("0." + frac))
            else:
                tt = float(t)
            still(name, tt, os.path.join(outdir, f"{name}_{t}.png"), scale)
        print("ok")
