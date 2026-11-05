# job job-rc1-11051645  started 2026-11-05T07:46:33Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commits `2e4e68b`, `cc44eb3`, `b14bea2` on `job-rc1-11051645`; diff vs base `f375432` is only `lab/rc/` (9 files), and `update_manifest.py --check` passes.

- tree_fold `typed.py`: 404.4 MiB peak, **95% list buffers** (384.4 MiB), input 7.9%, class/str ~0; tracked split 416.4 MiB (103% of RSS). CPython `main.py` 1051 MiB (2M scaled; 3M actual 1149 MiB).
- 16/16 programs matched CPython and had correct counting builds. Helper share: new programs 10.8-31.7%, compare tasks 0-1.47%, tree_fold 0.005%.
- **rc2/rc3: go** (five new programs halved to 1.032-1.053x). **rc4/rc5: marginal go**, RSS-only at 5.5-7.7% on tree_fold/term_rank/ticket_audit; instruction gain only 2.41% max. No reuse gain on the six class-object programs (AIL pool already does it).
- Instruction shares are gcov estimates: this runner has no PMU and `perf_event_open` hardware instructions returns ENOENT.
- Not pushed and no CI shards run, per the runner rule; `origin/integ` is not fetched in this grafted checkout, so the base diff uses `f375432`.
[cost $0.0000, opencode tokens {"total": 11973456, "input": 513361, "output": 49062, "reasoning": 63193, "cache.write": 0, "cache.read": 11347840}]
    tool time: bash 44.4 min, write 0.0 min, invalid 0.0 min
        600s bash   cd /home/runner/work/ail-ci/ail-ci && python3 lab/rc/run.py --only linkedlist --keep --out /tmp/rcwork/ll.json
        542s bash   rm -rf /tmp/rc1-*; cd /home/runner/work/ail-ci/ail-ci && time timeout 3000 python3 lab/rc/run.py --out /tmp/rc
        530s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='lab/rc/run.py'; s=open(p).read() s=s.replace("TREE_
        426s bash   df -h /tmp | tail -1; rm -rf /tmp/rc1-*; cd /home/runner/work/ail-ci/ail-ci && time timeout 3000 python3 lab/r
        109s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='lab/rc/run.py'; s=open(p).read() old="""    stdin_p
         54s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, random, time from pathlib impor
         50s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/rcwork/cmp && mkdir -p /tmp/rcwork/cmp && for t in berth_sim
         42s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' p='lab/rc/run.py'; s=open(p).read() # add category key

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: rc1 measurement-only (`lab/rc/`)

**What the change really does:** adds a measurement harness (`lab/rc/run.py`), six Python benchmark programs, and a pricing report (`PRICE.md`/`PRICE.json`). No compiler/runtime/C source is touched — `git diff work..HEAD` is exactly the 9 files under `lab/rc/`; `update_manifest.py --check` passes. So "programs that do not use the feature" are byte-identical by construction.

**Probes run (all in `/tmp/rprobes/`, `cmp.sh`):** `binarytrees`, `cfold`, `deriv`, `linkedlist`, `objscan`, `rbtree` — all 6/6 matched CPython 3.12 on both the default and `AIL_UNIFIED_FORCE=1` builds (exit 0, identical stdout). Re-measured RSS matches table (a) exactly: 1576, 1960, 7724, 6056, 16872, 5300 KiB.

**Report claims:**
- Verified: tree_fold typed.py 404.4 MiB and 95% list buffers; tracked 416.4 MiB (103%); helper counts/shares in table (b) match `PRICE.json`; helper definition/emission lines (pyfunc.py:34661/34670, emit_c.py:463/527) exist; only `lab/rc/` changed; `update_manifest.py --check` and `test_ail_safetynet` pass; rc2–rc5 arithmetic reproduces (e.g. binarytrees 1.0504x, term_rank 2.413%/1.0073x).
- Partly false: line 24 says tree_fold used the "compare input"; `run.py:451` uses `Random(1)`, not the compare seed `'tree_fold-20261012'` (input is 27,859,349 vs 27,877,476 B). I built typed.py and ran both: 404.4 vs 405.1 MiB — no effect on any conclusion. Also, hardware `perf_event_open` here fails EPERM/EACCES (paranoid=4), not ENOENT; the substance (no PMU, no icount/valgrind) is verified.
- Unverified: instruction shares (gcov estimate; no PMU and valgrind absent, so I could not independently calibrate them); the 2M=701 MiB main.py figure is not in the committed artifacts (only the 3M 1149 MiB run is); the task's 605 MiB AIL baseline is not reconciled — `docs/design/MEM_TREEFOLD.md` shows 603.7→450.2 MiB after an earlier runtime fix (main.ail), so 404 MiB for typed.py is plausible/stale-baseline, not a measurement error.
- Note (not blocking): rc4/rc5 "reuse peak" is the peak live of sites with any reuse, not the bytes actually reused (e.g. ticket_audit's 15.7 MiB comes from 172k ~11-byte reuses). The go is still met on term_rank + tree_fold under the stated 5% rule, and is labelled marginal.

**Pre-existing:** none (no compiler/runtime change; the 605 vs 404 gap predates this job).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1601223, "input": 88498, "output": 6970, "reasoning": 36699, "cache.write": 0, "cache.read": 1469056}]
    tool time: bash 4.1 min, read 0.0 min
        176s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_safe
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for f in binarytrees cfold deriv linkedlist objscan rbtree; do echo "###
         20s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, random p='lab/compare/tasks/tre
         19s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, random p='lab/compare/tasks/tre
          6s bash   cd /home/runner/work/ail-ci/ail-ci && time timeout 900 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compa
          3s bash   cd /tmp && for f in tf_seed1 tf_compare; do echo "=== $f ==="; (ulimit -v 1500000; /usr/bin/time -v /tmp/tf_ai
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 tools/update_manifest.py --check 2>&1 | tail -5; ech
          0s bash   cd /home/runner/work/ail-ci/ail-ci && for d in /tmp/cmp*/; do if [ -x "$d/exe_d" ]; then echo "=== $(basename 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T10:18:35Z
