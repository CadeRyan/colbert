// Candidate sieve for the remaining Sierpinski multipliers.
//
//   sieve NMIN NMAX PMAX [out.txt]        (PMAX <= 2^32)
//
// Removes every n in [NMIN, NMAX] for which k*2^n+1 has a prime factor p <= PMAX, for
// k in {21181, 22699, 24737, 55459, 67607}, and prints what is left together with the
// expected number of primes among the survivors.
//
// Method: small primes fix n to a few residue classes mod 720 for each k (these k are the
// ones that survive precisely because they are "almost covered"). For every larger p the
// condition 2^n = -1/k (mod p) becomes g^t = c with g = 2^720, one target per (k, class),
// solved for all targets at once by baby-step/giant-step over the t-range.
//
// This is a planning/worklist tool. A production search should start from a deep sieve
// (PrimeGrid sieved these sequences far beyond 2^32); survivors of a deeper sieve are a
// subset of the survivors printed here.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <omp.h>

typedef uint64_t u64; typedef uint32_t u32;
static const u32 KS[] = { 21181, 22699, 24737, 55459, 67607 };
static const int NK = 5;
static const u32 MOD = 720;

static inline u64 mulmod(u64 a, u64 b, u64 p) { return a * b % p; }          // p < 2^32
static u64 powmod(u64 a, u64 e, u64 p) { u64 r = 1; a %= p; for (; e; e >>= 1, a = mulmod(a, a, p)) if (e & 1) r = mulmod(r, a, p); return r; }
static u64 invmod(u64 a, u64 p) { return powmod(a, p - 2, p); }

struct Target { int k; u32 cls; };

int main(int argc, char** argv) {
  if (argc < 4) { fprintf(stderr, "usage: sieve NMIN NMAX PMAX [out.txt]\n"); return 2; }
  u64 n0 = strtoull(argv[1], 0, 10), n1 = strtoull(argv[2], 0, 10), pmax = (u64)strtod(argv[3], 0);
  if (pmax > 0xFFFFFFFFULL) pmax = 0xFFFFFFFFULL;
  const u64 R = n1 - n0 + 1;
  std::vector<std::vector<uint8_t>> dead(NK, std::vector<uint8_t>(R, 0));

  // --- stage 1: primes below SMALL by direct marking
  const u32 SMALL = 20000;
  std::vector<u32> base;
  { std::vector<uint8_t> c(65537, 0); for (u32 i = 2; i <= 65536; i++) if (!c[i]) { base.push_back(i); for (u64 j = (u64)i * i; j <= 65536; j += i) c[j] = 1; } }
  for (u32 p : base) {
    if (p == 2 || p >= SMALL) continue;
    u32 d = 1; for (u64 t = 2 % p; t != 1; t = t * 2 % p) d++;                 // ord_p(2)
    for (int ki = 0; ki < NK; ki++) {
      if (KS[ki] % p == 0) continue;
      u64 target = (p - invmod(KS[ki] % p, p)) % p, t = 1;                     // 2^n = -1/k
      for (u32 e = 0; e < d; e++, t = t * 2 % p)
        if (t == target) { for (u64 n = n0 + ((e + d - n0 % d) % d); n <= n1; n += d) dead[ki][n - n0] = 1; break; }
    }
  }
  // surviving residue classes mod 720
  std::vector<Target> targets;
  for (int ki = 0; ki < NK; ki++) {
    std::vector<u64> cnt(MOD, 0);
    for (u64 i = 0; i < R; i++) if (!dead[ki][i]) cnt[(n0 + i) % MOD]++;
    int nc = 0; for (u32 c = 0; c < MOD; c++) if (cnt[c]) { targets.push_back({ ki, c }); nc++; }
    fprintf(stderr, "k=%u: %d of 720 residue classes of n survive the primes below %u\n", KS[ki], nc, SMALL);
  }
  const u64 t0 = n0 / MOD, T = n1 / MOD - t0 + 1;                              // n = cls + 720 t
  const u32 m = (u32)std::max(16.0, std::ceil(std::sqrt((double)targets.size() * (double)T)));
  const u32 giant = (u32)((T + m - 1) / m);
  u32 hbits = 4; while ((1u << hbits) < 4 * m) hbits++;
  fprintf(stderr, "%zu (k, class) targets, t-range %llu, baby steps %u, giant steps %u per target\n", targets.size(), (unsigned long long)T, m, giant);

  // --- stage 2: primes in [SMALL, PMAX] by baby-step/giant-step, segmented
  const u64 SEG = 1 << 22;
  u64 nseg = (pmax - SMALL) / SEG + 1, nprimes = 0, nfactors = 0;
  double tstart = omp_get_wtime();
  #pragma omp parallel reduction(+ : nprimes, nfactors)
  {
    std::vector<uint8_t> comp(SEG);
    std::vector<u32> hkey((size_t)1 << hbits), hval((size_t)1 << hbits), hgen((size_t)1 << hbits, 0);
    u32 gen = 0; const u32 hmask = (1u << hbits) - 1;
    std::vector<std::pair<int, u64>> hits;
    #pragma omp for schedule(dynamic, 4)
    for (u64 sg = 0; sg < nseg; sg++) {
      u64 lo = SMALL + sg * SEG, hi = std::min(lo + SEG, pmax + 1);
      std::fill(comp.begin(), comp.end(), 0);
      for (u32 q : base) { if ((u64)q * q >= hi) break; for (u64 j = std::max((u64)q * q, (lo + q - 1) / q * q); j < hi; j += q) comp[j - lo] = 1; }
      for (u64 p = lo | 1; p < hi; p += 2) {
        if (comp[p - lo]) continue;
        nprimes++;
        u64 g = powmod(2, MOD, p), gi = invmod(g, p);
        // baby steps g^j, j < m
        if (++gen == 0) { std::fill(hgen.begin(), hgen.end(), 0); gen = 1; }
        u64 b = 1; u32 ord = 0;
        for (u32 j = 0; j < m; j++) {
          u32 h = (u32)(b * 2654435761u) >> (32 - hbits);
          while (hgen[h] == gen && hkey[h] != (u32)b) h = (h + 1) & hmask;
          if (hgen[h] != gen) { hgen[h] = gen; hkey[h] = (u32)b; hval[h] = j; }
          b = mulmod(b, g, p);
          if (b == 1) { ord = j + 1; break; }
        }
        u64 gim = powmod(gi, m, p), git0 = powmod(gi, t0 % (p - 1), p);
        u64 inv2cls[MOD + 1]; bool have = false;
        for (const Target& tg : targets) {
          if (KS[tg.k] % p == 0) continue;
          if (!have) { u64 i2 = invmod(2, p); inv2cls[0] = 1; for (u32 c = 1; c <= MOD; c++) inv2cls[c] = mulmod(inv2cls[c - 1], i2, p); have = true; }
          // g^(t0 + u) = -1/k * 2^-cls   =>   g^u = c
          u64 c = mulmod(mulmod(p - invmod(KS[tg.k] % p, p), inv2cls[tg.cls], p), git0, p);
          auto lookup = [&](u64 v, u32& j) -> bool {
            u32 h = (u32)(v * 2654435761u) >> (32 - hbits);
            while (hgen[h] == gen) { if (hkey[h] == (u32)v) { j = hval[h]; return true; } h = (h + 1) & hmask; }
            return false;
          };
          u32 j;
          if (ord) {                                   // g has small order: all solutions u = j (mod ord)
            if (lookup(c, j)) for (u64 u = j; u < T; u += ord) hits.push_back({ tg.k, tg.cls + MOD * (t0 + u) });
          } else {
            for (u32 i = 0; i < giant; i++, c = mulmod(c, gim, p))
              if (lookup(c, j)) { u64 u = (u64)i * m + j; if (u < T) hits.push_back({ tg.k, tg.cls + MOD * (t0 + u) }); }
          }
        }
      }
      if (hits.size() > 4096) {
        #pragma omp critical
        { for (auto& h : hits) if (h.second >= n0 && h.second <= n1 && !dead[h.first][h.second - n0]) { dead[h.first][h.second - n0] = 1; nfactors++; } }
        hits.clear();
      }
    }
    #pragma omp critical
    { for (auto& h : hits) if (h.second >= n0 && h.second <= n1 && !dead[h.first][h.second - n0]) { dead[h.first][h.second - n0] = 1; nfactors++; } }
  }
  fprintf(stderr, "sieved %llu primes up to %llu in %.0f s; %llu candidates removed by primes >= %u\n", (unsigned long long)nprimes,
          (unsigned long long)pmax, omp_get_wtime() - tstart, (unsigned long long)nfactors, SMALL);

  // --- report
  FILE* out = argc > 4 ? fopen(argv[4], "w") : nullptr;
  const double EG = 1.7810724179901979852;             // e^gamma
  double expTotal = 0; u64 total = 0;
  std::vector<std::pair<u64, u32>> all;
  printf("%8s %12s %16s\n", "k", "candidates", "expected primes");
  for (int ki = 0; ki < NK; ki++) {
    u64 c = 0; double ex = 0;
    for (u64 i = 0; i < R; i++) if (!dead[ki][i]) {
      u64 n = n0 + i; c++;
      ex += EG * std::log((double)pmax) / ((double)n * std::log(2.0) + std::log((double)KS[ki]));
      all.push_back({ n, KS[ki] });
    }
    printf("%8u %12llu %16.4f\n", KS[ki], (unsigned long long)c, ex);
    total += c; expTotal += ex;
  }
  printf("%8s %12llu %16.4f   (n in [%llu, %llu], sieved to p <= %llu)\n", "all", (unsigned long long)total, expTotal,
         (unsigned long long)n0, (unsigned long long)n1, (unsigned long long)pmax);
  if (out) {
    std::sort(all.begin(), all.end());
    fprintf(out, "# k n   -- survivors of trial division to p <= %llu, ordered by n\n", (unsigned long long)pmax);
    for (auto& a : all) fprintf(out, "%u %llu\n", a.second, (unsigned long long)a.first);
    fclose(out);
  }
  return 0;
}
