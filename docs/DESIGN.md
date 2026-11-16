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
| zero-padded transform, then reduce | proth20 (GPU); gwnum/LLR for large `k` | transform of twice the length |
| IBDWT with `k` folded into floating-point weights | gwnum/LLR for small `k` | the convolution output is `k` times larger, so each double holds `log2(k)/2` fewer bits: about 10 bits per word instead of 18 for the `k` in question |

`colbert` removes that factor by doing the weighted transform **exactly**, in a field where
the weights exist for every `k`, and where 92 bits of headroom make the extra `log2 k ≈ 16`
bits a small fraction of the budget rather than most of it.

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
`P` prime iff `x_{n−1} ≡ 2^n`.)

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

The second point is the heart of it. In the real numbers `−k·2^n` has no real `N`-th root at
all; in a prime field `GF(p)` with `p ≡ 1 mod N` it has one only for a fraction `1/N` of
primes. In `GF(q²)` over a Mersenne prime it always has one. (That 2 has such roots is what
PRPLL's Mersenne NTT uses; the observation here is that nothing is special about 2.)

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
are implemented and each prime picks its own.

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

| what | bits per word at n ≈ 46M, k ≈ 2^16 | transform size |
|---|---|---|
| this work, 92-bit exact | up to 27.4 (21.9 at the power-of-two size used today) | 2^21 words |
| proth20 (zero-padded, two 31-bit primes) | 19 | 2^23 words |
| double-precision IBDWT, `k` in the weights | about 10 | about 4.5M words |

proth20's figure comes from its own sizing code (`transformSize`/`digitBit` in `gpmp.h`);
the double-precision figure is the same bound applied to a 53-bit mantissa and is an
estimate, not a measurement of LLR.

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

Not new: the IBDWT (Crandall–Fagin); transforms over `GF(q²)` for Mersenne `q` (long known,
and what PRPLL's NTT modes use for Mersenne numbers); the Proth test; Gerbicz–Li checking;
the conjugate-pair real transform; block-parallel carries.

New as far as I can determine: using the surjectivity of the norm map on `GF(q²)` to get
IBDWT weights for a general multiplier `k`, giving a zero-padding-free exact transform for
`k·2^n + 1`; the `∘`-arithmetic formulation that makes the `1/k` wrap integral; the
per-prime choice between the fold and real structures by `(k/q)`; and a rigorous overflow
bound for it. I looked at the two closest programs directly: proth20 zero-pads, and PRPLL
(checked at its head commit of 16 November 2026) rejects everything that is not a Mersenne
number. I could not search the mersenneforum or PrimeGrid forums from this environment, so
"new" means "not in the code I could read", not "certainly never proposed".

## 10. Known limits and next steps

* Power-of-two sizes only. At `n ≈ 46M` that wastes about 20% (21.9 of a possible 27.4 bits
  per word). Radices 3, 7 and 11 divide both `M31 − 1` and `M61 − 1` and would close the gap.
* The OpenCL kernels are written for correctness: radix-16 passes with one table read per
  butterfly, nothing fused. They have only ever run on a CPU OpenCL runtime. Real GPU speed
  is unmeasured.
* No P−1 stage and no Pietrzak proof generation yet.
