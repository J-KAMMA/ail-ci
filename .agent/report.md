# job job-sched1-11051443  started 2026-11-05T05:45:36Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `ec09023`.

- `AIL_CURRENT/stdlib/sched.py`: `_invoke` now dispatches 0–16 positional action arguments instead of stopping at 8, so the review's 9-argument probe matches CPython in both builds. Beyond 16 it raises a named `TypeError`; the 16-branch limit keeps build time at ~8s (a 64-branch version cost ~36s/build).
- Probes: `p3_args9`, `p_sched0/1/7/8/9/16` match CPython in default and forced-general builds; `p_sched17` diverges only with the named boundary error.
- `test_ail_std_sched`: 2 tests OK (120.8s). `test_ail_safetynet`: 5 tests OK (172.2s, no memory cap; S4_generators_gc still needs >1.5GB).
- `tools/update_manifest.py --check`: rc=0. Updated `RESULTS.md` and the manifest hash.
- Not pushed, per the runner instructions.
[cost $0.0000, opencode tokens {"total": 1746588, "input": 68708, "output": 8258, "reasoning": 12662, "cache.write": 0, "cache.read": 1656960}]
    tool time: bash 32.9 min, edit 0.0 min, read 0.0 min
        618s bash   cd /tmp/probes && python3 - <<'EOF' for n in (0,1,2,7,8,9,16,32,64,65):     args = ", ".join("a%d" % i for i i
        535s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B AIL_CURRENT/test_ail_std_sched.py 2>&1 | t
        172s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -12
        171s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8
        123s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B AIL_CURRENT/test_ail_safetynet.py 2>&1 | t
        121s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; python3 -B AIL_CURRENT/test_ail_std_sched.py 2>&1 | t
         98s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p3_args9.py /tmp/probes/p_sched0.py /tmp/probes/p_s
         36s bash   cd /tmp/probes && python3 - <<'EOF' for n in (32, 64, 100):     args = ",".join("a%d"%i for i in range(n))    

## review 0
[model opencode/deepseek-v4.1-flash-free]
## What the change really does

Extends the `_invoke` positional-argument `elif` chain in `AIL_CURRENT/stdlib/sched.py` from 8 to 16 arguments (reformatting 6–8), changes the over-limit message to "more than 16", and updates the docstring, `RESULTS.md`, and the manifest hash. No compiler/runtime file is touched.

## Probes (`~/tools/cmp.sh`, general + default)

| probe | result |
|---|---|
| p0 (0 args) | matches both builds |
| p1 (1 arg) | matches both builds |
| p8 (8 args) | matches both builds |
| p9 (9 args) | matches both builds; **base diverges** (old defect fixed) |
| p16 (16 args) | matches both builds |
| p_sources (action via dict→list, arg via attribute) | matches both builds |
| p9_float (9 floats incl. negatives, 2**40) | matches both builds |
| p9_raise (9 args, action raises; rerun) | matches both (stdout, exit 1) |
| p_sched7 | matches both builds |
| p17 (17 args) | diverges: CPython `act 153 / done`; AIL `TypeError sched: more than 16 action arguments...`; **base also diverges** with the "eight" message |
| nosched.py `--debug-dir` vs base | `program.c` byte-identical (only `native_report.json` temp paths differ) |

## Claims in the report

- `_invoke` dispatches 0–16 — **verified**.
- 9-argument probe now matches in both builds — **verified** (base fails, HEAD matches).
- >16 raises named `TypeError` — **verified** (p17).
- ~8 s/build with 16 branches — **verified** (7.1 s HEAD vs 6.0 s base for p16); the 64-branch ~36 s comparison was **not verified**.
- `p_sched0/1/7/8/9/16` match both builds — **verified** for 0, 1, 7, 8, 9, 16 equivalents.
- `test_ail_std_sched` 2 tests OK, `test_ail_safetynet` 5 OK — **verified** (120.7 s, 172.4 s, 0 failed).
- Manifest check rc=0, hash updated, only permitted files touched — **verified**.

## Pre-existing / known

- 17+ positional action arguments still diverge from CPython, but the base also diverges (limit was 8), so this is the same documented limitation extended, not a new defect.
- No committed regression test covers 9–16 (only ad-hoc probes); the job test module still passes.

## Unverified

- 64-branch build cost (only the 16-branch timing was measured).
- Instruction counts / gdev speed: no compiler or runtime hot path changed, so not run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 533045, "input": 31071, "output": 5197, "reasoning": 10121, "cache.write": 0, "cache.read": 486656}]
    tool time: bash 5.9 min
        174s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date; python3 ../tools/par_check.py -j 2 test_ail_std_sched 
         71s bash   cd /tmp/rprobes && for p in p0 p8 p9 p16 p_sources; do echo "##### $p $(date +%H:%M:%S)"; bash ~/tools/cmp.sh 
         43s bash   cd /tmp/rprobes && cat > p9_float.py <<'EOF' import sched clock = [0.5] def tf(): return clock[0] def df(d):  
         39s bash   cd /tmp/rprobes && echo "##### HEAD p17 $(date +%H:%M:%S)"; bash ~/tools/cmp.sh /tmp/rprobes/p17.py /home/runn
         14s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/p_sched7.py /home/runner/work/ail-ci/ail-ci 2>&1; cd /home/r
         13s bash   cd /tmp/rprobes && rm -f /tmp/bt_h /tmp/bt_b; echo "HEAD:"; date +%H:%M:%S; /usr/bin/time -f "head %e s" env A
          1s bash   rm -rf /tmp/dbg_h /tmp/dbg_b /tmp/nosched_h /tmp/nosched_b; cd /tmp/rprobes python3 -B /home/runner/work/ail-c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; date

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T07:40:36Z
