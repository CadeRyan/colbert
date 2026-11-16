// OpenCL backend. Same arithmetic, tables and carry scheme as the CPU backend, so the two
// produce identical digit vectors.
#define CL_TARGET_OPENCL_VERSION 120
#include "engine.h"
#include <CL/cl.h>
#include <sstream>
#include <cstring>
#include <cstdio>

namespace {

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
  if (s.size() != 4) throw std::runtime_error("internal: kernel source has unexpected sections");
  return s;
}

struct OclEngine : Engine {
  Layout L; size_t N, M; std::string devName;
  cl_context ctx = nullptr; cl_command_queue q = nullptr; cl_program prog = nullptr;
  std::vector<cl_mem> regs, owned;
  cl_mem z61 = nullptr, y61 = nullptr, z31 = nullptr, y31 = nullptr, w61 = nullptr, w31 = nullptr, f61 = nullptr, f31 = nullptr,
         o61 = nullptr, o31 = nullptr, tw61 = nullptr, tw31 = nullptr, widthB = nullptr, carryB = nullptr, flagB = nullptr;
  cl_kernel kWeight[2] = {}, kPw[2] = {}, kDif[2][5] = {}, kDit[2][5] = {}, kCarry1 = nullptr, kCarry2 = nullptr;
  std::vector<int> plan;             // levels per pass, forward order
  u64 pending = 0;

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
    ctx = clCreateContext(nullptr, 1, &devs[pick].dev, nullptr, nullptr, &err); check(err, "context");
    q = clCreateCommandQueue(ctx, devs[pick].dev, 0, &err); check(err, "queue");

    Tables<F61> t61(L);
    std::unique_ptr<Tables<F31>> t31;
    if (L.nPrimes == 2) t31.reset(new Tables<F31>(L));

    auto sec = sections();
    std::string src = sec[0];
    for (int field : { 61, 31 }) {
      src += "#undef FIELD\n#define FIELD " + std::to_string(field) + "\n" + sec[1];
      for (int r = 1; r <= 4; r++) src += "#undef RR\n#define RR " + std::to_string(r) + "\n" + sec[2];
    }
    src += sec[3];
    const u128 Q = (u128)F61::P * F31::P, QH = Q / 2;
    char opts[512];
    snprintf(opts, sizeof opts, "-DNWORDS=%zuu -DMHALF=%zuu -DNPRIMES=%d -DFOLD61=%d -DFOLD31=%d -DTOPBASE=%lluUL -DTOPW=%du "
             "-DQL=%lluUL -DQH=%lluUL -DQHL=%lluUL -DQHH=%lluUL",
             N, M, L.nPrimes, (int)t61.fold, t31 ? (int)t31->fold : 0, (unsigned long long)L.topBase, (int)L.width[N - 2],
             (unsigned long long)(u64)Q, (unsigned long long)(u64)(Q >> 64), (unsigned long long)(u64)QH, (unsigned long long)(u64)(QH >> 64));
    const char* sp = src.c_str();
    prog = clCreateProgramWithSource(ctx, 1, &sp, nullptr, &err); check(err, "program");
    err = clBuildProgram(prog, 1, &devs[pick].dev, opts, nullptr, nullptr);
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
      kWeight[fi] = kernel("weight" + sfx); kPw[fi] = kernel("pw" + sfx);
      for (int r = 1; r <= 4; r++) { kDif[fi][r] = kernel("dif" + sfx + "_" + std::to_string(r)); kDit[fi][r] = kernel("dit" + sfx + "_" + std::to_string(r)); }
    }
    kCarry1 = kernel("carry1"); kCarry2 = kernel("carry2");
    for (int lv = ilog2(M); lv > 0;) { int r = lv >= 4 ? 4 : lv; if (lv == 5) r = 3; plan.push_back(r); lv -= r; }
  }
  ~OclEngine() override {
    if (q) clFinish(q);
    for (auto& ks : kDif) for (auto k : ks) if (k) clReleaseKernel(k);
    for (auto& ks : kDit) for (auto k : ks) if (k) clReleaseKernel(k);
    for (auto k : kWeight) if (k) clReleaseKernel(k);
    for (auto k : kPw) if (k) clReleaseKernel(k);
    if (kCarry1) clReleaseKernel(kCarry1);
    if (kCarry2) clReleaseKernel(kCarry2);
    for (auto m : owned) clReleaseMemObject(m);
    if (prog) clReleaseProgram(prog);
    if (q) clReleaseCommandQueue(q);
    if (ctx) clReleaseContext(ctx);
  }

  const Layout& layout() const override { return L; }
  std::string name() const override { return "opencl: " + devName; }

  void run(cl_kernel k, size_t gsize, std::initializer_list<cl_mem> bufs, const cl_uint* scalar = nullptr) {
    cl_uint i = 0;
    for (cl_mem b : bufs) check(clSetKernelArg(k, i++, sizeof(cl_mem), &b), "arg");
    if (scalar) check(clSetKernelArg(k, i++, sizeof(cl_uint), scalar), "arg");
    check(clEnqueueNDRangeKernel(q, k, 1, nullptr, &gsize, nullptr, 0, nullptr, nullptr), "enqueue");
  }
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
  void carry(cl_mem x) {
    run(kCarry1, N / 8, { z61, o61, z31, o31, widthB, x, carryB });
    run(kCarry2, N / 8, { x, carryB, widthB, flagB });
  }
  void sync() {
    check(clFinish(q), "finish"); pending = 0;
    int flag = 0; check(clEnqueueReadBuffer(q, flagB, CL_TRUE, 0, 4, &flag, 0, nullptr, nullptr), "flag");
    if (flag) throw std::runtime_error("internal: carry did not settle (OpenCL)");
  }
  void throttle() { if (++pending % 64 == 0) clFlush(q); if (pending >= 512) sync(); }

  void write(int r, const std::vector<i32>& d) override { check(clEnqueueWriteBuffer(q, regs.at(r), CL_TRUE, 0, N * 4, d.data(), 0, nullptr, nullptr), "write"); }
  void read(int r, std::vector<i32>& d) override { sync(); d.resize(N); check(clEnqueueReadBuffer(q, regs.at(r), CL_TRUE, 0, N * 4, d.data(), 0, nullptr, nullptr), "read"); }
  void copy(int dst, int src) override { check(clEnqueueCopyBuffer(q, regs.at(src), regs.at(dst), 0, 0, N * 4, 0, nullptr, nullptr), "copy"); }

  void square(int r, u64 count) override {
    cl_mem x = regs.at(r);
    int nf = L.nPrimes;
    for (u64 it = 0; it < count; it++) {
      for (int fi = 0; fi < nf; fi++) {
        cl_mem z = fi ? z31 : z61;
        forward(fi, x, z);
        run(kPw[fi], M / 2, { z, z, fi ? tw31 : tw61 });
        inverse(fi, z);
      }
      carry(x);
      throttle();
    }
    sync();
  }
  void mul(int dst, int src) override {
    cl_mem x = regs.at(dst), yv = regs.at(src);
    for (int fi = 0; fi < L.nPrimes; fi++) {
      cl_mem z = fi ? z31 : z61, y = fi ? y31 : y61;
      forward(fi, x, z); forward(fi, yv, y);
      run(kPw[fi], M / 2, { z, y, fi ? tw31 : tw61 });
      inverse(fi, z);
    }
    carry(x);
    sync();
  }
};

} // namespace

std::unique_ptr<Engine> makeOclEngine(const Layout& L, int nRegs, int device, bool verbose) {
  return std::unique_ptr<Engine>(new OclEngine(L, nRegs, device, verbose));
}

std::string listOclDevices() {
  std::ostringstream o; int i = 0;
  for (auto& d : enumerate()) o << i++ << ": " << d.name << (d.gpu ? "  [GPU]" : "  [CPU/other]") << "\n";
  if (!i) o << "no OpenCL devices found\n";
  return o.str();
}
