// Conversions between GMP integers and the engine's balanced variable-width digits.
#pragma once
#include "layout.h"
#include <gmpxx.h>

// GMP's *_ui / *_si functions and gmpxx's integer constructors take a C `long`, which is 32
// bits on Windows. Every 64-bit value crosses into or out of GMP through these instead.
inline mpz_class mpzFromU64(u64 v) {
  mpz_class r;
  mpz_import(r.get_mpz_t(), 1, -1, sizeof v, 0, 0, &v);
  return r;
}
inline mpz_class mpzFromI64(i64 v) {
  mpz_class r = mpzFromU64(v < 0 ? 0 - (u64)v : (u64)v);
  if (v < 0) r = -r;
  return r;
}
inline u64 low64(const mpz_class& x) {           // x mod 2^64 (non-negative for any x)
  mpz_class m;
  mpz_fdiv_r_2exp(m.get_mpz_t(), x.get_mpz_t(), 64);
  u64 v = 0; size_t count = 0;
  mpz_export(&v, &count, -1, sizeof v, 0, 0, m.get_mpz_t());
  return count ? v : 0;
}

inline mpz_class modulus(const Layout& L) { mpz_class P = L.k; P <<= L.n; return P + 1; }

// digits -> canonical residue in [0, P)
inline mpz_class toMpz(const Layout& L, const std::vector<i32>& d) {
  const size_t N = L.N;
  size_t nl = L.s[N - 1] / 64 + 2;
  std::vector<u64> limb(nl, 0);
  i64 c = 0;
  for (size_t j = 0; j + 1 < N; j++) {
    int w = L.width[j];
    i64 v = (i64)d[j] + c;
    u64 lo = (u64)v & ((1ULL << w) - 1);
    c = (v - (i64)lo) >> w;
    size_t q = L.s[j] / 64; unsigned off = L.s[j] % 64;
    limb[q] |= lo << off;
    if (off + w > 64) limb[q + 1] |= lo >> (64 - off);
  }
  mpz_class low, top = mpzFromI64((i64)d[N - 1] + c), P = modulus(L);
  mpz_import(low.get_mpz_t(), nl, -1, 8, 0, 0, limb.data());
  top <<= L.s[N - 1];
  low += top;
  mpz_class r; mpz_mod(r.get_mpz_t(), low.get_mpz_t(), P.get_mpz_t());
  return r;
}

// residue in [0, P) -> balanced digits
inline std::vector<i32> fromMpz(const Layout& L, const mpz_class& x) {
  const size_t N = L.N;
  std::vector<i32> d(N);
  // as 64-bit words whatever GMP's limb size is
  std::vector<u64> words((mpz_sizeinbase(x.get_mpz_t(), 2) + 63) / 64 + 1, 0);
  size_t nl = 0;
  mpz_export(words.data(), &nl, -1, sizeof(u64), 0, 0, x.get_mpz_t());
  const u64* lp = words.data();
  auto bits = [&](u64 pos, int w) -> u64 {
    size_t q = pos / 64; unsigned off = pos % 64;
    u64 v = q < nl ? lp[q] >> off : 0;
    if (off + w > 64 && q + 1 < nl) v |= lp[q + 1] << (64 - off);
    return w == 64 ? v : v & ((1ULL << w) - 1);
  };
  i64 c = 0;
  for (size_t j = 0; j + 2 < N; j++) {
    int w = L.width[j];
    i64 v = (i64)bits(L.s[j], w) + c; c = 0;
    if (v >= (i64)(1ULL << (w - 1))) { v -= (i64)(1ULL << w); c = 1; }
    d[j] = (i32)v;
  }
  // top two words jointly, balanced modulo topBase
  mpz_class t = x >> L.s[N - 2];
  i64 V = (i64)low64(t) + c;                     // <= k*2^topShift + 1
  if (V > (i64)(L.topBase / 2)) { V -= (i64)L.topBase; d[0] -= 1; }   // borrowed k*2^n == -1
  int w = L.width[N - 2];
  i64 lo = (i64)((u64)V & ((1ULL << w) - 1));
  if (lo >= (i64)(1ULL << (w - 1))) lo -= (i64)(1ULL << w);
  d[N - 2] = (i32)lo; d[N - 1] = (i32)((V - lo) >> w);
  return d;
}
