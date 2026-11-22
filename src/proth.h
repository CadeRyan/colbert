// Proth test of P = k*2^n + 1 on top of an Engine, with Gerbicz-Li error checking and
// resumable, verified checkpoints.
#pragma once
#include "engine.h"
#include <gmpxx.h>
#include <functional>

// Snapshot passed to ProthOptions::onEvent. Rates are milliseconds per squaring.
struct ProthStatus {
  u64 iteration = 0, total = 0;          // squarings done / needed (total = n - 1)
  u64 checksPassed = 0, rollbacks = 0;
  u64 verifiedIteration = 0;             // last state proven correct (and checkpointed, if enabled)
  u64 resumedFrom = 0;
  u32 gerbiczL = 0; u64 checkEvery = 0;
  double elapsed = 0, msPerIter = 0, msPerIterRecent = 0;
  std::string checkpoint;                // start: "none" | "new" | "resumed" | "rejected: <why>"
};

struct ProthOptions {
  u32 gerbiczL = 0;              // block length; 0 = pick ~sqrt(n)/2, capped
  std::string checkpointPath;    // empty = no checkpoints
  double reportSeconds = 30;     // human-readable progress on stderr
  bool quiet = false;
  // Machine-readable events: "start", "progress" (every eventSeconds), "verified", "rollback",
  // "stopped". Called on the testing thread at block boundaries.
  std::function<void(const char* event, const ProthStatus&)> onEvent;
  double eventSeconds = 5;
  // Polled at every block boundary. When it returns true the test forces a Gerbicz check,
  // saves the verified state and returns with ProthResult::stopped set.
  std::function<bool()> stopRequested;
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
  bool stopped = false;          // stopRequested() fired; no verdict. `iterations` = verified point
};

ProthResult prothTest(Engine& e, const ProthOptions& opt);

// Smallest prime a with Jacobi(a | P) = -1.
u32 prothBase(u32 k, u64 n);

// Default Gerbicz block length for n (what gerbiczL = 0 selects).
u32 defaultGerbiczL(u64 n);
