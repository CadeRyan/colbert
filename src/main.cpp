// colbert: Proth tests for the Sierpinski problem with a zero-padding-free weighted NTT.
#include "proth.h"
#include "pm1.h"
#include "mp.h"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <random>
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>
#include <cstdarg>

#ifndef COLBERT_VERSION
#define COLBERT_VERSION "unknown"
#endif
// Version of the machine interface (--json events, exit codes, commands). Bump it only for
// changes that would break a program reading the events; adding fields does not need a bump.
static const int PROTOCOL = 1;

static bool g_json = false;          // --json: JSON Lines events on stdout, human text on stderr only

static std::string quote(const std::string& s) {
  std::string o = "\"";
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += (char)c; }
    else if (c == '\n') o += "\\n";
    else if (c == '\t') o += "\\t";
    else if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; }
    else o += (char)c;
  }
  return o + "\"";
}
// Minimal JSON object builder: J().s("event", "x").u("k", 3).str()
struct J {
  std::string b = "{";
  J& key(const char* k) { if (b.size() > 1) b += ','; b += quote(k); b += ':'; return *this; }
  J& s(const char* k, const std::string& v) { key(k); b += quote(v); return *this; }
  J& u(const char* k, unsigned long long v) { key(k); b += std::to_string(v); return *this; }
  J& i(const char* k, long long v) { key(k); b += std::to_string(v); return *this; }
  J& f(const char* k, double v) { key(k); char t[32]; snprintf(t, sizeof t, "%.6g", std::isfinite(v) ? v : 0.0); b += t; return *this; }
  J& t(const char* k, bool v) { key(k); b += v ? "true" : "false"; return *this; }
  J& raw(const char* k, const std::string& v) { key(k); b += v; return *this; }
  std::string str() const { return b + "}"; }
};
static void emit(const J& j) { if (g_json) { printf("%s\n", j.str().c_str()); fflush(stdout); } }

// selftest lines: human text on stdout (as before), or one JSON event each
static void report(bool ok, const char* fmt, ...) {
  char buf[512]; va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
  if (g_json) emit(J().s("event", "check").t("ok", ok).s("text", buf));
  else { printf("%s  %s\n", ok ? "ok  " : "FAIL", buf); fflush(stdout); }
}

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

struct Args {
  std::string cmd, backend = "cpu", ckptDir, worktodo = "worktodo.txt", results = "results.jsonl", stopFile;
  std::vector<std::string> pos;
  int device = -1, primes = 2; size_t N = 0; u32 gl = 0; bool verbose = false;
  double eventSeconds = 5, benchSeconds = 0;
  // P-1: explicit bounds, or chosen from the sieve depth and the value of a test
  u64 b1 = 0, b2 = 0; double sieveBits = 32, testsSaved = 1.05, memoryMB = 0;
};

// spectrum memory for P-1 stage 2, and the plan the engine would follow
static size_t pm1Budget(const Args& a, const Engine& e) { return a.memoryMB > 0 ? (size_t)(a.memoryMB * 1048576.0) : pm1DefaultBudget(e); }
static Pm1Plan pm1PlanFor(const Args& a, u64 n, size_t spectrumBytes, size_t budget) {
  if (a.b1) {
    Pm1Plan p; p.B1 = a.b1; p.B2 = std::max(a.b2, a.b1);
    u32 D = pm1ChooseD(budget / spectrumBytes);
    p.probability = pm1Probability((double)p.B1, (double)p.B2, a.sieveBits); p.cost = pm1Cost((double)p.B1, (double)p.B2, D);
    p.saving = p.probability * a.testsSaved * (double)n - p.cost;
    return p;
  }
  return pm1Choose(a.testsSaved * (double)n, a.sieveBits, pm1ChooseD(budget / spectrumBytes));
}

static std::unique_ptr<Engine> makeEngine(const Args& a, u32 k, u64 n, int nRegs) {
  size_t N = a.N ? a.N : Layout::chooseN(k, n, a.primes);
  Layout L(k, n, N, a.primes);
  if (a.backend == "cpu") return makeCpuEngine(L, nRegs);
  if (a.backend == "ocl") return makeOclEngine(L, nRegs, a.device, a.verbose);
  throw std::runtime_error("unknown backend " + a.backend);
}

static void describe(const Engine& e) {
  const Layout& L = e.layout();
  std::string d = e.detail();
  fprintf(stderr, "%u*2^%llu+1: N=%zu words (%zu complex points/prime), %.2f bits/word, worst-case %.1f of %.1f bits, backend %s%s\n",
          L.k, (unsigned long long)L.n, L.N, L.N / 2, L.bitsPerWord, L.boundBits, L.modulusBits - 1, e.name().c_str(), d.empty() ? "" : (", " + d).c_str());
}

// --- selftest: products against GMP, both structures, both prime sets; then small Proth primes
static int selftest(const Args& a) {
  std::mt19937_64 rng(42);
  gmp_randclass gr(gmp_randinit_mt); gr.seed(7);
  int fails = 0, cases = 0;
  struct Case { u32 k; u64 n; };
  std::vector<Case> cs = { {21181, 2300}, {22699, 5000}, {24737, 9001}, {55459, 20011}, {67607, 40000}, {3, 1000}, {10223, 3333},
                           {46157, 100003}, {67607, 300007}, {21181, 1000003},
                           {21181, 300}, {67607, 2301}, {46157, 9300}, {55459, 4600}, {3, 2000}, {10223, 150000} };
  for (int primes : { 1, 2 }) for (const Case& c : cs) {
    Args b = a; b.primes = primes; b.N = 0;
    std::unique_ptr<Engine> e;
    try { e = makeEngine(b, c.k, c.n, 3); }
    catch (const std::runtime_error&) { if (primes == 1) continue; throw; }   // 61 bits alone rarely fit
    const Layout& L = e->layout();
    mpz_class P = modulus(L);
    bool ok = true;
    for (int rep = 0; rep < 3 && ok; rep++) {
      mpz_class x = gr.get_z_range(P), y = gr.get_z_range(P);
      if (rep == 2) { x = P - 1; y = P - 1; }                       // extreme operand
      e->write(0, fromMpz(L, x)); e->write(1, fromMpz(L, y));
      std::vector<i32> d;
      e->read(0, d); ok = ok && toMpz(L, d) == x;                   // round trip
      e->mul(0, 1); e->read(0, d);
      mpz_class want = (x * y % P) * L.k % P;
      ok = ok && toMpz(L, d) == want;
      e->square(1, 3); e->read(1, d);                               // y -> k^7 y^8
      mpz_class w2 = y; for (int i = 0; i < 3; i++) w2 = (w2 * w2 % P) * L.k % P;
      ok = ok && toMpz(L, d) == w2;
    }
    cases++; if (!ok) fails++;
    report(ok, "product check k=%u n=%llu N=%zu primes=%d bits/word=%.2f", c.k, (unsigned long long)c.n, L.N, primes, L.bitsPerWord);
  }
  // Proth verdicts against GMP on small numbers (primes and composites, k of the real size)
  std::vector<Case> pr;
  for (u32 k = 20001; k < 70000 && pr.size() < 12; k += 2)
    for (u64 n = 400; n < 440; n++) {
      mpz_class P = k; P <<= n; P += 1;
      if (mpz_probab_prime_p(P.get_mpz_t(), 10)) { pr.push_back({ k, n }); pr.push_back({ k, n + 1 }); break; }
    }
  for (u64 n : { 1000, 1001, 2000, 4001 }) for (u32 k : { 21181u, 22699u, 24737u, 55459u, 67607u }) pr.push_back({ k, n });
  for (const Case& c : pr) {
    Args b = a; b.N = 0;
    auto e = makeEngine(b, c.k, c.n, 4);
    ProthOptions o; o.quiet = true;
    ProthResult r = prothTest(*e, o);
    mpz_class P = modulus(e->layout()), y, ex = (P - 1) / 2, base = r.base;
    mpz_powm(y.get_mpz_t(), base.get_mpz_t(), ex.get_mpz_t(), P.get_mpz_t());
    bool want = y == P - 1;
    u64 wres = mpz_class(y & mpz_class("18446744073709551615")).get_ui();
    bool ok = want == r.prime && wres == r.res64 && r.rollbacks == 0;
    cases++; if (!ok) fails++;
    report(ok, "proth k=%u n=%llu base=%u -> %s res64=%016llx (gmp %016llx) checks=%llu", c.k, (unsigned long long)c.n, r.base,
           r.prime ? "PRIME" : "composite", (unsigned long long)r.res64, (unsigned long long)wres, (unsigned long long)r.checksPassed);
  }
  // injected fault: the Gerbicz check must catch it, roll back, and still give the right answer
  {
    Args b = a; b.N = 0;
    auto e = makeEngine(b, 22699, 6000, 4);
    ProthOptions o; o.quiet = true; o.gerbiczL = 20;
    bool fired = false;
    o.faultHook = [&](Engine& en, u64 it) { if (!fired && it >= 3000) { fired = true; std::vector<i32> d; en.read(0, d); d[5] ^= 4; en.write(0, d); } };
    ProthResult r = prothTest(*e, o);
    mpz_class P = modulus(e->layout()), y, ex = (P - 1) / 2, base = r.base;
    mpz_powm(y.get_mpz_t(), base.get_mpz_t(), ex.get_mpz_t(), P.get_mpz_t());
    u64 wres = mpz_class(y & mpz_class("18446744073709551615")).get_ui();
    bool ok = fired && r.rollbacks == 1 && wres == r.res64;
    cases++; if (!ok) fails++;
    report(ok, "fault injection: rollbacks=%llu, final residue %s", (unsigned long long)r.rollbacks, wres == r.res64 ? "correct" : "WRONG");
  }
  // P-1: factors found in stage 1, only in stage 2, and none; stage values against GMP
  {
    struct PC { u32 k; u64 n, B1, B2; const char* factor; int stage; double memMB; };
    // (no factor below 1000, like real candidates; found with plain Python, tools/pm1_cases.py)
    const PC pcs[] = { { 21181, 2108, 600, 600, "275024987", 1, 0 }, { 21181, 2132, 600, 30000, "5718863", 2, 0 },
                       { 21181, 2132, 600, 30000, "5718863", 2, 0.05 },          // tiny budget: a small D
                       { 21181, 2060, 600, 30000, "", 0, 0 }, { 55459, 30226, 1000, 60000, "25498789004617", 2, 0 } };
    for (const PC& c : pcs) {
      Args b = a; b.N = 0;
      auto e = makeEngine(b, c.k, c.n, 6);
      Pm1Options o; o.B1 = c.B1; o.B2 = c.B2; o.quiet = true; o.keepValues = true;
      if (c.memMB > 0) o.memoryBudget = (size_t)(c.memMB * 1048576.0); else o.memoryBudget = (size_t)64 << 20;
      Pm1Result r = pm1Run(*e, o);
      const Layout& L = e->layout();
      mpz_class P = modulus(L), E = 1, y;
      for (u64 p = 2; p <= c.B1; p++) { bool pr = true; for (u64 d = 2; d * d <= p; d++) if (p % d == 0) { pr = false; break; } if (!pr) continue; u64 q = p; while (q <= c.B1 / p) q *= p; E *= (unsigned long)q; }
      mpz_class three = 3; mpz_powm(y.get_mpz_t(), three.get_mpz_t(), E.get_mpz_t(), P.get_mpz_t());
      bool ok = r.y == y && r.stage == c.stage;
      if (c.factor[0]) ok = ok && r.factor == c.factor;
      else ok = ok && r.factor.empty();
      if (r.stage != 1 && c.B2 > c.B1 && r.D) {      // the stage-2 product itself
        mpz_class acc = 1, yD, ym, yr; mpz_class Dz = (unsigned long)r.D;
        for (u64 q = c.B1 + 1; q <= c.B2; q++) {
          bool pr = q > 1; for (u64 d = 2; d * d <= q; d++) if (q % d == 0) { pr = false; break; } if (!pr) continue;
          u64 m = q / r.D + 1, rr = m * r.D - q;
          mpz_class me = (unsigned long)(m * r.D), re = (unsigned long)rr;
          mpz_powm(ym.get_mpz_t(), y.get_mpz_t(), me.get_mpz_t(), P.get_mpz_t()); mpz_powm(yr.get_mpz_t(), y.get_mpz_t(), re.get_mpz_t(), P.get_mpz_t());
          acc = acc * (ym - yr) % P;
        }
        if (acc < 0) acc += P;
        ok = ok && acc == r.acc;
      }
      cases++; if (!ok) fails++;
      report(ok, "P-1 k=%u n=%llu B1=%llu B2=%llu D=%u -> %s (stage %d)", c.k, (unsigned long long)c.n, (unsigned long long)c.B1, (unsigned long long)c.B2, r.D,
             r.factor.empty() ? "no factor" : r.factor.c_str(), r.stage);
    }
  }
  if (g_json) emit(J().s("event", "selftest").u("passed", cases - fails).u("total", cases).t("ok", fails == 0).s("backend", a.backend).s("engine", COLBERT_VERSION));
  else printf("%d/%d checks passed on backend %s\n", cases - fails, cases, a.backend.c_str());
  return fails ? 1 : 0;
}

static std::string jsonResult(const Engine& e, const ProthResult& r) {
  const Layout& L = e.layout();
  char buf[600];
  snprintf(buf, sizeof buf, "{\"k\":%u,\"n\":%llu,\"result\":\"%s\",\"base\":%u,\"res64\":\"%016llx\",\"N\":%zu,\"iterations\":%llu,\"gerbicz_ok\":%llu,\"rollbacks\":%llu,\"seconds\":%.1f,\"backend\":%s,\"engine\":%s}",
           L.k, (unsigned long long)L.n, r.prime ? "PRIME" : "composite", r.base, (unsigned long long)r.res64, L.N, (unsigned long long)r.iterations,
           (unsigned long long)r.checksPassed, (unsigned long long)r.rollbacks, r.seconds, quote(e.name()).c_str(), quote(COLBERT_VERSION).c_str());
  return buf;
}


static bool fileExists(const std::string& p) { FILE* f = fopen(p.c_str(), "rb"); if (f) fclose(f); return f != nullptr; }

// P-1 on one number. Returns 0 when finished (factor or not), 3 when stopped by --stop-file.
static int runPm1(const Args& a, u32 k, u64 n) {
  auto e = makeEngine(a, k, n, 6);
  describe(*e);
  const Layout& L = e->layout();
  size_t budget = pm1Budget(a, *e);
  Pm1Plan plan = pm1PlanFor(a, n, e->spectrumBytes(), budget);
  const std::string backend = e->name();
  auto resultLine = [&](const Pm1Result* r) {
    J j; j.u("k", k).u("n", n).raw("pm1", J().u("b1", plan.B1).u("b2", plan.B2).str());
    if (r && !r->factor.empty()) j.s("factor", r->factor).i("stage", r->stage); else j.raw("factor", "null");
    if (r) j.u("D", r->D).f("seconds", r->seconds);
    j.u("N", L.N).s("backend", backend).s("engine", COLBERT_VERSION);
    return j;
  };
  if (!plan.B1) {
    fprintf(stderr, "P-1 does not pay for %u*2^%llu+1 at a sieve depth of %.0f bits; nothing to do\n", k, (unsigned long long)n, a.sieveBits);
    J j = resultLine(nullptr); j.t("skipped", true);
    if (g_json) { printf("{\"event\":\"pm1\",%s\n", j.str().c_str() + 1); fflush(stdout); }
    return 0;
  }
  Pm1Options o; o.B1 = plan.B1; o.B2 = plan.B2; o.memoryBudget = budget; o.eventSeconds = a.eventSeconds;
  if (!a.ckptDir.empty()) o.checkpointPath = a.ckptDir + "/" + std::to_string(k) + "_" + std::to_string(n) + ".pm1";
  if (!a.stopFile.empty()) { std::string sf = a.stopFile; o.stopRequested = [sf]() { return fileExists(sf); }; }
  fprintf(stderr, "P-1 with B1=%llu B2=%llu: %.2f%% chance of a factor for %.2f%% of a test\n", (unsigned long long)plan.B1, (unsigned long long)plan.B2,
          100 * plan.probability, 100 * plan.cost / (double)n);
  if (g_json) o.onEvent = [&](const char* ev, const Pm1Status& st) {
    J j; j.s("event", ev).s("phase", "pm1").u("k", k).u("n", n).i("stage", st.stage).u("iteration", st.done).u("total", st.total)
          .f("percent", 100.0 * st.done / std::max<u64>(1, st.total)).f("elapsed", st.elapsed).f("ms_per_iter", st.msPerUnit)
          .f("ms_per_iter_recent", st.msPerUnitRecent);
    double ms = st.msPerUnitRecent > 0 ? st.msPerUnitRecent : st.msPerUnit;
    if (ms > 0) j.f("eta_seconds", ms * (double)(st.total - std::min(st.total, st.done)) / 1e3);
    if (!strcmp(ev, "start"))
      j.u("N", L.N).i("primes", L.nPrimes).s("backend", backend).s("engine", COLBERT_VERSION).u("b1", st.B1).u("b2", st.B2).u("D", st.D)
       .f("probability", plan.probability).f("cost_iterations", plan.cost).s("checkpoint", st.checkpoint);
    if (!strcmp(ev, "stage2")) j.u("D", st.D);
    emit(j);
  };
  Pm1Result r = pm1Run(*e, o);
  if (r.stopped) { fprintf(stderr, "P-1 stopped on request\n"); return 3; }
  J j = resultLine(&r);
  if (g_json) { printf("{\"event\":\"pm1\",%s\n", j.str().c_str() + 1); fflush(stdout); }
  else printf("%s\n", j.str().c_str());
  std::ofstream(a.results, std::ios::app) << j.str() << "\n";
  if (!r.factor.empty()) fprintf(stderr, "P-1 found a factor of %u*2^%llu+1: %s (stage %d)\n", k, (unsigned long long)n, r.factor.c_str(), r.stage);
  else fprintf(stderr, "P-1 found no factor (B1=%llu, B2=%llu)\n", (unsigned long long)plan.B1, (unsigned long long)plan.B2);
  if (!o.checkpointPath.empty()) remove(o.checkpointPath.c_str());
  return 0;
}

// Returns 0 when a verdict was reached, 3 when stopped by --stop-file before the end.
static int runTest(const Args& a, u32 k, u64 n) {
  auto e = makeEngine(a, k, n, 4);
  describe(*e);
  const Layout& L = e->layout();
  ProthOptions o; o.gerbiczL = a.gl; o.eventSeconds = a.eventSeconds;
  if (!a.ckptDir.empty()) o.checkpointPath = a.ckptDir + "/" + std::to_string(k) + "_" + std::to_string(n) + ".ckpt";
  if (!a.stopFile.empty()) { std::string sf = a.stopFile; o.stopRequested = [sf]() { return fileExists(sf); }; }
  const std::string backend = e->name();
  if (g_json) o.onEvent = [&](const char* ev, const ProthStatus& st) {
    J j; j.s("event", ev).u("k", k).u("n", n).u("iteration", st.iteration).u("total", st.total)
          .f("percent", 100.0 * st.iteration / std::max<u64>(1, st.total)).u("verified_iteration", st.verifiedIteration)
          .u("checks_passed", st.checksPassed).u("rollbacks", st.rollbacks).f("elapsed", st.elapsed)
          .f("ms_per_iter", st.msPerIter).f("ms_per_iter_recent", st.msPerIterRecent);
    double ms = st.msPerIterRecent > 0 ? st.msPerIterRecent : st.msPerIter;
    if (ms > 0) j.f("eta_seconds", ms * (double)(st.total - std::min(st.total, st.iteration)) / 1e3);
    if (!strcmp(ev, "start"))
      j.u("N", L.N).i("primes", L.nPrimes).f("bits_per_word", L.bitsPerWord).s("backend", backend).s("engine", COLBERT_VERSION)
       .u("gerbicz_block", st.gerbiczL).u("check_every", st.checkEvery).u("resumed_from", st.resumedFrom).s("checkpoint", st.checkpoint);
    emit(j);
  };
  ProthResult r = prothTest(*e, o);
  if (r.stopped) {
    fprintf(stderr, "stopped on request at verified iteration %llu of %llu\n", (unsigned long long)r.iterations, (unsigned long long)(n - 1));
    return 3;
  }
  std::string js = jsonResult(*e, r);
  if (g_json) { printf("{\"event\":\"result\",%s\n", js.c_str() + 1); fflush(stdout); }
  else { printf("%s\n", js.c_str()); fflush(stdout); }
  std::ofstream(a.results, std::ios::app) << js << "\n";
  if (r.prime) fprintf(stderr, "\n*** %u*2^%llu+1 is PRIME (Proth, base %u) ***\n\n", k, (unsigned long long)n, r.base);
  return 0;
}

// time `iters` squarings at production size and verify them against GMP
static int bench(const Args& a, u32 k, u64 n, u64 iters, bool verify) {
  auto e = makeEngine(a, k, n, 2);
  describe(*e);
  const Layout& L = e->layout();
  mpz_class P = modulus(L);
  gmp_randclass gr(gmp_randinit_mt); gr.seed(1);
  mpz_class x = gr.get_z_range(P);
  e->write(0, fromMpz(L, x));
  e->square(0, 2);                                   // warm up (kernel compilation, page faults)
  double t = now(); std::vector<i32> d;
  if (a.benchSeconds > 0) {
    // time budget: ITERS is an upper bound; chunks double until the budget is spent
    u64 done = 0, chunk = 1;
    while (done < iters) {
      u64 c = std::min(chunk, iters - done);
      e->square(0, c); done += c; chunk *= 2;
      if (now() - t >= a.benchSeconds) break;
    }
    iters = done;
  } else e->square(0, iters);
  e->read(0, d); t = now() - t;
  FILE* human = g_json ? stderr : stdout;            // stdout carries only JSON in --json mode
  fprintf(human, "%.3f ms/iteration over %llu squarings (%s)  => %.1f hours per full test\n", 1e3 * t / iters, (unsigned long long)iters, e->name().c_str(), t / iters * n / 3600);
  J j; j.s("event", "bench").u("k", k).u("n", n).u("N", L.N).i("primes", L.nPrimes).u("iterations", iters).f("ms_per_iter", 1e3 * t / iters)
       .f("hours_per_test", t / iters * n / 3600).s("backend", e->name()).s("engine", COLBERT_VERSION);
  if (verify) {
    for (u64 i = 0; i < iters + 2; i++) x = (x * x % P) * L.k % P;
    bool ok = toMpz(L, d) == x;
    fprintf(human, "%s  %llu squarings at full size agree with GMP\n", ok ? "ok  " : "FAIL", (unsigned long long)(iters + 2));
    j.t("verified", ok);
    emit(j);
    return ok ? 0 : 1;
  }
  emit(j);
  if (g_oclProfile) fprintf(human, "kernel time by kernel (all launches, including warm-up):\n%s", oclProfileReport().c_str());
  return 0;
}

static int usage() {
  fprintf(stderr,
    "colbert %s - Proth tests of k*2^n+1 via a weighted NTT over GF(M61^2) x GF(M31^2)\n\n"
    "  colbert test K N        test one number (Gerbicz-checked, resumable with --ckpt DIR)\n"
    "  colbert pm1 K N         P-1 factoring (resumable with --ckpt DIR); bounds from --sieve-bits\n"
    "  colbert work            run every 'K N' line of --worktodo FILE (default worktodo.txt)\n"
    "  colbert bench K N ITERS time squarings at full size; add --verify to compare with GMP\n"
    "  colbert selftest        products and Proth verdicts against GMP\n"
    "  colbert info K N        show the transform that would be used\n"
    "  colbert devices         list OpenCL devices\n"
    "  colbert version         version, protocol and compiled-in backends\n\n"
    "  --backend cpu|ocl   --device I   --primes 1|2   --size N   --gerbicz L\n"
    "  --ckpt DIR   --worktodo FILE   --results FILE   --verbose\n"
    "  --json              machine-readable JSON Lines events on stdout (see docs/ENGINE_PROTOCOL.md)\n"
    "  --stop-file F       test/work: when F exists, verify, checkpoint and exit with status 3\n"
    "  --event-seconds S   --json progress interval (default 5)\n"
    "  --seconds S         bench: stop after about S seconds (ITERS becomes an upper bound)\n"
    "  --b1 B1 --b2 B2     pm1: bounds (default: chosen to save the most work)\n"
    "  --sieve-bits B      pm1/info: candidates have no factor below 2^B (default 32)\n"
    "  --tests-saved T     pm1/info: tests a factor saves, double checks included (default 1.05)\n"
    "  --memory MB         pm1: device memory for stage 2 (default: a quarter, at most 2 GiB)\n", COLBERT_VERSION);
  return 2;
}

static bool oclCompiledIn() {
  try { oclDeviceInfo(); return true; } catch (const std::exception& ex) { return std::string(ex.what()) != "built without OpenCL"; }
}

int main(int argc, char** argv) {
  Args a; bool verify = false;
  for (int i = 1; i < argc; i++) {
    std::string s = argv[i];
    auto val = [&]() -> std::string { if (i + 1 >= argc) { usage(); exit(2); } return argv[++i]; };
    if (s == "--backend") a.backend = val();
    else if (s == "--device") a.device = atoi(val().c_str());
    else if (s == "--primes") a.primes = atoi(val().c_str());
    else if (s == "--size") a.N = strtoull(val().c_str(), 0, 10);
    else if (s == "--gerbicz") a.gl = (u32)atoi(val().c_str());
    else if (s == "--ckpt") a.ckptDir = val();
    else if (s == "--worktodo") a.worktodo = val();
    else if (s == "--results") a.results = val();
    else if (s == "--verify") verify = true;
    else if (s == "--verbose") a.verbose = true;
    else if (s == "--json") g_json = true;
    else if (s == "--stop-file") a.stopFile = val();
    else if (s == "--event-seconds") a.eventSeconds = atof(val().c_str());
    else if (s == "--seconds") a.benchSeconds = atof(val().c_str());
    else if (s == "--profile") g_oclProfile = true;
    else if (s == "--b1") a.b1 = strtoull(val().c_str(), 0, 10);
    else if (s == "--b2") a.b2 = strtoull(val().c_str(), 0, 10);
    else if (s == "--sieve-bits") a.sieveBits = atof(val().c_str());
    else if (s == "--tests-saved") a.testsSaved = atof(val().c_str());
    else if (s == "--memory") a.memoryMB = atof(val().c_str());
    else if (a.cmd.empty()) a.cmd = s;
    else a.pos.push_back(s);
  }
  try {
    auto K = [&](size_t i) { return (u32)strtoul(a.pos.at(i).c_str(), 0, 10); };
    auto NN = [&](size_t i) { return (u64)strtoull(a.pos.at(i).c_str(), 0, 10); };
    if (a.cmd == "selftest") return selftest(a);
    if (a.cmd == "version") {
      bool ocl = oclCompiledIn();
      if (g_json) emit(J().s("event", "version").s("engine", "colbert").s("version", COLBERT_VERSION).i("protocol", PROTOCOL)
                        .raw("backends", ocl ? "[\"cpu\",\"ocl\"]" : "[\"cpu\"]")
                        .raw("features", "[\"json\",\"stop-file\",\"bench-seconds\",\"devices-json\",\"info-json\",\"checkpoint-status\",\"pm1\"]"));
      else printf("colbert %s (protocol %d, backends: cpu%s)\n", COLBERT_VERSION, PROTOCOL, ocl ? " ocl" : "");
      return 0;
    }
    if (a.cmd == "devices") {
      if (!g_json) { printf("%s", listOclDevices().c_str()); return 0; }
      std::string list = "[";
      try {
        for (auto& d : oclDeviceInfo()) {
          if (list.size() > 1) list += ",";
          list += J().i("index", d.index).s("name", d.name).s("type", d.gpu ? "GPU" : d.cpu ? "CPU" : "other").s("vendor", d.vendor)
                     .s("platform", d.platform).s("version", d.version).s("driver", d.driver).u("compute_units", d.computeUnits)
                     .u("clock_mhz", d.clockMHz).u("global_mem", d.globalMem).u("max_alloc", d.maxAlloc).t("unified_memory", d.unifiedMemory).str();
        }
        emit(J().s("event", "devices").t("opencl", true).raw("devices", list + "]"));
      } catch (const std::exception& ex) {
        emit(J().s("event", "devices").t("opencl", false).s("reason", ex.what()).raw("devices", "[]"));
      }
      return 0;
    }
    if (a.cmd == "test" && a.pos.size() == 2) return runTest(a, K(0), NN(1));
    if (a.cmd == "pm1" && a.pos.size() == 2) return runPm1(a, K(0), NN(1));
    if (a.cmd == "bench" && a.pos.size() == 3) return bench(a, K(0), NN(1), NN(2), verify);
    if (a.cmd == "info" && a.pos.size() == 2) {
      size_t N = a.N ? a.N : Layout::chooseN(K(0), NN(1), a.primes);
      Layout L(K(0), NN(1), N, a.primes);
      if (g_json) emit(J().s("event", "info").u("k", L.k).u("n", L.n).u("N", L.N).i("primes", L.nPrimes).f("bits_per_word", L.bitsPerWord)
                        .f("bound_bits", L.boundBits).f("limit_bits", L.modulusBits - 1).u("base", prothBase(L.k, L.n))
                        .u("gerbicz_block", a.gl ? a.gl : defaultGerbiczL(L.n)).u("bytes_per_checkpoint", 64 + 8ULL * L.N + 8)
                        .raw("pm1", [&]() {
                          size_t sb = L.N / 2 * (16 + (L.nPrimes == 2 ? 8 : 0)), budget = a.memoryMB > 0 ? (size_t)(a.memoryMB * 1048576.0) : (size_t)2 << 30;
                          Pm1Plan p = pm1PlanFor(a, L.n, sb, budget);
                          return J().u("b1", p.B1).u("b2", p.B2).f("probability", p.probability).f("cost_iterations", p.cost)
                                    .f("saving_iterations", p.saving).f("sieve_bits", a.sieveBits).u("D", pm1ChooseD(budget / sb)).str();
                        }()));
      else printf("k=%u n=%llu N=%zu bits/word=%.3f worst-case=%.2f bits (limit %.2f) base=%u\n", L.k, (unsigned long long)L.n, L.N, L.bitsPerWord, L.boundBits, L.modulusBits - 1, prothBase(L.k, L.n));
      return 0;
    }
    if (a.cmd == "work") {
      std::ifstream in(a.worktodo); std::string line; int done = 0;
      if (!in) throw std::runtime_error("cannot open " + a.worktodo);
      // skip numbers that already have a line in the results file
      std::ifstream rf(a.results); std::string all((std::istreambuf_iterator<char>(rf)), std::istreambuf_iterator<char>());
      while (std::getline(in, line)) {
        std::istringstream ls(line); u32 k; u64 n;
        if (line.empty() || line[0] == '#' || !(ls >> k >> n)) continue;
        if (all.find("{\"k\":" + std::to_string(k) + ",\"n\":" + std::to_string(n) + ",") != std::string::npos) continue;
        if (runTest(a, k, n) == 3) return 3;
        done++;
      }
      fprintf(stderr, "worktodo finished: %d tests run\n", done);
      return 0;
    }
  } catch (const std::exception& ex) {
    fprintf(stderr, "error: %s\n", ex.what());
    emit(J().s("event", "error").s("message", ex.what()));
    return 1;
  }
  return usage();
}
