# colbert

A GPU-oriented primality tester for the numbers that stand between us and a solved
Sierpiński problem: `k·2^n + 1` for `k` = 21181, 22699, 24737, 55459, 67607.

**New here?** Start with [the plain-language explainer](docs/EXPLAINER.md).

## The idea

Graphics cards are fast at whole-number arithmetic and slow at the double-precision
floating point that CPU testers use. Exact whole-number transforms (NTTs) suit them, but
until now nobody had a way to apply an NTT to `k·2^n + 1` without doubling its size
("zero padding"). As recently as 2024, the author of the leading GPU testers wrote that
no fast algorithm of this kind existed.

colbert does it. It carries out Percival's no-padding weighted transform exactly, in the
field `GF(q²)` with `q = 2^61 − 1` (and a second field with `q = 2^31 − 1`). In that field
the weights the transform needs exist for **every** `k`. The result handles about
**2.7× less data per squaring** than the existing GPU tester, and every squaring is exact
by a proof, not a round-off tolerance.

Most of the ingredients are prior work: Crandall, Fagin, Percival, Woltman and Gallot. The
new step is narrow, and [docs/NOVELTY.md](docs/NOVELTY.md) sets out exactly what it is and
how confident that claim is.

## Status

| | |
|---|---|
| mathematics | written out and proved in [DESIGN.md](docs/DESIGN.md); modelled in `proto/weighted_ntt.py` |
| CPU engine | complete; a correctness reference, **not** fast |
| OpenCL engine | complete, bit-identical to the CPU engine. Four-step radix-8 kernels (three passes per prime per squaring), with a startup self-check and the original kernels as fallback. **Not yet run on NVIDIA, AMD or Intel GPUs** |
| P−1 factoring | stages 1 and 2, on both engines, with bounds chosen from the sieve depth. With the project's list it finds a factor for about 1 number in 4 for under 4% of a test's work. See [PM1.md](docs/PM1.md) |
| verification | 64/64 self-checks on both engines and both GPU kernel sets; the SoB prime 46157·2^698207+1 proven prime; full-size squarings match GMP. See [RESULTS.md](docs/RESULTS.md) |
| GPU speed | **unmeasured on the GPUs that matter**. Apple M4 Pro: 3.03 ms per squaring at the leading edge, 40 hours per test (5.39 ms with the original kernels). See [PERFORMANCE.md](docs/PERFORMANCE.md) |
| a new prime | no. Nothing beyond PrimeGrid's frontier has been tested |

## Quick start

```bash
sudo apt-get install -y build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers clinfo   # macOS: brew install gmp libomp
```

```bash
make && make check
```

```bash
./colbert selftest --backend ocl
```

Full instructions: [docs/SETUP.md](docs/SETUP.md). First run on a GPU:
[docs/GPU_BENCHMARKING.md](docs/GPU_BENCHMARKING.md).

### The app

**No terminal needed:** double-click **Start Colbert.command** (macOS), **Start Colbert.bat**
(Windows) or **Start Colbert.sh** (Linux). The first time, it installs what the engine needs
(asking first) and builds it. After that it checks for updates and opens the app. From a
terminal, `make colbert colbert-cpu && python3 app/run.py` does the same.

The app opens in your browser. The app finds every GPU and CPU on the machine and
self-tests and times each one. It then runs the fastest, shows progress, speed and time
left, and saves progress so tests can be paused and resumed. It can test your own numbers,
or join a shared **ledger** that coordinates many computers with no gaps and no wasted
repeats. Guide: [docs/APP.md](docs/APP.md). Ledger design and deployment:
[docs/LEDGER.md](docs/LEDGER.md).

## Documentation

| document | for |
|---|---|
| [EXPLAINER.md](docs/EXPLAINER.md) | anyone: the problem and the idea, without the mathematics |
| [APP.md](docs/APP.md) | the desktop app: running colbert on any computer, alone or as part of the project |
| [LEDGER.md](docs/LEDGER.md) | the ledger that coordinates many computers: guarantees, protocol, operations, cost |
| [PM1.md](docs/PM1.md) | P−1 factoring before each test: how it works, how the bounds are chosen, what it saves |
| [ENGINE_PROTOCOL.md](docs/ENGINE_PROTOCOL.md) | the engine's machine interface, which the app and ledger rely on, and which tuning must keep |
| [SETUP.md](docs/SETUP.md) | installing, building, checking and running |
| [GPU_BENCHMARKING.md](docs/GPU_BENCHMARKING.md) | the protocol for validating and timing on a real GPU |
| [PERFORMANCE.md](docs/PERFORMANCE.md) | expected speed against proth20, llrCUDA and LLR2, and why |
| [NOVELTY.md](docs/NOVELTY.md) | prior-art review: what is new, what isn't, with sources |
| [DESIGN.md](docs/DESIGN.md) | the mathematics, with proofs |
| [RESULTS.md](docs/RESULTS.md) | everything that has actually been run, and the search economics |

## What finding the next prime takes

PrimeGrid's Seventeen or Bust search had reached n = 47,856,007 on 17 November 2026.
From there to n = 57.5 million:

* about 110,000 tests after a deep sieve (209,000 survive the shallow sieve in `data/`);
* **0.21 expected primes** in that whole range;
* about **520,000 tests per expected prime**, each one about 48 million squarings of a
  14.4-million-digit number.

A faster transform lowers the cost of each test. It can't lower the number of tests.

## Before spending money or GPU-years

* PrimeGrid runs this search and will test the same numbers. Testing ahead of their
  frontier duplicates work they will redo, and by community convention the range is theirs.
  A faster GPU tester is probably worth most as a contribution to their project.
* The candidate lists in `data/` are shallow: the project ledger's list is sieved to 2³², and
  PrimeGrid's much deeper sieve would remove roughly half of what is left.
* Confirm any prime with independent software before announcing it.

## Layout

    proto/weighted_ntt.py   pure-Python model of the transform, checked against big integers
    src/field.h             GF(q), GF(q^2) for q = 2^61-1, 2^31-1
    src/layout.*            digit layout, rigorous overflow bound, weight and twiddle tables
    src/cpu_engine.cpp      OpenMP reference engine
    src/kernels.cl          OpenCL kernels;  src/ocl_engine.cpp  host side
    src/proth.*             Proth test, Gerbicz-Li checking, verified checkpoints
    src/pm1.*               P-1 factoring (stages 1 and 2), bound selection
    src/main.cpp            command line, and the --json machine interface (docs/ENGINE_PROTOCOL.md)
    tools/check_protocol.py contract test for that interface (part of make check)
    app/                    desktop app (Python standard library): app/run.py
    ledger/                 work ledger: lease-based assignment, double checks; SQLite or Firestore
    deploy/ledger/          deploy the ledger to Cloud Run + Firestore, and tear it down
    tools/sieve.cpp         candidate sieve for the five k (p <= 2^32)
    tools/cost_model.py     candidates -> expected primes, GPU-hours, dollars
    tools/perf_model.py     first-principles speed model for colbert, proth20 and FP64 IBDWT
    deploy/gcp-benchmark.sh one-GPU benchmark on Google Cloud (not run)
    data/                   candidate lists: n in [45.5M, 57.5M] sieved to 1e9; the ledger's list,
                            n in [47.9M, 57.5M] sieved to 2^32, and the factors that removed the rest
