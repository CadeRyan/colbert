#include "layout.h"
#include <sstream>

static const long double Q61 = 2305843009213693951.0L, Q31 = 2147483647.0L;

Layout::Layout(u32 k_, u64 n_, size_t N_, int nPrimes_) : k(k_), n(n_), N(N_), nPrimes(nPrimes_) {
  auto fail = [&](const std::string& why) {
    std::ostringstream o; o << "k=" << k << " n=" << n << " N=" << N << ": " << why;
    throw std::runtime_error(o.str());
  };
  if (k < 3 || !(k & 1)) fail("k must be odd and >= 3");
  if (N < 16 || (N & (N - 1))) fail("N must be a power of two >= 16");
  if (n >= (1ULL << 31) || N > (1ULL << 26)) fail("size out of range");
  int lg = ilog2(N);
  // slope beta' = A / (N 2^FRAC), rounded up so that N*beta' >= n + log2 k
  u128 A = ((u128)n << FRAC) + (u128)ceill(log2l((long double)k) * (long double)(1ULL << FRAC)) + 1;
  int sh = lg + FRAC;
  s.resize(N); width.resize(N);
  for (size_t j = 0; j < N; j++) s[j] = (u32)(((u128)j * A + (((u128)1) << sh) - 1) >> sh);
  if (s[N - 2] > n) fail("words too small for this k");
  topShift = (int)(n - s[N - 2]);
  if (topShift > 36) fail("top words too wide");
  topBase = (u64)k << topShift;
  long double topMax = ldexpl((long double)k, (int)((i64)n - (i64)s[N - 1]) - 1) + 2;   // largest |x_{N-1}|
  int wmax = 0, wmin = 99;
  for (size_t j = 0; j + 1 < N; j++) {
    int w = (int)(s[j + 1] - s[j]); width[j] = (uint8_t)w;
    if (w > wmax) wmax = w;
    if (w < wmin) wmin = w;
  }
  width[N - 1] = 0;
  if (wmin < 10) fail("words too narrow (carry would not settle within a block)");
  if (wmax > 31 || topMax >= 2147483647.0L) fail("words too wide for 32-bit digits");
  bitsPerWord = (double)((long double)A / (long double)(1ULL << FRAC) / (long double)N);

  // Rigorous bound. With f_j = s_j - j beta' in [0,1) and X_j the largest |digit|,
  //   |d_m| <= k' * sum_i (X_i 2^{f_i}) (X_{m-i} 2^{f_{m-i}}) <= k' * sum_i (X_i 2^{f_i})^2
  // (Cauchy-Schwarz), k' = 2^{N beta' - n}. X includes the +1 left by the carry's last word.
  long double beta = (long double)A / (long double)(1ULL << FRAC) / (long double)N, S = 0;
  for (size_t j = 0; j < N; j++) {
    long double f = (long double)s[j] - (long double)j * beta;
    long double X = (j + 1 < N) ? ldexpl(1.0L, width[j] - 1) + 1 : topMax;
    long double v = X * powl(2.0L, f);
    S += v * v;
  }
  long double kp = powl(2.0L, (long double)A / (long double)(1ULL << FRAC) - (long double)n);
  long double bound = kp * S * 1.000001L;
  long double Q = nPrimes == 2 ? Q61 * Q31 : Q61;
  boundBits = (double)log2l(bound); modulusBits = (double)log2l(Q);
  if (bound >= Q / 2) fail("convolution could overflow the CRT modulus (N too small)");
}

size_t Layout::chooseN(u32 k, u64 n, int nPrimes) {
  for (size_t N = 16; N <= (1ULL << 26); N *= 2) {
    try { Layout L(k, n, N, nPrimes); return N; } catch (const std::runtime_error&) {}
  }
  throw std::runtime_error("no transform size fits this (k, n)");
}

// ------------------------------------------------------------------ tables

// modular inverse of a mod m (m odd), 64-bit
static u64 invmod(u64 a, u64 m) {
  i128 t = 0, nt = 1, r = m, nr = a % m;
  while (nr) { i128 q = r / nr; i128 x = t - q * nt; t = nt; nt = x; x = r - q * nr; r = nr; nr = x; }
  if (t < 0) t += m;
  return (u64)t;
}

template <class F> Tables<F>::Tables(const Layout& L) {
  const size_t N = L.N; M = N / 2;
  const int E = F::E; const u64 Pq = F::P;
  auto p2 = [&](u64 sft) { return F::mul2exp(1, (unsigned)(sft % E)); };
  auto ip2 = [&](u64 sft) { return F::mul2exp(1, (unsigned)((E - sft % E) % E)); };

  // element of order 2^(E+1): g^((q-1)/2) for a suitable g
  C h = { 0, 0 };
  for (u64 g = 2;; g++) {
    h = cpow<F>(C{ (T)g, 1 }, (Pq - 1) / 2);
    C t = h;
    for (int i = 0; i < E; i++) t = F::csqr(t);
    if (!(t.re == 1 && t.im == 0)) break;
  }
  C wM = cpow<F>(h, (1ULL << (E + 1)) / M);         // order M, norm 1 => inverse is the conjugate
  std::vector<C> pw(M / 2 ? M / 2 : 1);
  { C t = { 1, 0 }; for (size_t j = 0; j < M / 2; j++) { pw[j] = t; t = F::cmul(t, wM); } }
  w.assign(M, C{ 0, 0 });
  for (size_t hh = 1; hh < M; hh *= 2)
    for (size_t j = 0; j < hh; j++) w[hh + j] = pw[j * (M / (2 * hh))];

  T kq = (T)(L.k % Pq);
  T two_n = p2(L.n);
  T c = F::neg(F::mul(kq, two_n));                  // c = -k 2^n
  fold = !isQR<F>(c);
  if (fold) {
    // theta^N = c via the norm map: c = a^2 + b^2, theta = (a + bi)^((q+1)/N)
    T aa = 1, bb = 0;
    for (;; aa++) {
      T t = F::sub(c, F::mul(aa, aa));
      if (t == 0) { bb = 0; break; }
      if (isQR<F>(t)) { bb = fpow<F>(t, (Pq + 1) / 4); break; }
    }
    C th = cpow<F>(C{ aa, bb }, (1ULL << E) / N), thi = cinv<F>(th);
    C gam = cpow<F>(thi, M);                         // gamma^2 = 1/c, purely imaginary
    if (gam.re != 0) throw std::runtime_error("internal: gamma not imaginary");
    T g = gam.im, gi = finv<F>(g);
    T sc = F::mul(kq, finv<F>((T)(M % Pq)));
    W1.resize(M); W2.resize(M); U.resize(M); V.resize(M);
    C t = { 1, 0 }, ti = { 1, 0 };
    for (size_t j = 0; j < M; j++) {
      T e1 = p2(L.s[j]), e2 = F::mul(g, p2(L.s[j + M]));
      W1[j] = { F::mul(t.re, e1), F::mul(t.im, e1) };
      W2[j] = { F::neg(F::mul(t.im, e2)), F::mul(t.re, e2) };          // t * (i e2)
      T u = F::mul(sc, ip2(L.s[j])), v = F::mul(F::mul(sc, gi), ip2(L.s[j + M]));
      U[j] = { F::mul(ti.re, u), F::mul(ti.im, u) };
      V[j] = { F::mul(ti.re, v), F::mul(ti.im, v) };
      t = F::cmul(t, thi); ti = F::cmul(ti, th);
    }
  } else {
    // real N-th root of 1/c: the residues form a group of odd order (q-1)/2
    u64 m = (Pq - 1) / 2;
    T rho = fpow<F>(finv<F>(c), invmod(N % m, m)), rhoi = finv<F>(rho);
    T sc = F::mul(kq, finv<F>((T)((4 * M) % Pq)));
    a.resize(N); ai.resize(N);
    T t = 1, ti = sc;
    for (size_t j = 0; j < N; j++) {
      a[j] = F::mul(t, p2(L.s[j]));
      ai[j] = F::mul(ti, ip2(L.s[j]));
      t = F::mul(t, rho); ti = F::mul(ti, rhoi);
    }
    // pair i <-> positions p (and its mirror) in bit-reversed order; twiddle omega_M^{brev(p)}
    int mb = ilog2(M);
    tw.assign(M / 2 ? M / 2 : 1, C{ 1, 0 });
    for (size_t i = 1; i < M / 2; i++) {
      int hb = ilog2(i) + 1;                         // block [2^hb, 2^(hb+1))
      size_t p = ((size_t)1 << hb) + (i - ((size_t)1 << (hb - 1)));
      size_t kk = brev(p, mb);
      tw[i] = kk < M / 2 ? pw[kk] : C{ F::neg(pw[kk - M / 2].re), F::neg(pw[kk - M / 2].im) };
    }
  }
}

template struct Tables<F61>;
template struct Tables<F31>;
