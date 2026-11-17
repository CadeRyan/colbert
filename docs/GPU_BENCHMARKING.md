# Validating colbert on a GPU, and measuring its speed

This is the protocol for the first run on real GPU hardware. It answers, in order:

1. Does the GPU compute the right answers? (If not, nothing else matters.)
2. How fast is one squaring at the size that matters, n ≈ 48 million?
3. How does that compare with proth20 on the **same** GPU?
4. Does the performance model in [PERFORMANCE.md](PERFORMANCE.md) hold up?

Plan on about an hour for steps 1–3, plus an optional few hours for step 1d. Build and
install first as in [SETUP.md](SETUP.md).

## Before you start

Record the setup. Every number below means little without it:

```bash
./colbert devices
```

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total,clocks.max.sm,clocks.max.mem,power.limit --format=csv
```

(On AMD, use `rocm-smi --showproductname --showdriverversion --showmaxpower` instead.)

Let the GPU idle for a minute, close other GPU programs (browsers count), and keep the room
temperature normal. Speed falls as the card heats up, so the sustained numbers matter, not
the first seconds.

## Step 1: correctness

### 1a. Self-test through the GPU kernels (≈1 minute)

```bash
./colbert selftest --backend ocl
```

Pass: the last line reads `59/59 checks passed on backend ocl`. Anything less: **stop**, and
save the full output and the OpenCL build log (`--verbose`).

### 1b. Full-size squarings against GMP (≈5–15 minutes, mostly GMP)

```bash
./colbert bench 21181 47856020 3 --backend ocl --verify
```

```bash
./colbert bench 67607 47856023 3 --backend ocl --verify
```

These two `k` use different internal structures (see DESIGN.md §5), so both paths get
exercised at production size. Pass: `ok  5 squarings at full size agree with GMP`.

### 1c. A known prime, end to end (≈minutes on a GPU)

```bash
./colbert test 46157 698207 --backend ocl --results gpu_validation.jsonl
```

```bash
./colbert test 54767 1337287 --backend ocl --results gpu_validation.jsonl
```

Both are primes found by Seventeen or Bust. Pass: `"result":"PRIME"` with `"rollbacks":0`. For
reference, the first took 38 minutes on the 4-core CPU build.

### 1d. Optional: a larger known prime (several hours)

```bash
./colbert test 4847 3321063 --backend ocl --ckpt ckpt --results gpu_validation.jsonl
```

This 999,744-digit prime runs for millions of iterations. It is the best evidence of
long-run stability before trusting multi-hour tests.

## Step 2: speed at the leading edge

```bash
for k in 21181 22699 24737 55459 67607; do ./colbert bench $k 47856020 2000 --backend ocl; done 2>&1 | tee bench_colbert.txt
```

Each line reports milliseconds per iteration over 2000 squarings, after a warm-up, and the
implied hours per full test. Run the loop **three times** and use the median. All five
should be within a few percent of one another (same transform size); a big outlier means
something else was using the GPU.

Then check sustained speed. Start a real test and read the `ms/it` in its progress lines
after 10 minutes, once clocks and temperature have settled:

```bash
./colbert test 21181 47856020 --backend ocl --ckpt ckpt
```

Stop it with Ctrl-C after reading the number; the checkpoint lets it resume later if you
want.

While it runs, record power draw:

```bash
nvidia-smi --query-gpu=power.draw,clocks.sm,temperature.gpu --format=csv -l 5
```

## Step 3: the same number on proth20

proth20 is the existing GPU tester for these numbers, so it is the fair comparison. Build
it from https://github.com/galloty/proth20 (`make -f Makefile_linux64`), then:

```bash
./proth20 -q "21181*2^47856020+1"
```

It prints a progress line ending in `ms/mul`. Read it after 10 minutes, as above, then stop
it. That is the same unit as colbert's ms/iteration.

Also note proth20's power draw. **Tests per kWh** is the comparison that matters most for a
volunteer project; it is computed from ms per iteration and watts.

## Step 4: compare with the model

Edit the `devices` list in `tools/perf_model.py` to add your GPU's memory bandwidth,
FP64 rate and integer multiply rate (from its specification sheet), then run:

```bash
python3 tools/perf_model.py
```

What to expect, and how to read it:

| observation | meaning |
|---|---|
| colbert today is **slower** than proth20, roughly 2× | expected. The kernels are unoptimized (about 6× the memory passes of a tuned code; see PERFORMANCE.md) |
| colbert ms/iteration ≈ 5–8× the model's lower bound | consistent with the model; tuning should recover most of that |
| colbert ≫ 10× the lower bound | something besides memory traffic dominates (kernel launch overhead, or 64-bit multiplies far slower than assumed on this GPU). Worth profiling before optimizing |
| proth20 ≈ 1.3–2× its lower bound | confirms proth20 is near memory-bound, the premise of the 2.5× estimate |
| proth20 ≫ 2× its lower bound | proth20 is limited by something else, and the estimate of colbert's advantage must be redone |

## What to report

Add a section to [RESULTS.md](RESULTS.md) with:

* GPU model, driver version, OS, power limit and clocks (from "Before you start");
* step 1 pass or fail for each part, with the JSON lines from `gpu_validation.jsonl`;
* median ms/iteration from step 2 (benchmark and sustained), for colbert and proth20;
* average power draw for each program under load;
* the model's lower bound for this GPU.

From those: hours per test, tests per day, and tests per kWh for each program. If
anything failed, include the full output. A failure on real hardware is the most valuable
result this protocol can produce.

## If you're running this through a remote session

If Claude is driving the machine through Remote Control, it can run all of the above,
including building proth20 and editing the model. A person still needs to confirm the GPU
isn't otherwise busy, and should glance at temperatures during the long runs.
