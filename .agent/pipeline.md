# job job-rbsetord2_rr1-11081957  started 2026-11-08T10:58:22Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Final report:

- **Defect fixed:** `symmetric_difference_update` / `^=` now mutates in place walking the *other* operand's order (boxed `cruntime.py`), with the typed `set[int]` augmented form using a new `ail_iset_xor_update`. Dict arguments follow CPython's insertion-order fast path; other iterables build a set first. Non-in-place `^` / `symmetric_difference` keep CPython's copy-right order.
- **Probes:** 12 in `/tmp/probes/sdu_*.py` (minimal, large, `^=`, typed/typed method, dict order, list/tuple/range/iterator/generator, frozenset, alias/self, empty, values through argument/list item/field/dict value, plain `^`) — all match CPython on general and default builds.
- **Tests on final content, `-j 2`:** `test_ail_setorder`, `test_ail_sets_general`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 5 modules, 0 failed.
- **Records:** Added `S11`/`SDU_ORDER`/`TYPED_SDU` to `test_ail_setorder.py`, a DEVLOG entry, and a new DIFFERENCES row `C?-job-rbsetord2_rr1-11081957-1`.
- `tools/update_manifest.py --check` passes; `tools/diff_ids.py` is absent on this tree.
- Committed as `abe62e7`. No push.
[cost $0.0000, opencode tokens {"total": 4876511, "input": 83279, "output": 11971, "reasoning": 18125, "cache.write": 0, "cache.read": 4763136}]
    tool time: bash 5.7 min, edit 0.0 min
        262s bash   python3 tools/par_check.py -j 2 test_ail_setorder test_ail_sets_general test_ail_safetynet test_ail_files test
         27s bash   for p in /tmp/probes/sdu_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -v 
         25s bash   for p in /tmp/probes/sdu_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -v 
         19s bash   for p in /tmp/probes/sdu_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -v 
          4s bash   for p in /tmp/probes/sdu_typed.py /tmp/probes/sdu_typeddict.py; do echo "##### $(basename $p)"; bash ~/tools/c
          2s bash   cat > /tmp/probes/sdu_typed2.py <<'EOF' def main():     a: set[int] = set(range(0, 240, 8))     b: set[int] = 
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo rc=$?; git status --short
          0s bash   python3 tools/update_manifest.py --check && git add AIL_CURRENT/DEVLOG.md DIFFERENCES.md AIL_CURRENT/python/pk

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `job-rbsetord2_rr1-11081957` (commit `abe62e7`)

**What the diff really does.** Rewrites `ail_setx_symmetric_difference_update_set` to toggle `so` in place walking `other`'s table order (self clears), adds a dict fast path to `ail_meth_set_symmetric_difference_update` (insertion order), and adds `ail_iset_xor_update` selected only for typed `set[int]` `^=` via a new `_ail_iset_update` flag. Non-in-place `^`/`symmetric_difference` are unchanged. Matches the report.

**Tests.** `par_check.py -j 2 test_ail_setorder test_ail_sets_general test_ail_safetynet` → 3 modules, 0 failed (88 s). `tools/update_manifest.py --check` → rc 0. `tools/diff_ids.py` absent.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, general `g` + default `d`; all on HEAD, many also on `/tmp/base`):
- review case and large: `p1` (`[32, 8, 24, 40]`; `q.symmetric_difference_update({8,16,240})`), `p2` (large `so`, keys absent from `so`) — match.
- dict: `p3`, `p29` discriminating case (`{3:1,56:1}` → `[32,16,3,56,8,24,40]`, while list/set gives `[32,16,56,3,…]`), `p17`/`p31` large dict + pop — match.
- iterables: `p4a`/`p4b`/`p27` list, tuple, range, iterator, frozenset, dict view, generator *expression* — match; `p9` `^=` list/dict → TypeError matches.
- typed `set[int]`: `p5`/`p11`/`p16`/`p20`/`p23`/`p24`/`p28`/`p30` (`^=`, method, empty+large, negatives/2^40, frozenset/list/dict arg, args, non-in-place `^`) — match.
- dummies/re-add/pop: `p19`/`p25`/`p26`/`p31` — match (no post-deletion resize, finger preserved).
- routes/alias/self/field/subscript: `p6`/`p14`/`p21`/`p22` — match.
- worker's 12 `/tmp/probes/sdu_*.py` re-run: all match on both builds.
- unchanged C: `n1` (no sets) `program.c` byte-identical to `/tmp/base`; `n2` (sets, no sdu) diff confined to the sdu function.
- base comparison: every reviewed-defect probe that HEAD now matches is wrong on `/tmp/base` (e.g. `p15`/`p16`/`p20`/`p26`/`p29`), so these are fixes, not pre-existing.

**Pre-existing (identical on base, not blocking).**
- Sets containing `str`/`bytes` (and mixed sets) use deterministic insertion order; CPython's order is randomized per run. Documented in `DIFFERENCES.md`; `p10` differs on both builds.
- Generator *functions* (`yield`) are refused by name on both builds (`p4`).

**Report claims.** All verified: defect fixed (boxed/typed/`^=`/iterables), dict insertion-order fast path, non-in-place unchanged, 12 probes pass, records (S11, DEVLOG, DIFFERENCES `C?-job-rbsetord2_rr1-11081957-1`, manifest) present, commit `abe62e7`. `test_ail_files`/`test_ail_corpus_findings3` not re-run (outside reviewer scope). Speed not measured: `tools/icount.c` fails (`perf_event_open: Permission denied`) and no gdev program uses `symmetric_difference`; the change is off the hot path.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3`; instruction counts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4480017, "input": 63873, "output": 14293, "reasoning": 35643, "cache.write": 0, "cache.read": 4366208}]
    tool time: bash 4.1 min
         89s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_seto
         27s bash   ls /tmp/probes/sdu_*.py; echo ===; cd /tmp/probes && for p in sdu_*.py; do r=$(bash ~/tools/cmp.sh "$p" /home/
         14s bash   cd /tmp/rprobes && for p in p*.py; do echo "##### $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
         12s bash   cd /tmp/rprobes cat > p21_field.py <<'EOF' class C:     def __init__(self):         self.s: set[int] = {8, 16,
         11s bash   cd /tmp/rprobes cat > p23_typed_mixed.py <<'EOF' def main() -> None:     q: set[int] = {8, 16, 24}     q.symme
         11s bash   cd /tmp/rprobes cat > p4a_iter.py <<'EOF' def main():     c = {24}     c.symmetric_difference_update([16, 56, 
          9s bash   cd /tmp/rprobes cat > p11_typed2.py <<'EOF' def main() -> None:     a: set[int] = {32, 0, 24}     b: set[int] 
          9s bash   cd /tmp/rprobes cat > p25_dummies_after.py <<'EOF' def main():     s = set(range(0, 200, 8))     o = set(range

## full suite
test_ail_gaps_api2

## worker report (suite fix)
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `9966d380`.

- Root cause: `test_ail_gaps_api2.SetPop.test_pop_is_refused_by_name` asserted `set.pop()` is refused, but the re-applied setord2 change makes untyped int sets emulate CPython's table order, so `pop()` now succeeds and matches CPython. That test was the sole failure (confirmed by running the HEAD version: 14 tests, 1 failure in `SetPop`).
- Fix: replaced it with `test_pop_matches_cpython`, comparing a fixed program, an untyped add/discard/pop fuzz, and a typed `set[int]` fuzz against CPython on both general and default builds; removed the obsolete insertion-order model constants; updated DEVLOG + manifest.
- Verified: `test_ail_gaps_api2.SetPop` + `test_ail_setorder` pass (13 tests), full `test_ail_gaps_api2` passes (14 tests), `update_manifest.py --check` rc 0. The accepted sdu fix and its S11 tests are untouched.
[commandcode stop=end_turn turns=28 out_tokens=14141]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T14:19:03Z
