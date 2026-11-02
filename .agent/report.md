# job job-rbpyreach1-11021017  started 2026-11-02T01:24:28Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- Re-applied `job-pyreach1-11020650` onto `job-rbpyreach1-11021017`; kept both sides of the two overlapping fixes (`_Surface` match tables; `_claim` `comp_claims` plus `sys.argv` str claim).
- Added the accepted test module, `tests.d` registration, design doc, and DEVLOG entry.
- `tools/diff_ids.py` is absent on this tree; `tools/update_manifest.py` ran, and `--check` exits 0.
- Commit: `3667f3a` (16 files, +953/−57).

Tests (final tree, `-j 2`): 11 modules, 0 failed — `test_ail_pytyped_reach`, `test_ail_re`, `test_ail_nested_functions`, `test_ail_collections`, `test_ail_optional_locals`, `test_ail_optional_structs`, `test_ail_argv_slices`, `test_ail_strict`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

Probes (all `same stdout`, g and d builds): `p_argv_str`, `p_opt_ret`, `p_dict_list`, `p_dict_cmp`, `p_bytes_owned`, `p_bytearray_view`, `p_loop_def`, `p_groups`, `p_entry_re`. The `echo_pack` typed-path behaviour was verified by `test_lab_echo_pack_builds_on_the_typed_path`.
[cost $0.0233, opencode tokens {"total": 1028477, "input": 70278, "output": 5744, "reasoning": 10759, "cache.write": 0, "cache.read": 941696}]
    tool time: bash 36.4 min, write 0.0 min
       2031s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_re test_
        150s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_*.py; do echo "===== $(basename $p)"; bash ~/tool
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -20; echo "update exit ${PI
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && python3 tools/update_manifest.py --check; echo "ch
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest check exit $?";
          0s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pyreach1-11020650 2>&1 | tail -5 && git diff 2a932ebc4d5f6
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_syntax.py AIL_CURRENT/manifest.d/2c.txt AIL_CURR
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "diff_ids" . --exclude-dir=.git 2>/dev/null | head; cat ~/tools

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Re-applies the accepted `pyreach1` front-end work: `sys.argv[i]` typed `str`; inferred return kinds for unannotated helpers; `d.setdefault(k, []).append(v)` / truth-tested `d.get(k)` lowered to key→slot + rows; unannotated `bytes(...)` helpers treated as owned; bytearray passed as a read-only bytes view; loop-body nested `def` lifting; `for x in m.groups()` lowering; and entry recovery when generated helpers trail the script. It matches the fetched accepted diff, and the two known overlaps were kept on both sides (`comp_claims` in `_claim`, `_Surface` match tables).

**Probes.** 24 own probes under `/tmp/rprobes`, run with `cmp.sh` on HEAD and on `/tmp/base`. All matched CPython on both builds except the defects below. Representative passes: dict-of-lists via loop/if/list item/dict value/str key/negative/empty key, `get` compared with `[]`/`None` (left as written), optional helper returning str and a falling-off helper, owned `bytes` reused 2000×, bytearray summed then mutated, bytearray slice, loop `def` with break/recursion/captured mutation, `.groups()` with optional/alternate groups (named refusal) and repeat/nested/named groups, entry after generated helpers.

**Defects (regressions vs `/tmp/base`, which compiles all of them):**

1. `_dict_of_lists_kind` recurses forever on a value whose assignment chain reaches itself (`AIL_CURRENT/ail_syntax.py:4080`). Probe:
```python
def main():
    d = {}
    x = 1
    x = x
    d.setdefault("k", []).append(x)
    r = d.get("k")
    if r: sys.stdout.write("%d\n" % r[0])
main()
```
CPython/base: `1`. HEAD: both builds abort, `RecursionError: maximum recursion depth exceeded`. Same for `x = 1; y = x; x = y`.

2. `lower_dict_of_lists` rewrites every matched `setdefault(...).append(...)` as a statement, even when it is not a standalone statement, corrupting valid source (`ail_syntax.py:4198`, `:4233`). Probes (base/CPython pass):
```python
# p_dl_semi: expected "1 2"
d.setdefault("k", []).append(1); d.setdefault("k", []).append(2)
# p_dl_expr: expected "None 4"
x = d.setdefault("k", []).append(4)
# p_dl_lambda: expected "4"
f = lambda v: d.setdefault("k", []).append(v)
```
HEAD: `unexpected indent` / `cannot assign to lambda` on both builds; `/tmp/base` produces the CPython output.

**Report claims.** Verified: both-sides conflict resolution; added test module/tests.d/design doc/DEVLOG; `tools/diff_ids.py` absent (also absent on `work`); `update_manifest.py --check` exits 0; commit `3667f3a` is 16 files, +953/−57; `echo_pack` typed-path test passes. Partially verified: of the 11 modules I re-ran only the added `test_ail_pytyped_reach` (43.7 s) and `test_ail_safetynet` (224.2 s); both pass, the other 9 were not re-run. Unverified: the worker's own probe files (not in the tree), the other 9 modules, and speed/instruction counts.

Pre-existing differences: none observed; the non-feature probe's generated `program.c` is byte-identical on HEAD and base.

VERDICT: FIX
[cost $0.0433, opencode tokens {"total": 2019130, "input": 96971, "output": 9070, "reasoning": 29441, "cache.write": 0, "cache.read": 1883648}]
    tool time: bash 6.6 min
        229s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p_*.py; do echo "===== $(basename $p)"; ti
        128s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p_opt_str.py /tmp/rprobes/p_opt_falloff.py
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_dl_cycle.py /tmp/rprobes/p_dl_cycle2.py /tmp/rpr
         10s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p_dl_cycle.py /tmp/rprobes/p_dl_cycle2.py 
          8s bash   cd /tmp/rprobes && cat > p_dl_lambda.py <<'EOF' import sys  def main():     d = {}     f = lambda v: d.setdefa
          1s bash   rm -rf /tmp/dbg_head /tmp/dbg_base && cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/ail_chatgpt.py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && (nohup python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_s
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 --version && gcc --version | head -1 && git worktree add /tmp/ba

## fix round skipped: only 82 minutes left

FINAL VERDICT: FIX  2026-11-02T04:57:09Z
