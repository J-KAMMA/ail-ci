# job job-pre34-10240952  started 2026-10-24T00:52:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on branch `job-pre34-10240952`.

**Change**
- The reviewer’s listed “Unverified” items are performance/test-coverage claims, not executable CPython differences. The first executable difference in that area was percent formatting: a literal `"%d%%" % 60.0654` failed with `TypeError: unsupported format string passed to non-int` on both builds.
- `pyboxed2._percent_format` now keeps the direct formatter for int/bool and routes other `%d` operands through `safetyrt.ail2f_percent`, which already matches CPython: truncation toward zero, `ValueError` for NaN, `OverflowError` for infinity, and `%d format: a real number is required, not str`.
- Also fixed the precision-on-int fallback message (`%.3d`), which used `%d` with a string and crashed the compiler instead of falling back.
- DIFFERENCES: `C?-job-pre34-10240952-1`; new `test_ail_pre34.py`; DEVLOG and manifest updated.

**Commit:** `87f306f`

**Tests on final commit**
- `test_ail_pre34 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed (246 s).
- Additional targeted: `test_ail_pre34 test_ail_cov2 test_ail_lang_gaps test_ail_tuples test_ail_dunders`: 5 modules, 0 failed (203 s).
- `update_manifest.py --check`: rc 0.

**Probes (`cmp.sh`, both builds)**
- Match CPython: `pre34_pct_d_float`, `pre34_pct_types`, `pre34_pct_extra`, `pre34_pct_i`, `pre34_pct_computed`, `pre34_pct_rt_types`, `pre34_pct_rt_nonfinite`, `pre34_pct_values`, `pre34_pct_strformat`, `pre34_pct_float`.
- Reproduced the same failure on base `64d53b2` first.

**Residual (pre-existing, not claimed fixed)**
- Finite floats outside int64 still stop with the documented `AIL limit: integer overflow`; CPython prints a big integer.
- `format(x, "d")` / f-string `{x:d}` keep their pre-existing TypeError-vs-ValueError wording difference; this change targets `%` formatting only.
[cost $0.0000, opencode tokens {"total": 12062873, "input": 335031, "output": 62602, "reasoning": 2264, "cache.write": 0, "cache.read": 11662976}]
    tool time: bash 12.3 min, edit 0.0 min, read 0.0 min, write 0.0 min
        248s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 ../tools/par_check.py -j 2 test_ail_pre34 test_ail_safetynet test_ail
        205s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 ../tools/par_check.py -j 2 test_ail_pre34 test_ail_cov2 test_ail_lang
         73s bash   for f in /tmp/probes/pre34*.py; do echo "=== $(basename $f) ==="; bash ~/tools/cmp.sh "$f" $PWD 2>&1 | grep -E
         39s bash   for p in pre34_pct_d_float pre34_pct_types pre34_pct_i pre34_pct_computed pre34_pct_rt_nonfinite pre34_pct_val
         24s bash   for f in corpus/gdev/g03_016.py corpus/gdev/g03_032.py corpus/gdev/g19_010.py corpus/gdev/g07_034.py; do echo 
         19s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre34 2>&1 | tail -60
         19s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -m unittest -v test_ail_pre34 2>&1 | tail -30
         17s bash   for p in pre34_pct_d_float pre34_pct_types pre34_pct_i pre34_pct_computed; do echo "=== $p (base) ==="; bash ~

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `87f306f` (`work..HEAD`) — started 01:22, ended 01:31.

**What the change really does**: in `pyboxed2._percent_format`, a literal `%d` keeps `ail_obj_format` for int/bool and sends every other operand to `safetyrt.ail2f_percent` with the original directive; it also fixes the `Unsupported` label that formatted a string with `%d` and crashed the compiler. This matches the report.

**Probes** (`cmp.sh`, both builds unless stated):
- `p1_float_flags` (float, all flags/width/precision): HEAD matches CPython on both builds; base fails to build with the message-format crash.
- `p2_nonnumber` (str/list/dict/tuple/None, `__int__`, `__index__`, `__format__`): HEAD matches CPython exactly on both builds; base emits the wrong `non-int` message.
- `p3_paths` (argument, list item, attribute, dict value, multi-directive, mapping): default build matches; general build fails on computed `fmt % v` (`unsupported operand type(s) for %`), identical failure on base → pre-existing.
- `p4_edges` (int64 boundary, NaN/inf): finite values ≤ int64 match; `1e19` stops with `AIL limit: integer overflow` (base instead raised the old TypeError). NaN/inf themselves are covered by `test_ail_pre34` and pass.
- `p5`, `p6` (no feature / no `%d`): outputs match; `p6` generated C is byte-identical between base and HEAD.
- `p7` int/bool flags, `p8` side-effect `f()` called once, `p9` profile-percentage form, `p11` more flags/`*` width: all match on both builds; `p9` fails on base.
- Speed: unverified; `tools/icount` fails with `perf_event_open: Permission denied` (EPERM).

**Tests on HEAD**: `test_ail_pre34` 21.2 s and `test_ail_safetynet` 101.4 s — 2 modules, 0 failed. `update_manifest.py --check` rc 0.

**Claims check**:
- verified: literal `%d` routing, int/bool fast path, precision-message fix, truncation/type-error match, DIFFERENCES/test/DEVLOG/manifest, commit hash, manifest check, int64 residual.
- partially verified: "reproduced on base" — reproduced on `/tmp/base` (`work`, `0a61def`), not on `64d53b2`.
- unverified: the "first executable difference" interpretation of the perf4 list, the two extra test runs (4-module and 5-module), the exact `64d53b2` reproduction, and the `format(x,"d")`/f-string wording residual.

**Pre-existing / residual**: general-path computed `fmt % value` remains unsupported; finite floats outside int64 hit the documented `AIL limit: integer overflow` (now reachable through literal `%d`); `format(x,"d")`/f-string wording was not probed.

The change fixes the targeted literal-`%d` float percentage on both builds, with no observed regression.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1466551, "input": 86151, "output": 15153, "reasoning": 10751, "cache.write": 0, "cache.read": 1354496}]
    tool time: bash 3.0 min
        103s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && AIL_NO_CACHE=1 python3 ../tools/par_check.py -j 2 test
         23s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/*.py; do echo "=== $(basename $f) ==="; bash ~
         15s bash   cd /tmp/base; for f in /tmp/rprobes/p1_float_flags.py /tmp/rprobes/p2_nonnumber.py /tmp/rprobes/p3_paths.py /t
          9s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/p3_paths.py /tmp/rprobes/p4_edges.py; do echo "=====
          9s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/p7_sideflags.py /tmp/rprobes/p8_sideeffect.py; do ec
          5s bash   cat > /tmp/rprobes/p11_moreflags.py <<'EOF' class C:     pass   def main():     for x in [-1.9, 1.9, 0.5]:    
          4s bash   cat > /tmp/rprobes/p9_simple.py <<'EOF' def main():     part = 60     whole = 100     x = 100.0 * part / whole
          4s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/p2_nonnumber.py $PWD 2>&1 | tail -20

FINAL VERDICT: ACCEPT  2026-10-24T01:31:03Z
