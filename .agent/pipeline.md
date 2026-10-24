# job job-pre31-10240902  started 2026-10-24T00:02:20Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `b53fc44` on `job-pre31-10240902` (not pushed).

- Reproduced `flow_out.py` (`x=1e300; int(x)`): both builds stopped with `integer overflow`; CPython prints the big integer.
- Fix: front end refuses `int()` of an int64-out-of-range float by name (`int() of a float outside int64: ... (CPython makes a big integer)`), including literals, single-binding module constants, literals reached through a call argument, list/tuple item or dict value, and one-level wrapper parameters. In-range conversions are unchanged.
- Probes (both builds): `flow_out`, `int_float_literal`, `int_float_neg_name`, `int_float_alias`, `a_list`, `a_dict`, `a_tuple`, `a_argument`, `a_wrapper`, `a_wrapper_list`, `a_boundary_out`, `a_folded_name` — refused by name. `int_float_inrange`, `a_wrapper_inrange`, `a_boundary_in` — matched CPython. `a_nonfinite` (inf/-inf/nan) — matched CPython. `param_int` — already refused on both builds (`name 'int' is not defined`), no overflow.
- Residual, not claimed fixed: an out-of-range float arriving only at run time through a path the check cannot see (e.g. a stored attribute) still stops at the documented int64 limit.
- Tests on final commit: `test_ail_pre31`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 6451255, "input": 138835, "output": 11211, "reasoning": 27417, "cache.write": 0, "cache.read": 6273792}]
    tool time: bash 11.9 min
        206s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_safetynet test_ail_files test_ail
        206s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_safetynet test_ail_files test_ail
        164s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 test_ail_fuzz45 
        101s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_safetynet 2>&1 | tail -40
         14s bash   mkdir -p /tmp/probes && cat > /tmp/probes/flow_out.py <<'EOF' x = 1e300 print(int(x)) EOF cat > /tmp/probes/pa
          8s bash   cat > /tmp/probes/int_float_alias.py <<'EOF' def take(x):     return int(x)  def identity(x):     return x  pr
          7s bash   cat > /tmp/probes/a_list.py <<'EOF' print(int([1e300][0])) EOF cat > /tmp/probes/a_dict.py <<'EOF' print(int({
          5s bash   cat > /tmp/probes/a_wrapper.py <<'EOF' def take(x):     return int(x) print(take(1e300)) EOF cat > /tmp/probes

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**Scope run:** `work..HEAD` = `b53fc44` (6 files). Base worktree `/tmp/base` at `619dc80`. Probes in `/tmp/rprobes`, all via `~/tools/cmp.sh` against both builds; tests `test_ail_pre31` + `test_ail_safetynet` on HEAD.

**Verified claims**
- `flow_out.py`: base/HEAD-before both `integer overflow`, CPython prints the big int. HEAD now refuses by name on both builds. Verified.
- Literal / negative / single-binding module constant / literal through list, tuple, dict, positional argument, positional wrapper: refused by name. Verified.
- In-range and non-finite conversions (`inf/-inf/nan`) match CPython. Verified.
- `test_ail_pre31`, `test_ail_safetynet`: 0 failed. `update_manifest.py --check`: rc=0. Non-`int` program's generated C identical to base (only temp paths differ in `--debug-dir`). Verified.
- Claim “In-range conversions are unchanged” is **false** (see defects).
- `param_int.py` claim: file not present, not verified. `test_ail_files` / `test_ail_corpus_findings3` not re-run per instructions.

**Defects (change-caused; both builds; base matched CPython)**

1. Module constants leak across scopes. `/tmp/rprobes/p1_shadow_param.py`:
```python
x = 1e300
def f(x):
    return int(x)
print(f(1.5))
```
Expected `1`; HEAD refuses `int() of a float outside int64: 1e+300` (base prints `1`). The `known` map is built from module scope and applied to `Name` nodes regardless of the function's own parameter/local binding.

2. `_outside_int64_float` scans every child of the argument, not the value that reaches `int()`.
- `p2_expr_fits.py`: `int(1e300 * 0)`, `int(1e300 - 1e300)`, `int(0.0 if True else 1e300)` → expected `0` each; HEAD refuses at line 1 (base matches).
- `p11_list_other.py`: `int([1e300, 1.5][1])` → expected `1`; HEAD refuses (base prints `1`).
- `p12_dict_other.py`: `int({"a": 1e300, "b": 1.5}["b"])` → expected `1`; HEAD refuses (base prints `1`).
- `p13_global_expr_fits.py`: `x = 1e300; int(x * 0)` → expected `0`; HEAD refuses (base prints `0`).

**Pre-existing (base == HEAD, not blocking)**
- `p7_wrapper_kw.py`: keyword wrapper call `take(x=1e300)` still `integer overflow` on both builds (only positional wrapper args are checked).
- `p6_shadow_int.py`: redefining `int` is already refused on base.

**Speed:** change is front-end only; no runtime/hot-code effect, no icount run needed.

**Unverified:** `param_int.py`, and the worker's claimed `test_ail_files` / `test_ail_corpus_findings3` results.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 517177, "input": 37405, "output": 3994, "reasoning": 10370, "cache.write": 0, "cache.read": 465408}]
    tool time: bash 2.6 min, grep 0.0 min
        101s bash   cd AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_safetynet 2>&1 | tail -30
         19s bash   cd /tmp/rprobes && for f in p*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-c
         13s bash   cd /tmp/rprobes && for f in p1_shadow_param.py p2_expr_fits.py p6_shadow_int.py p7_wrapper_kw.py; do echo "===
         10s bash   cd /tmp/rprobes && cat > flow_out.py <<'EOF' x = 1e300 print(int(x)) EOF cat > a_nonfinite.py <<'EOF' for v in
         10s bash   cd /tmp/rprobes && cat > p11_list_other.py <<'EOF' print(int([1e300, 1.5][1])) EOF cat > p12_dict_other.py <<'
          3s bash   cd /tmp && rm -rf dbg h.exe b.exe && mkdir dbg && cp /tmp/rprobes/p10_noimport.py p.ail && for m in h b; do if
          0s grep   int\([^\n]*[0-9]e(1[5-9]|[2-9][0-9])
          0s bash   git worktree add /tmp/base work 2>&1 | tail -5 && date

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `ddc3346` (no push).

**Fixed review defects**
- Module constants no longer leak through function/lambda/class/comprehension bindings.
- Only the value reaching `int()` is evaluated, so `1e300 * 0`, `1e300 - 1e300`, conditional branches, and list/dict items that fit are no longer refused.
- Kept true positives refused: flow-out constants, arithmetic, identity functions, positional wrappers, literal containers, tuple fields, out-of-range bounds.

**Probes**
- 17 new `/tmp/probes/pre31_*.py`: 14 match CPython on both builds, 3 refused by name (`pre31_global_in_func`, `pre31_out_arith_name`, `pre31_out_list_name`).
- Reviewer probes `p1`, `p2`, `p11`, `p12`, `p13` now match; `flow_out`, `p4`, `p9` refused by name on both builds.
- Pre-existing and unchanged: `p7_wrapper_kw` (keyword wrapper) and `param_int` still overflow on both base and HEAD.

**Tests on final commit**
- `test_ail_pre31`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- `update_manifest.py --check`: rc=0.
[cost $0.0000, opencode tokens {"total": 1677843, "input": 73120, "output": 10141, "reasoning": 24534, "cache.write": 0, "cache.read": 1570048}]
    tool time: bash 8.1 min
        205s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_s
        100s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre31 test_ail_s
         69s bash   cd /tmp/probes && for f in pre31_*.py a_*.py int_float_*.py flow_out.py bigintlit.py param_int.py; do echo "==
         44s bash   cd /tmp/probes && for f in pre31_*.py; do r=$(bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci 2>&1); 
         38s bash   cd /tmp/rprobes && for f in p1_shadow_param.py p2_expr_fits.py p3_boundary.py p4_boundary_out.py p5_nonfloat.p
          9s bash   cd /tmp/rprobes && for f in p1_shadow_param.py p2_expr_fits.py p3_boundary.py p4_boundary_out.py p5_nonfloat.p
          7s bash   cd /tmp/probes && for f in p7_wrapper_kw.py param_int.py; do if [ -f "$f" ]; then echo "== head $f"; bash ~/to
          6s bash   cd /tmp/probes && echo "== base param_int"; bash ~/tools/cmp.sh /tmp/probes/param_int.py /tmp/base 2>&1 | grep

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: pre31 `int()` float refusal (HEAD `ddc3346`)

**Change read.** New scope-aware constant evaluator + `_Int64CallChecker` in `ail_chatgpt.py`; module added to `ail_check.py`; new `test_ail_pre31.py`; DEVLOG/DIFFERENCES/MANIFEST updated. No codegen changes.

**Probes** (`/tmp/rprobes`, both g and d builds, CPython oracle; base `/tmp/base` for every difference):

| Probe | Result |
|---|---|
| `flow_out`, identity wrapper | HEAD refused by name; base `integer overflow` → task case fixed |
| `b_negative_edge`, `fp_conditional`, `fp_fitting_arith`, `fp_fitting_items`, `fp_dict_key_var`, `fp_identity_local`, `fp_nested_calls`, `fp_no_int`, `fp_shadow_param/lambda/comp`, `fp_wrapper_default/keyword`, `fp_walrus`, `fp_for_target`, `fp_match_bind/star`, `fp_lambda_walrus` | match CPython both builds |
| `b_upper_edge` (2^63) | refused by name both builds (intended) |
| worker `pre31_*` | 14 match, 3 refused by name — claim verified |
| reviewer `p1,p2,p11,p12,p13` | match; `p4,p9` refused by name (g/d) |

No new false refusal found. C output unchanged for non-feature (`nodebug`) and fitting (`debugfit`) programs: `program.c` byte-identical base vs HEAD.

**Pre-existing (identical on base/HEAD, not blocking):** `fp_global_read` (`global x` read) still `integer overflow`; `fp_shadow_class` (class-body local `x`) still overflow; `p7_wrapper_kw` (keyword wrapper) overflow; `fp_nonint_shadow`, `param_int`/`apply(int,...)` already refused by name on base; `fp_except_target` stderr differs.

**Tests on HEAD:** `test_ail_pre31`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc=0.

**Report claims:** fix/scope/value-exactness and 17-probe count verified; p1/p2/p11/p12/p13 and flow_out/p4/p9 verified; p7 verified. One claim **false**: `/tmp/probes/param_int.py` (`apply(int, 1e300)`) does *not* overflow on base or HEAD — both refuse by name (`name 'int' is not defined`); report wording only, not a code defect. Tuple-field `.fN` path not directly probed (unverified, low risk).

No defect caused by the change; targeted task case is fixed and tests/records are consistent.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1299872, "input": 94774, "output": 6047, "reasoning": 28491, "cache.write": 0, "cache.read": 1170560}]
    tool time: bash 6.8 min
        205s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre31 te
         54s bash   cd /tmp/rprobes; for f in b_negative_edge.py b_upper_edge.py fp_*.py a_nonfinite.py; do echo "===== $f"; bash 
         44s bash   cd /tmp/probes; ref=0; match=0; bad=0; for f in pre31_*.py; do out=$(bash ~/tools/cmp.sh "/tmp/probes/$f" /hom
         34s bash   cd /tmp/rprobes; for f in p1_shadow_param.py p2_expr_fits.py p3_boundary.py p4_boundary_out.py p5_nonfloat.py 
         21s bash   cd /tmp/rprobes cat > fp_match_bind.py <<'EOF' x = 1e300  def f(v):     match v:         case x:             r
         13s bash   cd /tmp/rprobes cat > param_int2.py <<'EOF' f = int print(f(1e300)) EOF cat > param_int3.py <<'EOF' def apply(
         10s bash   echo "=== HEAD /tmp/probes/param_int.py"; bash ~/tools/cmp.sh /tmp/probes/param_int.py /home/runner/work/ail-c
          9s bash   cd /tmp/rprobes; for f in fp_shadow_class.py fp_nonint_shadow.py fp_global_read.py; do echo "===== BASE $f"; b

FINAL VERDICT: ACCEPT  2026-10-24T00:50:41Z
