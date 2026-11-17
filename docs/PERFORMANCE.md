# How fast should this be?

**Nothing on this page is a GPU measurement.** No GPU has run colbert yet. These are
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
| **today's unoptimized colbert kernels** vs tuned proth20 | yes | **probably about 2× *slower*** | medium: the kernels make ~6× more memory passes than a tuned code |

The method's advantage is real but moderate. It is a constant factor of about 2.5–3 against
the best existing GPU approach. It does not change the order of the cost, and it cannot
change the number of tests a prime takes (about half a million at these sizes; see
[RESULTS.md](RESULTS.md)). Collecting that factor requires optimization work that hasn't
been done yet.

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

## What today's code would do

The current OpenCL kernels were written to be obviously correct, not fast. Per squaring
they make:

* 5 forward and 5 inverse radix-16 passes per prime, each reading and writing the whole
  array;
* separate weight, pointwise, and two carry kernels;
* about one twiddle-table read per butterfly, from tables as large as the data.

That is roughly 35–40 array-sized transfers per prime per squaring, against about 6 for a
tuned code. Expected result on an RTX 4090: **about 1 ms per squaring, about 13 hours
per leading-edge test**. A tuned proth20 should land near 0.5 ms. So the first GPU
benchmark will most likely show colbert *losing* to proth20. That is expected. The
benchmark's job is to confirm the model's per-pass costs, not to show the final speed.

The optimizations needed to collect the advantage, roughly in order of payoff:

1. Fuse passes so each squaring makes ~3 round trips: weight + first passes; middle passes
   in local memory; last passes + pointwise + inverse first passes.
2. Generate twiddles on the fly or from small tables, instead of reading a table as large
   as the data.
3. Fuse the carry into the last inverse pass and the next squaring's weighting.
4. Use 3-multiply (Karatsuba) complex products in GF(M61²).
5. Write radix-3 and radix-7 passes for mixed-radix sizes (another ~14%).

PRPLL and genefer already do all of this for their transforms; the structure carries over.

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
