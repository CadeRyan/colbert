# Design: a zero-padding-free exact transform for Proth numbers

This document states the mathematics `colbert` relies on, proves the parts that need
proof, and says precisely what is and is not new. Everything here is exercised by
`proto/weighted_ntt.py` (a 300-line pure-Python model) and by `colbert selftest`.

## 1. The problem with k

A Proth test of `P = k·2^n + 1` is `n − 1` modular squarings of an `n`-bit number. For
`n ≈ 46 million` that is 46 million squarings of a 46-million-bit number, so the cost of one
squaring is the whole game.

For Mersenne numbers the squaring is as cheap as it can be: Crandall and Fagin's
irrational-base discrete weighted transform (IBDWT) turns reduction mod `2^p − 1` into the
wrap-around of a cyclic convolution, so a transform of the size of the *input* suffices.

For `k·2^n + 1` the wrap-around is `2^n ≡ −1/k`, which is not an integer. The two standard
answers both cost about a factor of two:

| approach | used by | what it costs |
|---|---|---|
| zero-padded transform, then reduce | proth20 (GPU); gwnum/LLR for very large `k` | transform of twice the length |
| IBDWT with `k` in the floating-point weights (Percival 2002; Woltman's "1/k" method) | gwnum → LLR2/PRST (CPU, what PrimeGrid runs); llrCUDA (GPU, FP64) | the convolution output is `k` times larger, so each double holds about `log2(k)/2` fewer bits. PrimeGrid's SoB tasks at n ≈ 31M used FFT lengths 2560K–2880K: about **10.8 bits per double**, against ~18–19 for a Mersenne number of that size |

`colbert` keeps the no-padding structure of the second row but does the weighted transform
**exactly**, in a field where the weights exist for every `k`, and where 92 bits of headroom
make the extra `log2 k ≈ 16` bits a small fraction of the budget rather than most of it.

## 2. Representation

Choose `N` words and a slope `β ≈ (n + log2 k)/N` (a fixed rational slightly above the true
value; see `Layout`). Put word `j` at bit position `s_j = ⌈jβ⌉`:

    x = Σ_{j<N} x_j · 2^{s_j}

Word `j` has base `2^{s_{j+1} − s_j}`. The top two words are reduced jointly modulo
`k·2^{n − s_{N−2}}`, so the number as a whole wraps at exactly `k·2^n ≡ −1 (mod P)`. Digits
are balanced (`|x_j| ≤ 2^{w_j − 1}`, plus at most 1 left by the parallel carry).

Two facts about `⌈·⌉` are used below; both hold for any real `β` with `⌊Nβ⌋ ≥ n`:

* (a) `s_i + s_j ≥ s_{i+j}`
* (b) `s_i + s_j − s_{i+j−N} ≥ n` when `i + j ≥ N`

## 3. The convolution

Multiply two such numbers and collect terms by `m = i + j mod N`:

* no wrap (`i + j = m`): `x_i y_j 2^{s_i+s_j} = x_i y_j · 2^{e} · 2^{s_m}` with `e = s_i+s_j−s_m ≥ 0` by (a);
* wrap (`i + j = m + N`): `2^{s_i+s_j} = 2^{e'} · 2^n · 2^{s_m}` with `e' ≥ 0` by (b), and `2^n ≡ −1/k`.

So `x·y ≡ Σ_m c_m 2^{s_m}` with `c_m = Σ_{nowrap} 2^e x_i y_j − (1/k) Σ_{wrap} 2^{e'} x_i y_j`.
The `c_m` are not integers, but

    d_m := k·c_m = k·Σ_{nowrap} 2^e x_i y_j − Σ_{wrap} 2^{e'} x_i y_j

is. **The transform therefore computes `x ∘ y := k·x·y mod P`.** That is harmless: `φ(x) = k·x`
is an isomorphism from `(Z/P, ∘)` to `(Z/P, ·)`, so squaring chains, products and the
Gerbicz check all go through unchanged in `∘`-arithmetic; one multiplication by `k` at the
very end converts back. (The Proth test starts from `x_0 = a^k / k = −2^n a^k` and declares
`P` prime iff `x_{n−1} ≡ 2^n`.) This is the same device as George Woltman's "1/k format" in
gwnum, where residues are stored pre-multiplied by `1/k`; it is not new here.

Now let `F` be a field containing an element `θ` with `θ^N = c := −k·2^n`, and set
`a_j = 2^{s_j} θ^{−j}`. Then `a_i a_j / a_m` equals `2^e` without wrap and `−2^{e'}/k` with
wrap, so

    d_m = k · a_m^{−1} · ( (a·x) ⊛ (a·y) )_m        (⊛ = cyclic convolution of length N)

One length-`N` weighted cyclic convolution, no padding.

## 4. Why GF(q²) with q a Mersenne prime

Take `q = 2^e − 1` prime (`e = 61` and `e = 31`) and `F = GF(q²) = GF(q)[i]`. Since
`q + 1 = 2^e`:

* `GF(q²)*` has order `(q−1)·2^e`, so it contains roots of unity of every power-of-two order
  up to `2^{e+1}`. Those of order dividing `2^e` have norm 1, i.e. `conj(ω) = ω^{−1}`.
* The norm map `h ↦ h^{q+1}` is onto `GF(q)*`. So for **any** `c ∈ GF(q)*`: pick `h` with
  `h·conj(h) = c` (solve `a² + b² = c`), and `θ = h^{(q+1)/N}` satisfies `θ^N = c`.

The second point is the heart of it. In the real numbers `−k·2^n` has no real `N`-th root
(floating-point codes use complex weights instead). In a prime field `GF(p)` with
`p ≡ 1 mod N` it has one only for about a fraction `1/N` of primes, so an implementation
would have to hunt for suitable primes for each `(k, n)`. In `GF(q²)` over a Mersenne prime
it always has one. (That 2 has such roots is what Mersenne-only codes in these fields rely
on; the observation here is that nothing is special about 2.)

Multiplication by powers of two is a rotation in these fields, and reduction mod `2^e − 1`
is a shift and an add, which is why they are the fields of choice for exact GPU transforms.

## 5. Half-length transforms

The inputs are "real" (in `GF(q)`), so `N/2` evaluation points determine everything. Which
half-length structure works depends on whether `c = −k·2^n` is a square in `GF(q)`; since
`2` is a square and `−1` is not, that is decided by the Legendre symbol `(k/q)`:

|  k    | (k / M31) | (k / M61) |
|-------|-----------|-----------|
| 21181 | +1 fold   | −1 real   |
| 22699 | −1 real   | −1 real   |
| 24737 | +1 fold   | −1 real   |
| 55459 | +1 fold   | −1 real   |
| 67607 | −1 real   | +1 fold   |

Both structures occur for the remaining Sierpiński `k`, in different combinations, so both
are implemented and each prime picks its own. Both structures themselves are Crandall's
(1999 "fast Galois transform" paper: the "nested-complex" real-signal transform and the
"folded-complex" right-angle transform). What is added here is the twist: the fold uses an
`N`-th root of `−k·2^n` instead of an `N`-th root of `−1`.

**Fold** (`c` a non-residue). `γ = θ^{−N/2}` satisfies `γ² = 1/c`, hence `γ = g·i` is purely
imaginary. With `M = N/2`, the real polynomial `Σ 2^{s_j} x_j Y^j` reduced mod `Y^M − γ` is
`Σ_{j<M} (2^{s_j} x_j + γ 2^{s_{j+M}} x_{j+M}) Y^j`; twisting by `θ^{−j}` makes it a plain
cyclic length-`M` problem. One complex table multiply in, one out; the real and imaginary
parts of the result are `d_j` and `d_{j+M}`.

**Real** (`c` a residue). Then `1/c` has an `N`-th root `ρ` in `GF(q)` itself (the residues
form a group of odd order, so `N` is invertible in the exponent). Real weights
`2^{s_j} ρ^j` turn the problem into a real cyclic convolution of length `N`, computed with a
length-`M` complex transform of `z_j = u_{2j} + i·u_{2j+1}` and the classical untangling of
conjugate pairs: with `Z_k = E_k + iO_k` and `conj(Z_{−k}) = E_k − iO_k`,

    E' = E₁E₂ + ω^k O₁O₂,      O' = E₁O₂ + E₂O₁.

This is the structure Mersenne testers use; it needs `conj(ω) = ω^{−1}`, which holds here
because the roots have norm 1. In bit-reversed order the partner of position `p` in the
block `[2^h, 2^{h+1})` is its mirror image `3·2^h − 1 − p`.

## 6. Exactness: a proof, not a tolerance

A floating-point FFT is correct when round-off stays below 0.5, which is monitored, not
proven. Here the only requirement is that `|d_m|` stays below half the CRT modulus
`Q = M61·M31 ≈ 2^92`. Writing `f_j = s_j − jβ ∈ [0,1)` and `X_j` for the largest digit
magnitude, `2^e = 2^{f_i+f_j−f_m}` and `2^{e'} = k'·2^{f_i+f_j−f_m}` with `k' = 2^{Nβ−n} ≈ k`, so

    |d_m| ≤ k' · 2^{−f_m} · Σ_i (X_i 2^{f_i})(X_{m−i} 2^{f_{m−i}}) ≤ k' · Σ_i (X_i 2^{f_i})²

by Cauchy–Schwarz. `Layout` evaluates the right-hand side for the actual word sizes and
refuses any configuration where it reaches `Q/2`. No input can overflow; there is no
round-off to watch. Roughly: `2β + log2 N + log2 k < 91.9`.

At the SoB leading edge (n = 47,856,007, k = 21181), from `tools/perf_model.py`:

| what | words | bits per word | transform data per squaring |
|---|---|---|---|
| this work, power-of-two sizes (today) | 2^21 | 22.8 | 24.0 MiB |
| this work, mixed-radix sizes (not yet written) | 7·2^18 | 26.1 | 21.0 MiB |
| proth20 (zero-padded, two 31-bit primes) | 2^23 points | 19 per input digit, padded 2× and rounded to a power of two | 64.0 MiB |
| double-precision IBDWT, `k` in the weights (gwnum, llrCUDA) | ~4.4M doubles | ~10.8 (observed by PrimeGrid) | ~33.8 MiB |

proth20's figure comes from its own sizing code (`transformSize`/`digitBit` in `gpmp.h`);
the double-precision figure scales PrimeGrid's published SoB FFT lengths to this `n`.
See [PERFORMANCE.md](PERFORMANCE.md) for what these sizes mean for speed.

## 7. Carry

The carry is the only sequential part. It is done in blocks of 8 words, in two parallel
passes: (1) CRT, add, and propagate inside each block, recording the carry out (up to about
72 bits); (2) add each block's carry into the next block (block 0 receives minus the last
block's carry, because `k·2^n ≡ −1`), propagate across 7 words, and let the 8th absorb the
residual `±1` un-normalised. That `±1` is included in the bound above. The engine raises an
error if a carry ever fails to settle; within the proven bounds it cannot.

## 8. Error checking

Exact arithmetic removes round-off errors, not hardware errors. Every run uses the
Gerbicz–Li check in `∘`-arithmetic: with `D_t = X_0 ∘ X_L ∘ … ∘ X_{tL}`,

    D_{t+1} = D_t ∘ X_{(t+1)L} = X_0 ∘ D_t^{∘ 2^L}

and comparing the two sides exposes an error in any squaring since the last verified state.
Checkpoints are written only after a passed check, so a pre-empted cloud instance resumes
from a state known to be good. The tail shorter than one block is run twice and compared.
`colbert selftest` injects a bit flip mid-run and requires the run to detect it, roll back,
and still produce the correct residue.

## 9. What is new, and what is not

Short version, with sources in [NOVELTY.md](NOVELTY.md):

| ingredient | first done by |
|---|---|
| irrational-base DWT, no padding (Mersenne) | Crandall & Fagin 1994 |
| no-padding DWT for `k·2^n ± 1`, floating point | Percival 2002; used in gwnum (Woltman) and llrCUDA |
| storing residues as `x/k` so products come out as `k·x·y` | Woltman, gwnum "1/k format" |
| transforms over `GF(q²)`, `q` Mersenne; real-signal and right-angle "folded" variants | Crandall 1999 ("fast Galois transform") |
| the `GF(M61²) × GF(M31²)` pair with CRT | Gallot (genefer22 design code, for `b^(2^m)+1`); PRPLL's M31+M61 NTT (Mersenne only) |
| Gerbicz–Li checking | Gerbicz; Li |
| **the Percival/Woltman DWT for `k·2^n+1` done exactly in `GF(q²)`, using the norm map to get an `N`-th root of `−k·2^n` for every `k`** | **not found in any source I could read; Gallot wrote in 2024 that no fast NTT algorithm for `k·b^n ± 1` exists** |
| per-prime choice of real vs folded structure by the Legendre symbol `(k/q)` | follows from the above |
| a rigorous worst-case overflow bound for that transform, enforced at run time | follows from the above |

So this is an adaptation of known techniques, not new mathematics. The one step I could
not find anywhere connects two existing lines of work. Percival's no-padding transform for
`k·2^n+1` had only been done in floating point. Exact Mersenne-field transforms had only
been used for moduli whose weights are powers of 2, and for those weights roots are easy.

## 10. Known limits and next steps

* Power-of-two sizes only. At the leading edge that costs about 14% (22.8 bits per word
  instead of 26.1). The odd factors of `gcd(M31 − 1, M61 − 1)` are 3², 7, 11, 31, 151 and 331,
  so sizes like `7·2^18` are available once radix-3/7 passes are written.
* The OpenCL kernels are written for correctness: radix-16 passes with one table read per
  butterfly, nothing fused. They have only ever run on a CPU OpenCL runtime. Real GPU speed
  is unmeasured.
* No P−1 stage and no Pietrzak proof generation yet. A proof would let a project skip the
  double-check, which is worth about a factor of 2 in throughput, as much as the transform.
