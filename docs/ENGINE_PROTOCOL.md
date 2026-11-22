# The engine's machine interface

The desktop app ([APP.md](APP.md)) and the ledger ([LEDGER.md](LEDGER.md)) use `colbert` only
through the interface on this page. Everything else can change freely during GPU tuning:
kernels, transform sizes, memory layout, the Gerbicz schedule, human-readable output.

`tools/check_protocol.py` tests this contract and runs as part of `make check`. If a change
passes `make check`, the app keeps working.

**Protocol version: 1.** It's reported by `colbert version --json`. Adding events or fields is
not a breaking change. Removing or renaming them, or changing their meaning, is a breaking
change and needs a new protocol number (`PROTOCOL` in `src/main.cpp`, `ENGINE_PROTOCOLS` in
`app/colbert_app/__init__.py`).

## Conventions

* `--json` puts one JSON object per line on **stdout**, each with an `"event"` field.
  Human-readable text goes to stderr. Nothing else is written to stdout.
* Readers ignore events and fields they don't know.
* Times are seconds and rates are milliseconds per squaring (`ms_per_iter`).

| exit status | meaning |
|---|---|
| 0 | success: a verdict, a benchmark, a passing selftest |
| 1 | error (an `error` event says why), or `selftest` had failures |
| 2 | usage error |
| 3 | `test`/`work`/`pm1` stopped because the `--stop-file` appeared; the last verified state is checkpointed |

## Commands

### `colbert version --json`

```json
{"event":"version","engine":"colbert","version":"1dde3c0","protocol":1,"backends":["cpu","ocl"],
 "features":["json","stop-file","bench-seconds","devices-json","info-json","checkpoint-status","pm1"]}
```

`version` comes from `git describe` at build time. Results carry it, and the ledger uses it to
tell builds apart. A build from uncommitted changes to `src/` or the Makefile is
`<commit>-dirty.<8 hex digits>`, where the digits hash the diff. Each distinct edit therefore
gets its own version. The app also keys its device checks on a hash of the binary itself.

### `colbert devices --json`

```json
{"event":"devices","opencl":true,"devices":[{"index":0,"name":"Apple M4 Pro","type":"GPU","vendor":"Apple",
 "platform":"Apple","version":"OpenCL 1.2 ","driver":"1.2 1.0","compute_units":20,"clock_mhz":1000,
 "global_mem":19069665280,"max_alloc":3575562240,"unified_memory":true}]}
```

`index` is what `--device` takes. `unified_memory` is true for integrated GPUs. A build
without OpenCL reports `"opencl":false` with a `reason`.

### `colbert info K N --json`

Reports the transform that would be used: `N`, `primes`, `bits_per_word`, `bound_bits`,
`limit_bits`, `base`, `gerbicz_block` (the default) and `bytes_per_checkpoint`. With the `pm1`
feature it also carries the P−1 plan for `--sieve-bits` (default 32): `"pm1": {"b1", "b2",
"probability", "cost_iterations", "saving_iterations", "sieve_bits", "D"}`. `b1` = 0 means P−1
does not pay for this number.

### `colbert selftest --json [--backend B --device I]`

One `check` event per case (`ok`, `text`), then
`{"event":"selftest","passed":59,"total":59,"ok":true,"backend":"ocl","engine":"…"}`.
The number of checks may grow, so the app uses `ok` and the exit status, not the count.

### `colbert bench K N ITERS --json [--seconds S] [--verify]`

`{"event":"bench","k":…,"n":…,"N":…,"iterations":…,"ms_per_iter":…,"hours_per_test":…,"backend":…,"engine":…}`.
With `--seconds S`, the run stops after about S seconds and ITERS is only an upper bound.
With `--verify`, the event adds `"verified": true|false`, comparing the result with GMP.

### `colbert test K N --json --ckpt DIR --stop-file F [--gerbicz L] [--event-seconds S]`

| event | when | fields beyond the common ones |
|---|---|---|
| `start` | once, before the first squaring | `N`, `primes`, `bits_per_word`, `backend`, `engine`, `gerbicz_block`, `check_every`, `resumed_from`, `checkpoint` |
| `progress` | every `--event-seconds` (default 5), at block boundaries | |
| `verified` | after each passing Gerbicz check; the checkpoint has been written | |
| `rollback` | a Gerbicz check failed; the run returns to `verified_iteration` | |
| `stopped` | the stop file was seen; the state at `iteration` is verified and saved; exit 3 | |
| `result` | the verdict; the same object is appended to `--results` | `result` (`PRIME`/`composite`), `base`, `res64`, `N`, `iterations`, `gerbicz_ok`, `rollbacks`, `seconds`, `backend`, `engine` |
| `error` | fatal; exit 1 | `message` |

Common fields on `start`, `progress`, `verified`, `rollback` and `stopped`: `k`, `n`,
`iteration`, `total` (= n − 1), `percent`, `verified_iteration`, `checks_passed`, `rollbacks`,
`elapsed`, `ms_per_iter` (since this run started), `ms_per_iter_recent` (since the previous
`progress` event), `eta_seconds`.

`checkpoint` on `start` is one of:

* `new`: no checkpoint existed;
* `resumed`: the run continues from `resumed_from`;
* `rejected: <reason>`: a checkpoint existed but doesn't fit this run. The engine moves it to
  `<file>.rejected`, never overwrites it, and starts from iteration 0.

A checkpoint is bound to (k, n, transform size, prime count, Proth base, Gerbicz block length).
**Pass the same `--gerbicz` when resuming.** The app records the value it chose for each
number. It also records the transform size and prime count from the `start` event, and passes
`--size` and `--primes` on every resume. A rebuilt engine whose automatic size choice has changed
can therefore still continue a test it didn't start.

**For engine developers:** if a change alters what a checkpoint's digits *mean* for the same
(k, n, N, primes, base, block length), change `CKPT_MAGIC` in `src/proth.cpp`. Old checkpoints
are then rejected (and kept) instead of being misread. A misread one would fail its first
Gerbicz check and could never produce a wrong verdict, but the run would end in an error rather
than a clean restart.

**Stopping.** Create the stop file. At the next block boundary the engine forces a Gerbicz
check, saves the verified state, emits `stopped` and exits with status 3. That takes at most
about two blocks of squarings. The engine doesn't delete the stop file; whoever created it does.

**Results file line.** Each line starts `{"k":K,"n":N,` (the `work` command's de-duplication
relies on this), followed by the fields of the `result` event.

### `colbert pm1 K N --json --ckpt DIR --stop-file F [--b1 B1 --b2 B2] [--sieve-bits B] [--memory MB]`

P−1 factoring ([PM1.md](PM1.md)), feature `pm1`. Without `--b1` the engine chooses the bounds
as `info` reports them. Units are stage-1 squarings plus stage-2 products, so `iteration` and
`total` count both stages; `ms_per_iter` is per unit.

| event | when | fields beyond the common ones |
|---|---|---|
| `start` | once | `phase` = `pm1`, `stage`, `b1`, `b2`, `D`, `probability`, `cost_iterations`, `N`, `primes`, `backend`, `engine`, `checkpoint` |
| `progress` | every `--event-seconds` | `phase`, `stage` |
| `stage2` | stage 1 found nothing; stage 2 begins | `D` (may be smaller than planned if memory was short) |
| `stopped` | the stop file was seen at a safe point; the state is saved; exit 3 | `phase`, `stage` |
| `pm1` | the outcome; the same object is appended to `--results` | `pm1` = `{b1, b2}`, `factor` (a decimal string, or `null`), `stage` (1 or 2, with a factor), `D`, `seconds`, `N`, `backend`, `engine`; `skipped` = true when P−1 does not pay (exit 0, nothing run) |

A found factor is a true divisor of P (it comes from a gcd) and may be composite. The P−1
checkpoint `DIR/K_N.pm1` is bound to (k, n, N, primes, B1); stage 2 resumes with any B2 and D.
It is removed when P−1 finishes.

## How the app uses this, and why it survives tuning

* It never parses stderr. Engine stderr is shown in its log, verbatim.
* Each engine build is identified by `version`. A build the app hasn't seen gets a `selftest`
  and a timed `bench` on every device before it gets work. So rebuilding after a kernel change
  re-validates automatically, and a build that miscomputes on some GPU is never used there.
* It chooses `--gerbicz` from the measured speed, so that a verified checkpoint lands about
  every 10 minutes (user setting). It stores the value with the task, so every restart
  resumes the same checkpoint.
* "Extra engine arguments" in its settings are passed to every Proth test. New tuning flags
  can be tried from the app without a new app release.
* With the `pm1` feature it plans P−1 with `info`, runs `pm1` before a first test when that
  pays, and pins the transform size from the `pm1` `start` event for the test that follows.

### Transform tuning knobs (environment variables)

These change speed only; every choice gives bit-identical results.

| variable | effect |
|---|---|
| `COLBERT_FFT=radix2` | use the original radix-2 kernels instead of the four-step transform |
| `COLBERT_CPG=1\|2` | columns per work-group in the column passes (default 2 where it fits) |
| `COLBERT_WOTF=0\|1` | weights from tables (0) or computed on the fly (1); default 1, except 0 on Apple GPUs |

The four-step kernels compare themselves with the radix-2 kernels on random data when the
engine starts; if they disagree, the engine falls back to radix-2 and says so (`--verbose`, and
in `bench`).
