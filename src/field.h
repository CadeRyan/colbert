// Arithmetic in GF(q) and GF(q^2) = GF(q)[i] for the Mersenne primes q = 2^61-1 and 2^31-1.
//
// Why these fields: q + 1 = 2^e, so GF(q^2)* contains roots of unity of every power-of-two
// order up to 2^(e+1), and every element of GF(q) is a (q+1)-th power in GF(q^2). The second
// fact is what gives an N-th root of -k*2^n for *any* k, i.e. a weighted transform for
// Proth moduli without zero padding (see docs/DESIGN.md).
#pragma once
#include <cstdint>
#include <cstddef>

typedef uint64_t u64;
typedef int64_t i64;
typedef uint32_t u32;
typedef int32_t i32;
typedef unsigned __int128 u128;
typedef __int128 i128;

struct F61 {
  typedef u64 T;
  struct C { T re, im; };
  static constexpr int E = 61;
  static constexpr u64 P = (1ULL << 61) - 1;
  static inline T add(T a, T b) { T s = a + b; return s >= P ? s - P : s; }
  static inline T sub(T a, T b) { return a >= b ? a - b : a + P - b; }
  static inline T neg(T a) { return a ? P - a : 0; }
  static inline T red(u128 t) {                       // t < 2^124
    u64 s = ((u64)t & P) + (u64)(t >> 61);            // < 2^61 + 2^63
    s = (s & P) + (s >> 61);                          // <= P + 4
    return s >= P ? s - P : s;
  }
  static inline T mul(T a, T b) { return red((u128)a * b); }
  static inline T fromInt(i32 x) { return x < 0 ? P - (u64)(-(i64)x) : (u64)x; }
  static inline C cmul(C a, C b) {
    return { red((u128)a.re * b.re + (u128)a.im * (P - b.im)),
             red((u128)a.re * b.im + (u128)a.im * b.re) };
  }
  static inline C csqr(C a) {
    return { red((u128)(a.re + a.im) * sub(a.re, a.im)), red((u128)(2 * a.re) * a.im) };
  }
  static inline T mul2exp(T a, unsigned s) {          // a * 2^s, a rotation mod 2^61-1
    s %= 61; if (!s) return a;
    return ((a << s) & P) | (a >> (61 - s));
  }
};

struct F31 {
  typedef u32 T;
  struct C { T re, im; };
  static constexpr int E = 31;
  static constexpr u32 P = (1U << 31) - 1;
  static inline T add(T a, T b) { u32 s = a + b; return s >= P ? s - P : s; }
  static inline T sub(T a, T b) { return a >= b ? a - b : a + P - b; }
  static inline T neg(T a) { return a ? P - a : 0; }
  static inline T red(u64 t) {                        // t < 2^63
    u64 s = (t & P) + (t >> 31);                      // < 2^31 + 2^32
    u32 r = (u32)((s & P) + (s >> 31));               // <= P + 2
    return r >= P ? r - P : r;
  }
  static inline T mul(T a, T b) { return red((u64)a * b); }
  static inline T fromInt(i32 x) { i64 v = x; if (v < 0) v += P; if (v < 0) v += P; return (u32)(v >= (i64)P ? v - P : v); }
  static inline C cmul(C a, C b) {
    return { red((u64)a.re * b.re + (u64)a.im * (P - b.im)),
             red((u64)a.re * b.im + (u64)a.im * b.re) };
  }
  static inline C csqr(C a) {
    return { red((u64)(a.re + a.im) * sub(a.re, a.im)), red((u64)(2 * (u64)a.re) * a.im) };
  }
  static inline T mul2exp(T a, unsigned s) {
    s %= 31; if (!s) return a;
    return ((a << s) & P) | (a >> (31 - s));
  }
};

template <class F> inline typename F::C cadd(typename F::C a, typename F::C b) { return { F::add(a.re, b.re), F::add(a.im, b.im) }; }
template <class F> inline typename F::C csub(typename F::C a, typename F::C b) { return { F::sub(a.re, b.re), F::sub(a.im, b.im) }; }
template <class F> inline typename F::C cconj(typename F::C a) { return { a.re, F::neg(a.im) }; }

template <class F> typename F::T fpow(typename F::T a, u64 n) {
  typename F::T r = 1;
  for (; n; n >>= 1, a = F::mul(a, a)) if (n & 1) r = F::mul(r, a);
  return r;
}
template <class F> typename F::T finv(typename F::T a) { return fpow<F>(a, (u64)F::P - 2); }
template <class F> typename F::C cpow(typename F::C a, u64 n) {
  typename F::C r = { 1, 0 };
  for (; n; n >>= 1, a = F::cmul(a, a)) if (n & 1) r = F::cmul(r, a);
  return r;
}
template <class F> typename F::C cinv(typename F::C a) {
  typename F::T d = finv<F>(F::add(F::mul(a.re, a.re), F::mul(a.im, a.im)));
  return { F::mul(a.re, d), F::mul(F::neg(a.im), d) };
}
template <class F> bool isQR(typename F::T c) { return fpow<F>(c, ((u64)F::P - 1) / 2) == 1; }
