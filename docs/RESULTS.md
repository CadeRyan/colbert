# Results so far

Everything below was run on a 4-core cloud VM with no GPU (Intel Xeon 2.1 GHz, 15 GB),
on 16 November 2026. "OpenCL" means the kernels in `src/kernels.cl` executed by PoCL, a
CPU implementation of OpenCL. No GPU has run this code yet.

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
does not depend on sieve depth. Scaled to an assumed deep-sieve depth of 1.4·10^17 the
range holds about 136,000 tests, i.e. about 505,000 tests per expected prime.

Reproduce with:

    ./sieve 45500000 57500000 1e9 candidates.txt
    tools/cost_model.py candidates.txt --psieve 1e9 --pdeep 1.4e17 --ms-per-iter 0.15 0.5 1.5 --usd-per-hour 0.25
