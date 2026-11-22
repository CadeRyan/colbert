# How fast should this be?

**Nothing on this page is a GPU measurement.** The only GPU colbert has run on so far is an
Apple M4 Pro (3.03 ms per squaring at the leading edge; [RESULTS.md](RESULTS.md)), which lacks
native 64-bit multiplies and says little about the GPUs modelled here. These are
estimates from a first-principles model (`tools/perf_model.py`), anchored where possible to
numbers PrimeGrid volunteers have published. The GPU benchmark in
[GPU_BENCHMARKING.md](GPU_BENCHMARKING.md) exists to replace them with measurements.

## Summary

At the current Seventeen or Bust leading edge (n ≈ 47.9 million, about 14.4 million digits):

| compared with | same hardware? | expected speed-up of a *tuned* colbert | confidence |
|---|---|---|---|
| proth20, the existing GPU Proth tester | yes, same GPU | **about 2.5×** (2.7× from data volume; ~3× once mixed-radix sizes exist) | medium: rests on both codes being memory-bound and equally well tuned |
| llrCUDA (FP64 IBDWT) on a consumer GPU | yes | **about 3×** | medium: consumer GPUs run FP64 at 1/64 rate, which starves llrCUDA |
| llrCUDA on a datacenter GPU (H100) | yes | **about 1.4×** | low-medium: both memory-bound there; colbert simply moves less data |
| LLR2/PRST on a high-end desktop CPU (what PrimeGrid runs today) | no | **about 4–8× per device**; **about 2–3× per kWh** | low: compares an RTX 4090 with an extrapolated 16-core CPU |
| **today's colbert kernels** (four-step, 21 Nov 2026) vs tuned proth20 | yes | **unmeasured; about 2× faster if memory-bound** | low: they move 1.2–1.5× the data the model assumes (2.7× ÷ that ≈ 2×), but on the only GPU measured, arithmetic rather than memory is the limit |

The method's advantage is real but moderate. It is a constant factor of about 2.5–3 against
the best existing GPU approach. It does not change the order of the cost, and it cannot
change the number of tests a prime takes (about half a million at these sizes; see
[RESULTS.md](RESULTS.md)). The kernels now make about as many passes over memory as the
model assumes, but none of the GPUs modelled here has run them, so the factor is still
unconfirmed. What is left to do is listed at the end ([What is left](#what-is-left)).

## Why the data volume decides it

One squaring at this size transforms a few tens of megabytes. That is far more than any
GPU's on-chip cache, so every pass of the transform streams the whole array through the
GPU's main memory. A GPU can do arithmetic far faster than it can move data. A
well-written FFT therefore ends up waiting on memory, and its time is roughly:

    time per squaring ≈ (memory round trips) × 2 × (bytes of transform data) / (memory bandwidth)

The best existing GPU codes (PRPLL is the reference) manage about three round trips per
squaring. Given that, **speed is proportional to the bytes of transform data**, and that is
what the new transform reduces:

| approach | transform data per squaring at n = 47.86M |
|---|---|
| proth20: exact, zero-padded, two 31-bit primes | 64.0 MiB |
| FP64 weighted transform (gwnum, llrCUDA): ~10.8 bits per double for these k | ~33.8 MiB |
| **colbert: exact, no padding, GF(M61²) × GF(M31²), power-of-two sizes** | **24.0 MiB** |
| colbert with mixed-radix sizes (not yet written) | 21.0 MiB |

colbert is not memory-bound by accident. Its multiply count is checked in the model too:
about 0.65 G 32-bit integer multiplies per squaring, about 0.02 ms on an RTX 4090. That
is well below the memory time even if 64-bit products cost several times more than
assumed.

## Model output

`python3 tools/perf_model.py` (k = 21181, n = 47,856,007, 3 round trips):

| lower bound, ms per squaring | RTX 4090 | RTX 5090 | H100 SXM |
|---|---|---|---|
| colbert, power-of-two | 0.150 | 0.084 | 0.045 |
| colbert, mixed-radix | 0.131 | 0.074 | 0.039 |
| proth20 | 0.399 | 0.225 | 0.120 |
| FP64 IBDWT (llrCUDA-style) | 0.427 (FP64-bound) | 0.347 (FP64-bound) | 0.063 |

Device figures are approximate published specifications: memory bandwidth 1008 / 1792 /
3350 GB/s; FP64 1.3 / 1.6 / 34 TFLOP/s; 32-bit integer multiply roughly half the FP32 rate.
Real programs reach these bounds only within a factor of about 1.3–2.

## What the code does now (four-step kernels, 21 November 2026)

The first OpenCL kernels were written to be obviously correct: per squaring and per prime,
5 forward and 5 inverse radix-16 passes over the whole array, separate weight, pointwise and
carry kernels, and a twiddle read per butterfly from tables as large as the data. About 0.81 GB
moved per squaring at the leading edge.

The fast path (`src/kernels.cl`, section `fft2`) replaces them for every size up to N = 2²¹
words, which covers n up to about 58 million:

1. **Three passes per prime instead of ten.** The 2²⁰-point transform is a four-step 1024 × 1024
   transform. One work-group does a whole 1024-point sub-transform in registers and local
   memory. `colfwd` weights the digits and transforms the columns; `rows` transforms the rows,
   does the pointwise product (including the conjugate-pair "untangle" of the real structure)
   and the inverse row transform in the same pass; `colinv` finishes the columns.
2. **Radix-8 butterflies with free twiddles.** w₈ = (1+i)·2^((q_bits−1)/2) is a primitive 8th
   root of unity in GF(q²) for both Mersenne primes, so a radix-8 butterfly needs only
   additions and bit rotations. Sub-transforms use 2.25 general multiplies per point instead
   of 5, with the radix-2 or radix-4 stage last, where it costs least.
3. **Squaring-specific arithmetic:** complex squaring with two products instead of four, and an
   untangle specialised for squaring.
4. **Local memory one 32-bit word per point** (values cross in parts), which doubles to
   quadruples the work-groups that fit on a GPU core. On the M4 Pro this alone took a squaring
   from 5.9 to 4.1 ms.
5. **The carry** computes the eight CRT values of a block independently before the serial
   chain (1.04 → 0.35 ms on the M4 Pro).
6. **Weights from two small tables and a rotation** instead of tables as large as the data
   (2^s mod a Mersenne prime is a rotation): about 56 MiB less read per squaring. Measured
   equal on the M4 Pro, which is limited by 64-bit arithmetic rather than memory; on by default
   elsewhere.
7. A startup self-check against the radix-2 kernels, with automatic fallback.

About 0.2 GB now moves per squaring, a quarter of before. That is 1.2–1.5× the three round
trips the model above assumes; the range depends on whether the weights come from tables.

| Apple M4 Pro, n = 47.9M, N = 2²¹ | ms per squaring | one test |
|---|---|---|
| original radix-2 kernels | 5.39 | 72 h |
| four-step kernels | **3.03** | **40 h** |

Where the time goes now (M4 Pro, `bench --profile`):

| kernel | field | ms per squaring | data in and out |
|---|---|---|---|
| `rows` | 61-bit | 1.22 | 32 MiB |
| `colfwd` | 61-bit | 0.52 | digits in, 16 MiB out |
| `carry1` | both | 0.35 | 24 MiB in, digits out |
| `colinv` | 61-bit | 0.32 | 32 MiB |
| `colfwd` | 31-bit | 0.25 | digits in, 8 MiB out |
| `rows` | 31-bit | 0.21 | 16 MiB |
| `colinv` | 31-bit | 0.10 | 16 MiB |
| `carry2` | both | 0.08 | a few words per block |

With weight tables (the Apple default), `colfwd` and `carry1` also read the weights.

In the 61-bit field, `rows` and `colinv` move the same amount of data, but `rows` takes four
times as long. It does two sub-transforms, the pointwise product and a twiddle, so on this GPU
arithmetic is the limit, not memory. Measured throughput: 16 G complex multiplications per
second in GF(M61²), against 95 G in GF(M31²), and 190–215 GB/s of memory bandwidth. The GPU
has no 64-bit integer multiplier and builds each 64-bit product from 32-bit ones. On GPUs
limited by memory bandwidth instead, the 4× cut in data moved should count for more. Those
are the discrete NVIDIA and AMD cards the model above is about, and this is unmeasured.

## What is left

The work is ordered by expected payoff for the project. Only the M4 Pro figures on this page
are measurements. Everything else is an estimate and is labelled as one.

### Fewer tests: sieve deeper

The cheapest test is one that never has to run. The ledger's list is sieved to 2³², where
`tools/sieve` stops. Sieving on to 2^b leaves about 32/b of the candidates (Mertens' theorem).
For the step from 10⁹ to 2³², that predicted 6.6% would be removed, and 6.6% were.

A deeper sieve also leaves fewer factors for P−1 to find, because the two methods find many of
the same ones, so the net saving is smaller than the share of candidates removed. The "work"
column counts tests, P−1 and the expected 5% of double checks, using the plans from
`colbert info --sieve-bits B` at n = 47.9M:

| sieve to | candidates left | P−1 finds a factor | work to cover a range of n | sieve time on this Mac |
|---|---|---|---|---|
| 2³² (today) | 100% | 24% | 100% | 7.5 min (measured, 14 cores) |
| 2³⁶ | 89% | 18% | 96% | ~2 hours |
| 2⁴⁰ | 80% | 12% | **92%** | **~1 day** |
| 2⁴⁴ | 73% | 7.7% | 87% | ~2 weeks |
| 2⁴⁸ | 67% | 4.5% | 82% | ~7 months |
| 2⁵⁷ (about PrimeGrid's sieve) | 56% | 0.9% | 71% | out of reach for one machine |

The sieve times assume each prime costs what it did in the 2³² run (453 s for 203 million
primes); the total grows with the number of primes. Before the tool can go past 2³², it needs
64-bit modular arithmetic: it computes `a * b % p` in 64 bits, which overflows for larger p.

A day of CPU time for 8% less work is the best trade on this page. Each test that isn't
needed saves 40 GPU-hours on this Mac, and the sieve runs on the CPU while the GPU tests.
PrimeGrid's own sieve output would save more still, if they will share it. A deeper list goes
into the ledger with `admin remove`, and the ledger's `sieve_bits` setting must then be raised
so P−1 plans for the new depth ([LEDGER.md](LEDGER.md)).

### Fewer tests: cheaper P−1 stage 2

**Prime pairing.** Stage 2 can work with x = y + 1/y instead of y. Since
x^(mD) − x^r = (y^(mD) − y^r)(1 − y^−(mD+r)), with x^j meaning y^j + y^−j, one product covers
both primes mD − r and mD + r. Only half the stored spectra are
needed, which leaves room for a larger D. With D = 330 this removes about 13% of stage-2
products and half the giant steps: about 0.4% of a test per number, out of P−1's 3.7%. It is
small, and worth doing with the next change to P−1.

### Faster squarings on every GPU

1. **Measure on an NVIDIA or AMD GPU** ([GPU_BENCHMARKING.md](GPU_BENCHMARKING.md)). Every
   estimate here about memory-bound GPUs depends on it.
2. **One inverse pass for both fields, with the block carries.** Today `colinv` writes 24 MiB
   that `carry1` reads straight back. A work-group holding a few adjacent columns (`CPG`
   already groups them) holds whole carry blocks. It could run both fields' inverse column
   transforms and `carry1`'s work in the same pass, leaving only `carry2`. That moves a fifth
   to a quarter less data on memory-bound GPUs.
3. **Then the next squaring's forward columns in the same pass**, as PRPLL's fused carry
   kernel does. This needs the carry between blocks handed from one work-group to the next
   during the pass. A squaring would then be two passes over the data instead of about three
   plus the digits: roughly half the data moved now. The digits would also be read once,
   not once per field.
4. **Mixed-radix sizes** (radix-3 and radix-7 sub-transforms). Every size is a power of two
   today, so at the leading edge the words carry fewer bits than the bound allows. The next
   smaller mixed size moves about 14% less data (24.0 → 21.0 MiB, from the model above).
5. **Four-step kernels for N = 2²² and above** (n above about 58 million), which still use
   the radix-2 kernels. The fast path takes sub-transforms of at most 1024 points, and
   2048-point ones would fit in local memory. The ledger's list stops at n = 57.5 million, so
   this isn't needed yet.

### Faster squarings where 64-bit multiplies are slow

On the M4 Pro, the 61-bit field takes 2.1 of the 3.03 ms, and it is limited by arithmetic.
GPUs generally build 64-bit multiplies from 32-bit ones, so these steps help elsewhere too,
but less where memory is the limit.

1. **Karatsuba products in GF(M61²).** `cmul61` uses four 64 × 64-bit products. Three
   suffice, at the cost of a few additions; the sums fit, since M61 leaves 3 bits spare in a
   64-bit word. General products are most of the 61-bit field's multiplications.
2. **Twiddles from full tables.** In both `colfwd` and `rows`, each four-step twiddle is
   built with a product from two small tables (`tw4`), and so is the untangle's root. Reading
   them from full tables saves about two products per point per squaring, for one more table
   read per point. This is the same trade the weights make per device (`COLBERT_WOTF`). For the
   weights it measured equal on the M4 Pro, so it needs measuring.
3. **Lazy reduction.** Values in GF(M61) use 61 of 64 bits, so butterfly additions can skip
   the compare-and-subtract for a level or two.
4. **Two 31-bit prime fields instead of GF(M61²)**, with Montgomery arithmetic. The estimate
   is about 1.8× less arithmetic on GPUs with slow 64-bit multiplies. This is the largest
   change listed: new fields, new bounds and a new CRT. The radix-8 butterflies would no
   longer be free, because that trick depends on Mersenne primes.

### The CPU engine

The CPU engine (`--backend cpu`, and `colbert-cpu`) is the scalar reference that the GPU code
is checked against: radix-2 passes, no SIMD, a twiddle read per butterfly. On this Mac's 14
cores it takes 20.9 ms per squaring, 277 hours per test. For comparison, the estimate for
PrimeGrid's LLR2 on the same Mac is 3–5 days (x86 code under Rosetta). The obvious steps are
the four-step radix-8 structure, SIMD for the 31-bit field, and the CPU's native 64-bit
multiplies for the 61-bit field. The gain is unmeasured. This matters only for computers
without a usable GPU.

## Against the CPUs PrimeGrid actually uses

PrimeGrid runs Seventeen or Bust with LLR2 on CPUs, so this comparison matters most, and
it is also the weakest. Published data points:

* 2020: two Intel 9960X machines (16 cores each), 16-thread tasks, averaged 26,674 s per SoB
  task at FFT length 3200K (n ≈ 34M), i.e. **1.6 tests per day per machine**.
* 2020: a Ryzen 3950X with dual-rank RAM ran a 3200K SoB task in about 20 hours.

Scaled to n = 47.86M (×1.4 iterations, ×1.4 FFT length), that is about 0.8 tests per day for
the 2020 machine. A current 16-core desktop with AVX-512 and DDR5 might manage 1–2. Against
that:

| | tests per day | approx. power | tests per kWh |
|---|---|---|---|
| 16-core desktop CPU, LLR2 (extrapolated) | 1–2 | ~200 W | ~0.2–0.4 |
| RTX 4090, proth20 (model, 0.5 ms) | ~3.6 | ~400 W | ~0.38 |
| RTX 4090, tuned colbert (model, 0.2–0.25 ms) | ~7–9 | ~400 W | ~0.75–0.95 |

One consistency check: the model says proth20 is faster than a CPU but no better per kWh.
That is what Yves Gallot reported on PrimeGrid's forum in 2024. A tuned colbert would be
the first GPU option that also wins on energy, and for a volunteer project energy is the
cost that counts.

## How to check these numbers

Run the protocol in [GPU_BENCHMARKING.md](GPU_BENCHMARKING.md) on one GPU, with colbert and
proth20 side by side. Then rerun `tools/perf_model.py` with that GPU's specifications. If
the measured ratio between the two programs is far from the data-volume ratio, the model
is wrong and this page should be rewritten.
