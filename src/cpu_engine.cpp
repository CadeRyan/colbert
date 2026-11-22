// Reference CPU backend (OpenMP). Also the oracle the OpenCL backend is tested against:
// both produce bit-identical digit vectors.
#include "engine.h"
#include <cstring>
#include <omp.h>

namespace {

const size_t CARRY_BLOCK = 8;       // words per carry block; must match the OpenCL kernels

template <class F> struct Xform {
  typedef typename F::T T; typedef typename F::C C;
  const Layout& L; Tables<F> tab; size_t M; int mb;
  std::vector<C> z, y;

  explicit Xform(const Layout& L_) : L(L_), tab(L_), M(L_.N / 2), mb(ilog2(L_.N / 2)), z(M), y(M) {}

  void weight(const i32* x, C* o) const {
    if (tab.fold) {
      #pragma omp parallel for schedule(static)
      for (size_t j = 0; j < M; j++) {
        T u = F::fromInt(x[j]), v = F::fromInt(x[j + M]);
        C a = tab.W1[j], b = tab.W2[j];
        o[j] = { F::add(F::mul(a.re, u), F::mul(b.re, v)), F::add(F::mul(a.im, u), F::mul(b.im, v)) };
      }
    } else {
      #pragma omp parallel for schedule(static)
      for (size_t j = 0; j < M; j++)
        o[j] = { F::mul(tab.a[2 * j], F::fromInt(x[2 * j])), F::mul(tab.a[2 * j + 1], F::fromInt(x[2 * j + 1])) };
    }
  }

  static inline void bfDif(C* p, C* q, const C* w, size_t h) {
    for (size_t j = 0; j < h; j++) {
      C a = p[j], b = q[j];
      p[j] = cadd<F>(a, b); q[j] = F::cmul(csub<F>(a, b), w[j]);
    }
  }
  static inline void bfDit(C* p, C* q, const C* w, size_t h) {
    for (size_t j = 0; j < h; j++) {
      C a = p[j], b = F::cmul(q[j], cconj<F>(w[j]));
      p[j] = cadd<F>(a, b); q[j] = csub<F>(a, b);
    }
  }
  static const size_t CB = 1 << 11;  // elements processed depth-first (fits L1/L2)

  void dif(C* o) const {             // natural order in, bit-reversed out
    const C* w = tab.w.data();
    size_t h = M / 2;
    for (; h >= CB; h /= 2) {
      size_t nb = M / (2 * h);
      if (nb >= (size_t)omp_get_max_threads()) {
        #pragma omp parallel for schedule(static)
        for (size_t b = 0; b < nb; b++) bfDif(o + 2 * h * b, o + 2 * h * b + h, w + h, h);
      } else {
        for (size_t b = 0; b < nb; b++) {
          const size_t ch = 1024;
          #pragma omp parallel for schedule(static)
          for (size_t j0 = 0; j0 < h; j0 += ch) bfDif(o + 2 * h * b + j0, o + 2 * h * b + h + j0, w + h + j0, ch < h - j0 ? ch : h - j0);
        }
      }
    }
    if (h == 0) return;
    size_t Lb = 2 * h;
    #pragma omp parallel for schedule(static)
    for (size_t b = 0; b < M; b += Lb)
      for (size_t hh = h; hh >= 1; hh /= 2)
        for (size_t b2 = b; b2 < b + Lb; b2 += 2 * hh) bfDif(o + b2, o + b2 + hh, w + hh, hh);
  }
  void dit(C* o) const {             // bit-reversed in, natural out, un-normalised
    const C* w = tab.w.data();
    size_t top = M / 2 < CB ? M / 2 : CB / 2;       // largest h done depth-first
    if (top >= 1) {
      size_t Lb = 2 * top;
      #pragma omp parallel for schedule(static)
      for (size_t b = 0; b < M; b += Lb)
        for (size_t hh = 1; hh <= top; hh *= 2)
          for (size_t b2 = b; b2 < b + Lb; b2 += 2 * hh) bfDit(o + b2, o + b2 + hh, w + hh, hh);
    }
    for (size_t h = top * 2; h <= M / 2 && h >= 1; h *= 2) {
      size_t nb = M / (2 * h);
      if (nb >= (size_t)omp_get_max_threads()) {
        #pragma omp parallel for schedule(static)
        for (size_t b = 0; b < nb; b++) bfDit(o + 2 * h * b, o + 2 * h * b + h, w + h, h);
      } else {
        for (size_t b = 0; b < nb; b++) {
          const size_t ch = 1024;
          #pragma omp parallel for schedule(static)
          for (size_t j0 = 0; j0 < h; j0 += ch) bfDit(o + 2 * h * b + j0, o + 2 * h * b + h + j0, w + h + j0, ch < h - j0 ? ch : h - j0);
        }
      }
    }
  }

  // pointwise product in bit-reversed order: o <- o * q   (q may alias o for squaring)
  void pointwise(C* o, const C* q) const {
    if (tab.fold) {
      #pragma omp parallel for schedule(static)
      for (size_t j = 0; j < M; j++) o[j] = F::cmul(o[j], q[j]);
      return;
    }
    // Real structure. Z_k = E_k + i O_k with E, O the transforms of the even/odd words;
    // conj(Z_{-k}) = E_k - i O_k. Product: E' = E1 E2 + w^k O1 O2, O' = E1 O2 + E2 O1.
    // (factors of 2 are left in: the result is 4x, undone by the inverse weights)
    auto pair = [&](size_t p, size_t pp, C t) {
      C a1 = o[p], b1 = cconj<F>(o[pp]), a2 = q[p], b2 = cconj<F>(q[pp]);
      C E1 = cadd<F>(a1, b1), D1 = csub<F>(a1, b1), E2 = cadd<F>(a2, b2), D2 = csub<F>(a2, b2);
      C O1 = { D1.im, F::neg(D1.re) }, O2 = { D2.im, F::neg(D2.re) };      // O = (a - b) / i
      C Ep = cadd<F>(F::cmul(E1, E2), F::cmul(t, F::cmul(O1, O2)));
      C Op = cadd<F>(F::cmul(E1, O2), F::cmul(E2, O1));
      o[p] = { F::sub(Ep.re, Op.im), F::add(Ep.im, Op.re) };               // E' + i O'
      o[pp] = { F::add(Ep.re, Op.im), F::sub(Op.re, Ep.im) };              // conj(E') + i conj(O')
    };
    pair(0, 0, C{ 1, 0 });
    if (M >= 2) pair(1, 1, C{ F::neg(1), 0 });
    #pragma omp parallel for schedule(static)
    for (size_t i = 1; i < M / 2; i++) {
      int hb = ilog2(i) + 1;
      size_t p = ((size_t)1 << hb) + (i - ((size_t)1 << (hb - 1)));
      pair(p, 3 * ((size_t)1 << hb) - 1 - p, tab.tw[i]);
    }
  }

  // d_m mod q: the un-weighted convolution output for word m
  inline T out(const C* o, size_t m) const {
    if (tab.fold) {
      if (m < M) { C u = tab.U[m], v = o[m]; return F::sub(F::mul(v.re, u.re), F::mul(v.im, u.im)); }
      C u = tab.V[m - M], v = o[m - M]; return F::add(F::mul(v.re, u.im), F::mul(v.im, u.re));
    }
    C v = o[m >> 1];
    return F::mul((m & 1) ? v.im : v.re, tab.ai[m]);
  }
};

struct CpuEngine : Engine {
  Layout L;
  Xform<F61> x61; std::unique_ptr<Xform<F31>> x31;
  std::vector<std::vector<i32>> regs;
  std::vector<i128> carryOut;

  CpuEngine(const Layout& L_, int nRegs) : L(L_), x61(L), regs(nRegs, std::vector<i32>(L_.N, 0)), carryOut(L_.N / CARRY_BLOCK) {
    if (L.nPrimes == 2) x31.reset(new Xform<F31>(L));
  }
  const Layout& layout() const override { return L; }
  std::string name() const override { return "cpu (" + std::to_string(omp_get_max_threads()) + " threads)"; }
  void write(int r, const std::vector<i32>& d) override { regs.at(r) = d; }
  void read(int r, std::vector<i32>& d) override { d = regs.at(r); }
  void copy(int dst, int src) override { regs.at(dst) = regs.at(src); }

  // CRT of the two residues, centred, as a signed 128-bit integer
  inline i128 value(size_t m) const {
    u64 r61 = x61.out(x61.z.data(), m);
    if (!x31) return r61 > F61::P / 2 ? (i128)r61 - (i128)F61::P : (i128)r61;
    u32 r31 = x31->out(x31->z.data(), m);
    u32 r61m = F31::red(r61);                              // r61 mod M31
    u32 t = F31::sub(r61m, r31); t = F31::add(t, t);       // (r31 - r61) / M61 mod M31;  M61 = 2^30 - 1, inverse -2
    const u128 Q = (u128)F61::P * F31::P;
    u128 v = (u128)r61 + (u128)F61::P * t;
    return v > Q / 2 ? (i128)v - (i128)Q : (i128)v;
  }

  static inline i32 split(i128& v, int w) {                // v -> balanced digit, v becomes the carry
    i64 lo = (i64)((u64)v & ((1ULL << w) - 1));
    if (lo >= (i64)(1ULL << (w - 1))) lo -= (i64)(1ULL << w);
    v = (v - lo) >> w;
    return (i32)lo;
  }
  // joint reduction of the top two words: V = v_{N-2} + v_{N-1} 2^w  ->  digits, carry
  inline void splitTop(i128 V, i32& lo, i32& hi, i128& c) const {
    i128 B = (i128)L.topBase, q = V / B, r = V - q * B;
    if (r > B / 2) { r -= B; q++; } else if (r < -(B / 2)) { r += B; q--; }
    lo = split(r, L.width[L.N - 2]); hi = (i32)r; c = q;
  }

  // mulc: the convolution output is multiplied by this small constant before carrying
  void carry(i32* x, u32 mulc = 1) {
    const size_t N = L.N, nb = N / CARRY_BLOCK;
    #pragma omp parallel for schedule(static)
    for (size_t b = 0; b < nb; b++) {
      i128 c = 0;
      for (size_t m = b * CARRY_BLOCK; m < (b + 1) * CARRY_BLOCK; m++) {
        i128 v = value(m) * (i128)mulc + c;
        if (m + 2 == N) { splitTop(v + ((value(m + 1) * (i128)mulc) << L.width[m]), x[m], x[m + 1], c); break; }
        x[m] = split(v, L.width[m]);
        c = v;
      }
      carryOut[b] = c;
    }
    // second pass: push each block's carry into the next block (k*2^n == -1 closes the ring);
    // the last word of a block absorbs the residual +-1 without re-normalising.
    bool bad = false;
    #pragma omp parallel for schedule(static)
    for (size_t b = 0; b < nb; b++) {
      i128 c = b ? carryOut[b - 1] : -carryOut[nb - 1];
      size_t m = b * CARRY_BLOCK;
      for (size_t i = 0; i + 1 < CARRY_BLOCK; i++, m++) { i128 v = (i128)x[m] + c; x[m] = split(v, L.width[m]); c = v; }
      if (c > 1 || c < -1) bad = true;
      x[m] += (i32)c;
    }
    if (bad) throw std::runtime_error("internal: carry did not settle");
  }

  void square(int r, u64 count) override { for (u64 it = 0; it < count; it++) sq(regs.at(r).data(), 1); }
  void squareMul(int r, const std::vector<u32>& mults) override { for (u32 c : mults) sq(regs.at(r).data(), c); }
  void sq(i32* x, u32 mulc) {
    x61.weight(x, x61.z.data()); x61.dif(x61.z.data()); x61.pointwise(x61.z.data(), x61.z.data()); x61.dit(x61.z.data());
    if (x31) { x31->weight(x, x31->z.data()); x31->dif(x31->z.data()); x31->pointwise(x31->z.data(), x31->z.data()); x31->dit(x31->z.data()); }
    carry(x, mulc);
  }

  // spectrum slots (P-1 stage 2): the forward transform of a register, both fields
  std::vector<std::vector<F61::C>> s61; std::vector<std::vector<F31::C>> s31;
  size_t spectrumBytes() const override { return L.N / 2 * (sizeof(F61::C) + (x31 ? sizeof(F31::C) : 0)); }
  size_t deviceMemory() const override { return (size_t)8 << 30; }
  int allocSlots(int want, size_t budget) override {
    int n = (int)std::min<size_t>((size_t)want, budget / spectrumBytes());
    s61.assign(n, std::vector<F61::C>(L.N / 2));
    s31.assign(x31 ? n : 0, std::vector<F31::C>(L.N / 2));
    return n;
  }
  void toSpectrum(int slot, int r) override {
    const i32* x = regs.at(r).data();
    x61.weight(x, s61.at(slot).data()); x61.dif(s61.at(slot).data());
    if (x31) { x31->weight(x, s31.at(slot).data()); x31->dif(s31.at(slot).data()); }
  }
  template <class F, class X> static void diff(X& xf, const std::vector<typename F::C>& a, const std::vector<typename F::C>& b) {
    #pragma omp parallel for schedule(static)
    for (size_t j = 0; j < a.size(); j++) xf.y[j] = csub<F>(a[j], b[j]);
  }
  void mulDiff(int r, int sa, int sb) override {
    i32* x = regs.at(r).data();
    x61.weight(x, x61.z.data()); x61.dif(x61.z.data());
    diff<F61>(x61, s61.at(sa), s61.at(sb)); x61.pointwise(x61.z.data(), x61.y.data()); x61.dit(x61.z.data());
    if (x31) {
      x31->weight(x, x31->z.data()); x31->dif(x31->z.data());
      diff<F31>(*x31, s31.at(sa), s31.at(sb)); x31->pointwise(x31->z.data(), x31->y.data()); x31->dit(x31->z.data());
    }
    carry(x);
  }
  void mul(int dst, int src) override {
    i32* x = regs.at(dst).data(); const i32* y = regs.at(src).data();
    x61.weight(x, x61.z.data()); x61.dif(x61.z.data());
    x61.weight(y, x61.y.data()); x61.dif(x61.y.data());
    x61.pointwise(x61.z.data(), x61.y.data()); x61.dit(x61.z.data());
    if (x31) {
      x31->weight(x, x31->z.data()); x31->dif(x31->z.data());
      x31->weight(y, x31->y.data()); x31->dif(x31->y.data());
      x31->pointwise(x31->z.data(), x31->y.data()); x31->dit(x31->z.data());
    }
    carry(x);
  }
};

} // namespace

std::unique_ptr<Engine> makeCpuEngine(const Layout& L, int nRegs) { return std::unique_ptr<Engine>(new CpuEngine(L, nRegs)); }
