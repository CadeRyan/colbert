# Is this new? A prior-art review

*Researched 17 November 2026. Where I read a primary source, it says so; where I only saw a
search-engine summary, it says that instead.*

## Verdict

**Probably yes, in a specific and modest sense.** It is a new combination of known
techniques, not new mathematics, and it fills a gap that the leading expert in this area
described publicly as open. The claim still rests on not finding a prior version rather
than on proof that none exists.

The strongest evidence: in February 2024, on PrimeGrid's forum, Yves Gallot wrote:

> "There exist fast algorithms to test numbers of the form k·b^n +/- 1 using double-precision
> floating-point numbers. But FP64 are not fast on Graphics Cards: number-theoretic
> transforms are more appropriate. But the forms of the numbers that can be tested using
> these transforms are limited: they must be a factor of x^n − 1 … Mersenne numbers,
> generalized Fermat numbers and b^2n − b^n + 1."
>
> "Surprisingly no fast algorithm exists for k·b^n +/- 1 but a fast generic reduction can be
> implemented. I will probably write a "universal" prime tester for GPU using this algorithm
> but it will still be six times slower than genefer."

Gallot wrote proth20, genefer and Proth.exe, and develops the integer-transform (NTT) prime
testers PrimeGrid runs on GPUs. colbert is exactly the "fast algorithm for k·2^n+1" with
number-theoretic transforms that this statement says does not exist. It is fast in the
sense meant there: the transform is the length of the number, with no padding and no
generic reduction. It gets round the "factor of x^n − 1" restriction because, in
`GF(q²)`, the weights turn reduction modulo `k·2^n+1` into reduction modulo `Y^N − c` for
a *field element* `c = −k·2^n`, not just `c = ±1`. I found no later program or post that
closes this gap. (Source: [PrimeGrid forum thread 10486](https://www.primegrid.com/forum_thread.php?id=10486),
messages 169806 and 169815, 28 February 2024, read directly.)

Almost every ingredient of colbert was published or shipped years ago. My first write-up
claimed more novelty than this review supports. The corrections:

* The no-padding weighted transform for `k·2^n+1` is **Colin Percival's (2002)**, and
  gwnum (used by LLR2 and PRST, which PrimeGrid runs) has used it for years. llrCUDA runs
  it on GPUs.
* The trick of computing `k·x·y` instead of `x·y` is **George Woltman's "1/k format"** in
  gwnum.
* Transforms over `GF(q²)` for Mersenne `q`, including both half-length structures colbert
  uses, are **Richard Crandall's (1999)**.
* The specific pair `GF(M61²) × GF(M31²)` combined by CRT appears in **Yves Gallot's
  genefer22 design code**, for generalized Fermat numbers. PRPLL ships M31+M61 transforms
  for Mersenne numbers.

What I could not find anywhere is the one step connecting those lines of work:

> Doing Percival's transform for `k·2^n+1` **exactly** in `GF(q²)`. The weights it needs are
> `N`-th roots of `−k·2^n`. In `GF(q²)` with `q = 2^e − 1` prime, every element of `GF(q)`
> has such roots, because the norm map `h ↦ h^(q+1)` is onto `GF(q)*`. So the exact
> transform exists for every `k`, with no padding.

Once that step is taken, the rest follows: choosing per prime between Crandall's two
structures by the Legendre symbol `(k/q)`, the integer overflow bound, and the
implementation.

The same argument covers `k·2^n − 1` (the Riesel problem, also a PrimeGrid project) with
`c = +k·2^n`. Bases other than 2 should work too, with base-`b` digits. colbert implements
only `k·2^n + 1`.

Every existing exact (integer) GPU tester for `k·2^n+1` that I found, which is proth20,
zero-pads. Every existing no-padding tester for `k·2^n+1` uses floating point.

## What I checked

### Primary sources read in full or in the relevant part

| source | what it shows |
|---|---|
| Percival, *Rapid multiplication modulo the sum and difference of highly composite numbers*, Math. Comp. 72 (2003) 387–395 | No-padding DWT for `a ± b`, explicitly "rapid computation modulo numbers of the form k·2^n ± 1". Floating point throughout; the paper's other contribution is rigorous round-off bounds. Notes that finite-field FFTs exist but treats only floating point. |
| Crandall, *Integer convolution via split-radix fast Galois transform* (1999) | DGT over `GF(p²)`, `p` Mersenne; real-signal "nested-complex" half-length transform; negacyclic "folded-complex" transform twisted by an `M`-th root of `i`; suggests `p = 2^61 − 1`. Only cyclic and negacyclic convolutions, i.e. moduli `2^N ± 1`, with no general multiplier. |
| llrCUDA source (`gwypnum.cu`, `lmenu.cu`; GitHub mirror `primesearch/llrCUDA`) | "Using George Woltman's 1/k method IBDWT for k's up to 19 bits", then rational-base DWT, zero-padding and generic reduction for larger `k`. All double precision (cuFFT). Residues are stored "pre-multiplied by 1/k". |
| proth20 source (`src/gpmp.h`, Gallot, 2020) | Exact RNS NTT over two 31-bit primes, **zero-padded** to twice the length. At the SoB leading edge: 2^23 points, 64 MiB per squaring. |
| genefer22 source (`design/galois.cpp`, Gallot) | Arithmetic in `GF(M61²)` and `GF(M31²)` with CRT, for `b^(2^m)+1`, whose weights are roots of `−1` and need no general multiplier. |
| PRPLL / gpuowl source, head commit of 16 Nov 2026 | NTT types over M31 and M61 (and FP32 hybrids); the work-file parser accepts only Mersenne numbers. |
| PrimeGrid forum thread 10486, Feb 2024 (Gallot) | NTTs are the right tool on GPUs but only for Mersenne, generalized Fermat and `b^2n − b^n + 1` forms; "no fast algorithm exists for k·b^n +/- 1"; plans a generic-reduction tester at ~6× the cost. |
| PrimeGrid forum thread 8682 (2019–2020) and subproject status page (17 Nov 2026) | SoB used FFT lengths 2560K–2880K at n ≈ 31M (≈10.8 bits per double). SoB leading edge n = 47,856,007. |

### Searches that found nothing closer

Web searches for combinations of: "number theoretic transform" or NTT with IBDWT and
`k·2^n+1` or Proth; "discrete weighted transform" with finite field, `N`-th root, norm map,
`GF(p²)`; Proth or `k·2^n+1` with GPU and no zero padding; PRPLL or gpuowl with Proth
support; Gallot's repositories for a newer Proth tester; the "Montgomery–McLaughlin–
Gallot–Woltman" generic reduction and any GPU tester built on it (none found). The closest results were the
sources above, Fermat-number NTTs (where `k = 1`), and lattice-cryptography negacyclic
NTTs (moduli `x^n + 1`, not integers).

### What I could not check

* **mersenneforum.org.** The site refuses this environment's requests, so I saw only
  search-engine summaries of its threads. This is the most likely place for an informal
  proposal of exactly this idea (e.g. in a thread on integer-arithmetic Lucas–Lehmer tests,
  or in PRPLL's NTT development thread), and the summaries are not enough to rule that out.
* **Prime95/gwnum source.** I relied on llrCUDA's description of Woltman's method rather
  than reading gwnum itself.
* **Private or unpublished code**, e.g. development versions of Gallot's programs.

### An alternative someone could have used instead

The same exact no-padding transform could be built in ordinary prime fields `GF(p)`, by
searching for NTT-friendly primes `p ≡ 1 (mod N)` in which `−k·2^n` happens to be an `N`-th
power. About one prime in `N` qualifies, and the search must be redone for every `(k, n)`.
I found no implementation of that either, but it shows the result is not unreachable by
other routes.

## How to settle it

Ask the people who would know. A short post in mersenneforum's "Software" or
"Computer Science & Computational Number Theory" section, or a message to Yves Gallot
(proth20, genefer) and George Woltman (gwnum), with a link to DESIGN.md, would get a
definite answer within days. If the idea is new to them, they are also the people best
placed to judge whether it is worth adopting.

## Sources

* C. Percival, [Rapid multiplication modulo the sum and difference of highly composite numbers](https://www.daemonology.net/papers/fft.pdf), Math. Comp. 72 (2003). [Semantic Scholar record](https://www.semanticscholar.org/paper/Rapid-multiplication-modulo-the-sum-and-difference-Percival/ecfddc6c315b4d01c83240d7f743f4a0f4f0be85)
* Y. Gallot, posts in [GPU computing tasks and the future](https://www.primegrid.com/forum_thread.php?id=10486), PrimeGrid forum, 28 Feb 2024
* [PrMers](https://github.com/veljjanoski/PrMers) (integer IBDWT over `2^64 − 2^32 + 1`, Mersenne only)
* R. E. Crandall, [Integer convolution via split-radix fast Galois transform](https://www.reed.edu/physics/faculty/crandall/papers/confgt.pdf) (1999)
* R. E. Crandall, B. Fagin, [Discrete weighted transforms and large-integer arithmetic](https://www.ams.org/journals/mcom/1994-62-205/S0025-5718-1994-1185244-1/S0025-5718-1994-1185244-1.pdf), Math. Comp. 62 (1994)
* [Irrational base discrete weighted transform](https://en.wikipedia.org/wiki/Irrational_base_discrete_weighted_transform) (Wikipedia)
* Y. Gallot, [proth20](https://github.com/galloty/proth20), [genefer22](https://github.com/galloty/genefer22), [genefer26](https://github.com/galloty/genefer26)
* [llrCUDA mirror](https://github.com/primesearch/llrCUDA); [PrimeGrid llrCUDA testing thread](http://www.primegrid.com/forum_thread.php?id=3215)
* [gpuowl / PRPLL](https://github.com/gwoltman/gpuowl); [PRPLL-NTT thread, mersenneforum](https://www.mersenneforum.org/node/1086160/page35) (summary only)
* PrimeGrid: [Max FFT size for each LLR project](http://www.primegrid.com/forum_thread.php?id=8682), [subproject status](http://www.primegrid.com/server_status_subprojects.php), [GPU computing tasks and the future](https://www.primegrid.com/forum_thread.php?id=10486)
* A. Thall, [Fast Mersenne prime testing on the GPU](https://www.andrewthall.org/papers/gpuMersenne2011MKII.pdf) (2011)
