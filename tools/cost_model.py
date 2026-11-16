#!/usr/bin/env python3
"""
What does it cost to find the next Colbert prime?

Reads a candidate file produced by ./sieve (survivors of trial division to p <= PSIEVE)
and turns it into expected primes, number of tests, GPU-hours and dollars for a given
speed and price. Every input that is an assumption rather than a measurement is a flag.

  tools/cost_model.py runs/candidates.txt --psieve 1e9 --pdeep 1.4e17 \
        --ms-per-iter 0.15 0.5 1.5 --usd-per-hour 0.25

Heuristic used: a number N with no prime factor below p is prime with probability
e^gamma * ln(p) / ln(N)  (Mertens). The expected number of primes in a range does not
depend on the sieve depth; the number of tests needed to find them does.
"""
import argparse, math, collections

EG = 1.7810724179901979852

ap = argparse.ArgumentParser()
ap.add_argument("candidates")
ap.add_argument("--psieve", type=float, required=True, help="depth the candidate file was sieved to")
ap.add_argument("--pdeep", type=float, default=1.4e17, help="depth of the sieve a real search would start from (ASSUMPTION, ~2^57)")
ap.add_argument("--ms-per-iter", type=float, nargs="+", default=[0.15, 0.5, 1.5], help="GPU squaring time at this size (UNMEASURED scenarios)")
ap.add_argument("--usd-per-hour", type=float, default=0.25, help="price of one GPU-hour (ASSUMPTION)")
ap.add_argument("--bins", type=float, default=2e6, help="width of the n ranges reported")
a = ap.parse_args()

rows = [tuple(map(int, l.split())) for l in open(a.candidates) if l[0] != "#"]
ratio = math.log(a.psieve) / math.log(a.pdeep)        # fraction of survivors that also survive the deep sieve
perk = collections.Counter(k for k, n in rows)
print(f"{len(rows)} survivors at p <= {a.psieve:.3g}; about {len(rows) * ratio:,.0f} would survive p <= {a.pdeep:.3g}")
print("per k (shallow sieve):", ", ".join(f"{k}: {c}" for k, c in sorted(perk.items())))
print()
hdr = f"{'n range':>18} {'tests':>9} {'E[primes]':>10} {'P(>=1)':>8} {'iterations':>11}" + "".join(f" {'GPU-h @' + format(m, 'g') + 'ms':>15}" for m in a.ms_per_iter)
print(hdr)
lo = min(n for k, n in rows); hi = max(n for k, n in rows)
cum_tests = cum_e = cum_iter = 0.0
b = lo
while b <= hi:
    sel = [(k, n) for k, n in rows if b <= n < b + a.bins]
    tests = len(sel) * ratio
    e = sum(EG * math.log(a.psieve) / (n * math.log(2) + math.log(k)) for k, n in sel)
    iters = sum(n for k, n in sel) * ratio
    cum_tests += tests; cum_e += e; cum_iter += iters
    print(f"{b/1e6:7.1f}M-{(b + a.bins)/1e6:6.1f}M {tests:9,.0f} {e:10.4f} {1 - math.exp(-e):8.2%} {iters:11.3e}" +
          "".join(f" {iters * m / 3.6e6:15,.0f}" for m in a.ms_per_iter))
    b += a.bins
print(f"{'whole range':>18} {cum_tests:9,.0f} {cum_e:10.4f} {1 - math.exp(-cum_e):8.2%} {cum_iter:11.3e}" +
      "".join(f" {cum_iter * m / 3.6e6:15,.0f}" for m in a.ms_per_iter))
print()
print(f"tests per expected prime here: {cum_tests / cum_e:,.0f}")
for m in a.ms_per_iter:
    gh = cum_iter * m / 3.6e6
    print(f"  at {m:g} ms/iter: {gh / cum_tests:5.1f} GPU-hours per test, {gh / cum_e:12,.0f} GPU-hours per expected prime, "
          f"${gh / cum_e * a.usd_per_hour:12,.0f} at ${a.usd_per_hour:g}/GPU-hour")
print()
print("chance of at least one prime for a given spend (tests taken in order of n):")
for m in a.ms_per_iter:
    out = []
    for usd in (100, 1000, 10000, 100000):
        budget_iters = usd / a.usd_per_hour * 3.6e6 / m
        e = 0.0; used = 0.0
        for k, n in sorted(rows, key=lambda r: r[1]):
            if used + n * ratio > budget_iters: break
            used += n * ratio
            e += EG * math.log(a.psieve) / (n * math.log(2) + math.log(k))
        out.append(f"${usd:,}: {1 - math.exp(-e):.3%}")
    print(f"  at {m:g} ms/iter  " + "   ".join(out))
