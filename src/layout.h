// Digit layout and per-prime weight/twiddle tables for P = k*2^n + 1.
#pragma once
#include "field.h"
#include <vector>
#include <string>
#include <stdexcept>
#include <cmath>

// x = sum_{j<N} x_j 2^{s_j}. Word j has base 2^{width_j}; the top two words are reduced
// jointly modulo topBase = k*2^{n - s_{N-2}}, so the whole number wraps at exactly
// k*2^n == -1 (mod P) whatever the ratio of log2(k) to the word size.
struct Layout {
  u32 k = 0; u64 n = 0; size_t N = 0;
  int nPrimes = 2;                 // 2: GF(M61^2) x GF(M31^2), 92-bit CRT;  1: GF(M61^2) only
  std::vector<u32> s;              // bit position of each word
  std::vector<uint8_t> width;      // width_j = s_{j+1} - s_j  (j < N-1); width_{N-1} unused
  int topShift = 0; u64 topBase = 0;   // topBase = k << topShift, topShift = n - s_{N-2}
  double bitsPerWord = 0, boundBits = 0, modulusBits = 0;

  static constexpr int FRAC = 40;  // s_j = ceil(j*A / (N * 2^FRAC)), A ~ (n + log2 k) * 2^FRAC

  // Throws std::runtime_error if (k, n, N, nPrimes) cannot be represented or the worst-case
  // convolution output could reach half the CRT modulus.
  Layout(u32 k, u64 n, size_t N, int nPrimes);

  // Smallest power-of-two N that is provably safe.
  static size_t chooseN(u32 k, u64 n, int nPrimes);
};

// Tables for one field. `fold` selects the structure:
//   fold:  -k*2^n is a non-residue in GF(q); z_j = W1_j x_j + W2_j x_{j+M}
//   real:  -k*2^n is a residue;              z_j = a_{2j} x_{2j} + i a_{2j+1} x_{2j+1}, conjugate-pair untangle
template <class F> struct Tables {
  typedef typename F::T T; typedef typename F::C C;
  bool fold = false; size_t M = 0;
  std::vector<C> w;                // stage twiddles: w[h + j] = omega_{2h}^j, h = 1,2,4..M/2
  std::vector<T> a, ai;            // real: forward / inverse weights (N each); ai includes k/(4M)
  std::vector<C> tw;               // real: omega_M^{brev(p)} for the M/2 conjugate pairs
  std::vector<C> W1, W2, U, V;     // fold: M each; U, V include k/M
  explicit Tables(const Layout& L);
};

inline size_t brev(size_t x, int bits) {
  size_t r = 0;
  for (int i = 0; i < bits; i++) { r = (r << 1) | (x & 1); x >>= 1; }
  return r;
}
inline int ilog2(size_t x) { int r = 0; while (x > 1) { x >>= 1; r++; } return r; }
