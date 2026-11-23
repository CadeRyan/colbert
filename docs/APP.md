# The Colbert app

The app runs colbert on your computer, shows how it's going, and can join a shared project
so that many computers work through the numbers together. It works on Windows, macOS and
Linux, with or without a graphics card.

## Install and open

**Download** the app for your computer from the
[latest release](https://github.com/CadeRyan/colbert/releases/latest). No GitHub account is
needed, and the engine is included, so there's nothing else to install:

| system | download | to install |
|---|---|---|
| Mac (Apple Silicon or Intel, macOS 12 or newer) | [Colbert-macOS.dmg](https://github.com/CadeRyan/colbert/releases/latest/download/Colbert-macOS.dmg) | open it, drag Colbert onto Applications, then open Colbert from Applications |
| Windows 10 or 11 (64-bit) | [Colbert-Windows-Setup.exe](https://github.com/CadeRyan/colbert/releases/latest/download/Colbert-Windows-Setup.exe) | run it. It installs for you only, with no administrator rights, and adds Colbert to the Start menu |
| Linux (x86-64) | [Colbert-Linux-x64.tar.gz](https://github.com/CadeRyan/colbert/releases/latest/download/Colbert-Linux-x64.tar.gz) | unpack it and run `./Colbert`. A graphics card also needs its OpenCL driver |

The app isn't signed yet, so the first open needs one extra step:

* **Mac:** if macOS says it can't check Colbert for malicious software, open System Settings →
  Privacy & Security, scroll down, and press *Open Anyway* next to Colbert.
* **Windows:** if SmartScreen says "Windows protected your PC", press *More info* → *Run anyway*.

Colbert opens in your web browser. That page *is* the app: it only works from this computer,
and closing the tab doesn't stop the work. Open Colbert again (from Applications or the Start
menu) to get back to the page; *Quit* in the app saves progress and stops. Once a day the app
asks GitHub whether a newer version is out, and if so says where to download it. Progress
carries over to the new version.

**From the source code**, to read or change it, double-click the start file for your system
in the colbert folder (a download or `git clone` of the repository):

| system | file | first time |
|---|---|---|
| macOS | **Start Colbert.command** | if macOS says it can't verify the file: right-click it → Open → Open. It may offer to install Apple's command line tools and Homebrew's `gmp` and `libomp`, then builds the engine (about a minute) |
| Windows | **Start Colbert.bat** | needs Python (the file opens the download page if it's missing; tick *Add python.exe to PATH*) and MSYS2 from msys2.org to build the engine. If SmartScreen warns: More info → Run anyway |
| Linux | **Start Colbert.sh** | choose *Run in Terminal*. It offers to install the compiler and libraries with your package manager (it asks for your password) |

After the first time it only checks for updates (in a clean git checkout), rebuilds the
engine if the code changed, and opens the app. A small window stays open while Colbert works.
Closing it, or Quit in the app, saves progress and stops.

The app opens in your web browser. That page *is* the app: it only works from this computer,
and closing the tab doesn't stop the work. Double-click the start file again to get back to it.

**From a terminal**, the start files do the equivalent of:

```bash
make colbert colbert-cpu        # the engine; see SETUP.md for compilers and libraries
python3 app/run.py
```

## First run

1. **Join.** The Overview asks for your name; press *Join and start*. To test your own
   numbers instead, use the Work tab: choose *My own numbers* and paste some. *Add a known-prime check* queues
   46157·2⁶⁹⁸²⁰⁷+1, a prime found in 2002. Proving it takes about 2½ minutes on an Apple M4 Pro
   GPU, and it confirms the whole pipeline works on your computer.
2. **Press Start.** Before the first test, the app checks every device it finds (next
   section). This takes one to three minutes.
3. **Overview tab.** This shows the number being tested and:
   * the percentage done and the squarings completed;
   * the **speed** in milliseconds per squaring, with a chart over time;
   * **time left** and the expected finish time;
   * **error checks**: how many Gerbicz checks have passed, and how many errors were caught
     and corrected;
   * **progress saved**: how long ago the last verified checkpoint was written. Pausing,
     quitting, a crash or a power cut lose at most the work since then.

**Pause** saves progress and stops, and Start continues from there. Pausing frees the
graphics card, for a game for example.

## Devices: with or without a graphics card

The Devices tab lists everything the engine can use:

* **graphics cards** (NVIDIA, AMD, Intel) and **integrated graphics** (Intel Iris/Arc, AMD
  APUs, Apple Silicon), through OpenCL;
* **the built-in CPU engine**, which works on any computer;
* OpenCL CPU drivers such as PoCL, if they're installed.

Each device is **self-tested** against exact arithmetic before it does any real work. It's
then **timed** at the size of current project work, and the fastest device that passes is
used. Choose a device yourself with *Use:*.

When the engine is updated (for example after GPU tuning), the app notices the new build and
checks every device again before using it. A device that fails the self-test with a build is
never used with that build.

What to expect for one test at the project's leading edge (n ≈ 48 million, a 14.4
million-digit number):

| device | time per squaring | one test |
|---|---|---|
| Apple M4 Pro GPU (measured 21 Nov 2026, four-step kernels) | 3.0 ms | about 1.7 days |
| Apple M4 Pro, 14 CPU cores (measured 21 Nov 2026) | 20.9 ms | about 11.5 days |
| 4-core cloud CPU (measured, docs/RESULTS.md) | 171–243 ms | about 3 months |
| fast NVIDIA/AMD card (estimate, docs/PERFORMANCE.md) | 0.15–1 ms | hours |

A CPU-only computer can contribute, but slowly. Leave it running, or pause and resume as you
like: progress is saved about every 10 minutes (adjustable in Settings), and a test can take
weeks without losing anything.

## Joining the project

When you join, the app registers this computer with the project's ledger and then:

* asks for one number at a time;
* for a number nobody has tested yet, first looks for a factor with P−1 when that saves work
  (about 1.5 hours on an M4 Pro at the leading edge, with about a 1-in-4 chance of finding one,
  which settles the number with no test at all; see [PM1.md](PM1.md)). Settings → "Look for a
  factor first" turns this off;
* reports progress every 15 minutes, which tells the ledger the computer is still working on
  it;
* uploads the result (or the factor) when it finishes. If the ledger can't be reached, the
  result is kept and uploaded later.

A computer that stops reporting for 3 days loses its number to someone else. If it comes
back first, it picks up where it left off. Some of your results will be double-checked by
other computers, and some of your work will be double checks of theirs. That's how the
project trusts results from computers it has never met. [LEDGER.md](LEDGER.md) explains the
details.

**What the project sees:** the name you give, this computer's name (Settings), your
operating system and device name, the engine version, speeds and results. Nothing else. (The
downloaded app also asks GitHub once a day for the newest version number, which tells GitHub
your IP address, as any visit to a website does.)

## If it finds a prime

The app shows a banner. A real discovery would be big news, so:

1. **Don't announce it.** The project double-checks it on another computer automatically.
   For numbers from your own list, re-test it on another computer, ideally with different
   software (LLR2 or PRST).
2. Keep the result line (Results tab) and the log.
3. Contact the project.

## Running without a window

On servers and cloud GPUs, from the Linux download (`./Colbert` takes the same options) or a
source checkout:

```bash
python3 app/run.py --headless --owner yourname           # joins the project's ledger
python3 app/run.py --headless --ledger https://… --owner yourname
python3 app/run.py --headless --local numbers.txt          # 'k n' per line
python3 app/run.py --headless --device ocl:0 --threads 8 --data /var/lib/colbert …
```

It prints a progress line every minute, saves progress and stops cleanly on Ctrl-C or
SIGTERM, and resumes when started again with the same `--data` directory. For two GPUs, run
two copies with different `--data` directories and `--device ocl:0` / `--device ocl:1`.

## Where things are

| | |
|---|---|
| data, settings, checkpoints, log | macOS `~/Library/Application Support/Colbert`, Windows `%APPDATA%\Colbert`, Linux `~/.local/share/colbert` (`--data` overrides) |
| the engine | inside the downloaded app (the Mac app runs a copy of it from its data folder), or `./colbert` in a source checkout, or Settings → Engine binary |

## Troubleshooting

| symptom | what to do |
|---|---|
| "The engine isn't available" | From source: run `make colbert colbert-cpu`, or press *Build it now*. From a download: download and install it again; the engine is included |
| Mac: "Please move Colbert to your Applications folder first" | it was opened from the disk image or from Downloads. Drag it onto Applications and open it from there |
| Mac: "Colbert couldn't start" | the message names a log file; its last lines say why |
| a device shows *failed* on the Devices tab | that device computes wrong answers with this engine build (often a driver problem). It won't be used. Try a driver update, then *Check all devices again* |
| no graphics card listed | install your GPU's OpenCL driver (SETUP.md). Without one, the CPU engine is used |
| "errors corrected" goes up often | the hardware is unstable, often heat or overclocking. Results are still right; the check exists for this |
| "Waiting: cannot reach the ledger" | the network or the project is down. The current test continues and results upload later |
| "The project ledger refused: engine build … withdrawn" | update the app; a problem was found in your engine version |
| Linux: "libgmp.so.10" or "libgomp.so.1: cannot open shared object file" in the engine error | `sudo apt-get install libgmp10 libgomp1` (or your distribution's equivalent). The OpenCL loader (`ocl-icd-libopencl1`) is optional: without it the app uses its CPU-only engine |
| the computer feels slow | the engine runs at low priority, but a CPU test uses every core. Set fewer CPU threads in Settings, or pause |
