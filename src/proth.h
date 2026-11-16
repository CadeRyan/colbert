// Proth test of P = k*2^n + 1 on top of an Engine, with Gerbicz-Li error checking and
// resumable, verified checkpoints.
#pragma once
#include "engine.h"
#include <gmpxx.h>
#include <functional>

struct ProthOptions {
  u32 gerbiczL = 0;              // block length; 0 = pick ~sqrt(n)/2, capped
  std::string checkpointPath;    // empty = no checkpoints
  double reportSeconds = 30;
  bool quiet = false;
  // testing hook: called after each block with the iteration count; may corrupt a register
  std::function<void(Engine&, u64)> faultHook;
};

struct ProthResult {
  bool prime = false;
  u32 base = 0;
  u64 res64 = 0;                 // low 64 bits of a^((P-1)/2) mod P  (== P-1 iff prime)
  u64 iterations = 0, checksPassed = 0, rollbacks = 0;
  double seconds = 0;
  bool resumed = false;
};

ProthResult prothTest(Engine& e, const ProthOptions& opt);

// Smallest prime a with Jacobi(a | P) = -1.
u32 prothBase(u32 k, u64 n);
