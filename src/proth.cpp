#include "proth.h"
#include "mp.h"
#include <chrono>
#include <cstdio>
#include <cmath>
#include <fstream>

// Registers
enum { RX = 0, RD = 1, RT = 2, RX0 = 3, NREGS = 4 };

u32 prothBase(u32 k, u64 n) {
  mpz_class P = k; P <<= n; P += 1;
  static const u32 primes[] = { 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151 };
  for (u32 a : primes) if (mpz_kronecker_ui(P.get_mpz_t(), a) == -1) return a;   // (P|a) = (a|P) as P = 1 mod 4
  throw std::runtime_error("no small base with Jacobi symbol -1 (is P a square?)");
}

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

// ---- checkpoint: verified (X, D) at an iteration that is a multiple of L
static const u32 CKPT_MAGIC = 0x43424C31;   // "CBL1"
static u64 fnv(const std::vector<i32>& v, u64 h) {
  for (i32 x : v) { h ^= (u32)x; h *= 1099511628211ULL; }
  return h;
}
static void saveCkpt(const std::string& path, const Layout& L, u32 base, u32 gl, u64 iter, const std::vector<i32>& X, const std::vector<i32>& D) {
  std::string tmp = path + ".tmp";
  FILE* f = fopen(tmp.c_str(), "wb");
  if (!f) throw std::runtime_error("cannot write checkpoint " + tmp);
  u64 hdr[8] = { CKPT_MAGIC, L.k, L.n, L.N, (u64)L.nPrimes, base, gl, iter };
  u64 sum = fnv(D, fnv(X, 1469598103934665603ULL ^ iter));
  bool ok = fwrite(hdr, sizeof hdr, 1, f) == 1 && fwrite(X.data(), 4, X.size(), f) == X.size() &&
            fwrite(D.data(), 4, D.size(), f) == D.size() && fwrite(&sum, 8, 1, f) == 1;
  ok = (fclose(f) == 0) && ok;
  if (!ok || rename(tmp.c_str(), path.c_str()) != 0) throw std::runtime_error("checkpoint write failed: " + path);
}
static bool loadCkpt(const std::string& path, const Layout& L, u32 base, u32 gl, u64& iter, std::vector<i32>& X, std::vector<i32>& D) {
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) return false;
  u64 hdr[8], sum = 0; X.resize(L.N); D.resize(L.N);
  bool ok = fread(hdr, sizeof hdr, 1, f) == 1 && fread(X.data(), 4, L.N, f) == L.N && fread(D.data(), 4, L.N, f) == L.N && fread(&sum, 8, 1, f) == 1;
  fclose(f);
  if (!ok || hdr[0] != CKPT_MAGIC || hdr[1] != L.k || hdr[2] != L.n || hdr[3] != L.N || hdr[4] != (u64)L.nPrimes || hdr[5] != base || hdr[6] != gl) return false;
  iter = hdr[7];
  return sum == fnv(D, fnv(X, 1469598103934665603ULL ^ iter));
}

ProthResult prothTest(Engine& e, const ProthOptions& opt) {
  const Layout& L = e.layout();
  const u64 total = L.n - 1;                         // squarings: y_0 = a^k, y_{n-1} = a^(k 2^(n-1))
  ProthResult R; R.base = prothBase(L.k, L.n);
  u32 gl = opt.gerbiczL ? opt.gerbiczL : (u32)std::max(4.0, std::min(1000.0, std::floor(std::sqrt((double)total / 2))));
  const u64 checkEvery = (u64)gl * gl;               // iterations between full Gerbicz verifications
  mpz_class P = modulus(L);
  double t0 = now(), tRep = t0;

  // x = y / k where y is the ordinary residue; 1/k == -2^n (mod P)
  mpz_class y0; mpz_ui_pow_ui(y0.get_mpz_t(), R.base, L.k);
  mpz_class x0 = (P - ((y0 << L.n) % P)) % P;
  std::vector<i32> X0 = fromMpz(L, x0), vx, vd;
  e.write(RX0, X0);

  u64 iter = 0;        // squarings applied to RX
  u64 good = 0;        // iteration of the last verified state (multiple of gl)
  std::vector<i32> goodX = X0, goodD = X0;
  if (!opt.checkpointPath.empty() && loadCkpt(opt.checkpointPath, L, R.base, gl, good, goodX, goodD)) {
    R.resumed = true;
    if (!opt.quiet) fprintf(stderr, "resuming from verified checkpoint at iteration %llu\n", (unsigned long long)good);
  }
  auto restore = [&]() { e.write(RX, goodX); e.write(RD, goodD); iter = good; };
  restore();

  // Gerbicz-Li. With D_t = X_0 o X_gl o ... o X_{t gl} and X_{(i+1)gl} = X_{i gl}^(o 2^gl):
  //     D_{t+1} = D_t o X_{(t+1)gl} = X_0 o D_t^(o 2^gl).
  // Comparing the two right-hand sides at one block boundary exposes an error made in ANY
  // squaring since the last verified state, at a cost of gl squarings per verification.
  const u64 lastFull = (total / gl) * gl;
  const u64 startIter = iter;
  while (iter < lastFull) {
    e.square(RX, gl); iter += gl;
    bool due = (iter - good) >= checkEvery || iter == lastFull;
    if (due) e.copy(RT, RD);                         // D_t
    e.mul(RD, RX);                                   // D_{t+1}
    if (opt.faultHook) opt.faultHook(e, iter);
    if (due) {
      e.square(RT, gl); e.mul(RT, RX0);              // X_0 o D_t^(2^gl)
      e.read(RT, vx); e.read(RD, vd);
      if (toMpz(L, vx) == toMpz(L, vd)) {
        R.checksPassed++;
        good = iter; e.read(RX, goodX); goodD = vd;
        if (!opt.checkpointPath.empty()) saveCkpt(opt.checkpointPath, L, R.base, gl, good, goodX, goodD);
      } else {
        R.rollbacks++;
        if (!opt.quiet) fprintf(stderr, "Gerbicz check FAILED at iteration %llu; rolling back to %llu\n", (unsigned long long)iter, (unsigned long long)good);
        if (R.rollbacks > 20) throw std::runtime_error("too many Gerbicz failures; hardware or software is unreliable");
        restore();
        continue;
      }
    }
    double t = now();
    if (!opt.quiet && t - tRep >= opt.reportSeconds) {
      tRep = t;
      double msit = 1e3 * (t - t0) / (double)std::max<u64>(1, iter - startIter);
      fprintf(stderr, "%u*2^%llu+1  %6.2f%%  iter %llu/%llu  %.3f ms/it  ETA %.1f h  checks ok %llu  rollbacks %llu\n", L.k, (unsigned long long)L.n,
              100.0 * iter / total, (unsigned long long)iter, (unsigned long long)total, msit, msit * (total - iter) / 3.6e6,
              (unsigned long long)R.checksPassed, (unsigned long long)R.rollbacks);
    }
  }

  // Tail (< gl squarings) is outside the Gerbicz chain: run it twice and compare.
  u64 tail = total - iter;
  std::vector<i32> f1, f2;
  for (int attempt = 0;; attempt++) {
    e.write(RX, goodX); e.square(RX, tail); e.read(RX, f1);
    e.write(RX, goodX); e.square(RX, tail); e.read(RX, f2);
    if (toMpz(L, f1) == toMpz(L, f2)) break;
    R.rollbacks++;
    if (attempt > 5) throw std::runtime_error("tail squarings do not reproduce");
  }
  iter = total;

  mpz_class xf = toMpz(L, f1);
  mpz_class y = (xf * L.k) % P;                      // ordinary residue a^((P-1)/2)
  R.prime = (y == P - 1);
  R.res64 = mpz_class(y & mpz_class("18446744073709551615")).get_ui();
  R.iterations = total; R.seconds = now() - t0;
  return R;
}
