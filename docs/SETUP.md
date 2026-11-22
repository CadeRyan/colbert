# Setup

How to build colbert, check it, and run tests. For measuring GPU speed, see
[GPU_BENCHMARKING.md](GPU_BENCHMARKING.md).

## What you need

| | required | notes |
|---|---|---|
| OS | Linux x86-64, macOS, Windows | Developed on Ubuntu 24.04; also tested on macOS 26 (Apple Silicon). Windows: WSL2 (NVIDIA's WSL driver exposes OpenCL), or a native MSYS2 build (below; not yet tested). |
| Compiler | g++ 9+ or clang 10+, C++17, OpenMP | `build-essential` |
| GMP | libgmp + libgmpxx | used for setup, conversions and checks, not in the inner loop |
| OpenCL | ICD loader + headers + a GPU driver with OpenCL 1.2 | only for the GPU backend; `make OPENCL=0` builds without it |
| Python 3 | optional | `proto/`, `tools/cost_model.py`, `tools/perf_model.py`; the prototype also needs `gmpy2` |

The GPU needs 64-bit integer support (every current NVIDIA, AMD and Intel discrete GPU
has it). It does **not** need fast double precision; the method was chosen for that reason.

**Apple Silicon:** Apple's GPUs have no native 64-bit integer multiply, and Apple has
deprecated OpenCL (it still ships). colbert passes every check on an M4 Pro GPU, at 3.03 ms per
squaring at the leading edge ([RESULTS.md](RESULTS.md)). That number says little about NVIDIA
or AMD hardware.

## Install dependencies

Ubuntu / Debian:

```bash
sudo apt-get install -y build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers clinfo
```

Then the OpenCL driver for your GPU:

* **NVIDIA:** the proprietary driver includes OpenCL. Check that `clinfo -l` lists the GPU.
  If it doesn't, install `nvidia-opencl-icd-<version>` matching your driver.
* **AMD:** ROCm's OpenCL runtime (`rocm-opencl-runtime`), or the AMDGPU-PRO OpenCL
  component for older cards.
* **Intel Arc:** `intel-opencl-icd`.
* **No GPU, just testing:** `sudo apt-get install pocl-opencl-icd` runs the OpenCL kernels on
  the CPU. It is slow, but it exercises the exact GPU code path. All OpenCL results in
  [RESULTS.md](RESULTS.md) so far come from PoCL.

Check:

```bash
clinfo -l
```

macOS (Homebrew; OpenCL is part of the system):

```bash
xcode-select --install; brew install gmp libomp
```

Windows without WSL, in an MSYS2 UCRT64 shell (the build is set up for this but hasn't been
tested yet; the GPU driver provides `OpenCL.dll`):

```bash
pacman -S make mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gmp mingw-w64-ucrt-x86_64-opencl-icd mingw-w64-ucrt-x86_64-opencl-headers
```

## Build

```bash
git clone https://github.com/CadeRyan/colbert.git
```

```bash
cd colbert && make
```

This produces `./colbert` (the tester) and `./sieve` (the candidate sieve). The OpenCL
kernels are compiled into the binary and built for your GPU at run time, so the binary does
not depend on the source tree.

Without OpenCL:

```bash
make OPENCL=0
```

`make colbert-cpu` builds a CPU-only companion binary next to `colbert`. The app falls back to
it on computers where the OpenCL loader library is missing, where `colbert` wouldn't start at
all.

For binaries that run on other people's computers, replace `-march=native`, which produces
code that crashes on older CPUs, and link statically:

```bash
make ARCH=-march=x86-64-v2 STATIC=1 colbert colbert-cpu      # Linux, Windows (MSYS2)
make ARCH=-mcpu=apple-m1 STATIC=1 colbert colbert-cpu        # macOS, Apple Silicon
```

The version stamped into every result comes from `git describe`. Builds from uncommitted
engine changes end in `-dirty.<hash of the diff>`, so each edit is a distinct build. The
ledger can be set to refuse these.

## Check that it works

```bash
./colbert devices
```

Lists OpenCL devices with their index. A GPU shows `[GPU]`; pass `--device I` to choose one.

```bash
make check
```

Runs the CPU self-test (64 checks against GMP, under a minute), the Python model, and
`tools/check_protocol.py`, which checks the machine interface the app relies on
([ENGINE_PROTOCOL.md](ENGINE_PROTOCOL.md)). Every line should start with `ok`.

```bash
./colbert selftest --backend ocl
```

Runs the same 64 checks through the OpenCL kernels on the default device. **This is the
first thing to run on a new GPU.** A failure means the GPU's compiler or hardware disagrees
with the reference, and no result from that device should be trusted until it is fixed.

## Testing numbers

One number:

```bash
./colbert test 21181 47856020 --backend ocl --ckpt ckpt
```

* Prints progress every 30 seconds: percent done, ms per iteration, ETA, and the number of
  error checks passed.
* `--ckpt DIR` writes a checkpoint after every *verified* block, so an interrupted run
  (power cut, pre-empted cloud VM, Ctrl-C) resumes from the last good state when restarted
  with the same command.
* The result is printed and appended as one JSON line to `results.jsonl` (`--results FILE`
  to change). `"result":"PRIME"` means Proth's test proved the number prime.
* A prime would print a banner. Before announcing anything, **re-test it with independent
  software** (LLR2 or PRST) and contact PrimeGrid.

A list of numbers:

```bash
./colbert work --worktodo list.txt --backend ocl --ckpt ckpt
```

`list.txt` has one `k n` pair per line (`#` starts a comment), the same format the sieve
writes. Numbers already present in the results file are skipped, so `work` can be stopped
and restarted freely.

Other commands:

| command | what it does |
|---|---|
| `./colbert info K N` | transform size, bits per word, worst-case bound and Proth base, without running anything |
| `./colbert bench K N ITERS [--verify]` | times `ITERS` squarings at full size; `--verify` compares the result with GMP (GMP takes several seconds per squaring at the leading edge, so keep `ITERS` small) |
| `./colbert test K N --primes 1` | use only the 61-bit field. Faster per point, but fits only small sizes |
| `./colbert test K N --size N` | force a transform size (must pass the overflow bound) |
| `./colbert test K N --gerbicz L` | Gerbicz block length (default about √(n/2), capped at 1000) |
| `./colbert pm1 K N` | P−1 factoring, bounds chosen from `--sieve-bits` (default 32); see [PM1.md](PM1.md) |
| `./colbert bench K N ITERS --backend ocl --profile` | time per GPU kernel |

## Candidates

```bash
./sieve 47856007 57500000 1e9 candidates.txt [factors.txt]
```

Sieves `n` in the range for all five `k`, removing every candidate with a prime factor up to
`1e9` (the limit is 2^32), and prints expected prime counts. On 2 cores this took 36 minutes
for that range. The output is a valid worktodo file. The optional `factors.txt` lists
`k n p` for each candidate removed by a prime `p ≥ 20000`, so every removal can be checked
on its own: `(k * pow(2, n, p) + 1) % p == 0` in Python.

To take newly factored candidates out of the ledger after a deeper sieve, pass the factor
file (or any `k n` list) to `python3 -m ledger admin remove` ([LEDGER.md](LEDGER.md)).

The list in `data/` is shallow. **A real search must start from a deep sieve.** PrimeGrid
has sieved these sequences far beyond 2^32, and testing survivors of a shallow sieve
wastes about half the work on numbers with known factors. Also, numbers below PrimeGrid's
leading edge (n = 47,856,007 on 17 Nov 2026) have already been tested.

```bash
python3 tools/cost_model.py candidates.txt --psieve 1e9 --ms-per-iter 0.15 0.5 1.0
```

Turns a candidate file into expected primes, GPU-hours and cost.

## Troubleshooting

| symptom | likely cause |
|---|---|
| `no OpenCL devices found` | ICD loader installed but no driver ICD: `ls /etc/OpenCL/vendors/` should list one `.icd` per driver |
| `OpenCL build failed:` followed by a log | the GPU's compiler rejected a kernel. Save the full log; it is the most useful bug report |
| `selftest` lines show `FAIL` on GPU but not on CPU | miscompilation or a hardware fault. Try another driver version; report it |
| `Gerbicz check FAILED … rolling back` during a run | an error was caught and corrected. Occasional ones on overclocked or hot GPUs are what the check is for; frequent ones mean unstable hardware |
| `carry did not settle` | should be impossible within the proven bounds; it indicates a bug. Report the `k`, `n` and device |
| `no transform size fits` | `n` outside the supported range (roughly 300 ≤ n < 2^31) |
