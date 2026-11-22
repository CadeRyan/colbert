// OpenCL kernels for colbert. The host assembles the program as
//   [common]  +  for FIELD in {61, 31}: ( [field] + for RR in 1..4: [pass] + [fft2] )  +  [carry]
// with these compile-time constants supplied on the build line:
//   NWORDS, MHALF (= NWORDS/2), NPRIMES, FOLD61, FOLD31, TOPBASE, TOPW (width of word N-2),
//   QL, QH, QHL, QHH (CRT modulus and half of it, as 64-bit halves),
//   LOGR, LOGC (fft2 only: the transform is done as R x C = MHALF, see the fft2 section)
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
#undef EB
#undef GF
#undef GIF
#define FN(x) XP2(x, FIELD)

#if FIELD == 61
#define T ulong
#define C ulong2
#define FOLD FOLD61
#define GF G61
#define GIF GI61
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
inline ulong2 csqr61(ulong2 a) {                    // (a+b)(a-b) + 2ab i: two products
  ulong s = a.x + a.y, d = sub61(a.x, a.y), t = a.x << 1;     // s, t < 2^62
  return (ulong2)(red61(s * d, mul_hi(s, d)), red61(t * a.y, mul_hi(t, a.y)));
}
inline ulong mul2exp61(ulong a, uint s) { return s ? ((a << s) & P61) | (a >> (61 - s)) : a; }   // a 2^s, 0 <= s < 61
#define EB 61
#else
#define T uint
#define C uint2
#define FOLD FOLD31
#define GF G31
#define GIF GI31
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
inline uint2 csqr31(uint2 a) {
  return (uint2)(red31((ulong)(a.x + a.y) * sub31(a.x, a.y)), red31((ulong)(a.x << 1) * a.y));
}
inline uint fromInt31(int x) { long v = x; if (v < 0) v += P31; if (v < 0) v += P31; return (uint)(v >= (long)P31 ? v - P31 : v); }
inline uint mul2exp31(uint a, uint s) { return s ? ((a << s) & P31) | (a >> (31 - s)) : a; }
#define EB 31
#endif

inline C FN(cadd)(C a, C b) { return (C)(FN(add)(a.x, b.x), FN(add)(a.y, b.y)); }
inline C FN(csub)(C a, C b) { return (C)(FN(sub)(a.x, b.x), FN(sub)(a.y, b.y)); }
inline C FN(conj)(C a) { return (C)(a.x, FN(neg)(a.y)); }
__kernel void FN(vsub)(__global const C* a, __global const C* b, __global C* out) { uint j = get_global_id(0); out[j] = FN(csub)(a[j], b[j]); }

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

//==== fft2
// The fast transform: the MHALF-point DFT as a four-step R x C transform (MHALF = R*C) with
// every sub-transform done by one work-group in registers and local memory, so a squaring
// makes three passes over each field's data instead of ten:
//   colfwd: weight the digits, R-point DFTs down the C columns, four-step twiddle
//   rows:   C-point DFTs along the rows, the pointwise product, inverse row DFTs, inverse twiddle
//   colinv: inverse R-point DFTs down the columns, natural order out (for carry1)
// Point j = c + C*t (column c, row t). After colfwd, row k1 holds frequency k1 of every
// column; after the row DFTs, position k1*C + k2 holds frequency k1 + R*k2.
// Sub-transforms are Stockham radix-8 (and a last radix-2 or radix-4 stage when log2 S is
// not a multiple of 3). w8 = (1+i) 2^((EB-1)/2) is a primitive 8th root of unity in GF(q^2), so the
// radix-8 butterflies need no multiplications, only additions and rotations. The host picks
// the M-th root of unity w with w^(M/8) = w8 and fills the tables:
//   TR[e] = w^(C e) (e < R),  TC[e] = w^(R e) (e < C),  TW1[e] = w^e (e < C),  TW2[e] = w^(C e) (e < R)
// All roots have norm 1, so their inverses are their conjugates.
#ifdef LOGR
#define FR (1u << LOGR)
#define FC (1u << LOGC)
#define H8 ((EB - 1) / 2)

inline C FN(rot)(C z, uint s) { return (C)(FN(mul2exp)(z.x, s), FN(mul2exp)(z.y, s)); }
inline C FN(mi)(C z) { return (C)(FN(neg)(z.y), z.x); }                                   // i z
inline C FN(mmi)(C z) { return (C)(z.y, FN(neg)(z.x)); }                                  // -i z
inline C FN(w8f)(C z) { return FN(rot)((C)(FN(sub)(z.x, z.y), FN(add)(z.x, z.y)), H8); }  // w8 z
inline C FN(w8i)(C z) { return FN(rot)((C)(FN(add)(z.x, z.y), FN(sub)(z.y, z.x)), H8); }  // z / w8

inline void FN(dft4)(C* v, uint b, uint s, int inv) {        // v[b + s i], i < 4, natural order out
  C a0 = v[b], a1 = v[b + s], a2 = v[b + 2 * s], a3 = v[b + 3 * s];
  C b0 = FN(cadd)(a0, a2), b1 = FN(csub)(a0, a2), b2 = FN(cadd)(a1, a3), b3 = FN(csub)(a1, a3);
  b3 = inv ? FN(mmi)(b3) : FN(mi)(b3);
  v[b] = FN(cadd)(b0, b2); v[b + 2 * s] = FN(csub)(b0, b2);
  v[b + s] = FN(cadd)(b1, b3); v[b + 3 * s] = FN(csub)(b1, b3);
}
inline void FN(dft8)(C* v, int inv) {                        // v[0..7], natural order out
  for (uint n = 0; n < 4; n++) {
    C a = v[n], b = v[n + 4], d = FN(csub)(a, b);
    v[n] = FN(cadd)(a, b);
    if (n == 1) d = inv ? FN(w8i)(d) : FN(w8f)(d);
    else if (n == 2) d = inv ? FN(mmi)(d) : FN(mi)(d);
    else if (n == 3) d = inv ? FN(mmi)(FN(w8i)(d)) : FN(mi)(FN(w8f)(d));
    v[n + 4] = d;
  }
  FN(dft4)(v, 0, 1, inv); FN(dft4)(v, 4, 1, inv);             // v = X0 X2 X4 X6 X1 X3 X5 X7
  C x2 = v[1], x4 = v[2], x6 = v[3], x1 = v[4], x3 = v[5], x5 = v[6];
  v[1] = x1; v[2] = x2; v[3] = x3; v[4] = x4; v[5] = x5; v[6] = x6;
}

// v[m] -> L[pos[m]], then v[m] <- L[nx + Q m], one 32-bit word of each value at a time, so
// local memory holds S words whatever the field.
inline void FN(xchg)(C* v, __local uint* L, const uint* pos, uint nx, uint Q) {
#if EB == 61
  // a component may be overwritten only after both of its halves have been sent
  uint lo[8];
  #pragma unroll
  for (uint part = 0; part < 4; part++) {
    barrier(CLK_LOCAL_MEM_FENCE);
    #pragma unroll
    for (uint m = 0; m < 8; m++) { ulong w = part < 2 ? v[m].x : v[m].y; L[pos[m]] = (uint)(part & 1 ? w >> 32 : w); }
    barrier(CLK_LOCAL_MEM_FENCE);
    #pragma unroll
    for (uint m = 0; m < 8; m++) {
      uint w = L[nx + Q * m];
      if (!(part & 1)) lo[m] = w;
      else if (part == 1) v[m].x = (ulong)lo[m] | ((ulong)w << 32);
      else v[m].y = (ulong)lo[m] | ((ulong)w << 32);
    }
  }
#else
  #pragma unroll
  for (uint part = 0; part < 2; part++) {
    barrier(CLK_LOCAL_MEM_FENCE);
    #pragma unroll
    for (uint m = 0; m < 8; m++) L[pos[m]] = part ? v[m].y : v[m].x;
    barrier(CLK_LOCAL_MEM_FENCE);
    #pragma unroll
    for (uint m = 0; m < 8; m++) { if (part) v[m].y = L[nx + Q * m]; else v[m].x = L[nx + Q * m]; }
  }
#endif
}

// S-point DFT (inverse: conjugate roots, unscaled) by the S/8 work-items of a group.
// In:  v[m] = element (idIn + (S/8) m) of the input.  Out: v[m] = element (idOut + (S/8) m)
// of the output. Between stages the work-items exchange through L, one component at a time
// (S words of local memory instead of S complex values: twice the work-groups fit on a
// compute unit). idIn/idOut let a caller hold a row in mirrored order (see rows); with a
// single stage they must be equal.
inline void FN(xform)(C* v, __local uint* L, const uint S, const uint LOGS, const uint id,
                      const uint idIn, const uint idOut, __global const C* tab, const int inv) {
  const uint Q = S / 8, r0 = 1u << (LOGS % 3), nst = (LOGS + 2) / 3;
  uint ns = 1;
  #pragma unroll
  for (uint st = 0; st < nst; st++) {
    const uint r = (r0 > 1 && st == nst - 1) ? r0 : 8, per = 8 / r;     // first stage: no twiddles
    const uint me = st == 0 ? idIn : st == nst - 1 ? idOut : id;
    uint pos[8];
    #pragma unroll
    for (uint u = 0; u < per; u++) {
      const uint j = me + Q * u, k = j & (ns - 1);
      if (ns > 1) {
        #pragma unroll
        for (uint i = 1; i < r; i++) {
          C w = tab[i * k * (S / (ns * r))];
          v[u + per * i] = FN(cmul)(v[u + per * i], inv ? FN(conj)(w) : w);
        }
      }
      if (r == 2) { C a = v[u], b = v[u + 4]; v[u] = FN(cadd)(a, b); v[u + 4] = FN(csub)(a, b); }
      else if (r == 4) FN(dft4)(v, u, 2, inv);
      else FN(dft8)(v, inv);
      #pragma unroll
      for (uint i = 0; i < r; i++) pos[u + per * i] = (j - k) * r + k + ns * i;
    }
    ns *= r;
    if (st + 1 < nst) {
      const uint nx = st + 1 == nst - 1 ? idOut : id;          // next stage's work-item index
      FN(xchg)(v, L, pos, nx, Q);
    }
  }
}

inline C FN(tw4)(__global const C* TW1, __global const C* TW2, uint e) {    // w^e, e < R*C
  return FN(cmul)(TW1[e & (FC - 1)], TW2[e >> LOGC]);
}

// digits -> weighted transform input for point j. With WOTF the weights are computed from
// two small tables and a rotation (2^s mod q is a rotation), instead of read from tables as
// large as the data: see the constants in layout.h.
//   real: a_m = rho^m 2^s_m = WA[m mod B] WB[m / B] 2^s_m;  fold: th^-j = WA[j mod B] WB[j / B]
// se[m] = s_m mod EB. The inverse weights (outw, used by carry1w) come from IA, IB the same way.
#if WOTF
#define WBLK (1u << WBL)
#if FOLD
inline C FN(win)(__global const int* x, __global const C* WA, __global const C* WB, __global const uchar* se, uint j) {
  C t = FN(cmul)(WA[j & (WBLK - 1)], WB[j >> WBL]);
  T u = FN(mul2exp)(FN(fromInt)(x[j]), se[j]);
  T v = FN(mul)((T)GF, FN(mul2exp)(FN(fromInt)(x[j + MHALF]), se[j + MHALF]));
  return FN(cmul)(t, (C)(u, v));
}
inline T FN(outw)(__global const C* z, __global const C* IA, __global const C* IB, __global const uchar* se, uint m) {
  uint j = m & (MHALF - 1), s = se[m];
  C w = FN(cmul)(IA[j & (WBLK - 1)], IB[j >> WBL]), v = z[j];
  T d = m < MHALF ? FN(sub)(FN(mul)(v.x, w.x), FN(mul)(v.y, w.y))
                  : FN(mul)(FN(add)(FN(mul)(v.x, w.y), FN(mul)(v.y, w.x)), (T)GIF);
  return FN(mul2exp)(d, s ? EB - s : 0);
}
#else
inline C FN(win)(__global const int* x, __global const T* WA, __global const T* WB, __global const uchar* se, uint j) {
  uint m0 = 2 * j, m1 = m0 + 1;
  T r0 = FN(mul2exp)(FN(mul)(WA[m0 & (WBLK - 1)], WB[m0 >> WBL]), se[m0]);
  T r1 = FN(mul2exp)(FN(mul)(WA[m1 & (WBLK - 1)], WB[m1 >> WBL]), se[m1]);
  return (C)(FN(mul)(r0, FN(fromInt)(x[m0])), FN(mul)(r1, FN(fromInt)(x[m1])));
}
inline T FN(outw)(__global const C* z, __global const T* IA, __global const T* IB, __global const uchar* se, uint m) {
  C v = z[m >> 1];
  uint s = se[m];
  T w = FN(mul2exp)(FN(mul)(IA[m & (WBLK - 1)], IB[m >> WBL]), s ? EB - s : 0);
  return FN(mul)((m & 1) ? v.y : v.x, w);
}
#endif
#else
#if FOLD
inline C FN(win)(__global const int* x, __global const C* tab, __global const C* unused, __global const uchar* se, uint j) {
  T u = FN(fromInt)(x[j]), v = FN(fromInt)(x[j + MHALF]);
  C a = tab[2 * j], b = tab[2 * j + 1];
  return (C)(FN(add)(FN(mul)(a.x, u), FN(mul)(b.x, v)), FN(add)(FN(mul)(a.y, u), FN(mul)(b.y, v)));
}
#else
inline C FN(win)(__global const int* x, __global const T* tab, __global const T* unused, __global const uchar* se, uint j) {
  return (C)(FN(mul)(tab[2 * j], FN(fromInt)(x[2 * j])), FN(mul)(tab[2 * j + 1], FN(fromInt)(x[2 * j + 1])));
}
#endif
#endif

// CPG adjacent columns per group, R/8 work-items each, interleaved so that neighbouring
// work-items touch neighbouring addresses
#ifndef CPG
#define CPG 1
#endif
__kernel void FN(colfwd)(__global const int* x, __global const FN(FT)* wt, __global const FN(FT)* wb, __global const uchar* se,
                         __global C* z, __global const C* TR, __global const C* TW1, __global const C* TW2) {
  __local uint Lall[CPG * FR];
  const uint lid = get_local_id(0), c = get_group_id(0) * CPG + lid % CPG, id = lid / CPG, Q = FR / 8;
  __local uint* L = Lall + (lid % CPG) * FR;
  C v[8];
  #pragma unroll
  for (uint m = 0; m < 8; m++) v[m] = FN(win)(x, wt, wb, se, c + FC * (id + Q * m));
  FN(xform)(v, L, FR, LOGR, id, id, id, TR, 0);
  #pragma unroll
  for (uint m = 0; m < 8; m++) {
    uint k1 = id + Q * m;
    z[k1 * FC + c] = FN(cmul)(v[m], FN(tw4)(TW1, TW2, c * k1));
  }
}

// inverse R-point DFTs down the columns, natural order out
__kernel void FN(colinv)(__global C* z, __global const C* TR) {
  __local uint Lall[CPG * FR];
  const uint lid = get_local_id(0), c = get_group_id(0) * CPG + lid % CPG, id = lid / CPG, Q = FR / 8;
  __local uint* L = Lall + (lid % CPG) * FR;
  C v[8];
  #pragma unroll
  for (uint m = 0; m < 8; m++) v[m] = z[(id + Q * m) * FC + c];
  FN(xform)(v, L, FR, LOGR, id, id, id, TR, 1);
  #pragma unroll
  for (uint m = 0; m < 8; m++) z[c + FC * (id + Q * m)] = v[m];
}

// one group per row: forward row DFTs only (the spectrum of an operand used in products)
__kernel void FN(rowsfwd)(__global const C* z, __global C* out, __global const C* TC) {
  __local uint L[FC];
  const uint r = get_group_id(0), id = get_local_id(0), Q = FC / 8;
  C v[8];
  #pragma unroll
  for (uint m = 0; m < 8; m++) v[m] = z[r * FC + id + Q * m];
  FN(xform)(v, L, FC, LOGC, id, id, id, TC, 0);
  #pragma unroll
  for (uint m = 0; m < 8; m++) out[r * FC + id + Q * m] = v[m];
}

// second operand at spectrum position p: mode 0 squares, 1 multiplies by ya, 2 by (ya - yb)
inline C FN(yop)(__global const C* ya, __global const C* yb, uint mode, uint p) {
  return mode == 2 ? FN(csub)(ya[p], yb[p]) : ya[p];
}

#if !FOLD
// real structure: Z = E + iO with conj(Z(-k)) = E - iO. Given Z(k) = a1, Z(-k) = b1 and the
// other operand's a2, b2, returns the product at k (*pk) and at -k (*pm); t = w^k. As in
// the CPU engine, the result is 4x (the inverse weights divide it out).
inline void FN(untangle)(C a1, C b1, C a2, C b2, C t, C* pk, C* pm) {
  b1 = FN(conj)(b1); b2 = FN(conj)(b2);
  C E1 = FN(cadd)(a1, b1), D1 = FN(csub)(a1, b1), E2 = FN(cadd)(a2, b2), D2 = FN(csub)(a2, b2);
  C O1 = (C)(D1.y, FN(neg)(D1.x)), O2 = (C)(D2.y, FN(neg)(D2.x));
  C Ep = FN(cadd)(FN(cmul)(E1, E2), FN(cmul)(t, FN(cmul)(O1, O2)));
  C Op = FN(cadd)(FN(cmul)(E1, O2), FN(cmul)(E2, O1));
  *pk = (C)(FN(sub)(Ep.x, Op.y), FN(add)(Ep.y, Op.x));
  *pm = (C)(FN(add)(Ep.x, Op.y), FN(sub)(Op.x, Ep.y));
}
// the same for a squaring: E' = E^2 + t O^2, O' = 2 E O
inline void FN(untangle2)(C a1, C b1, C t, C* pk, C* pm) {
  b1 = FN(conj)(b1);
  C E1 = FN(cadd)(a1, b1), D1 = FN(csub)(a1, b1);
  C O1 = (C)(D1.y, FN(neg)(D1.x));
  C Ep = FN(cadd)(FN(csqr)(E1), FN(cmul)(t, FN(csqr)(O1)));
  C Op = FN(cmul)(E1, O1); Op = FN(cadd)(Op, Op);
  *pk = (C)(FN(sub)(Ep.x, Op.y), FN(add)(Ep.y, Op.x));
  *pm = (C)(FN(add)(Ep.x, Op.y), FN(sub)(Op.x, Ep.y));
}
#endif

// inverse row DFT of v (row a), inverse four-step twiddle, store
inline void FN(rowout)(C* v, __local uint* L, __global C* z, uint a, uint id, uint idIn,
                       __global const C* TC, __global const C* TW1, __global const C* TW2) {
  const uint Q = FC / 8;
  FN(xform)(v, L, FC, LOGC, id, idIn, id, TC, 1);
  #pragma unroll
  for (uint m = 0; m < 8; m++) {
    uint c = id + Q * m;
#ifdef FAULT_FFT2              // test hook: breaks the fast path; the startup check must catch it
    z[a * FC + c] = v[m];
#else
    z[a * FC + c] = FN(cmul)(v[m], FN(conj)(FN(tw4)(TW1, TW2, c * a)));
#endif
  }
}

// Group g in [1, R/2) owns rows g and R-g; group 0 owns rows 0 and R/2. Frequency
// k = k1 + R k2 pairs with -k = (R-k1) + R(C-1-k2) for k1 > 0, and with (C-k2) mod C in row 0.
__kernel void FN(rows)(__global C* z, __global const C* ya, __global const C* yb, const uint mode,
                       __global const C* TC, __global const C* TW1, __global const C* TW2) {
  __local uint L[FC];
  const uint g = get_group_id(0), id = get_local_id(0), Q = FC / 8;
  const uint A = g, B = g ? FR - g : FR / 2;
  C va[8], vb[8];
#if FOLD
  #pragma unroll
  for (uint m = 0; m < 8; m++) va[m] = z[A * FC + id + Q * m];
  FN(xform)(va, L, FC, LOGC, id, id, id, TC, 0);
  #pragma unroll
  for (uint m = 0; m < 8; m++) { uint p = A * FC + id + Q * m; va[m] = mode ? FN(cmul)(va[m], FN(yop)(ya, yb, mode, p)) : FN(csqr)(va[m]); }
  FN(rowout)(va, L, z, A, id, id, TC, TW1, TW2);
  #pragma unroll
  for (uint m = 0; m < 8; m++) vb[m] = z[B * FC + id + Q * m];
  FN(xform)(vb, L, FC, LOGC, id, id, id, TC, 0);
  #pragma unroll
  for (uint m = 0; m < 8; m++) { uint p = B * FC + id + Q * m; vb[m] = mode ? FN(cmul)(vb[m], FN(yop)(ya, yb, mode, p)) : FN(csqr)(vb[m]); }
  FN(rowout)(vb, L, z, B, id, id, TC, TW1, TW2);
#else
  if (g == 0) {
    // rows 0 and R/2 pair with themselves: exchange partners through local memory
    for (uint h = 0; h < 2; h++) {
      const uint a = h ? FR / 2 : 0;
      #pragma unroll
      for (uint m = 0; m < 8; m++) va[m] = z[a * FC + id + Q * m];
      FN(xform)(va, L, FC, LOGC, id, id, id, TC, 0);
      // partners: write element k2 to slot (partner of k2), then read slot k2
      uint pos[8];
      #pragma unroll
      for (uint m = 0; m < 8; m++) { uint k2 = id + Q * m; pos[m] = h ? FC - 1 - k2 : (FC - k2) & (FC - 1); vb[m] = va[m]; }
      FN(xchg)(vb, L, pos, id, Q);
      #pragma unroll
      for (uint m = 0; m < 8; m++) {
        uint k2 = id + Q * m, pk2 = h ? FC - 1 - k2 : (FC - k2) & (FC - 1);
        C t = FN(cmul)(TW1[a], TC[k2]), pk, dummy;
        if (mode) FN(untangle)(va[m], vb[m], FN(yop)(ya, yb, mode, a * FC + k2), FN(yop)(ya, yb, mode, a * FC + pk2), t, &pk, &dummy);
        else FN(untangle2)(va[m], vb[m], t, &pk, &dummy);
        va[m] = pk;
      }
      FN(rowout)(va, L, z, a, id, id, TC, TW1, TW2);
    }
    return;
  }
  // row A in natural order, row B mirrored: vb[m] = element (Q-1-id) + Q m, so the partner
  // of va[m] (element C-1-k2 of row B) is vb[7-m]
  const uint idr = Q - 1 - id;
  #pragma unroll
  for (uint m = 0; m < 8; m++) va[m] = z[A * FC + id + Q * m];
  FN(xform)(va, L, FC, LOGC, id, id, id, TC, 0);
  #pragma unroll
  for (uint m = 0; m < 8; m++) vb[m] = z[B * FC + id + Q * m];
  FN(xform)(vb, L, FC, LOGC, id, id, idr, TC, 0);
  const C tA = TW1[A];
  #pragma unroll
  for (uint m = 0; m < 8; m++) {
    uint k2 = id + Q * m;
    C t = FN(cmul)(tA, TC[k2]), pk, pm;
    if (mode) FN(untangle)(va[m], vb[7 - m], FN(yop)(ya, yb, mode, A * FC + k2), FN(yop)(ya, yb, mode, B * FC + FC - 1 - k2), t, &pk, &pm);
    else FN(untangle2)(va[m], vb[7 - m], t, &pk, &pm);
    va[m] = pk; vb[7 - m] = pm;
  }
  FN(rowout)(va, L, z, A, id, id, TC, TW1, TW2);
  FN(rowout)(vb, L, z, B, id, idr, TC, TW1, TW2);
#endif
}
#undef FR
#undef FC
#undef H8
#endif

//==== carry
typedef struct { ulong lo; long hi; } i128;

inline i128 add128(i128 a, i128 b) { i128 r; r.lo = a.lo + b.lo; r.hi = a.hi + b.hi + (long)(r.lo < a.lo); return r; }
inline i128 neg128(i128 a) { i128 r; r.lo = ~a.lo + 1UL; r.hi = ~a.hi + (long)(r.lo == 0); return r; }
inline i128 sext128(long v) { i128 r; r.lo = (ulong)v; r.hi = v < 0 ? -1L : 0L; return r; }
// a * c for a small unsigned c (P-1 stage 1 multiplies by the base this way)
inline i128 mulsmall128(i128 a, uint c) {
  i128 r; r.lo = a.lo * (ulong)c; r.hi = a.hi * (long)c + (long)mul_hi(a.lo, (ulong)c); return r;
}
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

// CRT of the per-prime outputs for one word, centred
inline i128 crt128(ulong r61, uint r31) {
  i128 v;
#if NPRIMES == 2
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
inline i128 value128(__global const ulong2* z61, __global const OT61* o61,
                     __global const uint2* z31, __global const OT31* o31, uint m) {
#if NPRIMES == 2
  return crt128(out61(z61, o61, m), out31(z31, o31, m));
#else
  return crt128(out61(z61, o61, m), 0);
#endif
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

// One block of CARRY_BLOCK words from their CRT values: digits and the block's carry out.
inline void carryBlock(i128* val, __global const uchar* width, __global int* x, __global ulong2* carryOut, uint b) {
  const uint m0 = b * CARRY_BLOCK;
  uchar wd[CARRY_BLOCK];
  #pragma unroll
  for (uint i = 0; i < CARRY_BLOCK; i++) wd[i] = width[m0 + i];
  int out[CARRY_BLOCK];
  i128 c = sext128(0);
  if (m0 + CARRY_BLOCK == NWORDS) {
    // last block: the top two words are reduced jointly
    #pragma unroll
    for (uint i = 0; i + 2 < CARRY_BLOCK; i++) { i128 v = add128(val[i], c); out[i] = split128(&v, wd[i]); c = v; }
    splitTop(add128(add128(val[CARRY_BLOCK - 2], c), shl128(val[CARRY_BLOCK - 1], TOPW)), &out[CARRY_BLOCK - 2], &out[CARRY_BLOCK - 1], &c);
  } else {
    #pragma unroll
    for (uint i = 0; i < CARRY_BLOCK; i++) { i128 v = add128(val[i], c); out[i] = split128(&v, wd[i]); c = v; }
  }
  #pragma unroll
  for (uint i = 0; i < CARRY_BLOCK; i++) x[m0 + i] = out[i];
  carryOut[b] = (ulong2)(c.lo, (ulong)c.hi);
}

__kernel void carry1(__global const ulong2* z61, __global const OT61* o61, __global const uint2* z31, __global const OT31* o31,
                     __global const uchar* width, __global int* x, __global ulong2* carryOut, const uint mulc) {
  uint b = get_global_id(0), m0 = b * CARRY_BLOCK;
  // the CRT values are independent of each other; only the carry chain is serial
  i128 val[CARRY_BLOCK];
  #pragma unroll
  for (uint i = 0; i < CARRY_BLOCK; i++) val[i] = value128(z61, o61, z31, o31, m0 + i);
  if (mulc != 1) {
    #pragma unroll
    for (uint i = 0; i < CARRY_BLOCK; i++) val[i] = mulsmall128(val[i], mulc);
  }
  carryBlock(val, width, x, carryOut, b);
}

#if defined(LOGR) && WOTF
// carry1 with the inverse weights computed on the fly (fast path)
__kernel void carry1w(__global const ulong2* z61, __global const FT61* ia61, __global const FT61* ib61, __global const uchar* se61,
                      __global const uint2* z31, __global const FT31* ia31, __global const FT31* ib31, __global const uchar* se31,
                      __global const uchar* width, __global int* x, __global ulong2* carryOut, const uint mulc) {
  uint b = get_global_id(0), m0 = b * CARRY_BLOCK;
  i128 val[CARRY_BLOCK];
  #pragma unroll
  for (uint i = 0; i < CARRY_BLOCK; i++) {
#if NPRIMES == 2
    val[i] = crt128(outw61(z61, ia61, ib61, se61, m0 + i), outw31(z31, ia31, ib31, se31, m0 + i));
#else
    val[i] = crt128(outw61(z61, ia61, ib61, se61, m0 + i), 0);
#endif
  }
  if (mulc != 1) {
    #pragma unroll
    for (uint i = 0; i < CARRY_BLOCK; i++) val[i] = mulsmall128(val[i], mulc);
  }
  carryBlock(val, width, x, carryOut, b);
}
#endif

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
