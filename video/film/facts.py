"""
Every figure the video states, in one place.

PROJECTED figures are marked. They come from tools/perf_model.py and docs/PERFORMANCE.md,
not from measurements on a GPU. Replace them with measured values (see
docs/GPU_BENCHMARKING.md) before publishing, then re-render.
"""

FRONTIER_N = 47_856_007            # PrimeGrid SoB leading edge, 17 Nov 2026 (subproject status page)
CANDIDATE = (21181, 47_856_068)    # a real survivor of the sieve just beyond the frontier
REMAINING_K = [21181, 22699, 24737, 55459, 67607]

# (k, n, year) of the twelve primes found by Seventeen or Bust and PrimeGrid
SOB_PRIMES = [
    (46157, 698207, 2002), (65567, 1013803, 2002), (44131, 995972, 2002), (69109, 1157446, 2002),
    (54767, 1337287, 2002), (5359, 5054502, 2003), (28433, 7830457, 2004), (27653, 9167433, 2005),
    (4847, 3321063, 2005), (19249, 13018586, 2007), (33661, 7031232, 2007), (10223, 31172165, 2016),
]
SEVENTEEN = sorted([k for k, _, _ in SOB_PRIMES] + REMAINING_K)
TWELFTH_DIGITS = 9_383_761
TWELFTH_DAYS = "8 days, 22 hours"   # discoverer's Core i7-4770, LLR (PrimeGrid announcement)

PAGES = 3000                        # 14.4M digits at ~4,800 digits per page (80 x 60)

# transform data per squaring at the frontier, MiB (tools/perf_model.py)
DATA_MIB = {"Zero-padded (proth20)": 64.0, "k in decimal weights (LLR2, llrCUDA)": 33.8, "colbert": 24.0}

# ---- PROJECTED, RTX 4090 --------------------------------------------------------------
MS_PER_SQUARING = {"proth20": 0.55, "colbert": 0.22}          # PROJECTED
HOURS_PER_TEST = {name: ms * FRONTIER_N / 3.6e6 for name, ms in MS_PER_SQUARING.items()}
SPEEDUP = MS_PER_SQUARING["proth20"] / MS_PER_SQUARING["colbert"]
TESTS_PER_KWH = {"CPU · LLR2": 0.30, "GPU · proth20": 0.38, "GPU · colbert": 0.85}   # PROJECTED
# ----------------------------------------------------------------------------------------

EXPECTED_PRIMES = 0.21              # n in [47.86M, 57.5M], all five k (docs/RESULTS.md)
TESTS_PER_PRIME = 518_000
REPO_URL = "github.com/CadeRyan/colbert"
