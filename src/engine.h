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
  virtual void write(int reg, const std::vector<i32>& digits) = 0;
  virtual void read(int reg, std::vector<i32>& digits) = 0;
  virtual void copy(int dst, int src) = 0;
  virtual void square(int reg, u64 count) = 0;     // reg <- reg o reg, `count` times
  virtual void mul(int dst, int src) = 0;          // dst <- dst o src   (dst != src)
};

std::unique_ptr<Engine> makeCpuEngine(const Layout& L, int nRegs);
// device < 0 picks the first GPU, falling back to any OpenCL device.
std::unique_ptr<Engine> makeOclEngine(const Layout& L, int nRegs, int device, bool verbose);
std::string listOclDevices();
