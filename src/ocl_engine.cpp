// OpenCL backend. Same arithmetic, tables and carry scheme as the CPU backend, so the two
// produce identical digit vectors.
#define CL_TARGET_OPENCL_VERSION 120
#define CL_SILENCE_DEPRECATION              // macOS: OpenCL is deprecated but still shipped
#include "engine.h"
#ifdef __APPLE__
#include <OpenCL/cl.h>
#else
#include <CL/cl.h>
#endif
#include <sstream>
#include <cstring>
#include <cstdio>
#include <map>
#include <cstdlib>
#include <random>

bool g_oclProfile = false;

namespace {

// bench --profile: kernel name -> (launches, total ns)
std::map<std::string, std::pair<unsigned long long, double>> g_prof;

const char* kSource =
#include "kernels.inc"
;

void check(cl_int err, const char* what) {
  if (err != CL_SUCCESS) throw std::runtime_error(std::string("OpenCL error ") + std::to_string(err) + " in " + what);
}

struct Dev { cl_platform_id plat; cl_device_id dev; std::string name; bool gpu; };

std::vector<Dev> enumerate() {
  std::vector<Dev> out;
  cl_uint np = 0;
  if (clGetPlatformIDs(0, nullptr, &np) != CL_SUCCESS || !np) return out;
  std::vector<cl_platform_id> ps(np); clGetPlatformIDs(np, ps.data(), nullptr);
  for (auto p : ps) {
    cl_uint nd = 0;
    if (clGetDeviceIDs(p, CL_DEVICE_TYPE_ALL, 0, nullptr, &nd) != CL_SUCCESS || !nd) continue;
    std::vector<cl_device_id> ds(nd); clGetDeviceIDs(p, CL_DEVICE_TYPE_ALL, nd, ds.data(), nullptr);
    for (auto d : ds) {
      char nm[256] = { 0 }; cl_device_type t = 0;
      clGetDeviceInfo(d, CL_DEVICE_NAME, sizeof nm - 1, nm, nullptr);
      clGetDeviceInfo(d, CL_DEVICE_TYPE, sizeof t, &t, nullptr);
      out.push_back({ p, d, nm, (t & CL_DEVICE_TYPE_GPU) != 0 });
    }
  }
  return out;
}

std::vector<std::string> sections() {
  std::vector<std::string> s(1);
  std::istringstream in(kSource); std::string line;
  while (std::getline(in, line)) {
    if (line.rfind("//====", 0) == 0) s.emplace_back(); else s.back() += line + "\n";
  }
  if (s.size() != 5) throw std::runtime_error("internal: kernel source has unexpected sections");
  return s;
}

// Tables for the four-step transform of M = R*Cn points (kernels.cl, fft2 section): the M-th
// root of unity w is chosen so that w^(M/8) = (1+i) 2^((E-1)/2), the root the radix-8
// butterflies use without multiplying.
template <class F> struct Fft2Tables {
  typedef typename F::C C; typedef typename F::T T;
  std::vector<C> TR, TC, TW1;              // TR = w^(Cn e) (also TW2), TC = w^(R e), TW1 = w^e
  Fft2Tables(size_t R, size_t Cn) {
    const int E = F::E; const u64 Pq = F::P; const size_t M = R * Cn;
    C h = { 0, 0 };                          // order 2^(E+1), as in Tables
    for (u64 g = 2;; g++) {
      h = cpow<F>(C{ (T)g, 1 }, (Pq - 1) / 2);
      C t = h;
      for (int i = 0; i < E; i++) t = F::csqr(t);
      if (!(t.re == 1 && t.im == 0)) break;
    }
    C w0 = cpow<F>(h, (1ULL << (E + 1)) / M), b = cpow<F>(w0, M / 8), w = { 0, 0 };
    T s8 = F::mul2exp(1, (E - 1) / 2);
    bool found = false;
    for (u64 v : { 1, 3, 5, 7 }) {
      C t = cpow<F>(b, v);
      if (t.re == s8 && t.im == s8) { w = cpow<F>(w0, v); found = true; break; }
    }
    if (!found) throw std::runtime_error("internal: no M-th root of unity with the radix-8 root");
    auto powers = [&](C base, size_t n) { std::vector<C> o(n); C t = { 1, 0 }; for (size_t i = 0; i < n; i++) { o[i] = t; t = F::cmul(t, base); } return o; };
    TW1 = powers(w, Cn); TR = powers(cpow<F>(w, Cn), R); TC = powers(cpow<F>(w, R), Cn);
  }
};

struct OclEngine : Engine {
  Layout L; size_t N, M; std::string devName;
  cl_context ctx = nullptr; cl_command_queue q = nullptr; cl_program prog = nullptr;
  std::vector<cl_mem> regs, owned;
  cl_mem z61 = nullptr, y61 = nullptr, z31 = nullptr, y31 = nullptr, w61 = nullptr, w31 = nullptr, f61 = nullptr, f31 = nullptr,
         o61 = nullptr, o31 = nullptr, tw61 = nullptr, tw31 = nullptr, widthB = nullptr, carryB = nullptr, flagB = nullptr;
  cl_kernel kWeight[2] = {}, kPw[2] = {}, kDif[2][5] = {}, kDit[2][5] = {}, kVsub[2] = {}, kCarry1 = nullptr, kCarry2 = nullptr;
  std::vector<cl_mem> slot61, slot31;   // spectrum slots (P-1 stage 2)
  cl_ulong globalMem = 0;
  std::vector<int> plan;             // levels per pass, forward order
  // fast path (fft2): four-step R x C transform; the radix-2 passes above are the fallback
  bool fast = false; size_t R = 0, CC = 0, cpg = 1; int logR = 0, logC = 0;
  std::string fastNote;              // why the fast path is off, if it failed its startup check
  cl_mem tr[2] = {}, tc[2] = {}, tw1[2] = {};
  cl_kernel kColF[2] = {}, kColI[2] = {}, kRows[2] = {}, kRowsF[2] = {}, kCarry1w = nullptr;
  // weights computed on the fly (fast path): two-level tables, s_m mod E per word
  bool wotf = false; int wbl = 0;
  cl_mem wa[2] = {}, wb[2] = {}, ia[2] = {}, ib[2] = {}, se[2] = {};

  template <class F> void weightTables(const Tables<F>& t, int fi) {
    typedef typename F::C C; typedef typename F::T T;
    const size_t B = (size_t)1 << wbl;
    std::vector<uint8_t> sm(N);
    for (size_t m = 0; m < N; m++) sm[m] = (uint8_t)(L.s[m] % F::E);
    se[fi] = upload(sm);
    if (t.fold) {
      C thi = cinv<F>(t.th), thB = cpow<F>(t.th, B), thiB = cpow<F>(thi, B);
      std::vector<C> A1(B), B1(M / B), A2(B), B2(M / B);
      C x = { 1, 0 }, y = { 1, 0 };
      for (size_t e = 0; e < B; e++) { A1[e] = x; A2[e] = y; x = F::cmul(x, thi); y = F::cmul(y, t.th); }
      x = { 1, 0 }; y = { t.sc, 0 };
      for (size_t e = 0; e < M / B; e++) { B1[e] = x; B2[e] = y; x = F::cmul(x, thiB); y = F::cmul(y, thB); }
      wa[fi] = upload(A1); wb[fi] = upload(B1); ia[fi] = upload(A2); ib[fi] = upload(B2);
    } else {
      T ri = finv<F>(t.rho), rB = fpow<F>(t.rho, B), riB = fpow<F>(ri, B);
      std::vector<T> A1(B), B1(N / B), A2(B), B2(N / B);
      T x = 1, y = 1;
      for (size_t e = 0; e < B; e++) { A1[e] = x; A2[e] = y; x = F::mul(x, t.rho); y = F::mul(y, ri); }
      x = 1; y = t.sc;
      for (size_t e = 0; e < N / B; e++) { B1[e] = x; B2[e] = y; x = F::mul(x, rB); y = F::mul(y, riB); }
      wa[fi] = upload(A1); wb[fi] = upload(B1); ia[fi] = upload(A2); ib[fi] = upload(B2);
    }
  }
  u64 pending = 0;
  std::vector<std::pair<cl_kernel, cl_event>> events;   // profiling only

  template <class V> cl_mem upload(const V& v) {
    cl_int err; size_t bytes = v.size() * sizeof(v[0]);
    cl_mem m = clCreateBuffer(ctx, CL_MEM_READ_ONLY | CL_MEM_COPY_HOST_PTR, bytes ? bytes : 16, bytes ? (void*)v.data() : nullptr, &err);
    if (!bytes) m = clCreateBuffer(ctx, CL_MEM_READ_ONLY, 16, nullptr, &err);
    check(err, "upload"); owned.push_back(m); return m;
  }
  cl_mem alloc(size_t bytes) {
    cl_int err; cl_mem m = clCreateBuffer(ctx, CL_MEM_READ_WRITE, bytes, nullptr, &err);
    check(err, "alloc"); owned.push_back(m); return m;
  }
  cl_kernel kernel(const std::string& name) {
    cl_int err; cl_kernel k = clCreateKernel(prog, name.c_str(), &err);
    check(err, ("kernel " + name).c_str()); return k;
  }

  // forward / output tables in the layout the kernels expect (see kernels.cl)
  template <class F> void tables(const Tables<F>& t, cl_mem& w, cl_mem& f, cl_mem& o, cl_mem& tw) {
    typedef typename F::C C;
    w = upload(t.w);
    if (t.fold) {
      std::vector<C> ft(2 * M), ot(2 * M);
      for (size_t j = 0; j < M; j++) {
        ft[2 * j] = t.W1[j]; ft[2 * j + 1] = t.W2[j];
        ot[j] = { t.U[j].re, F::neg(t.U[j].im) };
        ot[j + M] = { t.V[j].im, t.V[j].re };
      }
      f = upload(ft); o = upload(ot); tw = upload(std::vector<C>(1));
    } else {
      f = upload(t.a); o = upload(t.ai); tw = upload(t.tw);
    }
  }

  OclEngine(const Layout& L_, int nRegs, int device, bool verbose) : L(L_), N(L_.N), M(L_.N / 2) {
    auto devs = enumerate();
    if (devs.empty()) throw std::runtime_error("no OpenCL devices found");
    int pick = device;
    if (pick < 0) { pick = 0; for (size_t i = 0; i < devs.size(); i++) if (devs[i].gpu) { pick = (int)i; break; } }
    if (pick >= (int)devs.size()) throw std::runtime_error("no such OpenCL device");
    devName = devs[pick].name;
    cl_int err;
    clGetDeviceInfo(devs[pick].dev, CL_DEVICE_GLOBAL_MEM_SIZE, sizeof globalMem, &globalMem, nullptr);
    ctx = clCreateContext(nullptr, 1, &devs[pick].dev, nullptr, nullptr, &err); check(err, "context");
    q = clCreateCommandQueue(ctx, devs[pick].dev, g_oclProfile ? CL_QUEUE_PROFILING_ENABLE : 0, &err); check(err, "queue");

    Tables<F61> t61(L);
    std::unique_ptr<Tables<F31>> t31;
    if (L.nPrimes == 2) t31.reset(new Tables<F31>(L));

    // fast path when M = 2^m splits into R x C sub-transforms that fit one work-group
    {
      cl_ulong lmem = 0; size_t maxWg = 0;
      clGetDeviceInfo(devs[pick].dev, CL_DEVICE_LOCAL_MEM_SIZE, sizeof lmem, &lmem, nullptr);
      clGetDeviceInfo(devs[pick].dev, CL_DEVICE_MAX_WORK_GROUP_SIZE, sizeof maxWg, &maxWg, nullptr);
      int m = ilog2(M);
      logR = m / 2; logC = m - logR; R = (size_t)1 << logR; CC = (size_t)1 << logC;
      const char* env = getenv("COLBERT_FFT");
      bool forceOld = env && std::string(env) == "radix2";
      fast = !forceOld && m >= 6 && logC <= 10 && lmem >= CC * 4 + 1024 && maxWg >= CC / 8;
      // Weights from small tables + rotations instead of data-sized tables: saves ~56 MiB of
      // reads per squaring. Apple GPUs are limited by 64-bit arithmetic rather than memory
      // here, so they keep the tables (measured equal). COLBERT_WOTF=0/1 overrides.
      char vendor[256] = { 0 };
      clGetDeviceInfo(devs[pick].dev, CL_DEVICE_VENDOR, sizeof vendor - 1, vendor, nullptr);
      const char* wo = getenv("COLBERT_WOTF");
      wotf = fast && (wo ? std::string(wo) != "0" : std::string(vendor).find("Apple") == std::string::npos);
      wbl = (ilog2(N) + 1) / 2;
      cpg = 1;                                  // columns per work-group in the column passes
      const char* cp = getenv("COLBERT_CPG");
      size_t want = cp ? (size_t)atoi(cp) : 2;
      while (cpg * 2 <= want && cpg * 2 <= CC && (R / 8) * cpg * 2 <= maxWg && lmem >= R * 4 * cpg * 2 + 1024) cpg *= 2;
    }
    auto sec = sections();
    std::string src = sec[0];
    for (int field : { 61, 31 }) {
      src += "#undef FIELD\n#define FIELD " + std::to_string(field) + "\n" + sec[1];
      for (int r = 1; r <= 4; r++) src += "#undef RR\n#define RR " + std::to_string(r) + "\n" + sec[2];
      src += sec[3];
    }
    src += sec[4];
    const u128 Q = (u128)F61::P * F31::P, QH = Q / 2;
    char opts[512];
    snprintf(opts, sizeof opts, "-DNWORDS=%zuu -DMHALF=%zuu -DNPRIMES=%d -DFOLD61=%d -DFOLD31=%d -DTOPBASE=%lluUL -DTOPW=%du "
             "-DQL=%lluUL -DQH=%lluUL -DQHL=%lluUL -DQHH=%lluUL",
             N, M, L.nPrimes, (int)t61.fold, t31 ? (int)t31->fold : 0, (unsigned long long)L.topBase, (int)L.width[N - 2],
             (unsigned long long)(u64)Q, (unsigned long long)(u64)(Q >> 64), (unsigned long long)(u64)QH, (unsigned long long)(u64)(QH >> 64));
    std::string optStr = opts;
    if (fast) optStr += " -DLOGR=" + std::to_string(logR) + "u -DLOGC=" + std::to_string(logC) + "u -DCPG=" + std::to_string(cpg) + "u";
    if (wotf) {
      optStr += " -DWOTF=1 -DWBL=" + std::to_string(wbl) + "u";
      optStr += " -DG61=" + std::to_string((unsigned long long)t61.g) + "UL -DGI61=" + std::to_string((unsigned long long)t61.gi) + "UL";
      optStr += " -DG31=" + std::to_string(t31 ? (unsigned long long)t31->g : 0ULL) + "U -DGI31=" + std::to_string(t31 ? (unsigned long long)t31->gi : 0ULL) + "U";
    } else optStr += " -DWOTF=0 -DG61=0UL -DGI61=0UL -DG31=0U -DGI31=0U";
    if (const char* x = getenv("COLBERT_CLOPTS")) optStr += std::string(" ") + x;    // experiments only
    const char* sp = src.c_str();
    prog = clCreateProgramWithSource(ctx, 1, &sp, nullptr, &err); check(err, "program");
    err = clBuildProgram(prog, 1, &devs[pick].dev, optStr.c_str(), nullptr, nullptr);
    if (err != CL_SUCCESS || verbose) {
      size_t len = 0; clGetProgramBuildInfo(prog, devs[pick].dev, CL_PROGRAM_BUILD_LOG, 0, nullptr, &len);
      std::string log(len, 0); clGetProgramBuildInfo(prog, devs[pick].dev, CL_PROGRAM_BUILD_LOG, len, &log[0], nullptr);
      if (err != CL_SUCCESS) throw std::runtime_error("OpenCL build failed:\n" + log);
      if (len > 2) fprintf(stderr, "OpenCL build log:\n%s\n", log.c_str());
    }

    tables(t61, w61, f61, o61, tw61);
    z61 = alloc(M * 16); y61 = alloc(M * 16);
    if (t31) { tables(*t31, w31, f31, o31, tw31); z31 = alloc(M * 8); y31 = alloc(M * 8); }
    else { w31 = f31 = o31 = tw31 = z31 = y31 = alloc(16); }
    widthB = upload(L.width);
    carryB = alloc((N / 8) * 16);
    flagB = alloc(4);
    int zero = 0; check(clEnqueueWriteBuffer(q, flagB, CL_TRUE, 0, 4, &zero, 0, nullptr, nullptr), "flag");
    for (int i = 0; i < nRegs; i++) regs.push_back(alloc(N * 4));

    for (int fi = 0; fi < (t31 ? 2 : 1); fi++) {
      std::string sfx = fi == 0 ? "61" : "31";
      kWeight[fi] = kernel("weight" + sfx); kPw[fi] = kernel("pw" + sfx); kVsub[fi] = kernel("vsub" + sfx);
      for (int r = 1; r <= 4; r++) { kDif[fi][r] = kernel("dif" + sfx + "_" + std::to_string(r)); kDit[fi][r] = kernel("dit" + sfx + "_" + std::to_string(r)); }
    }
    kCarry1 = kernel("carry1"); kCarry2 = kernel("carry2");
    if (fast) {
      auto up = [&](int fi, auto& t) { tr[fi] = upload(t.TR); tc[fi] = upload(t.TC); tw1[fi] = upload(t.TW1); };
      { Fft2Tables<F61> t(R, CC); up(0, t); }
      if (t31) { Fft2Tables<F31> t(R, CC); up(1, t); }
      if (wotf) {
        weightTables(t61, 0);
        if (t31) weightTables(*t31, 1);
        else wa[1] = wb[1] = ia[1] = ib[1] = se[1] = alloc(16);
        kCarry1w = kernel("carry1w");
      }
      for (int fi = 0; fi < (t31 ? 2 : 1); fi++) {
        std::string sfx = fi == 0 ? "61" : "31";
        kColF[fi] = kernel("colfwd" + sfx); kColI[fi] = kernel("colinv" + sfx);
        kRows[fi] = kernel("rows" + sfx); kRowsF[fi] = kernel("rowsfwd" + sfx);
        if (verbose)
          for (cl_kernel k : { kColF[fi], kColI[fi], kRows[fi], kRowsF[fi] }) {
            char nm[64] = { 0 }; size_t wg = 0; cl_ulong pm = 0, lm = 0;
            clGetKernelInfo(k, CL_KERNEL_FUNCTION_NAME, sizeof nm - 1, nm, nullptr);
            clGetKernelWorkGroupInfo(k, devs[pick].dev, CL_KERNEL_WORK_GROUP_SIZE, sizeof wg, &wg, nullptr);
            clGetKernelWorkGroupInfo(k, devs[pick].dev, CL_KERNEL_PRIVATE_MEM_SIZE, sizeof pm, &pm, nullptr);
            clGetKernelWorkGroupInfo(k, devs[pick].dev, CL_KERNEL_LOCAL_MEM_SIZE, sizeof lm, &lm, nullptr);
            fprintf(stderr, "kernel %-10s max work-group %zu, private %llu B, local %llu B\n", nm, wg, (unsigned long long)pm, (unsigned long long)lm);
          }
      }
    }
    for (int lv = ilog2(M); lv > 0;) { int r = lv >= 4 ? 4 : lv; if (lv == 5) r = 3; plan.push_back(r); lv -= r; }
    if (fast && !(getenv("COLBERT_FFT") && std::string(getenv("COLBERT_FFT")) == "four-step-unchecked")) startupCheck();
  }
  // The fast path must give exactly what the radix-2 kernels give. Check one squaring and one
  // product on random digits before trusting it; on any difference, fall back for good.
  void startupCheck() {
    std::mt19937_64 rng(12345);
    auto rnd = [&]() { std::vector<i32> d(N); for (size_t j = 0; j < N; j++) { int w = j + 1 < N ? L.width[j] : 8; d[j] = (i32)((i64)(rng() % (1ULL << w)) - (i64)(1ULL << (w - 1))); } return d; };
    std::vector<i32> a = rnd(), b = rnd();
    cl_mem x0 = alloc(N * 4), x1 = alloc(N * 4), y0 = alloc(N * 4);
    std::vector<i32> r[2][2];
    for (int path = 0; path < 2; path++) {
      fast = path == 0;
      check(clEnqueueWriteBuffer(q, x0, CL_TRUE, 0, N * 4, a.data(), 0, nullptr, nullptr), "write");
      check(clEnqueueWriteBuffer(q, x1, CL_TRUE, 0, N * 4, a.data(), 0, nullptr, nullptr), "write");
      check(clEnqueueWriteBuffer(q, y0, CL_TRUE, 0, N * 4, b.data(), 0, nullptr, nullptr), "write");
      squareBuf(x0, 1); mulBuf(x1, y0); sync();
      for (int k = 0; k < 2; k++) { r[path][k].resize(N); check(clEnqueueReadBuffer(q, k ? x1 : x0, CL_TRUE, 0, N * 4, r[path][k].data(), 0, nullptr, nullptr), "read"); }
    }
    fast = r[0][0] == r[1][0] && r[0][1] == r[1][1];
    if (!fast) {
      fastNote = " (four-step kernels failed the startup check on this device)";
      fprintf(stderr, "warning: OpenCL four-step transform disagrees with the radix-2 kernels on this device; using radix-2\n");
    }
  }

  ~OclEngine() override {
    if (q) clFinish(q);
    for (auto& ks : kDif) for (auto k : ks) if (k) clReleaseKernel(k);
    for (auto& ks : kDit) for (auto k : ks) if (k) clReleaseKernel(k);
    for (auto k : kWeight) if (k) clReleaseKernel(k);
    for (auto k : kPw) if (k) clReleaseKernel(k);
    for (auto k : kVsub) if (k) clReleaseKernel(k);
    for (auto* ks : { kColF, kColI, kRows, kRowsF }) for (int i = 0; i < 2; i++) if (ks[i]) clReleaseKernel(ks[i]);
    if (kCarry1) clReleaseKernel(kCarry1);
    if (kCarry2) clReleaseKernel(kCarry2);
    if (kCarry1w) clReleaseKernel(kCarry1w);
    for (auto m : owned) clReleaseMemObject(m);
    for (auto m : slot61) clReleaseMemObject(m);
    for (auto m : slot31) clReleaseMemObject(m);
    if (prog) clReleaseProgram(prog);
    if (q) clReleaseCommandQueue(q);
    if (ctx) clReleaseContext(ctx);
  }

  const Layout& layout() const override { return L; }
  std::string name() const override { return "opencl: " + devName; }
  std::string detail() const override {
    if (!fast) return "radix-2" + fastNote;
    return "four-step " + std::to_string(R) + "x" + std::to_string(CC) + (cpg > 1 ? ", " + std::to_string(cpg) + " columns/group" : "") + (wotf ? ", computed weights" : "");
  }

  void run(cl_kernel k, size_t gsize, std::initializer_list<cl_mem> bufs, const cl_uint* scalar = nullptr) {
    cl_uint i = 0;
    for (cl_mem b : bufs) check(clSetKernelArg(k, i++, sizeof(cl_mem), &b), "arg");
    if (scalar) check(clSetKernelArg(k, i++, sizeof(cl_uint), scalar), "arg");
    cl_event ev = nullptr;
    check(clEnqueueNDRangeKernel(q, k, 1, nullptr, &gsize, nullptr, 0, nullptr, g_oclProfile ? &ev : nullptr), "enqueue");
    if (ev) events.push_back({ k, ev });
  }
  void collect() {
    for (auto& ke : events) {
      cl_ulong a = 0, b = 0; char nm[128] = { 0 };
      clGetEventProfilingInfo(ke.second, CL_PROFILING_COMMAND_START, sizeof a, &a, nullptr);
      clGetEventProfilingInfo(ke.second, CL_PROFILING_COMMAND_END, sizeof b, &b, nullptr);
      clGetKernelInfo(ke.first, CL_KERNEL_FUNCTION_NAME, sizeof nm - 1, nm, nullptr);
      auto& slot = g_prof[nm]; slot.first++; slot.second += (double)(b - a);
      clReleaseEvent(ke.second);
    }
    events.clear();
  }
  struct Arg { size_t size; const void* p; };
  static Arg A(const cl_mem& m) { return { sizeof(cl_mem), &m }; }
  static Arg A(const cl_uint& u) { return { sizeof(cl_uint), &u }; }
  void launch(cl_kernel k, size_t groups, size_t local, std::initializer_list<Arg> args) {
    cl_uint i = 0;
    for (const Arg& a : args) check(clSetKernelArg(k, i++, a.size, a.p), "arg");
    size_t gsize = groups * local;
    cl_event ev = nullptr;
    check(clEnqueueNDRangeKernel(q, k, 1, nullptr, &gsize, &local, 0, nullptr, g_oclProfile ? &ev : nullptr), "enqueue");
    if (ev) events.push_back({ k, ev });
  }
  // fft2: columns forward (digits -> z), rows (pointwise mode 0 square, 1 * ya, 2 * (ya - yb)),
  // columns inverse; rowsfwd leaves the spectrum of z in `out`
  void colF(int fi, cl_mem x, cl_mem z) {
    cl_mem w0 = wotf ? wa[fi] : (fi ? f31 : f61), w1 = wotf ? wb[fi] : w0, s0 = wotf ? se[fi] : widthB;
    launch(kColF[fi], CC / cpg, R / 8 * cpg, { A(x), A(w0), A(w1), A(s0), A(z), A(tr[fi]), A(tw1[fi]), A(tr[fi]) });
  }
  void rows(int fi, cl_mem z, cl_mem ya, cl_mem yb, cl_uint mode) { launch(kRows[fi], R / 2, CC / 8, { A(z), A(ya), A(yb), A(mode), A(tc[fi]), A(tw1[fi]), A(tr[fi]) }); }
  void colI(int fi, cl_mem z) { launch(kColI[fi], CC / cpg, R / 8 * cpg, { A(z), A(tr[fi]) }); }
  void rowsF(int fi, cl_mem z, cl_mem out) { launch(kRowsF[fi], R, CC / 8, { A(z), A(out), A(tc[fi]) }); }

  void forward(int fi, cl_mem x, cl_mem z) {
    cl_mem w = fi ? w31 : w61;
    run(kWeight[fi], M, { x, fi ? f31 : f61, z });
    cl_uint h0 = (cl_uint)(M / 2);
    for (int r : plan) { run(kDif[fi][r], M >> r, { z, w }, &h0); h0 >>= r; }
  }
  void inverse(int fi, cl_mem z) {
    cl_mem w = fi ? w31 : w61;
    cl_uint hmin = 1;
    for (size_t i = plan.size(); i-- > 0;) {
      int r = plan[i]; cl_uint h0 = hmin << (r - 1);
      run(kDit[fi][r], M >> r, { z, w }, &h0);
      hmin <<= r;
    }
  }
  void carry(cl_mem x, cl_uint mulc = 1) {
    size_t blocks = N / 8, lw = blocks < 64 ? blocks : 64;
    if (fast && wotf) launch(kCarry1w, blocks / lw, lw, { A(z61), A(ia[0]), A(ib[0]), A(se[0]), A(z31), A(ia[1]), A(ib[1]), A(se[1]), A(widthB), A(x), A(carryB), A(mulc) });
    else if (fast) launch(kCarry1, blocks / lw, lw, { A(z61), A(o61), A(z31), A(o31), A(widthB), A(x), A(carryB), A(mulc) });
    else run(kCarry1, N / 8, { z61, o61, z31, o31, widthB, x, carryB }, &mulc);
    run(kCarry2, N / 8, { x, carryB, widthB, flagB });
  }
  void sync() {
    check(clFinish(q), "finish"); pending = 0;
    if (!events.empty()) collect();
    int flag = 0; check(clEnqueueReadBuffer(q, flagB, CL_TRUE, 0, 4, &flag, 0, nullptr, nullptr), "flag");
    if (flag) throw std::runtime_error("internal: carry did not settle (OpenCL)");
  }
  void throttle() { if (++pending % 64 == 0) clFlush(q); if (pending >= 512) sync(); }

  void write(int r, const std::vector<i32>& d) override { check(clEnqueueWriteBuffer(q, regs.at(r), CL_TRUE, 0, N * 4, d.data(), 0, nullptr, nullptr), "write"); }
  void read(int r, std::vector<i32>& d) override { sync(); d.resize(N); check(clEnqueueReadBuffer(q, regs.at(r), CL_TRUE, 0, N * 4, d.data(), 0, nullptr, nullptr), "read"); }
  void copy(int dst, int src) override { check(clEnqueueCopyBuffer(q, regs.at(src), regs.at(dst), 0, 0, N * 4, 0, nullptr, nullptr), "copy"); }

  void square(int r, u64 count) override { squareBuf(regs.at(r), count); sync(); }
  void mul(int dst, int src) override { mulBuf(regs.at(dst), regs.at(src)); sync(); }
  void squareMul(int r, const std::vector<u32>& mults) override {
    for (size_t i = 0; i < mults.size(); i++) squareBuf(regs.at(r), 1, mults[i]);
    sync();
  }

  // --- spectrum slots (P-1 stage 2)
  size_t spectrumBytes() const override { return M * 16 + (L.nPrimes == 2 ? M * 8 : 0); }
  size_t deviceMemory() const override { return (size_t)globalMem; }
  int allocSlots(int want, size_t budget) override {
    for (auto m : slot61) clReleaseMemObject(m);
    for (auto m : slot31) clReleaseMemObject(m);
    slot61.clear(); slot31.clear();
    int n = (int)std::min<size_t>((size_t)want, budget / spectrumBytes());
    for (int i = 0; i < n; i++) {
      cl_int err; cl_mem a = clCreateBuffer(ctx, CL_MEM_READ_WRITE, M * 16, nullptr, &err);
      if (err != CL_SUCCESS) { n = i; break; }
      cl_mem b = nullptr;
      if (L.nPrimes == 2) { b = clCreateBuffer(ctx, CL_MEM_READ_WRITE, M * 8, nullptr, &err); if (err != CL_SUCCESS) { clReleaseMemObject(a); n = i; break; } }
      slot61.push_back(a); if (b) slot31.push_back(b);
    }
    return n;
  }
  void toSpectrum(int s, int r) override {
    cl_mem x = regs.at(r);
    for (int fi = 0; fi < L.nPrimes; fi++) {
      cl_mem z = fi ? z31 : z61, out = fi ? slot31.at(s) : slot61.at(s);
      if (fast) { colF(fi, x, z); rowsF(fi, z, out); continue; }
      forward(fi, x, z);
      check(clEnqueueCopyBuffer(q, z, out, 0, 0, M * (fi ? 8 : 16), 0, nullptr, nullptr), "copy");
    }
    throttle();
  }
  void mulDiff(int r, int sa, int sb) override {
    cl_mem x = regs.at(r);
    for (int fi = 0; fi < L.nPrimes; fi++) {
      cl_mem z = fi ? z31 : z61, a = fi ? slot31.at(sa) : slot61.at(sa), b = fi ? slot31.at(sb) : slot61.at(sb);
      if (fast) { colF(fi, x, z); rows(fi, z, a, b, 2); colI(fi, z); continue; }
      cl_mem y = fi ? y31 : y61;
      forward(fi, x, z);
      run(kVsub[fi], M, { a, b, y });
      run(kPw[fi], M / 2, { z, y, fi ? tw31 : tw61 });
      inverse(fi, z);
    }
    carry(x);
    throttle();
  }

  void squareBuf(cl_mem x, u64 count, cl_uint mulc = 1) {
    int nf = L.nPrimes;
    for (u64 it = 0; it < count; it++) {
      for (int fi = 0; fi < nf; fi++) {
        cl_mem z = fi ? z31 : z61;
        if (fast) { colF(fi, x, z); rows(fi, z, z, z, 0); colI(fi, z); continue; }
        forward(fi, x, z);
        run(kPw[fi], M / 2, { z, z, fi ? tw31 : tw61 });
        inverse(fi, z);
      }
      carry(x, mulc);
      throttle();
    }
  }
  void mulBuf(cl_mem x, cl_mem yv) {
    for (int fi = 0; fi < L.nPrimes; fi++) {
      cl_mem z = fi ? z31 : z61, y = fi ? y31 : y61;
      if (fast) { colF(fi, yv, z); rowsF(fi, z, y); colF(fi, x, z); rows(fi, z, y, y, 1); colI(fi, z); continue; }
      forward(fi, x, z); forward(fi, yv, y);
      run(kPw[fi], M / 2, { z, y, fi ? tw31 : tw61 });
      inverse(fi, z);
    }
    carry(x);
  }
};

} // namespace

std::unique_ptr<Engine> makeOclEngine(const Layout& L, int nRegs, int device, bool verbose) {
  return std::unique_ptr<Engine>(new OclEngine(L, nRegs, device, verbose));
}

std::string oclProfileReport() {
  double tot = 0; for (auto& kv : g_prof) tot += kv.second.second;
  std::ostringstream o; char line[200];
  for (auto& kv : g_prof) {
    snprintf(line, sizeof line, "  %-14s %9llu launches  %10.3f ms total  %8.1f us each  %5.1f%%\n", kv.first.c_str(), kv.second.first,
             kv.second.second / 1e6, kv.second.second / 1e3 / (double)kv.second.first, 100.0 * kv.second.second / (tot > 0 ? tot : 1));
    o << line;
  }
  return o.str();
}

std::string listOclDevices() {
  std::ostringstream o; int i = 0;
  for (auto& d : enumerate()) o << i++ << ": " << d.name << (d.gpu ? "  [GPU]" : "  [CPU/other]") << "\n";
  if (!i) o << "no OpenCL devices found\n";
  return o.str();
}

// Same order and indices as listOclDevices(), with what the app needs to choose a device.
std::vector<OclDeviceInfo> oclDeviceInfo() {
  std::vector<OclDeviceInfo> out; int i = 0;
  auto str = [](cl_device_id d, cl_device_info what) {
    char buf[512] = { 0 }; clGetDeviceInfo(d, what, sizeof buf - 1, buf, nullptr); return std::string(buf);
  };
  for (auto& d : enumerate()) {
    OclDeviceInfo x; x.index = i++; x.name = d.name; x.gpu = d.gpu;
    cl_device_type t = 0; clGetDeviceInfo(d.dev, CL_DEVICE_TYPE, sizeof t, &t, nullptr);
    x.cpu = (t & CL_DEVICE_TYPE_CPU) != 0;
    x.vendor = str(d.dev, CL_DEVICE_VENDOR); x.version = str(d.dev, CL_DEVICE_VERSION); x.driver = str(d.dev, CL_DRIVER_VERSION);
    char pn[256] = { 0 }; clGetPlatformInfo(d.plat, CL_PLATFORM_NAME, sizeof pn - 1, pn, nullptr); x.platform = pn;
    cl_uint cu = 0, mhz = 0; cl_ulong mem = 0, alloc = 0; cl_bool uni = CL_FALSE;
    clGetDeviceInfo(d.dev, CL_DEVICE_MAX_COMPUTE_UNITS, sizeof cu, &cu, nullptr);
    clGetDeviceInfo(d.dev, CL_DEVICE_MAX_CLOCK_FREQUENCY, sizeof mhz, &mhz, nullptr);
    clGetDeviceInfo(d.dev, CL_DEVICE_GLOBAL_MEM_SIZE, sizeof mem, &mem, nullptr);
    clGetDeviceInfo(d.dev, CL_DEVICE_MAX_MEM_ALLOC_SIZE, sizeof alloc, &alloc, nullptr);
    clGetDeviceInfo(d.dev, CL_DEVICE_HOST_UNIFIED_MEMORY, sizeof uni, &uni, nullptr);   // true: integrated GPU
    x.computeUnits = cu; x.clockMHz = mhz; x.globalMem = mem; x.maxAlloc = alloc; x.unifiedMemory = uni == CL_TRUE;
    out.push_back(x);
  }
  return out;
}
