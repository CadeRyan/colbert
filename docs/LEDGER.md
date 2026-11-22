# The ledger: coordinating many computers

The ledger is a small web service that hands out numbers to test and records what comes back.
Every copy of the Colbert app that joins the project talks to it. Its job is to make sure that,
however many computers join or leave and however unreliable they are:

* **no candidate is skipped** (no gaps);
* **no work is repeated unless repeating it is the point** (no needless duplication);
* **every result that matters is checked by an independent computer** before it counts;
* **a bad engine build can be withdrawn** and its results redone.

Code: `ledger/`. Tests: `ledger/tests/`. Deployment: `deploy/ledger/`.

**The project's ledger:** https://colbert-ledger-214187368360.us-central1.run.app (status page
at `/`). It runs on Cloud Run + Firestore in the Google Cloud project `colbert-ledger-f1a3`, and
the app offers to join it by default (`PROJECT_LEDGER_URL` in `app/colbert_app/__init__.py`).
It holds the 194,260 candidates in `data/candidates_47.9M-57.5M_p4.3e9.txt.gz` (n from
47,900,038 to 57,499,858, sieved to 2^32), loaded on 21 November 2026 as the 207,973 survivors
of the 10⁹ sieve with the 13,713 listed in `data/factors_47.9M-57.5M_p1e9-4.3e9.txt` removed.
New candidates can only be appended above n = 57,499,858.

## How it works

### Candidates and the cursor

The candidate list (sieve output, `k n` per line) is loaded once with `admin seed` and stored
in order of increasing n. A **cursor** marks how far into the list work has been issued. New
work always comes from the cursor, so the search advances as a contiguous wavefront. Loading a
longer list later appends to it; re-loading the same list adds nothing.

### Assignments and leases

Giving a number to a computer creates an **assignment** with a **lease** (default 3 days).
While it works, the app sends a heartbeat every 15 minutes with its progress, and each heartbeat
renews the lease. A computer that is switched off, uninstalled or broken stops sending them, and
its lease runs out. The next request for work then returns that number to the pool, and it goes
out again ahead of anything new.

If the original computer comes back before anyone else has picked the number up, it simply
reclaims it and continues from its checkpoint. If it comes back after the number went to
someone else, both carry on: the first result to arrive counts, and the second becomes its
double check, or is told to stop when it isn't needed.

A computer has at most one live assignment. Asking for work while holding one returns the same
one, so retries after network errors never create duplicates.

### The invariant behind "no gaps"

> Every candidate that has been issued but not settled has at least one live assignment or
> exactly one entry in the queue.

Every operation preserves it: issuing, expiry, heartbeats, results, releases, removals and
withdrawn builds. `admin audit` checks it across the whole ledger, along with the claim that
every list position below the cursor has been issued or deliberately skipped, and that the
count of removed candidates still ahead of the cursor (which the status page subtracts) matches
the list. `admin audit --repair` re-queues anything that has fallen through and corrects that
count. The tests run the audit
after every scenario, including a stress test with eight concurrent workers, short leases,
workers vanishing mid-test and one worker returning wrong residues.

### Results and double checks

A result reports the verdict (`PRIME` or `composite`) and **res64**, the low 64 bits of the
final residue. Two independent tests of the same number must produce the same res64. A
candidate is **settled** when it has either:

* **done**: one result, and policy didn't ask for a check; or
* **verified**: matching results from at least two different computers, more than agree on
  any other answer. If the results have ever disagreed, the winning side must also include two
  different owners; or
* **factored**: someone found a factor ([PM1.md](PM1.md)). The ledger checks it itself
  (q divides k·2ⁿ+1 is one modular exponentiation), so it needs no double check, ends any
  check in progress, and marks a reported prime for that number as refuted.

Policy asks for a check when any of these hold:

| reason | why |
|---|---|
| the result is PRIME | always: a prime needs independent confirmation before anyone hears of it |
| the computer hasn't yet had `worker_trust_after` (2) results confirmed | new hardware, new drivers, or a newcomer who might be gaming the system |
| the engine build hasn't yet had `engine_trust_after` (5) results confirmed by a *different* build or backend | a fresh build after kernel tuning is checked until it has a track record |
| the test needed 3 or more error corrections | the hardware is marginal |
| random, with probability `dc_fraction` (5%) | keeps everyone honest; nobody can predict which results get checked |

A computer never checks its own result. A check is also *preferred* to come from a
different owner and a different implementation: another engine build, or CPU against GPU.
The reason: one person's machines may share a bad driver, and a deterministic bug in one build
produces the same wrong residue every time. A computer that wouldn't be independent gets fresh
work instead. Only after a check has waited `dc_other_impl_wait_seconds` (1 day) for an
independent computer does it go to whoever asks, so a small project with one kind of hardware
still makes progress.

**Mismatches.** When two results disagree, the candidate goes into **conflict** and gets a
tie-break. The tie-break never goes to an owner who already reported on that number. Whoever
ends up on the losing side has their trust reduced, which means more of their future results
get checked. A late result can't overturn this. A two-against-two split stays a conflict, and
one person's machines can't out-vote an independent result, even when they agree with each
other.

**Primes on the status page.** A reported prime is listed as *awaiting independent check*
until it is settled, then as *verified* or *refuted*.

**Strict mode.** `dc_distinct_owner=true` makes the owner rule absolute, and agreement then
counts distinct owners rather than computers. Turn it on once the project has enough
participants. While one person runs every machine, it would leave every check waiting forever.

### Engine builds

Every result records the engine's `version` (from `git describe`). During tuning this lets you
contain a bad build:

```bash
python3 -m ledger admin invalidate 1dde3c0
```

This marks every result from that build invalid and re-queues whatever those results had
settled. It also blocks the build from new work, so clients are told to update. Computers
still running that build are told to stop at their next heartbeat, and their numbers go
straight back into the pool. Results the build sends afterwards are recorded but count for
nothing. Results from the build that other builds had independently confirmed stay settled.

Dirty builds get their own version: `<commit>-dirty.<hash of the source diff>`. So during
tuning, every distinct uncommitted kernel edit is a separate build. Each one has to earn trust
separately, and each can be withdrawn on its own.

Related settings: `blocked_engines` and `allowed_engines` (lists of builds), and
`accept_dirty_engines` (false: refuse builds from modified source).

### Speed limits

`max_projected_days` (default 0 = no limit) refuses work to devices whose benchmark says a
test would take longer than that. With no limit, a CPU-only computer can take a leading-edge
test, and it may hold that number for months. Its lease stays alive as long as it keeps
reporting.

## Protocol (version 1)

JSON over HTTPS. Workers authenticate with `Authorization: Bearer WORKER_ID:TOKEN`, received
once from `/v1/register`. Errors are `{"error": "...", "code": "..."}` with these statuses:

| status | meaning | client should |
|---|---|---|
| 401 | unknown worker or wrong token | register again |
| 403 | refused by policy (`too_slow`, `disabled`, `invite_required`, `registration_closed`) | stop and tell the user |
| 404 | no such assignment for this worker | drop the assignment |
| 426 | engine build withdrawn or not accepted | stop and ask the user to update |
| 429, 503 | rate-limited, or transient contention | retry after `Retry-After`, with jitter |

| endpoint | body → response |
|---|---|
| `GET /v1/status` | public: candidates (loaded minus removed), removed, counts by status, `tested_through_n` (every candidate below has a result), `complete_through_n` (every candidate below is settled), tests in the last 24 h, projected days to finish, primes reported, top contributors. Cached 30 s |
| `POST /v1/register` | `{owner, name, invite?, info}` → `{worker_id, token, config}` |
| `POST /v1/work` | `{info: {engine, backend, ms_per_iter, …}}` → `{assignment: {id, k, n, kind, lease_until, pm1_done?} \| null, reason?, retry_after?, config}`. `pm1_done` = `{b1, b2}` when P−1 already ran on this number without a factor. `kind` is `first`, `dc` or `tiebreak`. `reason` is `paused`, `not_started` (no candidates loaded yet), `exhausted`, or `waiting` (only checks remain, and this computer isn't independent of the earlier results) |
| `POST /v1/progress` | `{assignment, report: {iteration, ms_per_iter, checks_passed, rollbacks, phase?, pm1?}}` → `{action: "continue" \| "abandon", reason?, config}`. `phase` is `pm1` or `test`; `pm1` = `{b1, b2}` reports P−1 finished without a factor, and the ledger keeps the largest bounds on the number |
| `POST /v1/result` | `{assignment, result: <the engine's result event>}` → `{accepted, status, double_check}`. Or a factor: `result: {k, n, factor, b1, b2, stage, engine, backend}`, refused with 422 `not_a_factor` unless it divides k·2ⁿ+1. Safe to repeat |
| `POST /v1/release` | `{assignment}`: hand work back early |
| `GET /v1/me` | this worker's counts, recent history and current assignment |
| `/v1/admin/*` | `config`, `seed`, `remove`, `invalidate`, `audit`, `export`: `Authorization: Bearer admin:ADMIN_TOKEN` |

`config` in responses carries `heartbeat_seconds`, `lease_seconds`, `message` (shown in every
app), `paused`, `pm1` (whether apps should run P−1 before first tests) and `sieve_bits` (the
depth the candidate list was sieved to; apps choose P−1 bounds from it). The project's list is
sieved to 2³², so `sieve_bits` is 32; after a deeper sieve, raise it with `admin config`.

The server checks every result: it must belong to an assignment held by that worker, match
its k and n, report n − 1 iterations, and a PRIME verdict must come with res64 = 0.

## Running it

### Locally (development, or a self-hosted project on one machine)

```bash
LEDGER_ADMIN_TOKEN=$(openssl rand -hex 16) python3 -m ledger serve --db ledger.sqlite --port 8080
```

Standard library only: one SQLite file, which you can back up by copying it. Open
http://127.0.0.1:8080 for the status page. Use `--host 0.0.0.0` to accept other computers, and
put TLS in front of it.

### On Google Cloud

```bash
PROJECT=colbert-ledger-1234 BILLING=XXXXXX-XXXXXX-XXXXXX deploy/ledger/deploy.sh
```

This creates a dedicated project with:

* the service on **Cloud Run**, scaling to zero, at most 2 instances;
* the data in **Firestore** (native mode). Every query uses Firestore's automatic indexes, so
  there's nothing to configure;
* a service account that can only read and write Firestore;
* the admin token in **Secret Manager**;
* a monthly **budget alert**.

Re-run the script to deploy new code. `deploy/ledger/teardown.sh` deletes the whole project.

The script uses a dedicated build service account with only `roles/run.builder`. New projects'
default build account no longer has the permissions Cloud Build needs. The budget is created
in the billing account's own currency, which budgets require.

The same logic runs on both stores. The SQLite store also enforces Firestore's
reads-before-writes rule, so local tests catch a violation, and the test suite runs unchanged
against the Firestore emulator:

```bash
gcloud emulators firestore start --host-port=localhost:8686 &
FIRESTORE_EMULATOR_HOST=localhost:8686 python3 -m unittest ledger.tests.test_firestore
```

### Day-to-day administration

```bash
export LEDGER_URL=https://colbert-ledger-214187368360.us-central1.run.app
export LEDGER_ADMIN_TOKEN=$(gcloud --project colbert-ledger-f1a3 secrets versions access latest --secret colbert-ledger-admin-token)
python3 -m ledger admin status
python3 -m ledger admin seed candidates.txt.gz --min-n 47900000
python3 -m ledger admin remove factors.txt             # a deeper sieve found factors (k n [p] per line)
python3 -m ledger admin config message='"Engine 2.0 is out: please update"'
python3 -m ledger admin config registration='"invite"' invite_code='"spring-2027"'
python3 -m ledger admin config paused=true             # stop issuing work
python3 -m ledger admin invalidate <engine-version>
python3 -m ledger admin audit
python3 -m ledger admin export --out backup.jsonl      # every issued candidate and its results
```

## What it costs on Google Cloud

The service handles roughly one request per computer per 15 minutes (heartbeats), plus a few
per finished test. A leading-edge test takes hours to days, so that's light traffic.

| computers | requests / month | Firestore reads / day | writes / day | expected cost |
|---|---|---|---|---|
| 10 | ~30,000 | ~5,000 | ~1,000 | **$0** (inside the free tier) |
| 100 | ~300,000 | ~60,000 | ~12,000 | **≈ $0–1 / month** |
| 1,000 | ~3,000,000 | ~600,000 | ~120,000 | **≈ $10–20 / month** (Firestore operations, plus Cloud Run beyond 2M requests) |

Free quotas used, per month unless stated: Cloud Run 2M requests and 180,000 vCPU-seconds;
Firestore 50,000 reads, 20,000 writes per day and 1 GiB storage; Secret Manager 6 secret
versions; Artifact Registry 0.5 GB. Each deploy adds a container image of about 150 MB to
Artifact Registry, so delete old images now and then. The numbers above are estimates from the
request pattern, not measurements. The budget alert is there to catch a surprise.

Levers if it grows: raise `heartbeat_seconds` (halving the heartbeat rate roughly halves the
cost), and the status page is already cached.

## Security model, and what it doesn't protect against

* Workers hold random 32-character tokens, stored only as hashes. The admin token sits in
  Secret Manager. Admin endpoints are off when no token is set.
* Registration can be `open`, `invite` (requires a code) or `closed`.
* Rate limits per worker and per IP stop runaway clients (per instance, in memory). The IP is
  the address the last trusted proxy saw: a client can write anything at the front of
  `X-Forwarded-For`, so only entries added by proxies count (`LEDGER_PROXY_HOPS`: 1 on Cloud
  Run, 0 when serving directly; add one for a load balancer in front).
* Anything that costs the server real work, such as checking a factor, happens only after
  the worker's token has been checked, and a factor is checked without building k·2ⁿ+1.
* **Sybil attacks.** One person can register many computers under many names. Random
  double checks, trust that has to be earned, and the preference for checks by other owners
  make a forged result likely to be caught, but not certain. The defence that removes this
  entirely is a proof of work. LLR2 and PRST attach a Pietrzak/VDF certificate to each test,
  which the server can verify in a fraction of the test's time; that would let this ledger
  drop most double checks. It's the natural next step (see below).

## Known limits and next steps

* **Checkpoints stay on the computer.** If a computer disappears, its partial work is lost
  and the number restarts from zero elsewhere. Uploading checkpoints (16 MB at the leading
  edge) to Cloud Storage would let another computer resume abandoned work.
* **Proof-of-work certificates** (above) would replace most double checks.
* **One device per app.** A computer with two GPUs runs two copies of the app, each with
  its own `--data` directory.
* **PrimeGrid.** PrimeGrid's Seventeen or Bust subproject is testing this range now, and
  numbers below its leading edge have already been tested (see the README). Seed the ledger
  only with ranges you mean to test, and from a deep sieve.
