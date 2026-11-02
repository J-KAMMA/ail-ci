# job job-rbpyreach1-11021550  started 2026-11-02T07:04:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects on branch `job-rbpyreach1-11021550`, commit `456b1d0`.

- `_dict_of_lists_kind`: added cycle detection (`seen`); `x = x` and `x = 1; y = x; x = y` now compile to int instead of recursing.
- `lower_dict_of_lists`: lowers only standalone `setdefault(...).append(...)` expressions; assignments, lambda bodies, and inline suites are left as written. Continuation indentation uses line indentation, so `;`-separated calls stay valid.

Probes: 11/11 match CPython on both builds (`p_dl_cycle`, `p_dl_cycle2`, `p_dl_semi`, `p_dl_expr`, `p_dl_lambda`, `p_dl_basic`, `p_dl_nested`, `p_dl_mixed`, `p_dl_inline`, `p_dl_inline_for`, `p_dl_inline_def`).

Tests: 6 modules passed — `test_ail_pytyped_reach`, `test_ail_typedreach1`, `test_ail_typedreach2`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet`. `tools/update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 1132053, "input": 99032, "output": 7150, "reasoning": 11855, "cache.write": 0, "cache.read": 1014016}]
    tool time: bash 9.1 min, edit 0.0 min
        199s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pytyped_reach test_ail_files te
        191s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         98s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_typedreach1 test_ail_typedreach
         24s bash   cd /tmp/probes && cat > p_dl_inline.py <<'EOF' import sys  def main():     d = {}     if True: d.setdefault("k
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c " import sys; sys.path.insert(0,'AIL_CURRENT') import ail_syn
         11s bash   for p in /tmp/probes/p_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "/home/runner/work/ail-c
          5s bash   cd /tmp/probes && cat > p_dl_nested.py <<'EOF' import sys  def helper(v, d):     d.setdefault("k", []).append(
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -c "import ast; ast.parse(open('AIL_CURRENT/ail_syntax.py').read

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds a `seen` cycle guard to `_dict_of_lists_kind` (`ail_syntax.py:4059`), and restricts `lower_dict_of_lists` to standalone `Expr` `setdefault(...).append(...)` calls, skipping assignments, lambda/value positions and inline suites, with continuation padding taken from line indentation (`ail_syntax.py:4136-4260`). Matches the report.

**Probes.** Ran the 11 `p_dl_*` probes plus 13 own probes (`r_cycle_*`, `r_semi_three`, `r_mix_*`, `r_else_line`, `r_try`, `r_while`, `r_for_semi`, `r_nested_if`, `r_arg_value`, `r_no_get`, `r_get_none`, `r_paren`) on HEAD. All match CPython on both builds except `r_paren`. Confirmed on `/tmp/base` (work): cycle probes abort with `RecursionError` there; HEAD gives CPython's output for `x=x`, `x=1;y=x;x=y`, and non-int-valued cycles (subscript/attribute/tuple). Assignments/lambdas/inline suites are left byte-identical by `lower_dict_of_lists`; semicolon and nested-indent continuations compile. A no-feature program's `program.c` is byte-identical on HEAD and base.

**Defects.** None introduced by this change.

**Report claims.** Verified: both named defects fixed; 11/11 probes pass both builds; inline/assignment/lambda left as written; line-indentation padding; all 6 named test modules pass on HEAD (`test_ail_pytyped_reach`, `test_ail_typedreach1/2`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet`, 0 failed); `update_manifest.py --check` exits 0. Unverified: nothing material; speed not measured (compile-time-only change).

**Pre-existing.** `(d.setdefault("k", []).append(1))` (parenthesized standalone expression) is lowered into statements inside parentheses and fails to compile; identical failure on base `work`, so not caused by this fix.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 778608, "input": 93063, "output": 5987, "reasoning": 19334, "cache.write": 0, "cache.read": 660224}]
    tool time: bash 5.8 min
        138s bash   cd /home/runner/work/ail-ci/ail-ci && date && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_py
        130s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
         51s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p_dl_*.py /tmp/rprobes/r_*.py; do echo "==
         13s bash   cd /tmp/rprobes && cat > r_for_semi.py <<'EOF' import sys  def main():     d = {}     for i in range(2):      
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r_cycle_sub2.py /tmp/rprobes/r_cycle_neg.py /tmp/r
          4s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest check exit $?";
          3s bash   cd /tmp/base && for p in /tmp/rprobes/p_dl_semi.py /tmp/rprobes/p_dl_expr.py /tmp/rprobes/p_dl_lambda.py; do e
          2s bash   cd /tmp/base && for p in /tmp/rprobes/r_cycle_sub2.py /tmp/rprobes/r_cycle_neg.py /tmp/rprobes/r_cycle_tuple.p

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T08:49:03Z
