# The Last Five: explainer video

An illustrated, motion-graphics explainer (about 14 minutes, 1920×1080, 60 fps) about the
Sierpiński problem and colbert, following [docs/EXPLAINER.md](../docs/EXPLAINER.md).
Every frame is drawn in code by a small engine on [Skia](https://skia.org/) (`toon/`).
Every number on screen is computed (`tools/prep_data.py`) or taken from a cited source
(`film/facts.py`), and every sound is synthesised (`toon/sfx.py`).

## Before publishing: the projected figures

Scene 14 ("What it buys") presents GPU results **as if measured**: 2.5× faster than proth20,
about 3 hours per test on an RTX 4090, and nearly 3× the tests per kWh of a CPU. They are
projections from `tools/perf_model.py`. Run the benchmark in
[docs/GPU_BENCHMARKING.md](../docs/GPU_BENCHMARKING.md), put the measured values in
`film/facts.py` (and the matching words in `film/script.py`), then re-render. The video's
audience includes the people best placed to check these numbers.

Also: the end card shows `github.com/CadeRyan/colbert`. Make the repository public first,
or change `REPO_URL` in `film/facts.py`.

## Recording the voice-over

1. Read [VO_SCRIPT.md](VO_SCRIPT.md). It has one section per scene, with the file name to use,
   beat markers (▸), and a pronunciation guide.
2. Save one file per scene in `vo/`, e.g. `vo/02_sierpinski.wav` (WAV, FLAC, MP3 or M4A).
3. Optional, for exact sync: in Audacity, add a label at the start of each ▸ beat and export the
   labels as `vo/02_sierpinski.txt`. Without labels, each scene's animations are stretched to
   the length of its recording, in proportion to the words in each beat.
4. Build:

   ```bash
   video/.venv/bin/python video/build.py all
   ```

   The result is `out/colbert_explainer.mp4`, plus `out/colbert_explainer.srt` (captions) and
   `out/colbert_explainer_youtube_description.txt` (chapters with timestamps), all timed to
   your recording.

A scene without a recording is timed from its word count and stays silent, so you can record
and rebuild one scene at a time (`--only 02`).

## Sound

The mix has three layers, normalised together to −14 LUFS (YouTube's playback level):

* your voice-over;
* sound effects (pops, hops, chimes, whooshes…) synthesised in `toon/sfx.py` and triggered by
  cues each scene declares with `self.sfx(time, kind)`;
* a soft ambient music bed, also synthesised, ducked automatically under the voice.

The music bed is a placeholder. To use a licensed track instead, or none:

```bash
video/.venv/bin/python video/build.py assemble --music path/to/track.wav
```

```bash
video/.venv/bin/python video/build.py assemble --no-music
```

## Placeholder narration

`build.py scratch-vo` synthesises the whole script with [Piper](https://github.com/rhasspy/piper)
(offline text-to-speech) into `vo_scratch/`, with exact beat labels, for checking pacing:

```bash
video/.venv/bin/python video/build.py all --vo video/vo_scratch
```

## Setup

System packages (Ubuntu/Debian):

```bash
sudo apt-get install -y ffmpeg libegl1 libgl1 python3-venv fonts-inter fonts-jetbrains-mono
```

Python environment:

```bash
python3 -m venv video/.venv && video/.venv/bin/pip install -r video/requirements.txt
```

Data for the scenes (about one second):

```bash
video/.venv/bin/python video/tools/prep_data.py
```

The display typeface, [Fredoka](https://github.com/google/fonts/tree/main/ofl/fredoka) (SIL Open
Font License, `assets/fonts/OFL.txt`), is in `assets/fonts/`.

## Commands

| command | what it does |
|---|---|
| `build.py script` | regenerate `VO_SCRIPT.md` from `film/script.py` |
| `build.py render [--preview] [--only 03,07]` | render scenes; unchanged scenes are skipped |
| `build.py assemble [--preview] [--music F] [--no-music]` | join scenes, mix audio, write captions and chapters |
| `build.py all` | render + assemble + thumbnail |
| `build.py thumbnail` | `out/thumbnail.png` (1920×1080) |
| `build.py stills` | one still per beat in `out/stills/`, for checking layout |
| `build.py scratch-vo --voice M.onnx` | placeholder narration |
| `python -m toon.render still SceneName b2.5 DIR` | one still, halfway through beat 2 |

`--preview` renders at 960×540 and 30 fps in about 12 minutes on 4 cores. A full 1080p60 render
takes roughly an hour.

## Layout

    film/script.py      the narration, split into scenes and beats (edit words here)
    film/facts.py       every figure the video states, with sources; projections marked
    film/timing.py      beat timing from recordings, Audacity labels, or word counts
    toon/core.py        the engine: easing, text, glows, skies, camera, scene base class
    toon/art.py         characters and props: number creatures, stars, clocks, machines…
    toon/sfx.py         synthesised sound effects and music bed
    toon/render.py      parallel rendering to video, and single stills
    toon/scenes/        the seventeen scenes
    build.py            render, assemble, captions, chapters, thumbnail
    tools/prep_data.py  computes the on-screen data into data/
    vo/                 your recordings go here
