# Results so far

The first section is the first run on a real GPU, an Apple M4 Pro, on 21 November 2026.
Everything after it was run on a 4-core cloud VM with no GPU (Intel Xeon 2.1 GHz, 15 GB) on
16 November 2026. There, "OpenCL" means the kernels in `src/kernels.cl` executed by PoCL, a
CPU implementation of OpenCL. **No NVIDIA, AMD or Intel GPU has run this code yet.**

## Apple M4 Pro, 21 November 2026

MacBook with an M4 Pro (14 CPU cores, 20 GPU cores, 24 GB unified memory), macOS 26.2,
Apple OpenCL 1.2 (deprecated by Apple but still shipped), Apple clang 17, engine `1dde3c0-dirty`.
Apple's GPUs have no native 64-bit integer multiply, so these speeds say little about
NVIDIA or AMD hardware.

| check | result |
|---|---|
| `selftest --backend ocl` on the GPU | **59/59** (17 s) |
| `selftest` on the CPU engine | 59/59 |
| 5 consecutive squarings at full size vs GMP, `67607·2^47856023+1` (fold structure) | **match** |
| 5 consecutive squarings at full size vs GMP, `21181·2^47856020+1` (real structure) | **match** |
| `46157·2^698207+1` (Seventeen or Bust prime), GPU, end to end | **PRIME**, 3 Gerbicz checks, 0 rollbacks, **136 s** (38 min on the 4-core CPU build) |
| `tools/check_protocol.py` (stop, resume, rejected checkpoint, residue unchanged by an interruption) | pass on both backends |

| speed at the leading edge (`bench 21181 47856020`, N = 2^21) | ms per squaring | one test |
|---|---|---|
| GPU (OpenCL), original radix-2 kernels | 5.19 | 69 hours |
| GPU (OpenCL), four-step kernels (same day, later) | **3.03** | **40 hours** |
| CPU engine, 14 threads | 20.9 | 277 hours |

The GPU proves the known prime about 17 times faster than the 4-core cloud CPU did. At the
leading edge the four-step kernels are 7 times faster than this machine's own 14 CPU cores.
See PERFORMANCE.md for what changed and where the time goes.

### Four-step kernels and P−1 (21 November 2026, later)

| check | result |
|---|---|
| `selftest` on the CPU engine, the four-step GPU kernels, and the radix-2 GPU kernels | **64/64** each (59 as before, plus 5 P−1 cases) |
| four-step kernels with weights from tables and computed on the fly, 1 and 2 columns per group | 64/64 each |
| sizes covered by the self-test on the four-step path | 8×8 to 128×256 points, both 61- and 31-bit fields, both weight structures |
| 4 consecutive squarings at n = 47,900,038 vs GMP, all five k (both structures in both fields) | **match** |
| a deliberately broken four-step kernel (`FAULT_FFT2`) | caught by the startup check; the engine falls back to radix-2 and still matches GMP |
| P−1 stage 1 and the stage-2 product vs GMP; D = 2310 and D = 120 | match |
| P−1 at full size: `55459·2^47900038+1`, B1 = 20,000, B2 = 300,000, stopped in stage 2 and resumed | no factor (as expected at such small bounds); stage-1 step 2.93 ms, stage-2 product 3.47 ms |
| end to end (ledger + headless app): `55459·2^30226+1` and `46157·2^698207+1` | factor found by P−1 and accepted by the ledger; P−1 found nothing for the prime, which the test then proved prime |
| `tools/check_protocol.py` (now with P−1 events, stop and resume in stage 2) | pass on both backends |

## Correctness

| check | CPU engine | OpenCL engine |
|---|---|---|
| `selftest`: products `k·x·y mod P` vs GMP for 25 (k, n, size) cases, incl. all five k, both transform structures, one and two primes, n up to 1,000,003 | 25/25 | 25/25 |
| `selftest`: Proth verdict and 64-bit residue vs GMP for 33 numbers (12 primes/neighbours with 15-bit k, the five k at n = 1000, 1001, 2000, 4001) | 33/33 | 33/33 |
| `selftest`: injected bit flip is detected by the Gerbicz check, rolled back, final residue correct | pass | pass |
| full production size: `67607·2^46000000+1`, 22 consecutive squarings vs GMP | match | not run |
| full production size: `21181·2^46000028+1`, 8 consecutive squarings vs GMP | not run | match |
| `46157·2^698207+1` (Seventeen or Bust prime, 210,186 digits) | **PRIME**, 3 Gerbicz checks, 0 rollbacks | not run |
| composite residues vs GMP `powmod`: `21181·2^100004+1`, `67607·2^100003+1`, `55459·2^250007+1` | 3/3 match | not run |
| `proto/weighted_ntt.py`: 120 random products, 19 Proth verdicts vs Python integers / GMP | pass | n/a |
| `tools/sieve`: survivors for n in [100000, 104000], p <= 200000, vs gcd with the primorial | identical (156 of 156, 0 disagreements) | n/a |

Not yet done: a full test of a multi-million-bit number on the OpenCL path; any run on GPU
hardware; comparison of residues with LLR2/PRST (neither was obtainable in this
environment).

## Speed (CPU only, for the record)

| what | time per squaring |
|---|---|
| CPU engine, n = 698,207 (N = 2^15), 4 threads, uncontended | about 1.7 ms |
| CPU engine, n = 46M (N = 2^21), 2 threads, machine shared with the sieve | 243 ms |
| OpenCL on PoCL, n = 46M (N = 2^21), 4 threads | 171 ms |

These say nothing about GPU speed, and the CPU engine is far slower than LLR's hand-tuned
floating-point code on the same hardware. It exists to be obviously correct.

## Candidates, n in [45,500,000, 57,500,000]

Sieved to p <= 10^9 (50,845,272 primes, 36 minutes on 2 cores). The list is in
`data/candidates_45.5M-57.5M_p1e9.txt.gz`.

| k | residue classes of n mod 720 left by primes < 20000 | candidates | expected primes |
|---|---|---|---|
| 21181 | 24 | 61,569 | 0.0639 |
| 22699 | 8 | 25,235 | 0.0262 |
| 24737 | 18 | 64,676 | 0.0672 |
| 55459 | 28 | 86,636 | 0.0900 |
| 67607 | 8 | 21,874 | 0.0227 |
| all | | 259,990 | 0.2701 |

"Expected primes" is the Mertens heuristic `e^γ ln(p) / ln(N)` summed over candidates; it
does not depend on sieve depth.

**Correction (17 Nov 2026).** The 45.5M lower limit came from a search-engine snippet.
PrimeGrid's live status page shows the SoB leading edge at **n = 47,856,007** (minimum
remaining n 47,200,294), so most of the first 2.4M of this list has already been tested by
PrimeGrid. Restricted to n ≥ 47,856,007:

| | value |
|---|---|
| candidates surviving p ≤ 10^9 | 208,912 (21181: 49,466; 22699: 20,286; 24737: 52,014; 55459: 69,593; 67607: 17,553) |
| expected after a deep sieve to ~1.4·10^17 (assumed depth) | ~109,700 tests |
| expected primes, n in [47.86M, 57.5M] | 0.212 (19% chance of at least one) |
| tests per expected prime | ~518,000 |

Reproduce with:

    ./sieve 45500000 57500000 1e9 candidates.txt
    tools/cost_model.py candidates.txt --psieve 1e9 --pdeep 1.4e17 --ms-per-iter 0.15 0.5 1.5 --usd-per-hour 0.25

For the post-wavefront figures, first keep only lines with `n >= 47856007`.
