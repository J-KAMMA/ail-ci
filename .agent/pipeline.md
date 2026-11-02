# job job-rbprog7-11021443  started 2026-11-02T05:53:37Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied `job-prog7-11020729` on `job-rbprog7-11021443`.

- Applied: bool-row typing, row receiver resolution in `boolkind`, constant-tuple loop lowering (`tupcommon/tupexpr/tupstmt/tuplib`), host `repr` unprintable table, `test_ail_prog7.py`, `tests.d` registration, `lab/progfix/prog7.md`, DEVLOG entries dated 2026-11-02.
- `tools/diff_ids.py` does not exist in this tree; `update_manifest.py` ran and `--check` exited 0.
- Tests: 40 passed (`prog7`, `tuples`, `nested_lists`, `boolfield`); 25 passed, 1 skipped (`safetynet`, `files`, `corpus_findings3`).
- Probes (both `cmp.sh` builds matched CPython stdout/exit): `p_nested_bool_rows`, `p_tuple_const_loop`, `p_tuple_value_alias`, `p_tuple_empty_mixed`, `p_bool_field_rows`, `p_repr_unprintable`.
- Commit: `c572b02`; working tree clean except pre-existing untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 1549163, "input": 55194, "output": 7343, "reasoning": 6306, "cache.write": 0, "cache.read": 1480320}]
    tool time: bash 14.6 min
        557s bash   python3 -m unittest test_ail_safetynet test_ail_files test_ail_corpus_findings3 > /tmp/tests_b.log 2>&1; echo 
        276s bash   python3 -m unittest test_ail_prog7 test_ail_tuples test_ail_nested_lists test_ail_boolfield > /tmp/tests_a.log
         19s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_nested_bool_rows.py /tmp/probes/p_tuple_const_loop.py 
         11s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_tuple_value_alias.py') s=p.read_text().replace
          7s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-prog7-11020729 2>&1 | tail -5
          2s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p_repr_unprintable.py') s=p.read_text().replace(
          1s bash   cat > /tmp/probes/p_repr_unprintable.py <<'PY' def main() -> None:     parts = [         "\x00", "\x01", "\t",
          1s bash   git add AIL_CURRENT/test_ail_prog7.py AIL_CURRENT/tests.d/test_ail_prog7.txt lab/progfix/prog7.md && python3 t

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does.** Faithful re-application of `job-prog7-11020729`: bool rows become `_AilRow_bool` (`nested_lists.py`), `boolkind.py` resolves `x[i].field` receivers from `list[Row]` annotations/list literals, constant-tuple loops are lowered to a pre-built list (`tup*.py`), and `_ail_srepr` now uses the host `str.isprintable()` table. Each code hunk is byte-identical to the original job diff (only base line numbers/index hashes differ); the extra `manifest.d/ac.txt` update is the required `update_manifest.py` result on this base.

**Verified claims.**
- `tools/diff_ids.py` absent: true.
- `update_manifest.py --check` exits 0: true.
- Tests on HEAD: all 7 modules pass (`prog7`, `tuples`, `nested_lists`, `boolfield`, `safetynet`, `files`, `corpus_findings3`), 542s, 0 failed.
- All six worker probes match CPython on both `cmp.sh` builds: true (re-ran them).
- C unchanged for programs not using the feature: true for my `p_no_feature.py` and `p_tuple_index.py` (`--debug-dir/program.c` byte-identical vs `/tmp/base`).

**Defect (caused by this change).**
1. Constant-tuple lowering ignores control flow and assumes a syntactically earlier assignment always ran, so it replaces a real `UnboundLocalError` with a built list.
```python
def f(flag: bool) -> int:
    if flag:
        t = ((1, 2), (3, 4))
    total = 0
    for a, b in t:
        total += a * b
    return total

def main() -> None:
    print(f(True))
    print(f(False))

main()
```
Expected (CPython): `14`, then `UnboundLocalError: cannot access local variable 't' ...`, exit 1. Actual on HEAD (both `g` and `d` builds): `14\n14`, exit 0. Same defect with the assignment inside a loop that runs zero times (`for _k in range(n): t = (5,6,7)` then `in range(0)`). On `/tmp/base` both builds match CPython. Cause: `tuple_literals` records the assignment but `lower_for` never checks that the assignment dominates the loop.

**Pre-existing (does not count).** `p_repr_chars.py` general build (`g`) refuses `chr()` of non-BMP U+1F600 (`not in the subset ... 16-bit v2 runtime`); identical on base; default build matches CPython.

**Unverified.** Speed via `tools/icount.c`: `perf_event_open: Permission denied` here. The report's "ten lab/compare tasks keep byte-identical program.c" claim: not re-run (only two synthetic no-feature programs checked).

VERDICT: FIX
1. Constant-tuple loop lowering suppresses `UnboundLocalError` when the tuple assignment is conditional or in a loop that may run zero times (probe `/tmp/rprobes/p_cond_tuple_unbound.py`: expected `14` + UnboundLocalError/exit 1, actual `14\n14`/exit 0 on both builds; base is correct). Require the recorded assignment to dominate the loop, or drop the transform when the assignment is inside `if`/loop/try.
[cost $0.0000, opencode tokens {"total": 3547458, "input": 236560, "output": 10518, "reasoning": 22044, "cache.write": 0, "cache.read": 3278336}]
    tool time: bash 9.5 min
        120s bash   cd AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_safetynet test_ail_tuples t
        110s bash   sleep 110; cat /tmp/tests_head.log; echo ---; ps -eo pid,etime,cmd | grep -E "par_check|unittest" | grep -v gr
         60s bash   sleep 60; cat /tmp/tests_head.log; echo ---; ps -eo pid,etime,cmd | grep -E "par_check|unittest" | grep -v gre
         60s bash   sleep 60; cat /tmp/tests_head.log; echo ---; ps -eo pid,etime,cmd | grep -E "par_check|unittest" | grep -v gre
         60s bash   sleep 60; cat /tmp/tests_head.log; echo ---; ps -eo pid,etime,cmd | grep -E "par_check|unittest" | grep -v gre
         35s bash   date; for p in /tmp/probes/*.py; do echo "######## $(basename $p)"; timeout 180 bash ~/tools/cmp.sh "$p" "$PWD
         21s bash   date; for p in /tmp/rprobes/*.py; do echo "######## $(basename $p)"; timeout 180 bash ~/tools/cmp.sh "$p" "$PW
         20s bash   cd AIL_CURRENT && setsid bash -c 'python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_safetynet test_ai

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `f410b2f`.

**Fix**
- Constant-tuple loop lowering now only reuses an assignment that dominates the loop. `tupstmt.py` restores the tuple-literal map around `if`/`while`/`for`/`with`/`try` (and `else` bodies).
- Also forgets names rebound without an `ast.Name` store: `except ... as t`, nested `def`/`class`, import aliases, `del` targets, and any name assigned in a branch once the branch ends.

**Probes** (all matched CPython on both `g` and `d` builds)
`p_dom_both_branches`, `branch_reassign`, `branch_reassign_nonlit`, `def_shadow`, `except_body_assigned`, `except_shadow`, `for_else`, `for_zero`, `if_unbound`, `legit_before_if`, `legit_before_while`, `legit_inner_loop`, `legit_inside_if`, `legit_nested_if`, `legit_try_body`, `nested_unpack`, `reassign_after`, `scalar_if_unbound`, `try_assigned`, `try_else`, `try_unbound`, `while_zero`, `with_after`, `with_shadow` — 24/24.

One extra probe, `p_dom_import_shadow`, still differs; it also differs on `/tmp/base`, so it is a pre-existing function-local import-hoisting bug, not from this change.

**Tests on final commit** (`par_check.py -j 2`, 926s, 0 failed)
`test_ail_prog7`, `test_ail_tuples`, `test_ail_nested_lists`, `test_ail_boolfield`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

`update_manifest.py --check` exits 0; `tools/diff_ids.py` is absent from this tree. Working tree clean except pre-existing untracked `.agent/pipeline.md`.
[cost $0.0557, opencode tokens {"total": 3234582, "input": 165301, "output": 9904, "reasoning": 26417, "cache.write": 0, "cache.read": 3032960}]
    tool time: bash 38.1 min
        929s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_tuples
        914s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog7 test_ail_tuples
        166s bash   cat > /tmp/probes/p_dom_with_shadow.py <<'EOF' def f() -> int:     t = ((1, 2), (3, 4))     total = 0     with
        161s bash   cat > /tmp/probes/p_dom_with_after.py <<'EOF' class Ctx:     def __enter__(self) -> int:         return 0     
         52s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_dom_*.py; do echo "######## $(basename $p)"; timeout 2
         26s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_dom_except_shadow.py /tmp/probes/p_dom_import_shadow.p
         22s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_dom_import_shadow.py /tmp/probes/p_dom_def_shadow.py /
          9s bash   cat > /tmp/probes/p_dom_except_shadow.py <<'EOF' def f() -> int:     t = ((1, 2), (3, 4))     try:         rai

## review 1 skipped: only -3 minutes left

FINAL VERDICT: FIX  2026-11-02T10:52:19Z
