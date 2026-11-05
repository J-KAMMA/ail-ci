# job job-safestop1-11052024  started 2026-11-05T11:26:18Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `a8a1cd4` on `job-safestop1-11052024` (not pushed, per the runner note).

- `lab/safety/stops/RESULTS.md`: 20 programs, 80 cells — 63 match, 10 stop-differs, 3 silent-wrong, 3 crash, 1 refused.
- Confirmed the probe: general mode `AIL_UNIFIED_FORCE=1` segfaults on direct/mutual/method recursion; typed/default match.
- Largest finding: 5000-deep recursion exits 0 in typed/default/general while CPython raises `RecursionError`.
- `python3 AIL_CURRENT/test_ail_safety_stops.py` passes; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; manifest `--check` passes.
- Diff from base `03e5350` touches only the permitted files; no CI shards run because no push was made.
[cost $0.0000, opencode tokens {"total": 983996, "input": 50402, "output": 9146, "reasoning": 10144, "cache.write": 0, "cache.read": 914304}]
    tool time: bash 7.5 min, write 0.0 min, edit 0.0 min
        347s bash   set -o pipefail for t in test_ail_safety_stops test_ail_safetynet test_ail_files test_ail_corpus_findings3; do
         54s bash   python3 lab/safety/stops/run.py
         31s bash   python3 lab/safety/stops/run.py
         14s bash   python3 AIL_CURRENT/test_ail_safety_stops.py -v
          3s bash   cd /tmp/probes && rm -rf b_* && mkdir -p b_typed b_default b_general b_hybrid python3 -B /home/runner/work/ail
          1s bash   cd /home/runner/work/ail-ci/ail-ci/lab/safety/stops && for f in *.py; do python3 -B "$f" >/tmp/o 2>/tmp/e; s=$
          0s bash   git add AIL_CURRENT/test_ail_safety_stops.py AIL_CURRENT/tests.d/test_ail_safety_stops.txt lab/safety/stops/01
          0s bash   python3 tools/update_manifest.py --check; echo manifest_check=$?; git diff --stat 03e5350 HEAD; git status --s

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All checks are done; here is my review.

**What the change really does:** It adds a 20-program runtime-stop corpus (`lab/safety/stops/*.py`), a four-mode build/run/classify harness (`run.py`) that regenerates `RESULTS.md` with per-cell classes and auto-follow-ups, and a default+general ratchet test registered through `tests.d/` and the manifest. It touches no compiler or runtime file, matching the report.

**Probes** (`/tmp/rprobes`, `cmp.sh` against `$PWD`, differing ones also against `/tmp/base`):

| probe | result |
|---|---|
| p1_zero_sources (zero via dict value, attribute, list item, arg; `//`, `%`, `/`) | general + default: stdout/exit/last-line match CPython |
| p2_zero_float_negative (`1.0 / -0.0`) | general matches `ZeroDivisionError: float division by zero`; default says `division by zero` → stop-differs; **identical on base** |
| p3_rec_deep200k (depth 200000) | general: SIGSEGV (139), default: `RecursionError` match; **identical on base** |
| p4_conv_transport (`int(float("-inf"))` from dict value) | both modes match CPython |
| p5_nofeature (plain program) | both modes match; `--debug-dir` `program.c` **byte-identical HEAD vs base** |

**Tests:** `par_check.py -j 2 test_ail_safety_stops test_ail_safetynet` → 2 modules, 0 failed. Standalone `python3 AIL_CURRENT/test_ail_safety_stops.py` → OK (1 test, 14 s). Manifest `--check` → 0.

**Claims:** 20 rows / 80 cells and 63/10/3/3/1 totals — verified (independent rerun reproduced the table exactly; only the recorded base SHA differs, since HEAD moved). General-mode segfaults on direct, mutual and method recursion; typed/default match — verified by hand. 5000-deep exits 0 in typed, default and general — verified by hand. Test passes, safetynet passes, manifest check passes, diff touches only permitted files, branch not pushed (origin ref is still at `03e5350`) — verified. `test_ail_files` and `test_ail_corpus_findings3` — **unverified** (instruction says not to run the wider suite).

**Pre-existing** (identical on base, non-blocking): 04/12/16/17/18 message-only stop-differs; 09's silent exit-0 at depth 5000 and SIGSEGV at 200000 in general mode.

**Minor, non-blocking:** `run.py` maps *any* nonzero build to `refused`, so a compiler crash during a build would be filed as a refusal (only 19/typed hits this path and it is a genuine named refusal: `call to next()`). The hybrid column is vacuous — every sampled hybrid build has `"extension": null`, so those 20 `match` cells just rerun CPython. No runtime/I-O/mutation work to probe and no hot-code change, so no speed check.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=21 out_tokens=34355]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T13:01:53Z
