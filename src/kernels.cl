// OpenCL kernels for colbert. The host assembles the program as
//   [common]  +  for FIELD in {61, 31}: ( [field] + for RR in 1..4: [pass] )  +  [carry]
// with these compile-time constants supplied on the build line:
//   NWORDS, MHALF (= NWORDS/2), NPRIMES, FOLD61, FOLD31, TOPBASE, TOPW (width of word N-2),
//   QL, QH, QHL, QHH (CRT modulus and half of it, as 64-bit halves)
// Sections are separated by lines starting with "//====".
// Results are bit-identical to src/cpu_engine.cpp, which is the oracle in the tests.

#define PASTE2(a, b) a##b
#define XP2(a, b) PASTE2(a, b)
#define PASTE3(a, b, c) a##b##_##c
#define XP3(a, b, c) PASTE3(a, b, c)
#define CARRY_BLOCK 8

//==== field
#undef T
#undef C
#undef FN
#undef FOLD
#define FN(x) XP2(x, FIELD)

#if FIELD == 61
#define T ulong
#define C ulong2
#define FOLD FOLD61
#define P61 0x1FFFFFFFFFFFFFFFUL
inline ulong add61(ulong a, ulong b) { ulong s = a + b; return s >= P61 ? s - P61 : s; }
inline ulong sub61(ulong a, ulong b) { return a >= b ? a - b : a + P61 - b; }
inline ulong neg61(ulong a) { return a ? P61 - a : 0; }
// (hi:lo) < 2^124  ->  [0, P)
inline ulong red61(ulong lo, ulong hi) {
  ulong s = (lo & P61) + ((lo >> 61) | (hi << 3));
  s = (s & P61) + (s >> 61);
  return s >= P61 ? s - P61 : s;
}
inline ulong mul61(ulong a, ulong b) { return red61(a * b, mul_hi(a, b)); }
inline ulong2 cmul61(ulong2 a, ulong2 b) {
  ulong nb = P61 - b.y;
  ulong l1 = a.x * b.x, h1 = mul_hi(a.x, b.x), l2 = a.y * nb, h2 = mul_hi(a.y, nb);
  ulong l = l1 + l2, h = h1 + h2 + (ulong)(l < l1);
  ulong m1 = a.x * b.y, g1 = mul_hi(a.x, b.y), m2 = a.y * b.x, g2 = mul_hi(a.y, b.x);
  ulong m = m1 + m2, g = g1 + g2 + (ulong)(m < m1);
  return (ulong2)(red61(l, h), red61(m, g));
}
inline ulong fromInt61(int x) { return x < 0 ? P61 - (ulong)(-(long)x) : (ulong)x; }
#else
#define T uint
#define C uint2
#define FOLD FOLD31
#define P31 0x7FFFFFFFU
inline uint add31(uint a, uint b) { uint s = a + b; return s >= P31 ? s - P31 : s; }
inline uint sub31(uint a, uint b) { return a >= b ? a - b : a + P31 - b; }
inline uint neg31(uint a) { return a ? P31 - a : 0; }
inline uint red31(ulong t) {                       // t < 2^63
  ulong s = (t & P31) + (t >> 31);
  uint r = (uint)((s & P31) + (s >> 31));
  return r >= P31 ? r - P31 : r;
}
inline uint mul31(uint a, uint b) { return red31((ulong)a * b); }
inline uint2 cmul31(uint2 a, uint2 b) {
  return (uint2)(red31((ulong)a.x * b.x + (ulong)a.y * (P31 - b.y)), red31((ulong)a.x * b.y + (ulong)a.y * b.x));
}
inline uint fromInt31(int x) { long v = x; if (v < 0) v += P31; if (v < 0) v += P31; return (uint)(v >= (long)P31 ? v - P31 : v); }
#endif

inline C FN(cadd)(C a, C b) { return (C)(FN(add)(a.x, b.x), FN(add)(a.y, b.y)); }
inline C FN(csub)(C a, C b) { return (C)(FN(sub)(a.x, b.x), FN(sub)(a.y, b.y)); }
inline C FN(conj)(C a) { return (C)(a.x, FN(neg)(a.y)); }

#if FOLD
// fold structure: z_j = W1_j x_j + W2_j x_{j+M};  tab = (W1_0, W2_0, W1_1, W2_1, ...)
typedef C FN(FT);
typedef C FN(OT);
__kernel void FN(weight)(__global const int* x, __global const C* tab, __global C* z) {
  uint j = get_global_id(0);
  T u = FN(fromInt)(x[j]), v = FN(fromInt)(x[j + MHALF]);
  C a = tab[2 * j], b = tab[2 * j + 1];
  z[j] = (C)(FN(add)(FN(mul)(a.x, u), FN(mul)(b.x, v)), FN(add)(FN(mul)(a.y, u), FN(mul)(b.y, v)));
}
__kernel void FN(pw)(__global C* z, __global const C* y, __global const C* tw) {
  uint j = get_global_id(0);
  z[j] = FN(cmul)(z[j], y[j]);
  z[j + MHALF / 2] = FN(cmul)(z[j + MHALF / 2], y[j + MHALF / 2]);
}
// d_m mod q;  tab[m] = (U.re, -U.im) for m < M, (V.im, V.re) for m >= M
inline T FN(out)(__global const C* z, __global const C* tab, uint m) {
  C v = z[m & (MHALF - 1)], u = tab[m];
  return FN(add)(FN(mul)(v.x, u.x), FN(mul)(v.y, u.y));
}
#else
// real structure: z_j = a_{2j} x_{2j} + i a_{2j+1} x_{2j+1}
typedef T FN(FT);
typedef T FN(OT);
__kernel void FN(weight)(__global const int* x, __global const T* tab, __global C* z) {
  uint j = get_global_id(0);
  z[j] = (C)(FN(mul)(tab[2 * j], FN(fromInt)(x[2 * j])), FN(mul)(tab[2 * j + 1], FN(fromInt)(x[2 * j + 1])));
}
// Conjugate pair (p, pp) in bit-reversed order. With Z = E + iO, conj(Z') = E - iO:
//   E' = E1 E2 + t O1 O2,  O' = E1 O2 + E2 O1   (4x; the inverse weights divide it out)
inline void FN(pair)(__global C* z, __global const C* y, uint p, uint pp, C t) {
  C a1 = z[p], b1 = FN(conj)(z[pp]), a2 = y[p], b2 = FN(conj)(y[pp]);
  C E1 = FN(cadd)(a1, b1), D1 = FN(csub)(a1, b1), E2 = FN(cadd)(a2, b2), D2 = FN(csub)(a2, b2);
  C O1 = (C)(D1.y, FN(neg)(D1.x)), O2 = (C)(D2.y, FN(neg)(D2.x));
  C Ep = FN(cadd)(FN(cmul)(E1, E2), FN(cmul)(t, FN(cmul)(O1, O2)));
  C Op = FN(cadd)(FN(cmul)(E1, O2), FN(cmul)(E2, O1));
  z[p] = (C)(FN(sub)(Ep.x, Op.y), FN(add)(Ep.y, Op.x));
  z[pp] = (C)(FN(add)(Ep.x, Op.y), FN(sub)(Op.x, Ep.y));
}
__kernel void FN(pw)(__global C* z, __global const C* y, __global const C* tw) {
  uint i = get_global_id(0);
  if (i == 0) {
    FN(pair)(z, y, 0, 0, (C)(1, 0));
    FN(pair)(z, y, 1, 1, (C)(FN(neg)(1), 0));
  } else {
    uint hb = 32 - clz(i);                         // pair lives in block [2^hb, 2^(hb+1))
    uint p = (1u << hb) + (i - (1u << (hb - 1)));
    FN(pair)(z, y, p, 3u * (1u << hb) - 1u - p, tw[i]);
  }
}
inline T FN(out)(__global const C* z, __global const T* tab, uint m) {
  C v = z[m >> 1];
  return FN(mul)((m & 1) ? v.y : v.x, tab[m]);
}
#endif

//==== pass
// One pass = RR consecutive radix-2 levels done in registers on 2^RR elements.
// h0 is the largest half-size of the pass, hmin = h0 >> (RR-1) the smallest.
#define FNR(x) XP3(x, FIELD, RR)
__kernel void FNR(dif)(__global C* z, __global const C* w, const uint h0) {
  const uint hmin = h0 >> (RR - 1);
  uint gid = get_global_id(0), j = gid & (hmin - 1), base = (gid / hmin) * 2 * h0 + j;
  C u[1 << RR];
  for (uint i = 0; i < (1u << RR); i++) u[i] = z[base + i * hmin];
  for (uint l = 0; l < RR; l++) {
    uint hl = 1u << (RR - 1 - l), H = h0 >> l;
    for (uint lb = 0; lb < (1u << RR); lb += 2 * hl)
      for (uint i = 0; i < hl; i++) {
        C a = u[lb + i], b = u[lb + i + hl];
        u[lb + i] = FN(cadd)(a, b);
        u[lb + i + hl] = FN(cmul)(FN(csub)(a, b), w[H + j + i * hmin]);
      }
  }
  for (uint i = 0; i < (1u << RR); i++) z[base + i * hmin] = u[i];
}
__kernel void FNR(dit)(__global C* z, __global const C* w, const uint h0) {
  const uint hmin = h0 >> (RR - 1);
  uint gid = get_global_id(0), j = gid & (hmin - 1), base = (gid / hmin) * 2 * h0 + j;
  C u[1 << RR];
  for (uint i = 0; i < (1u << RR); i++) u[i] = z[base + i * hmin];
  for (int l = RR - 1; l >= 0; l--) {
    uint hl = 1u << (RR - 1 - l), H = h0 >> l;
    for (uint lb = 0; lb < (1u << RR); lb += 2 * hl)
      for (uint i = 0; i < hl; i++) {
        C a = u[lb + i], b = FN(cmul)(u[lb + i + hl], FN(conj)(w[H + j + i * hmin]));
        u[lb + i] = FN(cadd)(a, b);
        u[lb + i + hl] = FN(csub)(a, b);
      }
  }
  for (uint i = 0; i < (1u << RR); i++) z[base + i * hmin] = u[i];
}
#undef FNR

//==== carry
typedef struct { ulong lo; long hi; } i128;

inline i128 add128(i128 a, i128 b) { i128 r; r.lo = a.lo + b.lo; r.hi = a.hi + b.hi + (long)(r.lo < a.lo); return r; }
inline i128 neg128(i128 a) { i128 r; r.lo = ~a.lo + 1UL; r.hi = ~a.hi + (long)(r.lo == 0); return r; }
inline i128 sext128(long v) { i128 r; r.lo = (ulong)v; r.hi = v < 0 ? -1L : 0L; return r; }
inline i128 shl128(i128 a, uint s) { i128 r; r.lo = a.lo << s; r.hi = (long)(((ulong)a.hi << s) | (a.lo >> (64 - s))); return r; }

// v -> balanced digit of width w (1 <= w <= 31); v becomes the carry
inline int split128(i128* v, uint w) {
  long lo = (long)(v->lo & ((1UL << w) - 1UL));
  if (lo >= (long)(1UL << (w - 1))) lo -= (long)(1UL << w);
  ulong nl = v->lo - (ulong)lo;
  long nh = v->hi - (lo < 0 ? -1L : 0L) - (long)(v->lo < (ulong)lo);
  v->lo = (nl >> w) | ((ulong)nh << (64 - w));
  v->hi = nh >> w;
  return (int)lo;
}

// CRT of the per-prime outputs for word m, centred
inline i128 value128(__global const ulong2* z61, __global const OT61* o61,
                     __global const uint2* z31, __global const OT31* o31, uint m) {
  ulong r61 = out61(z61, o61, m);
  i128 v;
#if NPRIMES == 2
  uint r31 = out31(z31, o31, m);
  ulong s = (r61 & P31) + (r61 >> 31);
  uint r61m = (uint)((s & P31) + (s >> 31)); if (r61m >= P31) r61m -= P31;
  uint t = sub31(r61m, r31); t = add31(t, t);     // (r31 - r61) / M61 mod M31
  ulong tl = (ulong)t << 61, th = (ulong)t >> 3;   // M61 * t = (t << 61) - t
  ulong lo = tl - (ulong)t, hi = th - (ulong)(tl < (ulong)t);
  ulong lo2 = lo + r61; hi += (ulong)(lo2 < lo);
  if (hi > QHH || (hi == QHH && lo2 > QHL)) { ulong b = (ulong)(lo2 < QL); lo2 -= QL; hi = hi - QH - b; }
  v.lo = lo2; v.hi = (long)hi;
#else
  v = sext128(r61 > P61 / 2 ? (long)r61 - (long)P61 : (long)r61);
#endif
  return v;
}

// joint reduction of the top two words modulo TOPBASE (truncating division, then balance)
inline void splitTop(i128 V, int* lo, int* hi, i128* c) {
  bool sg = V.hi < 0;
  i128 mag = sg ? neg128(V) : V;
  ulong ql = 0, qh = 0, rem = 0;
  for (int b = 127; b >= 0; b--) {
    ulong bit = (b >= 64 ? ((ulong)mag.hi >> (b - 64)) : (mag.lo >> b)) & 1UL;
    rem = (rem << 1) | bit;
    if (rem >= TOPBASE) { rem -= TOPBASE; if (b >= 64) qh |= 1UL << (b - 64); else ql |= 1UL << b; }
  }
  i128 q; q.lo = ql; q.hi = (long)qh;
  long r = (long)rem;
  if (sg) { q = neg128(q); r = -r; }
  const long hb2 = (long)(TOPBASE / 2);
  if (r > hb2) { r -= (long)TOPBASE; q = add128(q, sext128(1)); }
  else if (r < -hb2) { r += (long)TOPBASE; q = add128(q, sext128(-1)); }
  i128 rr = sext128(r);
  *lo = split128(&rr, TOPW);
  *hi = (int)rr.lo;
  *c = q;
}

__kernel void carry1(__global const ulong2* z61, __global const OT61* o61, __global const uint2* z31, __global const OT31* o31,
                     __global const uchar* width, __global int* x, __global ulong2* carryOut) {
  uint b = get_global_id(0);
  i128 c = sext128(0);
  for (uint m = b * CARRY_BLOCK; m < (b + 1) * CARRY_BLOCK; m++) {
    i128 v = add128(value128(z61, o61, z31, o31, m), c);
    if (m + 2 == NWORDS) {
      int lo, hi;
      splitTop(add128(v, shl128(value128(z61, o61, z31, o31, m + 1), TOPW)), &lo, &hi, &c);
      x[m] = lo; x[m + 1] = hi;
      break;
    }
    x[m] = split128(&v, width[m]);
    c = v;
  }
  carryOut[b] = (ulong2)(c.lo, (ulong)c.hi);
}

// Push each block's carry into the next block; k*2^n == -1 closes the ring. The last word
// of a block absorbs the residual +-1 without re-normalising. flag[0] is set if a carry
// failed to settle (cannot happen within the proven bounds; checked by the host).
__kernel void carry2(__global int* x, __global const ulong2* carryOut, __global const uchar* width, __global int* flag) {
  uint b = get_global_id(0);
  ulong2 ci = carryOut[b ? b - 1 : NWORDS / CARRY_BLOCK - 1];
  i128 c; c.lo = ci.x; c.hi = (long)ci.y;
  if (b == 0) c = neg128(c);
  uint m = b * CARRY_BLOCK;
  for (uint i = 0; i + 1 < CARRY_BLOCK; i++, m++) {
    i128 v = add128(sext128((long)x[m]), c);
    x[m] = split128(&v, width[m]);
    c = v;
  }
  if (!((c.hi == 0 && c.lo <= 1UL) || (c.hi == -1L && c.lo == ~0UL))) flag[0] = 1;
  x[m] += (int)c.lo;
}
