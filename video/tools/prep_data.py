#!/usr/bin/env python3
"""
Compute every number the video shows, so that nothing on screen is invented.

  video/.venv/bin/python video/tools/prep_data.py          (about 5 minutes on 4 cores)

Writes video/data/*.json:
  first_prime.json   for each odd k < 78557: the smallest n <= NMAX with k*2^n+1 prime,
                     or null if none was found up to NMAX
  covering.json      for 78557*2^n+1, the covering prime that divides it, for n = 0..35
  candidate.json     the leading and trailing digits and digit count of a real next
                     candidate beyond PrimeGrid's frontier (21181*2^47856068+1, from the sieve)
  sequences.json     the first terms of k*2^n+1 for the small examples, with primality
"""
import json, math, os, sys
from multiprocessing import Pool
import gmpy2
from gmpy2 import mpz
import mpmath

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
NMAX = 1200
KMAX = 78557
SIERPINSKI_17 = [4847, 5359, 10223, 19249, 21181, 22699, 24737, 27653, 28433, 33661,
                 44131, 46157, 54767, 55459, 65567, 67607, 69109]


def first_prime(k):
    if k in SIERPINSKI_17:            # their primes (where known) are millions of bits long
        return k, None
    x = mpz(k)
    for n in range(1, NMAX + 1):
        x <<= 1
        if gmpy2.is_prime(x + 1, 10):
            return k, n
    return k, None


def main():
    os.makedirs(OUT, exist_ok=True)
    ks = list(range(1, KMAX, 2))
    with Pool() as pool:
        res = dict(pool.map(first_prime, ks, chunksize=256))
    found = {k: n for k, n in res.items() if n is not None}
    missing = [k for k, n in res.items() if n is None]
    json.dump({"nmax": NMAX, "first_n": {str(k): res[k] for k in ks}}, open(os.path.join(OUT, "first_prime.json"), "w"))
    print(f"{len(ks)} odd k; prime found for {len(found)} with n <= {NMAX}; "
          f"{len(missing)} without (incl. the 17 SoB k): {missing[:40]}{' ...' if len(missing) > 40 else ''}")

    # covering set of 78557: every n is covered by one of 3, 5, 7, 13, 19, 37, 73
    cover = [3, 5, 7, 13, 19, 37, 73]
    slots = []
    for n in range(36):
        v = 78557 * pow(2, n) + 1
        ps = [p for p in cover if v % p == 0]
        assert ps, f"n={n} not covered"
        slots.append(ps[0])
    # the period: 2 has order 2,4,3,12,18,36,9 mod these primes -> lcm 36
    json.dump({"k": 78557, "primes": cover, "period": 36, "slot_prime": slots,
               "first_terms": [[n, str(78557 * 2**n + 1), [p for p in cover if (78557 * 2**n + 1) % p == 0][0]] for n in range(1, 13)]},
              open(os.path.join(OUT, "covering.json"), "w"))
    print("covering slots:", slots)

    # a real candidate beyond the frontier
    k, n = 21181, 47856068
    digits = math.floor(n * math.log10(2) + math.log10(k)) + 1
    mpmath.mp.dps = 2600
    lg = mpmath.log10(k) + n * mpmath.log10(2)
    frac = lg - mpmath.floor(lg)
    lead = mpmath.nstr(mpmath.power(10, frac), 2400, strip_zeros=False).replace(".", "")[:2200]
    D = 2200
    tail = str((k * pow(2, n, 10**D) + 1) % 10**D).zfill(D)
    json.dump({"k": k, "n": n, "digits": digits, "leading": lead, "trailing": tail},
              open(os.path.join(OUT, "candidate.json"), "w"))
    print(f"candidate {k}*2^{n}+1 has {digits:,} digits; starts {lead[:20]}..., ends ...{tail[-20:]}")

    seqs = {}
    for k in (3, 5, 7, 78557):
        terms = []
        for n in range(1, 13):
            v = k * 2**n + 1
            terms.append([n, str(v), bool(gmpy2.is_prime(v))])
        seqs[str(k)] = terms
    json.dump(seqs, open(os.path.join(OUT, "sequences.json"), "w"))
    print("k=3 terms:", [(t[1], t[2]) for t in seqs["3"][:8]])


if __name__ == "__main__":
    main()
