// colbert: Proth tests for the Sierpinski problem with a zero-padding-free weighted NTT.
#include "proth.h"
#include "mp.h"
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <random>
#include <fstream>
#include <sstream>
#include <iostream>

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }

struct Args {
  std::string cmd, backend = "cpu", ckptDir, worktodo = "worktodo.txt", results = "results.jsonl";
  std::vector<std::string> pos;
  int device = -1, primes = 2; size_t N = 0; u32 gl = 0; bool verbose = false;
};

static std::unique_ptr<Engine> makeEngine(const Args& a, u32 k, u64 n, int nRegs) {
  size_t N = a.N ? a.N : Layout::chooseN(k, n, a.primes);
  Layout L(k, n, N, a.primes);
  if (a.backend == "cpu") return makeCpuEngine(L, nRegs);
  if (a.backend == "ocl") return makeOclEngine(L, nRegs, a.device, a.verbose);
  throw std::runtime_error("unknown backend " + a.backend);
}

static void describe(const Engine& e) {
  const Layout& L = e.layout();
  fprintf(stderr, "%u*2^%llu+1: N=%zu words (%zu complex points/prime), %.2f bits/word, worst-case %.1f of %.1f bits, backend %s\n",
          L.k, (unsigned long long)L.n, L.N, L.N / 2, L.bitsPerWord, L.boundBits, L.modulusBits - 1, e.name().c_str());
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
    printf("%s  product check k=%u n=%llu N=%zu primes=%d bits/word=%.2f\n", ok ? "ok  " : "FAIL", c.k, (unsigned long long)c.n, L.N, primes, L.bitsPerWord);
    fflush(stdout);
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
    printf("%s  proth k=%u n=%llu base=%u -> %s res64=%016llx (gmp %016llx) checks=%llu\n", ok ? "ok  " : "FAIL", c.k, (unsigned long long)c.n, r.base,
           r.prime ? "PRIME" : "composite", (unsigned long long)r.res64, (unsigned long long)wres, (unsigned long long)r.checksPassed);
    fflush(stdout);
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
    printf("%s  fault injection: rollbacks=%llu, final residue %s\n", ok ? "ok  " : "FAIL", (unsigned long long)r.rollbacks, wres == r.res64 ? "correct" : "WRONG");
  }
  printf("%d/%d checks passed on backend %s\n", cases - fails, cases, a.backend.c_str());
  return fails ? 1 : 0;
}

static std::string jsonResult(const Engine& e, const ProthResult& r) {
  const Layout& L = e.layout();
  char buf[600];
  snprintf(buf, sizeof buf, "{\"k\":%u,\"n\":%llu,\"result\":\"%s\",\"base\":%u,\"res64\":\"%016llx\",\"N\":%zu,\"iterations\":%llu,\"gerbicz_ok\":%llu,\"rollbacks\":%llu,\"seconds\":%.1f,\"backend\":\"%s\"}",
           L.k, (unsigned long long)L.n, r.prime ? "PRIME" : "composite", r.base, (unsigned long long)r.res64, L.N, (unsigned long long)r.iterations,
           (unsigned long long)r.checksPassed, (unsigned long long)r.rollbacks, r.seconds, e.name().c_str());
  return buf;
}

static int runTest(const Args& a, u32 k, u64 n) {
  auto e = makeEngine(a, k, n, 4);
  describe(*e);
  ProthOptions o; o.gerbiczL = a.gl;
  if (!a.ckptDir.empty()) o.checkpointPath = a.ckptDir + "/" + std::to_string(k) + "_" + std::to_string(n) + ".ckpt";
  ProthResult r = prothTest(*e, o);
  std::string js = jsonResult(*e, r);
  printf("%s\n", js.c_str()); fflush(stdout);
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
  double t = now(); e->square(0, iters); std::vector<i32> d; e->read(0, d); t = now() - t;
  printf("%.3f ms/iteration over %llu squarings (%s)  => %.1f hours per full test\n", 1e3 * t / iters, (unsigned long long)iters, e->name().c_str(), t / iters * n / 3600);
  if (verify) {
    for (u64 i = 0; i < iters + 2; i++) x = (x * x % P) * L.k % P;
    bool ok = toMpz(L, d) == x;
    printf("%s  %llu squarings at full size agree with GMP\n", ok ? "ok  " : "FAIL", (unsigned long long)(iters + 2));
    return ok ? 0 : 1;
  }
  return 0;
}

static int usage() {
  fprintf(stderr,
    "colbert - Proth tests of k*2^n+1 via a weighted NTT over GF(M61^2) x GF(M31^2)\n\n"
    "  colbert test K N        test one number (Gerbicz-checked, resumable with --ckpt DIR)\n"
    "  colbert work            run every 'K N' line of --worktodo FILE (default worktodo.txt)\n"
    "  colbert bench K N ITERS time squarings at full size; add --verify to compare with GMP\n"
    "  colbert selftest        products and Proth verdicts against GMP\n"
    "  colbert info K N        show the transform that would be used\n"
    "  colbert devices         list OpenCL devices\n\n"
    "  --backend cpu|ocl   --device I   --primes 1|2   --size N   --gerbicz L\n"
    "  --ckpt DIR   --worktodo FILE   --results FILE   --verbose\n");
  return 2;
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
    else if (a.cmd.empty()) a.cmd = s;
    else a.pos.push_back(s);
  }
  try {
    auto K = [&](size_t i) { return (u32)strtoul(a.pos.at(i).c_str(), 0, 10); };
    auto NN = [&](size_t i) { return (u64)strtoull(a.pos.at(i).c_str(), 0, 10); };
    if (a.cmd == "selftest") return selftest(a);
    if (a.cmd == "devices") { printf("%s", listOclDevices().c_str()); return 0; }
    if (a.cmd == "test" && a.pos.size() == 2) return runTest(a, K(0), NN(1));
    if (a.cmd == "bench" && a.pos.size() == 3) return bench(a, K(0), NN(1), NN(2), verify);
    if (a.cmd == "info" && a.pos.size() == 2) {
      size_t N = a.N ? a.N : Layout::chooseN(K(0), NN(1), a.primes);
      Layout L(K(0), NN(1), N, a.primes);
      printf("k=%u n=%llu N=%zu bits/word=%.3f worst-case=%.2f bits (limit %.2f) base=%u\n", L.k, (unsigned long long)L.n, L.N, L.bitsPerWord, L.boundBits, L.modulusBits - 1, prothBase(L.k, L.n));
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
        runTest(a, k, n); done++;
      }
      fprintf(stderr, "worktodo finished: %d tests run\n", done);
      return 0;
    }
  } catch (const std::exception& ex) {
    fprintf(stderr, "error: %s\n", ex.what());
    return 1;
  }
  return usage();
}
