# colbert

A Proth-test engine aimed at the five numbers that stand between us and a solved
Sierpiński problem: `k·2^n + 1` for `k` = 21181, 22699, 24737, 55459, 67607.

The idea in one paragraph. Every existing tester pays roughly a factor of two for the
multiplier `k`: either a zero-padded transform (proth20 on GPUs), or a floating-point
weighted transform in which `k` eats almost half of each word (LLR/gwnum). `colbert` does
the weighted transform exactly, in `GF(q²)` for the Mersenne primes `q = 2^61−1` and
`2^31−1`, where the needed `N`-th root of `−k·2^n` exists for **every** `k`. The transform
is the size of the number, nothing is padded, and correctness of each squaring is a theorem
about integer bounds rather than a round-off tolerance. See [docs/DESIGN.md](docs/DESIGN.md).

## Status

| | |
|---|---|
| mathematics | proven in DESIGN.md, modelled in `proto/weighted_ntt.py` |
| CPU engine | complete; a correctness oracle, **not** fast |
| OpenCL engine | complete and bit-identical to the CPU engine; **has only run on a CPU OpenCL runtime, never on a GPU** |
| verification | see [docs/RESULTS.md](docs/RESULTS.md) |
| GPU speed | **unmeasured**. This is the number everything else depends on |
| a new prime | no. Nothing has been searched yet |

## Build and check

    apt-get install build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers
    make                 # builds ./colbert and ./sieve      (make OPENCL=0 for CPU only)
    make check           # 59 checks against GMP, plus the Python model

    ./colbert selftest --backend ocl          # same checks through the OpenCL kernels
    ./colbert test 46157 698207               # a known Seventeen or Bust prime (~20 min on 4 cores)
    ./colbert bench 67607 46000000 20 --verify --backend ocl   # full-size squarings vs GMP
    ./colbert work --worktodo list.txt --ckpt ckpt/ --backend ocl

`test` and `work` checkpoint only verified states, so a pre-empted machine resumes safely.
Results are appended as JSON lines to `results.jsonl`.

## What it would take to find the next one

`./sieve` and `tools/cost_model.py` turn "how hard is this" into numbers. For
`n` from 45.5M (about where PrimeGrid's search stands; I could not reach primegrid.com from
the build environment, so that figure is from a search-engine snippet) to 57.5M:

* 259,990 candidates survive trial division to 10⁹ (measured here); about 136,000 would
  survive a deep sieve to ~1.4·10¹⁷ (assumed depth).
* Expected primes in that whole range: **0.27**. About **505,000 tests per expected prime**.
* Each test is ~46–57 million squarings of a number that size.

| GPU squaring time (assumed) | GPU-hours per test | GPU-hours per expected prime |
|---|---|---|
| 0.15 ms | 2.1 | 1.1 million |
| 0.5 ms | 7.2 | 3.6 million |
| 1.5 ms | 21.5 | 10.8 million |

No algorithm changes the half-million tests; only the cost of a test can move. The three
rows are scenarios, not measurements.

## Layout

    proto/weighted_ntt.py   pure-Python model of the transform, checked against big integers
    src/field.h             GF(q), GF(q^2) for q = 2^61-1, 2^31-1
    src/layout.*            digit layout, rigorous overflow bound, weight and twiddle tables
    src/cpu_engine.cpp      OpenMP reference engine
    src/kernels.cl          OpenCL kernels;  src/ocl_engine.cpp  host side
    src/proth.*             Proth test, Gerbicz-Li checking, verified checkpoints
    tools/sieve.cpp         candidate sieve for the five k (p <= 2^32)
    tools/cost_model.py     candidates -> expected primes, GPU-hours, dollars
    deploy/gcp-benchmark.sh one-GPU benchmark on Google Cloud (not yet run)
    data/                   candidate list for n in [45.5M, 57.5M], sieved to 1e9

## Caveats worth knowing before spending anything

* The candidate list here is shallow (10⁹). A real search should start from a deep sieve;
  testing this list as-is would waste about half the work on numbers with known factors.
* PrimeGrid runs the Seventeen or Bust search and will test the same numbers. Running
  ahead of their wavefront duplicates work they will redo, and by the community's
  conventions the range is theirs. Talk to them first; a faster GPU tester may be worth
  more inside their project than beside it.
* A positive result must be confirmed with independent software before any announcement.
