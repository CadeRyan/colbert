#!/usr/bin/env python3
"""
First-principles cost model for ONE modular squaring of k*2^n+1 at Sierpinski-problem
sizes, for four approaches. This is a model, not a measurement: it counts bytes that
must cross GPU memory and the multiplications that must be executed, and turns those into
lower bounds on time for a given device. Real programs are slower than both bounds.

    tools/perf_model.py [--k 21181] [--n 47856007] [--passes 3]

Sources for each approach's parameters are in docs/PERFORMANCE.md.
"""
import argparse, math

ap = argparse.ArgumentParser()
ap.add_argument("--k", type=int, default=21181)
ap.add_argument("--n", type=int, default=47_856_007)       # PrimeGrid SoB leading edge, 17 Nov 2026
ap.add_argument("--passes", type=float, default=3.0,
                help="round trips through device memory per squaring for a well-tuned code (PRPLL-class codes do about 3)")
a = ap.parse_args()
k, n = a.k, a.n
lk = math.log2(k)

def pow2_at_least(x):
    p = 1
    while p < x: p *= 2
    return p

rows = []

# --- colbert: exact weighted transform over GF(M61^2) x GF(M31^2), no padding
# N words; constraint (Layout): 2*b + log2(N) + log2(k) < ~91.9 bits (proof in DESIGN.md).
def colbert(power_of_two):
    best = None
    sizes = [2**e for e in range(18, 26)] if power_of_two else \
            [m * 2**e for e in range(14, 26) for m in (1, 3, 7, 9, 11, 21, 33)]  # odd factors must divide gcd(M31-1, M61-1)
    for N in sorted(sizes):
        b = (n + lk) / N
        if 2 * b + math.log2(N) + lk + 0.3 < 91.0 and b <= 31:
            best = N; break
    N = best; M = N // 2
    bytes_point = 16 + 8                                  # one GF(M61^2) + one GF(M31^2) element
    data = M * bytes_point
    lg = math.log2(M)
    bfly = 2 * (M / 2) * lg                               # forward + inverse butterflies, per prime
    # cost in 32-bit integer multiply instructions: GF(M61^2) complex mul = 3 (Karatsuba) 64x64->128
    # products at ~8 IMADs each; GF(M31^2) = 3 32x32->64 products at 2 each
    imul = bfly * (3 * 8 + 3 * 2) + N * 10                # + weights, pointwise, CRT/carry
    return dict(name="colbert, power-of-two sizes" if power_of_two else "colbert, mixed-radix sizes (future)",
                words=N, bits=(n + lk) / N, data=data, imul=imul, fp64=0)

rows.append(colbert(True))
rows.append(colbert(False))

# --- proth20 (Gallot): zero-padded RNS NTT with two 31-bit primes (gpmp.h transformSize/digitBit)
P1P2 = 2130706433 * 2013265921
def proth20():
    for digit_bit in range(21, 1, -1):
        e = n // digit_bit; s = n % digit_bit
        x_hi = e + (2 * (int(lk) + 1 + s) + digit_bit - 1) // digit_bit
        size = 2048
        while size < 2 * x_hi: size *= 2
        if (size / 2) * (2**digit_bit - 1) ** 2 < P1P2 / 2:
            break
    data = size * 8                                       # two uint32 residues per point
    bfly = 2 * (size / 2) * math.log2(size)               # forward + inverse, per prime
    imul = 2 * bfly * 3 + size * 6                        # Montgomery modmul ~3 IMAD; 2 primes
    return dict(name="proth20 (GPU, zero-padded NTT)", words=size, bits=n / size, data=data, imul=imul, fp64=0)
rows.append(proth20())

# --- gwnum / LLR2 / PRST (CPU) and llrCUDA (GPU): floating-point IBDWT with Woltman's 1/k method.
# Observed: PrimeGrid SoB at n ~ 31M ran FFT lengths 2560K-2880K (forum thread 8682, 2019),
# i.e. ~10.8 bits per double for these k. Scale that density to n.
def fp64_ibdwt(name):
    bits = 10.8
    N = (n + lk) / bits
    data = N * 8
    flops = 2 * 5 * (N / 2) * math.log2(N / 2) + 20 * N  # real-input FFT pair, ~5 N log N flops per complex FFT
    return dict(name=name, words=N, bits=bits, data=data, imul=0, fp64=flops)
rows.append(fp64_ibdwt("gwnum-style FP64 IBDWT (LLR2/PRST on CPU, llrCUDA on GPU)"))

print(f"k = {k}, n = {n:,}  ({(n * math.log10(2)):,.0f} digits); {a.passes:g} memory round trips per squaring assumed\n")
print(f"{'approach':58} {'words':>10} {'bits/word':>9} {'data MiB':>9} {'int mul G':>9} {'fp64 GF':>8}")
for r in rows:
    print(f"{r['name']:58} {r['words']/1e6:9.2f}M {r['bits']:9.2f} {r['data']/2**20:9.1f} {r['imul']/1e9:9.2f} {r['fp64']/1e9:8.2f}")

devices = [  # name, memory GB/s, int32 multiply Tops/s (approx: IMAD rate), fp64 TFLOP/s (vector)
    ("RTX 4090 (consumer)", 1008, 41, 1.3),
    ("RTX 5090 (consumer)", 1792, 52, 1.6),
    ("H100 SXM (datacenter)", 3350, 33, 34),
]
print("\nLower bound on ms per squaring = max(memory time, multiply time). Real code is slower.")
print(f"{'approach':58}" + "".join(f" {d[0]:>22}" for d in devices))
for r in rows:
    cells = []
    for _, bw, imul, fp in devices:
        tm = a.passes * 2 * r["data"] / (bw * 1e9) * 1e3
        tc = (r["imul"] / (imul * 1e12) + r["fp64"] / (fp * 1e12)) * 1e3
        cells.append(f"{max(tm, tc):8.3f} ({'mem' if tm >= tc else 'cmp'})")
    print(f"{r['name']:58}" + "".join(f" {c:>22}" for c in cells))
