# Setup

How to build colbert, check it, and run tests. For measuring GPU speed, see
[GPU_BENCHMARKING.md](GPU_BENCHMARKING.md).

## What you need

| | required | notes |
|---|---|---|
| OS | Linux x86-64 | Developed and tested on Ubuntu 24.04. Windows: use WSL2 (NVIDIA's WSL driver exposes OpenCL). macOS: builds, but see the Apple note below. |
| Compiler | g++ 9+ or clang 10+, C++17, OpenMP | `build-essential` |
| GMP | libgmp + libgmpxx | used for setup, conversions and checks, not in the inner loop |
| OpenCL | ICD loader + headers + a GPU driver with OpenCL 1.2 | only for the GPU backend; `make OPENCL=0` builds without it |
| Python 3 | optional | `proto/`, `tools/cost_model.py`, `tools/perf_model.py`; the prototype also needs `gmpy2` |

The GPU needs 64-bit integer support (every current NVIDIA, AMD and Intel discrete GPU
has it). It does **not** need fast double precision; the method was chosen for that reason.

**Apple Silicon:** Apple's GPUs have no native 64-bit integer multiply, and Apple has
deprecated OpenCL. colbert should run there, but slowly, and speed numbers from a Mac say
nothing about NVIDIA or AMD hardware.

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

## Check that it works

```bash
./colbert devices
```

Lists OpenCL devices with their index. A GPU shows `[GPU]`; pass `--device I` to choose one.

```bash
make check
```

Runs the CPU self-test (59 checks against GMP, a few seconds) and the Python model. Every
line should start with `ok`.

```bash
./colbert selftest --backend ocl
```

Runs the same 59 checks through the OpenCL kernels on the default device. **This is the
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

## Candidates

```bash
./sieve 47856007 57500000 1e9 candidates.txt
```

Sieves `n` in the range for all five `k`, removing every candidate with a prime factor up to
`1e9` (the limit is 2^32), and prints expected prime counts. On 2 cores this took 36 minutes
for that range. The output is a valid worktodo file.

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
