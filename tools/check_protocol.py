#!/usr/bin/env python3
"""
Contract test for colbert's machine interface (docs/ENGINE_PROTOCOL.md).

The desktop app and the ledger depend only on this interface, not on engine internals, so
kernel and transform tuning can change anything else freely. This test fails if a change
breaks what they rely on: the --json events, exit codes, stop/resume via --stop-file and
checkpoints, the results-file line format, and correct residues across an interruption.

  python3 tools/check_protocol.py ./colbert [--backend cpu|ocl]

Runs in about ten seconds on a laptop CPU. Exit status 0 means every check passed.
"""
import json, os, shutil, subprocess, sys, tempfile, time

BIN = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "./colbert")
BACKEND = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else "cpu"
K, N, GL = 21181, 60013, 16          # composite; small enough for seconds on any CPU
fails = 0
# tiny transforms: thread start-up costs more than it saves
os.environ.setdefault("OMP_NUM_THREADS", "1")


def check(ok, what):
    global fails
    print(("ok    " if ok else "FAIL  ") + what, flush=True)
    if not ok:
        fails += 1


def events(args, **kw):
    """Run colbert with --json; return (exit code, list of events, stderr)."""
    p = subprocess.run([BIN, *args, "--json"], capture_output=True, text=True, **kw)
    evs = []
    for line in p.stdout.splitlines():
        try:
            evs.append(json.loads(line))
        except json.JSONDecodeError:
            evs.append({"event": "<not json>", "line": line})
    return p.returncode, evs, p.stderr


def main():
    tmp = tempfile.mkdtemp(prefix="colbert-protocol-")
    try:
        run(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("%s: %d failure(s)" % ("protocol ok" if not fails else "PROTOCOL BROKEN", fails))
    sys.exit(1 if fails else 0)


def run(tmp):
    rc, ev, _ = events(["version"])
    v = ev[0] if ev else {}
    check(rc == 0 and v.get("event") == "version" and isinstance(v.get("protocol"), int) and "cpu" in v.get("backends", []),
          "version: protocol %s, backends %s, engine %s" % (v.get("protocol"), v.get("backends"), v.get("version")))

    rc, ev, _ = events(["devices"])
    d = ev[0] if ev else {}
    check(rc == 0 and d.get("event") == "devices" and isinstance(d.get("devices"), list) and isinstance(d.get("opencl"), bool),
          "devices: opencl=%s, %d device(s)" % (d.get("opencl"), len(d.get("devices", []))))

    rc, ev, _ = events(["info", str(K), str(N)])
    info = ev[0] if ev else {}
    check(rc == 0 and info.get("event") == "info" and info.get("N", 0) > 0 and info.get("base", 0) > 1,
          "info: N=%s base=%s gerbicz_block=%s" % (info.get("N"), info.get("base"), info.get("gerbicz_block")))

    rc, ev, _ = events(["bench", str(K), str(N), "100000", "--seconds", "0.5", "--backend", BACKEND])
    b = ev[-1] if ev else {}
    check(rc == 0 and b.get("event") == "bench" and b.get("ms_per_iter", 0) > 0 and 0 < b.get("iterations", 0) < 100000,
          "bench --seconds: %s iterations, %.4f ms/iter" % (b.get("iterations"), b.get("ms_per_iter", 0)))

    check(all(e.get("event") != "<not json>" for e in ev), "stdout carries only JSON in --json mode")

    # --- interrupted run: stop at the first verified block, then resume to the end
    ck, stop, results = os.path.join(tmp, "ck"), os.path.join(tmp, "stop"), os.path.join(tmp, "r.jsonl")
    os.makedirs(ck)
    cmd = [BIN, "test", str(K), str(N), "--json", "--backend", BACKEND, "--gerbicz", str(GL), "--event-seconds", "0",
           "--ckpt", ck, "--results", results, "--stop-file", stop]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    seen = []
    for line in p.stdout:
        e = json.loads(line)
        seen.append(e)
        if e["event"] == "verified" and not os.path.exists(stop):
            open(stop, "w").close()
    rc = p.wait()
    kinds = [e["event"] for e in seen]
    start = seen[0] if seen else {}
    check(start.get("event") == "start" and start.get("checkpoint") == "new" and start.get("gerbicz_block") == GL
          and start.get("total") == N - 1 and "backend" in start and "engine" in start,
          "start event: checkpoint=%s gerbicz_block=%s total=%s" % (start.get("checkpoint"), start.get("gerbicz_block"), start.get("total")))
    check("progress" in kinds and all(k in seen[kinds.index("progress")] for k in
          ("iteration", "total", "percent", "ms_per_iter", "ms_per_iter_recent", "checks_passed", "rollbacks", "verified_iteration")),
          "progress events carry iteration, rate, checks and rollbacks")
    stopped = seen[-1] if seen else {}
    check(rc == 3 and stopped.get("event") == "stopped" and 0 < stopped.get("iteration", 0) < N - 1
          and stopped["iteration"] == stopped.get("verified_iteration"),
          "stop file: exit 3, stopped at verified iteration %s" % stopped.get("iteration"))
    check(not os.path.exists(results) or not open(results).read().strip(), "stopped run writes no result line")
    check(os.path.exists(os.path.join(ck, "%d_%d.ckpt" % (K, N))), "checkpoint written")

    os.remove(stop)
    rc, ev, _ = events(cmd[1:cmd.index("--json")] + cmd[cmd.index("--json") + 1:])
    start = ev[0] if ev else {}
    res = ev[-1] if ev else {}
    check(start.get("checkpoint") == "resumed" and start.get("resumed_from") == stopped.get("iteration"),
          "resume: checkpoint=%s from iteration %s" % (start.get("checkpoint"), start.get("resumed_from")))
    check(rc == 0 and res.get("event") == "result" and res.get("iterations") == N - 1 and "engine" in res,
          "result event after resume: %s res64=%s" % (res.get("result"), res.get("res64")))
    lines = open(results).read().splitlines() if os.path.exists(results) else []
    check(len(lines) == 1 and lines[0].startswith('{"k":%d,"n":%d,' % (K, N)) and json.loads(lines[0]).get("res64") == res.get("res64"),
          "results file: one line, starts with {\"k\":K,\"n\":N, (the work-command dedupe key)")

    # residues are checked against GMP by `selftest`; here: an interruption must not change them
    rc, ev, _ = events(["test", str(K), str(N), "--backend", BACKEND, "--results", os.path.join(tmp, "u.jsonl")])
    straight = ev[-1] if ev else {}
    check(rc == 0 and straight.get("res64") == res.get("res64") and straight.get("result") == res.get("result"),
          "interrupted-and-resumed residue equals an uninterrupted run (%s)" % straight.get("res64"))

    # --- a checkpoint that does not fit the run is set aside, never silently overwritten
    os.remove(results)
    shutil.rmtree(ck); os.makedirs(ck)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    for line in p.stdout:
        if json.loads(line)["event"] == "verified" and not os.path.exists(stop):
            open(stop, "w").close()
    p.wait()
    os.remove(stop)
    other = [a if a != str(GL) else str(GL * 2) for a in cmd]
    q = subprocess.Popen(other, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    first = json.loads(q.stdout.readline())
    open(stop, "w").close()
    q.communicate()
    check(first.get("checkpoint", "").startswith("rejected") and os.path.exists(os.path.join(ck, "%d_%d.ckpt.rejected" % (K, N))),
          "mismatched checkpoint rejected and kept: %s" % first.get("checkpoint", "")[:70])

    rc, ev, _ = events(["test", "21181", "10"])
    check(rc == 1 and ev and ev[-1].get("event") == "error" and ev[-1].get("message"),
          "error event and exit 1: %s" % (ev[-1].get("message") if ev else None))

    pm1(tmp)


def pm1(tmp):
    """P-1 factoring: events, the result line, stop/resume, and a run that does not pay."""
    rc, ev, _ = events(["version"])
    check("pm1" in (ev[0].get("features", []) if ev else []), "version lists the pm1 feature")
    rc, ev, _ = events(["info", "55459", "47900038", "--sieve-bits", "32"])
    plan = (ev[0] if ev else {}).get("pm1", {})
    check(rc == 0 and plan.get("b1", 0) > 0 and plan.get("b2", 0) >= plan["b1"] and 0 < plan.get("probability", 0) < 1
          and plan.get("cost_iterations", 0) > 0, "info carries a P-1 plan: B1=%s B2=%s" % (plan.get("b1"), plan.get("b2")))

    # a factor found in stage 2 (21181*2^2132+1 = 5718863 * ...; see tools/pm1_cases.py)
    results = os.path.join(tmp, "p.jsonl")
    rc, ev, _ = events(["pm1", "21181", "2132", "--b1", "600", "--b2", "30000", "--backend", BACKEND, "--results", results,
                        "--event-seconds", "0"])
    kinds = [e["event"] for e in ev]
    start, last = (ev[0] if ev else {}), (ev[-1] if ev else {})
    check(start.get("event") == "start" and start.get("phase") == "pm1" and start.get("b1") == 600 and start.get("b2") == 30000
          and start.get("total", 0) > 0 and start.get("D", 0) > 0, "pm1 start event: phase, bounds, D, total")
    check("stage2" in kinds and all(e.get("phase") == "pm1" for e in ev if e["event"] in ("start", "progress", "stage2")),
          "pm1 progress and stage2 events carry phase=pm1")
    check(rc == 0 and last.get("event") == "pm1" and last.get("factor") == "5718863" and last.get("stage") == 2 and "engine" in last,
          "pm1 result event: factor %s in stage %s" % (last.get("factor"), last.get("stage")))
    lines = open(results).read().splitlines() if os.path.exists(results) else []
    line = json.loads(lines[0]) if lines else {}
    check(len(lines) == 1 and line.get("factor") == "5718863" and line.get("pm1", {}).get("b1") == 600, "pm1 results line")

    # stop in stage 2, resume, same factor as an uninterrupted run
    ck, stop = os.path.join(tmp, "pck"), os.path.join(tmp, "pstop")
    os.makedirs(ck)
    cmd = [BIN, "pm1", "55459", "30226", "--b1", "1000", "--b2", "60000", "--json", "--backend", BACKEND, "--event-seconds", "0",
           "--ckpt", ck, "--results", os.path.join(tmp, "q.jsonl"), "--stop-file", stop]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    seen = []
    for l in p.stdout:
        e = json.loads(l)
        seen.append(e)
        if e["event"] == "stage2":
            open(stop, "w").close()
    rc = p.wait()
    check(rc == 3 and seen and seen[-1]["event"] == "stopped" and seen[-1].get("stage") == 2 and os.path.exists(os.path.join(ck, "55459_30226.pm1")),
          "pm1 stop file in stage 2: exit 3, checkpoint written")
    os.remove(stop)
    rc, ev, _ = events(cmd[1:cmd.index("--json")] + cmd[cmd.index("--json") + 1:])
    check(rc == 0 and ev and ev[0].get("checkpoint") == "resumed" and ev[0].get("stage") == 2 and ev[-1].get("factor") == "25498789004617",
          "pm1 resumes in stage 2 and finds %s" % (ev[-1].get("factor") if ev else None))
    check(not os.path.exists(os.path.join(ck, "55459_30226.pm1")), "pm1 removes its checkpoint when done")

    # bounds left to the engine, where P-1 does not pay
    rc, ev, _ = events(["pm1", "21181", "2060", "--backend", BACKEND, "--results", os.path.join(tmp, "s.jsonl")])
    check(rc == 0 and ev and ev[-1].get("event") == "pm1" and ev[-1].get("skipped") is True and ev[-1].get("factor") is None,
          "pm1 that does not pay: skipped, exit 0")


if __name__ == "__main__":
    main()
