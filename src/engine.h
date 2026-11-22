// Backend-independent interface: a handful of residue registers and the one operation
//   a o b := k*a*b mod (k*2^n + 1)
// that the weighted transform computes. phi(x) = k*x maps (Z/P, o) isomorphically onto
// (Z/P, *), so everything a Proth test needs (squaring chains, Gerbicz products) can be
// phrased with `o` alone.
#pragma once
#include "layout.h"
#include <memory>
#include <string>

struct Engine {
  virtual ~Engine() {}
  virtual const Layout& layout() const = 0;
  virtual std::string name() const = 0;
  virtual std::string detail() const { return ""; }   // e.g. which transform the backend uses
  virtual void write(int reg, const std::vector<i32>& digits) = 0;
  virtual void read(int reg, std::vector<i32>& digits) = 0;
  virtual void copy(int dst, int src) = 0;
  virtual void square(int reg, u64 count) = 0;     // reg <- reg o reg, `count` times
  virtual void mul(int dst, int src) = 0;          // dst <- dst o src   (dst != src)

  // --- P-1 support
  // For each c in mults: reg <- c * (reg o reg). c is small (1 <= c < 2^16); the factor is
  // applied to the convolution output before the carry, so it costs nothing extra.
  virtual void squareMul(int reg, const std::vector<u32>& mults) = 0;
  // Spectrum slots: transformed values kept on the device (stage 2 of P-1).
  virtual size_t spectrumBytes() const = 0;        // device memory per slot
  virtual int allocSlots(int want, size_t budgetBytes) = 0;   // returns how many were allocated
  virtual void toSpectrum(int slot, int reg) = 0;  // slot <- transform of reg
  virtual void mulDiff(int reg, int slotA, int slotB) = 0;    // reg <- reg o (A - B)
  virtual size_t deviceMemory() const = 0;         // total device memory (bytes), for budgeting
};

std::unique_ptr<Engine> makeCpuEngine(const Layout& L, int nRegs);
// OpenCL: when set before the engine is made, every kernel launch is timed and
// oclProfileReport() summarises the time per kernel (bench --profile).
extern bool g_oclProfile;
std::string oclProfileReport();
// device < 0 picks the first GPU, falling back to any OpenCL device.
std::unique_ptr<Engine> makeOclEngine(const Layout& L, int nRegs, int device, bool verbose);
std::string listOclDevices();

struct OclDeviceInfo {
  int index = 0;
  std::string name, vendor, version, driver, platform;
  bool gpu = false, cpu = false, unifiedMemory = false;   // unified: integrated GPU (or a CPU device)
  unsigned computeUnits = 0, clockMHz = 0;
  unsigned long long globalMem = 0, maxAlloc = 0;
};
// Throws std::runtime_error in a build without OpenCL.
std::vector<OclDeviceInfo> oclDeviceInfo();
