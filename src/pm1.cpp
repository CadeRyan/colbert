#include "pm1.h"
#include "mp.h"
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <numeric>
#ifdef _WIN32
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static bool replaceFile(const std::string& from, const std::string& to) {
  return MoveFileExA(from.c_str(), to.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != 0;
}
#else
static bool replaceFile(const std::string& from, const std::string& to) { return rename(from.c_str(), to.c_str()) == 0; }
#endif

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

// ------------------------------------------------------------------ primes

static std::vector<u32> smallPrimes(u32 limit) {
  std::vector<uint8_t> c(limit + 1, 0); std::vector<u32> p;
  for (u32 i = 2; i <= limit; i++) if (!c[i]) { p.push_back(i); for (u64 j = (u64)i * i; j <= limit; j += i) c[j] = 1; }
  return p;
}

// primes in (lo, hi], in increasing order, a segment at a time
struct PrimeRange {
  u64 lo, hi, segLo; std::vector<u32> base; std::vector<u64> buf; size_t at = 0;
  PrimeRange(u64 lo_, u64 hi_) : lo(lo_), hi(hi_), segLo(lo_ + 1) { base = smallPrimes((u32)std::sqrt((double)hi) + 2); }
  bool next(u64& q) {
    while (at == buf.size()) {
      if (segLo > hi) return false;
      const u64 S = 1 << 20, a = segLo, b = std::min(hi, segLo + S - 1);
      std::vector<uint8_t> comp(b - a + 1, 0);
      for (u32 p : base) {
        if ((u64)p * p > b) break;
        for (u64 j = std::max((u64)p * p, (a + p - 1) / p * p); j <= b; j += p) comp[j - a] = 1;
      }
      buf.clear(); at = 0;
      for (u64 v = a; v <= b; v++) if (v >= 2 && !comp[v - a]) buf.push_back(v);
      segLo = b + 1;
    }
    q = buf[at++];
    return true;
  }
};

static u64 primeCount(u64 lo, u64 hi) { PrimeRange r(lo, hi); u64 q, c = 0; while (r.next(q)) c++; return c; }

// E = prod p^floor(log_p B1), by a product tree
static mpz_class stage1Exponent(u64 B1) {
  std::vector<mpz_class> v;
  for (u32 p : smallPrimes((u32)B1)) { u64 q = p; while (q <= B1 / p) q *= p; v.push_back(mpz_class((unsigned long)q)); }
  if (v.empty()) return 1;
  while (v.size() > 1) {
    std::vector<mpz_class> w((v.size() + 1) / 2);
    for (size_t i = 0; i < w.size(); i++) w[i] = 2 * i + 1 < v.size() ? v[2 * i] * v[2 * i + 1] : v[2 * i];
    v.swap(w);
  }
  return v[0];
}

static u32 phi(u32 D) { u32 c = 0; for (u32 r = 1; r < D; r++) if (std::gcd(r, D) == 1) c++; return c; }

u32 pm1ChooseD(size_t slots) {
  for (u32 D : { 2310u, 1050u, 630u, 420u, 330u, 210u, 120u, 90u, 60u, 30u, 6u })
    if ((size_t)phi(D) + 1 <= slots) return D;
  return 0;
}

size_t pm1DefaultBudget(const Engine& e) { return std::min<size_t>(e.deviceMemory() / 4, (size_t)2 << 30); }

// ------------------------------------------------------------------ checkpoint

static const u64 PM1_MAGIC = 0x314D5043;   // "CPM1"
static u64 fnv(const std::vector<i32>& v, u64 h) { for (i32 x : v) { h ^= (u32)x; h *= 1099511628211ULL; } return h; }

static void saveCkpt(const std::string& path, const Layout& L, u64 B1, u64 B2, int stage, u64 pos, const std::vector<std::vector<i32>>& vs) {
  std::string tmp = path + ".tmp";
  FILE* f = fopen(tmp.c_str(), "wb");
  if (!f) throw std::runtime_error("cannot write checkpoint " + tmp);
  u64 hdr[10] = { PM1_MAGIC, L.k, L.n, L.N, (u64)L.nPrimes, B1, B2, (u64)stage, pos, vs.size() };
  u64 sum = 1469598103934665603ULL ^ pos;
  bool ok = fwrite(hdr, sizeof hdr, 1, f) == 1;
  for (auto& v : vs) { ok = ok && fwrite(v.data(), 4, v.size(), f) == v.size(); sum = fnv(v, sum); }
  ok = ok && fwrite(&sum, 8, 1, f) == 1;
  ok = (fclose(f) == 0) && ok;
  if (!ok || !replaceFile(tmp, path)) throw std::runtime_error("checkpoint write failed: " + path);
}

static std::string loadCkpt(const std::string& path, const Layout& L, u64 B1, int& stage, u64& pos, std::vector<std::vector<i32>>& vs) {
  FILE* f = fopen(path.c_str(), "rb");
  if (!f) return "none";
  u64 hdr[10], sum = 0;
  bool ok = fread(hdr, sizeof hdr, 1, f) == 1 && hdr[9] >= 1 && hdr[9] <= 2;
  if (ok) {
    vs.assign(hdr[9], std::vector<i32>(L.N));
    for (auto& v : vs) ok = ok && fread(v.data(), 4, L.N, f) == L.N;
    ok = ok && fread(&sum, 8, 1, f) == 1;
  }
  fclose(f);
  if (!ok) return "rejected: file is truncated or from a different transform size";
  if (hdr[0] != PM1_MAGIC) return "rejected: not a colbert P-1 checkpoint";
  if (hdr[1] != L.k || hdr[2] != L.n) return "rejected: checkpoint is for a different number";
  if (hdr[3] != L.N || hdr[4] != (u64)L.nPrimes) return "rejected: transform size or prime count differs";
  if (hdr[5] != B1) return "rejected: B1 differs (checkpoint " + std::to_string(hdr[5]) + ")";
  u64 s = 1469598103934665603ULL ^ hdr[8];
  for (auto& v : vs) s = fnv(v, s);
  if (s != sum) return "rejected: checksum mismatch (corrupt file)";
  stage = (int)hdr[7]; pos = hdr[8];
  return "resumed";
}

// ------------------------------------------------------------------ the run

Pm1Result pm1Run(Engine& e, const Pm1Options& o) {
  const Layout& L = e.layout();
  const mpz_class P = modulus(L);
  enum { RX = 0, RACC = 1, RG = 2, RXG = 3, RT = 4, RY2 = 5 };
  Pm1Result R; R.B1 = o.B1; R.B2 = std::max(o.B2, o.B1);
  const double t0 = now();
  if (o.B1 < 2) throw std::runtime_error("P-1 needs B1 >= 2");

  // representatives in the engine's o-domain: rep(v) = v / k = -v 2^n (mod P); value = k rep
  mpz_class two_n = mpz_class(1) << L.n;
  auto rep = [&](const mpz_class& v) { mpz_class r = (P - (v * two_n) % P) % P; return fromMpz(L, r); };
  auto value = [&](int reg) { std::vector<i32> d; e.read(reg, d); mpz_class x = toMpz(L, d); return mpz_class((x * L.k) % P); };
  auto gcdFactor = [&](const mpz_class& v) -> std::string {
    mpz_class g; mpz_gcd(g.get_mpz_t(), v.get_mpz_t(), P.get_mpz_t());
    return (g > 1 && g < P) ? g.get_str() : std::string();
  };

  const mpz_class E = stage1Exponent(o.B1);
  const u64 nbits = mpz_sizeinbase(E.get_mpz_t(), 2);
  size_t budget = o.memoryBudget ? o.memoryBudget : pm1DefaultBudget(e);
  R.D = R.B2 > R.B1 ? pm1ChooseD(budget / e.spectrumBytes()) : 0;
  if (R.B2 > R.B1 && !R.D) throw std::runtime_error("not enough device memory for P-1 stage 2");

  Pm1Status st; st.B1 = R.B1; st.B2 = R.B2; st.D = R.D;
  const u64 units1 = nbits - 1;
  u64 primes2 = R.B2 > R.B1 ? primeCount(R.B1, R.B2) : 0;
  const u64 units2 = R.B2 > R.B1 ? primes2 + (R.B2 - R.B1) / R.D + R.D / 2 : 0;
  st.total = units1 + units2;

  int stage = 1; u64 pos = 1;                    // stage 1: exponent bits consumed (the top bit starts it)
  std::vector<std::vector<i32>> vs;
  st.checkpoint = "new";
  if (!o.checkpointPath.empty()) {
    std::string c = loadCkpt(o.checkpointPath, L, o.B1, stage, pos, vs);
    if (c == "resumed") st.checkpoint = c;
    else if (c != "none") {
      replaceFile(o.checkpointPath, o.checkpointPath + ".rejected");
      st.checkpoint = c + " (kept as " + o.checkpointPath + ".rejected)";
      stage = 1; pos = 1; vs.clear();
    }
  }

  double tEv = now(), tCk = now(), tRep = now(); u64 doneEv = 0, doneStart = 0;
  auto emit = [&](const char* ev) {
    if (!o.onEvent) return;
    double t = now();
    st.elapsed = t - t0; st.stage = stage;
    u64 here = st.done > doneStart ? st.done - doneStart : 0;
    st.msPerUnit = here ? 1e3 * (t - t0) / (double)here : 0;
    if (st.done > doneEv && t > tEv) st.msPerUnitRecent = 1e3 * (t - tEv) / (double)(st.done - doneEv);
    if (!strcmp(ev, "progress")) { tEv = t; doneEv = st.done; }
    o.onEvent(ev, st);
  };
  auto tick = [&]() {
    double t = now();
    if (o.onEvent && t - tEv >= o.eventSeconds) emit("progress");
    if (!o.quiet && t - tRep >= o.reportSeconds) {
      tRep = t;
      double ms = 1e3 * (t - t0) / (double)std::max<u64>(1, st.done - doneStart);
      fprintf(stderr, "P-1 %u*2^%llu+1  stage %d  %6.2f%%  %.3f ms/unit  ETA %.1f h\n", L.k, (unsigned long long)L.n, stage,
              100.0 * st.done / std::max<u64>(1, st.total), ms, ms * (st.total - std::min(st.total, st.done)) / 3.6e6);
    }
  };
  auto stopNow = [&]() { return o.stopRequested && o.stopRequested(); };

  // ---------------------------------------------------------------- stage 1
  if (stage == 1) {
    if (vs.empty()) e.write(RX, rep(3)); else e.write(RX, vs[0]);
    st.done = doneStart = doneEv = pos - 1;
    emit("start");
    std::vector<u32> mults;
    while (pos < nbits) {
      u64 chunk = std::min<u64>(1024, nbits - pos);
      mults.resize(chunk);
      for (u64 i = 0; i < chunk; i++) mults[i] = mpz_tstbit(E.get_mpz_t(), nbits - 1 - (pos + i)) ? 3 : 1;
      e.squareMul(RX, mults);
      pos += chunk; st.done += chunk;
      tick();
      bool stop = stopNow();
      if (!o.checkpointPath.empty() && (stop || now() - tCk >= o.checkpointSeconds) && pos < nbits) {
        std::vector<i32> d; e.read(RX, d);
        saveCkpt(o.checkpointPath, L, R.B1, R.B2, 1, pos, { d });
        tCk = now();
      }
      if (stop && pos < nbits) {
        if (o.checkpointPath.empty()) throw std::runtime_error("stop requested without a checkpoint directory");
        R.stopped = true; R.seconds = now() - t0; emit("stopped"); return R;
      }
    }
    mpz_class y = value(RX);
    if (o.keepValues) R.y = y;
    R.factor = gcdFactor(y - 1);
    if (!R.factor.empty() || R.B2 <= R.B1) { R.stage = R.factor.empty() ? 0 : 1; R.seconds = now() - t0; return R; }
    stage = 2; pos = R.B1;                       // stage 2: every prime <= pos is done
    std::vector<i32> d; e.read(RX, d);
    e.write(RACC, rep(1));
    if (!o.checkpointPath.empty()) { std::vector<i32> a; e.read(RACC, a); saveCkpt(o.checkpointPath, L, R.B1, R.B2, 2, pos, { a, d }); tCk = now(); }
  } else {
    // resumed in stage 2: vs = { acc, y }
    e.write(RACC, vs[0]); e.write(RX, vs[1]);
    st.done = doneStart = doneEv = units1 + (pos > R.B1 ? primeCount(R.B1, std::min(pos, R.B2)) : 0);
    emit("start");
    if (o.keepValues) R.y = value(RX);
  }

  // ---------------------------------------------------------------- stage 2
  if (pos < R.B2) {
    int want = (int)phi(R.D) + 1;
    int got = e.allocSlots(want, budget);
    if (got < want) { R.D = pm1ChooseD((size_t)got); want = (int)phi(R.D) + 1; if (!R.D || e.allocSlots(want, budget) < want) throw std::runtime_error("not enough device memory for P-1 stage 2"); }
    st.D = R.D;
    emit("stage2");
    const u32 D = R.D; const int slotX = want - 1;
    std::vector<int> slotOf(D, -1);
    // baby steps: spectra of y^r for r < D coprime to D; G = y^D
    e.copy(RY2, RX); e.mul(RY2, RX);
    e.copy(RT, RX);
    int s = 0;
    for (u32 r = 1; r < D; r += 2) {
      if (std::gcd(r, D) == 1) { slotOf[r] = s; e.toSpectrum(s++, RT); }
      if (r == D - 1) { e.copy(RG, RT); e.mul(RG, RX); }
      else e.mul(RT, RY2);
      st.done++;
    }
    tick();
    // giant steps: X = y^(mD); each prime q = mD - r multiplies acc by (X - y^r)
    PrimeRange pr(pos, R.B2);
    u64 q, mCur = 0;
    while (pr.next(q)) {
      u64 m = q / D + 1;
      if (m != mCur) {
        if (mCur && (stopNow() || (!o.checkpointPath.empty() && now() - tCk >= o.checkpointSeconds))) {
          // every prime below mCur*D is done
          if (o.checkpointPath.empty()) throw std::runtime_error("stop requested without a checkpoint directory");
          std::vector<i32> a, d; e.read(RACC, a); e.read(RX, d);
          saveCkpt(o.checkpointPath, L, R.B1, R.B2, 2, mCur * D - 1, { a, d });
          tCk = now();
          if (stopNow()) { R.stopped = true; R.seconds = now() - t0; emit("stopped"); return R; }
        }
        if (!mCur || m - mCur > 64) {            // X = G^m
          e.copy(RXG, RG);
          for (int b = 62 - __builtin_clzll(m) + 1; b-- > 0;) { e.square(RXG, 1); if ((m >> b) & 1) e.mul(RXG, RG); }
        } else {
          for (; mCur < m; mCur++) { e.mul(RXG, RG); st.done++; }
        }
        mCur = m;
        e.toSpectrum(slotX, RXG);
      }
      e.mulDiff(RACC, slotX, slotOf[m * D - q]);
      st.done++;
      tick();
    }
    e.allocSlots(0, 0);
  }
  mpz_class acc = value(RACC);
  if (o.keepValues) R.acc = acc;
  R.factor = gcdFactor(acc);
  R.stage = R.factor.empty() ? 0 : 2;
  R.seconds = now() - t0;
  return R;
}

// ------------------------------------------------------------------ bounds

// Dickman's rho on [0, 40], step 1/RH
static const int RH = 1000;
static const std::vector<double>& rhoTable() {
  static std::vector<double> t;
  if (!t.empty()) return t;
  t.resize(40 * RH + 1);
  for (int i = 0; i <= 40 * RH; i++) {
    double u = (double)i / RH;
    if (u <= 1) t[i] = 1;
    else if (u <= 2) t[i] = 1 - std::log(u);
    else t[i] = t[i - 1] - 0.5 / RH * (t[i - 1 - RH] / (u - 1.0 / RH) + t[i - RH] / u);   // rho' = -rho(u-1)/u
  }
  return t;
}
static double rho(double u) {
  if (u <= 1) return 1;
  if (u >= 40) return 0;
  const auto& t = rhoTable(); double x = u * RH; int i = (int)x; double f = x - i;
  return t[i] * (1 - f) + t[std::min(i + 1, 40 * RH)] * f;
}
// probability that a number of log_B1 size `a` is B1-smooth but for one prime factor below B1^b
static double sigma(double a, double b) {
  if (a <= 1) return 1;
  double s = rho(a), hi = std::min(a, b);
  if (hi > 1) {
    const int n = 200; double h = (hi - 1) / n, acc = 0;
    for (int i = 0; i <= n; i++) { double t = 1 + i * h, w = (i == 0 || i == n) ? 1 : (i % 2 ? 4 : 2); acc += w * rho(a - t) / t; }
    s += acc * h / 3;
  }
  return std::min(1.0, s);
}

double pm1Probability(double B1, double B2, double sieveBits) {
  if (B1 < 2) return 0;
  double lb = std::log(B1), b = std::log(std::max(B2, B1)) / lb, p = 0;
  // a factor f with 2^(j-1) <= f < 2^j exists with probability ~1/j (Mertens), and is found
  // when (f - 1)/2 is (B1, B2)-smooth. The sum is the expected number of factors found; the
  // chance of at least one is 1 - exp(-sum).
  for (int j = (int)std::ceil(sieveBits) + 1; j < 1000; j++) {
    double term = sigma((j - 2) * std::log(2.0) / lb, b) / j;
    p += term;
    if (term < 1e-12) break;
  }
  return 1 - std::exp(-p);
}

static double piApprox(double x) { if (x < 3) return 0; double l = std::log(x); return x / l * (1 + 1 / l + 2 / (l * l)); }

double pm1Cost(double B1, double B2, u32 D) {
  double c = B1 / std::log(2.0);                          // bits of E: one squaring each
  if (B2 > B1 && D) c += 1.1 * (piApprox(B2) - piApprox(B1)) + 2.2 * (B2 - B1) / D + D / 2.0;
  return c;
}

Pm1Plan pm1Choose(double testCost, double sieveBits, u32 D) {
  Pm1Plan best;
  for (double B1 = 1e4; B1 <= 2e8; B1 *= 1.1) {
    for (double r : { 1.0, 5.0, 10.0, 20.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0 }) {
      if (r > 1 && !D) break;
      double B2 = B1 * r, p = pm1Probability(B1, B2, sieveBits), c = pm1Cost(B1, B2, D), s = p * testCost - c;
      if (s > best.saving) { best.B1 = (u64)B1; best.B2 = (u64)B2; best.probability = p; best.cost = c; best.saving = s; }
    }
  }
  // round to two significant digits
  auto round2 = [](u64 v) { if (v < 100) return v; u64 m = 1; while (v / m >= 100) m *= 10; return (v + m / 2) / m * m; };
  if (best.B1) {
    best.B1 = round2(best.B1); best.B2 = std::max(best.B1, round2(best.B2));
    best.probability = pm1Probability((double)best.B1, (double)best.B2, sieveBits); best.cost = pm1Cost((double)best.B1, (double)best.B2, D);
    best.saving = best.probability * testCost - best.cost;
  }
  return best;
}
