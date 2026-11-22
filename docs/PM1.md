# P−1 factoring

Before a number gets its first Proth test, the app runs Pollard's P−1 method on it. A factor
proves the number composite, so it needs no test at all; the ledger checks the factor with one
modular exponentiation and the number is settled.

With the project's candidate list (sieved to 2³²), P−1 at the bounds the engine picks finds a
factor for about **one number in four**, for **under 4% of the work of a test**. That removes
about a fifth of the project's total work. A deeper sieve would find many of the same factors
more cheaply (PrimeGrid's sieve reaches about 2⁵⁷, where P−1 barely pays); until we have one,
P−1 is the cheapest way to remove work.

## How it works

For a prime factor f of P = k·2ⁿ+1, Fermat's little theorem gives 3^(f−1) ≡ 1 (mod f), so f
divides gcd(3^E − 1, P) whenever f − 1 divides E.

* **Stage 1.** E is the product of every prime power up to B1. If f − 1 is B1-smooth (all its
  prime factors are at most B1), stage 1 finds f. Cost: about 1.44·B1 squarings of P, the same
  squarings as a Proth test. The multiplication by 3 is folded into the carry step, so it is
  free.
* **Stage 2.** It catches factors where f − 1 is B1-smooth apart from one prime q with
  B1 < q ≤ B2. With y = 3^E, every prime q = mD − r (0 < r < D, gcd(r, D) = 1) multiplies an
  accumulator by y^(mD) − y^r. The y^r are kept on the GPU as transformed values ("spectra"),
  so each prime costs one product in the transform domain, about 1.2 squarings. D is chosen
  from the GPU memory available (D = 330 and 81 spectra of 24 MiB each, about 2 GB, at the
  leading edge with the default budget).

GCDs use GMP and take about 5 seconds at n ≈ 48 million.

**No error checking is needed.** A gcd is always a true divisor of P, so a hardware error can
only hide a factor, never invent one. A number whose P−1 finds nothing goes on to the Proth
test, which is Gerbicz-checked as before.

## Choosing B1 and B2

`colbert pm1` (and `colbert info`) choose the bounds that maximise

    expected saving = P(factor | B1, B2, sieve depth) × (cost of a test) − cost of P−1

P(factor) is the usual estimate (as GIMPS uses): a factor between 2^(j−1) and 2^j exists with
probability about 1/j, and it is found when (f−1)/2 is (B1, B2)-smooth, from Dickman's ρ. The
cost of a test includes the expected 5% of double checks. At n ≈ 48 million:

| sieve depth | B1 | B2 | chance of a factor | P−1 cost (share of a test) | saving (share of a test) |
|---|---|---|---|---|---|
| 2³² (the project's list) | 340,000 | 17,000,000 | 24% | 3.7% | 22% |
| 2⁴⁰ | 410,000 | 12,000,000 | 12% | 3.1% | 9.5% |
| 2⁵⁰ | 230,000 | 4,600,000 | 3.3% | 1.5% | 2.1% |
| 2⁵⁷ (about PrimeGrid's sieve) | 90,000 | 1,800,000 | 0.9% | 0.6% | 0.3% |

The ledger publishes the sieve depth of its list (`sieve_bits` in its config), so every app plans
the same way. For your own lists the app assumes 2³² (Settings, `sieve_bits`).

On the Apple M4 Pro, P−1 for one leading-edge number takes about 1.5 hours; the test takes 40.

## In the app and the ledger

* The app runs P−1 only before a **first** test (never for a double check), and only when it
  pays: a number whose test is already far along is not worth factoring.
* A factor is uploaded as a result `{"factor": "…"}`. The ledger verifies it and marks the
  number **factored**, which is final: no double check, and any reported prime for that
  number is marked refuted.
* P−1 that finds nothing is reported with the next heartbeat (`"pm1": {"b1", "b2"}`). The
  ledger keeps the bounds on the number, so if the assignment is handed to someone else, they
  skip straight to the test.
* P−1 checkpoints like a test (every 10 minutes, and on pause), in `checkpoints/K_N.pm1`.
* Settings → "Look for a factor first (P−1)" turns it off.

## Commands

    colbert pm1 K N [--b1 B1 --b2 B2] [--sieve-bits 32] [--memory MB] [--ckpt DIR] [--stop-file F] [--json]
    colbert info K N --json --sieve-bits 32          # includes the plan: "pm1": {b1, b2, probability, cost_iterations, ...}

Events are listed in [ENGINE_PROTOCOL.md](ENGINE_PROTOCOL.md). `selftest` checks stage 1 and the
stage-2 product against GMP on numbers with known factors (`tools/pm1_cases.py` finds them),
and `tools/check_protocol.py` checks stopping and resuming in stage 2.
