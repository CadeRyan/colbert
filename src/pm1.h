// P-1 factoring of P = k*2^n + 1 on an Engine (see docs/PM1.md).
//
// Stage 1: y = 3^E mod P with E = prod p^floor(log_p B1) over primes p <= B1; a factor f of P
// is found when f - 1 is B1-smooth: gcd(y - 1, P).
// Stage 2: for every prime q in (B1, B2], the product of (y^(mD) - y^r) with q = mD - r,
// 0 < r < D, gcd(r, D) = 1; finds f when f - 1 = (B1-smooth) * q. The y^r are kept as
// spectra on the device, so each prime costs one transform-domain product.
//
// Errors in P-1 can only hide a factor (a gcd is always a true divisor of P), so P-1 has no
// error check of its own; the Proth test that follows a negative P-1 is Gerbicz-checked.
#pragma once
#include "engine.h"
#include <gmpxx.h>
#include <functional>

struct Pm1Status {
  int stage = 1;                 // 1 or 2
  u64 done = 0, total = 0;       // work units over both stages (stage 1: squarings, stage 2: products)
  u64 B1 = 0, B2 = 0; u32 D = 0;
  double elapsed = 0, msPerUnit = 0, msPerUnitRecent = 0;
  std::string checkpoint;        // "new" | "resumed" | "rejected: <why>"
};

struct Pm1Options {
  u64 B1 = 0, B2 = 0;            // B2 <= B1: stage 1 only
  std::string checkpointPath;    // empty: no checkpoints
  bool quiet = false;
  double reportSeconds = 30, eventSeconds = 5, checkpointSeconds = 600;
  size_t memoryBudget = 0;       // bytes for stage-2 spectra; 0: pm1DefaultBudget()
  bool keepValues = false;       // testing: return the stage results as integers
  std::function<void(const char* event, const Pm1Status&)> onEvent;   // "start", "progress", "stage2", "stopped"
  std::function<bool()> stopRequested;
};

struct Pm1Result {
  bool stopped = false;
  std::string factor;            // decimal; empty if none found
  int stage = 0;                 // the stage that found it
  u64 B1 = 0, B2 = 0; u32 D = 0;
  double seconds = 0;
  mpz_class y, acc;              // keepValues: 3^E mod P and the stage-2 product (ordinary residues)
};

Pm1Result pm1Run(Engine& e, const Pm1Options& o);

// Spectrum memory used by default: a quarter of the device memory, at most 2 GiB.
size_t pm1DefaultBudget(const Engine& e);
// The largest baby-step span D whose phi(D) + 1 spectra fit in `slots`.
u32 pm1ChooseD(size_t slots);

// Probability that P-1 with (B1, B2) finds a factor of a number with no factor below
// 2^sieveBits (Dickman's rho; the usual heuristic, as used by GIMPS).
double pm1Probability(double B1, double B2, double sieveBits);
// Cost of P-1 in squarings of P.
double pm1Cost(double B1, double B2, u32 D);

// The bounds that maximise probability * testCost - cost (testCost: squarings a factor saves,
// i.e. a Proth test plus the expected share of double checks). B1 = 0: P-1 does not pay.
struct Pm1Plan { u64 B1 = 0, B2 = 0; double probability = 0, cost = 0, saving = 0; };
Pm1Plan pm1Choose(double testCost, double sieveBits, u32 D);
