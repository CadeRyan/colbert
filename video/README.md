# The Last Five: explainer video

A motion-graphics explainer (about 12–13 minutes, 1920×1080, 60 fps) that tells the story of the
Sierpiński problem and explains colbert, following [docs/EXPLAINER.md](../docs/EXPLAINER.md).
Every frame is generated in code with [Manim](https://www.manim.community/), and every number on
screen is computed (see `tools/prep_data.py`) or taken from a cited source (see `film/facts.py`).

## Before publishing: the projected figures

Scene 12 ("What it buys") presents GPU results **as if measured**: 2.5× faster than proth20,
about 3 hours per test on an RTX 4090, and nearly 3× the tests per kWh of a CPU. They are
projections from `tools/perf_model.py`. Run the benchmark in
[docs/GPU_BENCHMARKING.md](../docs/GPU_BENCHMARKING.md), put the measured values in
`film/facts.py` (and the matching words in `film/script.py`), then re-render. The video's audience
includes the people best placed to check these numbers.

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
   your recording. Audio is normalised to −14 LUFS, YouTube's playback level.

A scene without a recording is timed from its word count and stays silent, so you can record
and rebuild one scene at a time.

Optional music bed, automatically ducked under the voice:

```bash
video/.venv/bin/python video/build.py assemble --music path/to/track.wav
```

## Placeholder narration

`build.py scratch-vo` synthesises the whole script with [Piper](https://github.com/rhasspy/piper)
(an offline text-to-speech voice) into `vo_scratch/`, with exact beat labels. It is useful for
checking pacing before recording:

```bash
video/.venv/bin/python video/build.py all --vo video/vo_scratch
```

## Setup

System packages (Ubuntu/Debian):

```bash
sudo apt-get install -y ffmpeg libcairo2-dev libpango1.0-dev pkg-config python3-dev python3-venv fonts-inter fonts-jetbrains-mono
```

Python environment:

```bash
python3 -m venv video/.venv && video/.venv/bin/pip install -r video/requirements.txt
```

Data for the scenes (about one second):

```bash
video/.venv/bin/python video/tools/prep_data.py
```

## Commands

| command | what it does |
|---|---|
| `build.py script` | regenerate `VO_SCRIPT.md` from `film/script.py` |
| `build.py render [--preview] [--only 03,07]` | render scenes; unchanged scenes are skipped |
| `build.py assemble [--preview] [--music F]` | join scenes, mix audio, write captions and chapters |
| `build.py all` | render + assemble + thumbnail |
| `build.py thumbnail` | `out/thumbnail.png` |
| `build.py scratch-vo --voice M.onnx` | placeholder narration |

`--preview` renders at 480p15 in a few minutes, for checking layout and timing. A full 1080p60
render takes roughly 30–60 minutes on 4 cores.

## Layout

    film/script.py      the narration, split into scenes and beats (edit words here)
    film/facts.py       every figure the video states, with sources; projections marked
    film/timing.py      beat timing from recordings, Audacity labels, or word counts
    film/style.py       palette, type and the base scene class
    film/scenes_*.py    the fifteen scenes
    scenes.py           entry point for manim
    build.py            render, assemble, captions, chapters, thumbnail
    tools/prep_data.py  computes the on-screen data into data/
    vo/                 your recordings go here
