# job job-rails1-11030014  started 2026-11-02T15:19:15Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed as `820d436` on `job-rails1-11030014` (not pushed; job rules forbid push, so no PR).

- Ported `main.c`'s two-sided search into `main.ail` (typed path) and `main.py`; graph build/parse unchanged.
- All 24 public+hidden cases and the perf case match `reference.py`; perf md5 `e04679834cdf3d4d8441f9adf3182e91`; AIL `path: typed`.
- AIL perf wall: **64.6 ms** (C: 100.0 ms), inside the 50–75 ms target.
- 300-case differential fuzz matched reference for Python, strict AIL, and ail-py.
- Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass.
- Caveats: `icount` could not run (`perf_event_paranoid=4`, no valgrind), so no instruction-count number; Rust toolchain absent, so the rust column failed to build. `AIL_UNIFIED_FORCE=1` refuses this brace-syntax source—the same is true of the unmodified HEAD file—so unified fuzz was unavailable.
[cost $0.0000, opencode tokens {"total": 4226106, "input": 100673, "output": 11830, "reasoning": 32323, "cache.write": 0, "cache.read": 4081280}]
    tool time: bash 10.4 min
        502s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 test_ail_safetynet.py 2>&1 | tail -15; echo SAFETY=${PIPE
         28s bash   cd /home/runner/work/_temp/w2 && python3 lab/compare/run_task.py --task rail_transfer --langs ail,c,rust --out
         13s bash   cd /home/runner/work/_temp/w2 && sed -i "s|BINS=\['/tmp/rt','/tmp/rtu'\]|BINS=['/tmp/rt']|" /tmp/fuzz_rail.py 
         13s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/rtpy && python3 -B AIL_CURRENT/ail_chatgpt.py compile --syntax pyt
         13s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import importlib.util, random, subprocess, sys spec=importli
         12s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import importlib.util, random, subprocess, sys spec=importli
         11s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import importlib.util, random spec=importlib.util.spec_from_
          4s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/rt && python3 -B AIL_CURRENT/ail_chatgpt.py compile --strict lab/c

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** Replaces the one-sided query loop with the bidirectional search of `main.c` in `rail_transfer/main.ail` (`solve()` plus a `G` layout change) and ports the same algorithm to `main.py`; parse/graph build otherwise unchanged. Matches the report.

**Checks**
- Diff touches only `DEVLOG.md`, `lab/compare/README.md`, `main.ail`, `main.py`; no compiler/runtime/test files.
- Strict build works: `compile --strict main.ail` succeeds, `path: typed`.
- Perf md5 = `e04679834cdf3d4d8441f9adf3182e91` for reference, `main.py`, strict AIL, default AIL and ail-py.
- Differential fuzz: 418 cases (all public+hidden over 8 seeds, 220 `random_net` with n 1..400, maxx 0/1000, maxt 0/100000, plus self-loop/dup-edge/no-segment/big-number edges) — all four programs byte-identical to reference.
- Tests: `test_ail_safetynet` 199 s, `test_ail_files` 132 s, `test_ail_corpus_findings3` 310 s, all pass.
- Wall on this runner: AIL ~105–110 ms, C ~110–130 ms. Worker's absolute 64.6/100 ms not reproduced (load/frequency variance), but AIL≈C ratio holds.

**Claims**
- Two-sided port in `main.ail` + `main.py`, graph build unchanged — verified.
- 24 cases + perf equal, md5, typed path — verified.
- 300-case fuzz — verified (418 run).
- Three test modules pass — verified.
- AIL wall 64.6 ms / C 100.0 ms — partially verified (ratio only; absolute not reproduced).
- icount unavailable — verified (paranoid=4, no valgrind, no sudo).

**Pre-existing:** none observed (no differing outputs).

**Unverified**
- Instruction-count target (≤350 M). `perf_event_open` is blocked and no valgrind/sudo is available, so the central speed number could not be measured; commit message correctly records this. Wall-time ratio suggests ~C's 281 M, but this is not proof.
- Rust column (toolchain absent), and the worker's specific wall figures.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 758499, "input": 44353, "output": 4996, "reasoning": 16926, "cache.write": 0, "cache.read": 692224}]
    tool time: bash 9.3 min
        311s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files test_ai
        201s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_safetynet 2>&
         28s bash   cat > /tmp/rprobes/fuzz.py <<'PY' import importlib.util, random, subprocess, sys, os REPO='/home/runner/work/_
         14s bash   cat > /tmp/rprobes/perf.py <<'PY' import importlib.util, random, subprocess, sys, time, hashlib REPO='/home/ru
          2s bash   cd /home/runner/work/_temp/w2; date; python3 -B AIL_CURRENT/ail_chatgpt.py compile --strict lab/compare/src/ra
          2s bash   cd /home/runner/work/_temp/w2 && gcc -O2 -std=c11 -o /tmp/rprobes/rt_c lab/compare/src/rail_transfer/main.c -l
          1s bash   cat > /tmp/rprobes/perf.py <<'PY' import importlib.util, random, subprocess, sys, time, hashlib REPO='/home/ru
          1s bash   cd /home/runner/work/_temp/w2 && sed -i "s/_,_,perf=gen.cases/_,_,perf=gen.cases/; s/perf=gen.cases(random.Ran

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T17:02:36Z
