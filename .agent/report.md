# job job-algos1-11051131  started 2026-11-05T02:35:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed on `job-algos1-11051131` (not pushed, per runner instruction).

- **Programs:** 12 plain-Python algorithms + `examples/algos/run.py`.
- **Default build:** 11/12 build and match CPython stdout + exit; RPN builds but stops loudly on `2 ** 70` (`OverflowError`, exit 1), never prints a wrong value.
- **Forced general:** 11/12 also match with `AIL_UNIFIED_FORCE=1`.
- **Strict:** 0 typed, 12 refused; first blockers grouped/ranked in `RESULTS.md`.
- **Speed:** geomean 1.04x vs CPython (median of 3, 1.5 GB cap); instruction counting unavailable (`perf_event_open` denied).
- **Blockers:** top three buckets are module-level script state (12 programs), `str in list[str]` (4), and int-keyed dicts of containers (2); reproducers added under `examples/algos/repro/`.
- **Test:** `test_ail_examples_algos.py` registered via `tests.d`; passes in ~45–65 s.
- **Required tests on final commit:** `test_ail_examples_algos`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass.
- **Manifest:** `tools/update_manifest.py --check` passes.
- **Diff:** only `examples/algos/` plus the new test module, its `tests.d` entry, and the two manifest shards. CI shards/PR were not run because pushing is disabled in this environment.
[cost $0.0000, opencode tokens {"total": 3018890, "input": 98481, "output": 19278, "reasoning": 26379, "cache.write": 0, "cache.read": 2874752}]
    tool time: bash 32.8 min, write 0.0 min, edit 0.0 min
        609s bash   time python3 -B AIL_CURRENT/test_ail_examples_algos.py -q && time python3 -B AIL_CURRENT/test_ail_safetynet.py
        545s bash   python3 -B examples/algos/run.py
        412s bash   python3 -B AIL_CURRENT/test_ail_examples_algos.py -q && python3 -B AIL_CURRENT/test_ail_safetynet.py -q && pyt
        135s bash   cd /tmp/algobuild && for d in */; do n=${d%/}; rm -f "$n/$n.forced.out"; ( ulimit -v 1500000; AIL_NO_CACHE=1 A
         69s bash   cd /tmp/algobuild && for d in */; do n=${d%/}; ( ulimit -v 1500000; ./$n/$n.out >$n/run.out 2>$n/run.err ); rc
         66s bash   rm -rf /tmp/algobuild && mkdir -p /tmp/algobuild && cd /tmp/algobuild && for f in /home/runner/work/_temp/w2/e
         65s bash   printf 'test_ail_examples_algos\n' > AIL_CURRENT/tests.d/test_ail_examples_algos.txt && time python3 -B AIL_CU
         17s bash   for f in examples/algos/*.py; do n=$(basename "$f"); /usr/bin/time -f "$n %e s %M KB" python3 -B "$f" >/tmp/$n

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. Findings below.

**What the change does:** adds 12 plain-Python algorithm programs plus `examples/algos/run.py` (builds default/strict/`AIL_UNIFIED_FORCE=1`, compares stdout+exit against CPython, times, writes `RESULTS.md`), three blocker reproducers, an algos test module registered via `tests.d`, and two manifest-shard entries. No compiler/runtime file is touched.

**Claims checked**
- Diff is only `examples/algos/`, `AIL_CURRENT/test_ail_examples_algos.py`, its `tests.d` entry, and two manifest shards; `tools/update_manifest.py --check` rc=0. **Verified.**
- All 12 programs at default size, default build and `AIL_UNIFIED_FORCE=1`: stdout+exit identical to CPython for 11; `rpn.py` builds and stops loudly (`OverflowError`, exit 1, only the `2**70` line missing) in both builds, which the task allows. **Verified** with `cmp.sh` on every program.
- Strict: all 12 refused (rc=3), 0 typed; first refusal lines match the `RESULTS.md` table exactly. **Verified.**
- `test_ail_examples_algos` + `test_ail_safetynet` pass under `par_check.py -j 2` (49.6s / 198.6s). **Verified.**
- `icount` unavailable: `perf_event_open: Permission denied`. **Verified** by building/running `tools/icount.c`.
- Geomean arithmetic in `RESULTS.md` = 1.034 → 1.04x. Blocker reproducers reproduce the claimed refusals. **Verified.**
- Minor, non-behavioral: repro `01`/`03` are 12 lines, above the task's “3–10 lines” (the report says 7–13). Content and refusals are correct.

**Unverified:** wall-time/instruction measurements were not independently re-timed; `test_ail_files` and `test_ail_corpus_findings3` were not run (outside reviewer scope); CI shards not run (push disabled). No pre-existing differences observed — no compiler/runtime code changed, so base comparison is not applicable.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 705386, "input": 83422, "output": 3785, "reasoning": 20419, "cache.write": 0, "cache.read": 597760}]
    tool time: bash 5.5 min
        200s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_examples_algo
         39s bash   cd /home/runner/work/_temp/w2 && cp examples/algos/topo.py /tmp/rprobes/topo_default.py && cp examples/algos/s
         25s bash   cd /home/runner/work/_temp/w2 && for n in lcs levenshtein dijkstra; do cp examples/algos/$n.py /tmp/rprobes/${
         23s bash   cd /home/runner/work/_temp/w2 && for n in mandelbrot sudoku huffman life; do cp examples/algos/$n.py /tmp/rpro
         18s bash   cd /home/runner/work/_temp/w2 && date && bash ~/tools/cmp.sh /tmp/rprobes/wordfreq_default.py $PWD 2>&1 | tail
         12s bash   cd /home/runner/work/_temp/w2 && date && rm -rf /tmp/strictcheck && mkdir /tmp/strictcheck && for f in example
          9s bash   mkdir -p /tmp/rprobes && cd /home/runner/work/_temp/w2 && cp examples/algos/rpn.py /tmp/rprobes/rpn_default.py
          1s bash   cd /home/runner/work/_temp/w2 && date && for f in examples/algos/repro/*.py; do n=$(basename "$f" .py); AIL_NO

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T04:40:26Z
