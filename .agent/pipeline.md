# job job-std_string-11012216  started 2026-11-01T13:18:40Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining review defect by tracking each receiver's possible type, so only non-known-non-Template receivers reach the Template helper. Unrelated `.is_valid`/`.substitute` attributes are ordinary calls again; the two general-path collision cases are now named refusals instead of crashes.

Probes (`bash ~/tools/cmp.sh`, both builds):
- match CPython: `p9_setattr_only`, `p7_dataclass_flag`, `p3_collision`, `p3_collision2`, `p_template_ok`, `p9b_class_method`
- named refusal: `p8_setattr`, `p9_lambda_method`, `p8b_setattr_init`, `getattr_value`

Tests (final code): `test_ail_std_string` 0 failed (199 s); `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` 0 failed (344 s). `update_manifest.py --check` exit 0. Added regression tests and DEVLOG/RESULTS notes. Commit `0f7cdc3`.
[cost $0.0000, opencode tokens {"total": 3743430, "input": 109939, "output": 10489, "reasoning": 18138, "cache.write": 0, "cache.read": 3604864}]
    tool time: bash 19.5 min, edit 0.0 min
        345s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_file
        200s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && date && python3 tools/par_check.py -
        174s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_std_string 2>&1 | tail 
        124s bash   for p in p8_setattr p9_setattr_only p9_lambda_method p7_dataclass_flag p3_collision p3_collision2 p_template_o
        103s bash   for p in p8_setattr p9_lambda_method p7_dataclass_flag p3_collision p3_collision2 p_template_ok getattr_value 
         97s bash   for p in p8_setattr p9_setattr_only p9_lambda_method p7_dataclass_flag p3_collision p3_collision2 p_template_o
         65s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p8_setattr.py <<'EOF' import string class Box: pass def check(): ret
         32s bash   cat > /tmp/probes/p8b_setattr_init.py <<'EOF' import string class Box:     def __init__(self):         self.ta

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** adds a scope-unaware name→binding classification (`kind_of_name`/`kind_of_value`/`receiver_kind`) and uses it to gate the `string.Template` method lowering: calls are skipped only when the receiver is *known* non-Template, and the method-as-value refusal now fires only when the receiver is *known* Template. Plus regression tests, DEVLOG, RESULTS, manifest. It does roughly what the report says, but it overstates "unrelated `.is_valid`/`.substitute` attributes are ordinary calls again".

**Probes** (`bash ~/tools/cmp.sh`, both builds; base = `/tmp/base`):
- match CPython on HEAD: `p3_collision`, `p3_collision2`, `p7_dataclass_flag`, `p9_setattr_only`, `p9b_class_method`, `p_template_ok`, `pI_call_param`, `pK`/`pL` variants.
- named refusal on HEAD: `p8_setattr`, `p9_lambda_method`.
- **regressions** (base refused or matched, HEAD fails/crashes): `pE2`, `pF`, `pJ`, `pH`, `pA`, `pN`.

**Defects**

1. `visit_Attribute` (`AIL_CURRENT/ail_syntax.py:1849`) refuses a Template method used as a value only when `receiver_kind(...) == 'template'`. A receiver it cannot classify (function parameter, subscript, call result) skips the refusal and compiles to an ordinary attribute read, which crashes at run time. `pE2_value_arg.py`:
   ```python
   import string
   def get_valid(x):
       return x.is_valid
   def main():
       t = string.Template("$x")
       f = get_valid(t)
       print(f())
   main()
   ```
   Expected CPython: `True`, exit 0. Base: named refusal `not in the subset: string.Template.is_valid used as a value`. HEAD (g and d): `AttributeError: '_AilStringTemplate' object has no attribute 'is_valid'`, exit 1. Same for `pJ` (dict value), `pF` (call result), `pH` (Template parameter). `pA` is the same gate via an assignment target: CPython `1\nBOX`, base refusal, HEAD `AttributeError: 'Box' object has no attribute 'template'`, exit 1. The gate should be `!= 'other'`, like the call gate.

2. The new binding map is keyed by name globally, not by scope. A real Template call through a parameter is not lowered when an unrelated same-named variable elsewhere holds a non-Template. `pN_false_other.py`:
   ```python
   import string
   class Box:
       def __init__(self): self.tag = "box"
   def render(t):
       return t.substitute(x=1)
   def main():
       t = Box(); print(t.tag)
       tpl = string.Template("$x")
       print(render(tpl))
   main()
   ```
   Expected CPython and base (g and d): `box` then `1`, exit 0. HEAD: both builds fail (`not in the subset: substitute() called with an unknown keyword argument x`; d: type error at `p.ail:152`). The receiver kind must be resolved per scope, or parameters treated as unknown.

**Claims:** unrelated receivers now ordinary (`p3_collision`, `p3_collision2`, `p7_dataclass_flag`, `p9b_class_method`): verified. `p8_setattr`/`p9_lambda` named refusals: verified (p8's message is the class-without-`__init__` refusal, not the Template one). Listed probes matching CPython: verified. `test_ail_std_string` + `test_ail_safetynet`: 0 failed (198 s). `update_manifest.py --check`: exit 0. `test_ail_files`, `test_ail_corpus_findings3`: unverified (not re-run).

**Pre-existing:** non-Template `.is_valid()` through a parameter (`pM`) crashes identically on base and HEAD, so that hijack is not caused here. Non-feature C unchanged (checked `berth_sim`; change is gated on `template_used`). Speed: compile-time-only, not measured.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; the full 10 `lab/compare` byte-identity set (only `berth_sim` checked); gdev instruction counts.

VERDICT: FIX
1. `visit_Attribute` value gate must refuse when the receiver is not known non-Template (`!= 'other'`), not only when known Template; currently `pE2_value_arg.py` prints `True` (exit 0) on CPython and is refused on base, but on HEAD raises `AttributeError: '_AilStringTemplate' object has no attribute 'is_valid'` (exit 1). `pA_arg_call.py` likewise: CPython `1\nBOX`, base refusal, HEAD `AttributeError: 'Box' object has no attribute 'template'`.
2. Make the binding classification scope-aware (or treat parameters as unknown): `pN_false_other.py` prints `box\n1` (exit 0) on CPython and base, but HEAD fails to build both paths (`not in the subset: substitute() called with an unknown keyword argument x`) because the parameter `t` is classified from an unrelated local `t = Box()`.
[cost $0.0000, opencode tokens {"total": 1358139, "input": 37383, "output": 6379, "reasoning": 22089, "cache.write": 0, "cache.read": 1292288}]
    tool time: bash 11.1 min
        200s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_stri
        120s bash   cd /tmp/rprobes && for p in pA_arg_call pB_dict_call pC_list_call pD_attr_call pE_value_arg pE2_value_arg pF_v
        107s bash   cd /tmp/probes && for p in p3_collision p3_collision2 p7_dataclass_flag p9_setattr_only p9b_class_method p_tem
         72s bash   cd /tmp/rprobes && for p in pF2_value_call pJ_dict_value pH_value_ok pI_call_param; do echo "===== HEAD $p ===
         66s bash   cd /tmp/rprobes && cat > pK_call_unknown.py <<'EOF' import string  class Box:     def __init__(self):         
         40s bash   cd /tmp/rprobes && cat > pM_call_unknown.py <<'EOF' import string  class Box:     def __init__(self):         
         25s bash   cd /tmp/rprobes && cat > pN_false_other.py <<'EOF' import string  class Box:     def __init__(self):         s
         23s bash   cd /tmp && rm -rf dbg_base dbg_head && mkdir dbg_base dbg_head && cd /home/runner/work/ail-ci/ail-ci && AIL_NO

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `8a44a19`.

- Scope-aware receiver classification; parameters resolved per function/call site.
- Value gate now refuses any receiver not known non-Template; only attribute reads, so assignment targets like `self.substitute = "S"` still build.
- Probes: `pE2`, `pF`, `pH`, `pJ` refused by name; `pA`, `pN`, `pI`, `pK`, `pM`, `p3_collision2`, `p7_dataclass_flag`, `p9b_class_method`, `p_template_ok`, `pG_direct` match CPython on both builds; new probes `p_scope_local`, `p_param_kw`, `p_infer_kw`, `p_nested_scope` match.
- `lab/compare` generated C: 10/10 byte-identical.
- Final commit tests: `test_ail_std_string`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `python3 tools/update_manifest.py --check` exits 0.
[cost $0.0000, opencode tokens {"total": 2735497, "input": 53137, "output": 10936, "reasoning": 19904, "cache.write": 0, "cache.read": 2651520}]
    tool time: bash 28.4 min, edit 0.0 min
        410s bash   python3 tools/update_manifest.py --check && cd AIL_CURRENT && date && timeout 3600 python3 ../tools/par_check.
        318s bash   cd AIL_CURRENT && date && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files te
        242s bash   cd AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_std_string 2>&1 | tail -60
        109s bash   cd /tmp/probes && for p in p3_collision p7_dataclass_flag p9_setattr_only p9b_class_method p_template_ok p8_se
        108s bash   cd /tmp/probes && for p in p3_collision p3_collision2 p7_dataclass_flag p9_setattr_only p9b_class_method p_tem
        104s bash   cd /tmp/rprobes && for p in pB_dict_call pC_list_call pD_attr_call pG_direct pK_call_unknown pL_call_known_oth
        101s bash   cd /tmp/rprobes && for p in pA_arg_call pG_direct pK_call_unknown pM_call_unknown pN_false_other pE2_value_arg
         87s bash   mkdir -p /tmp/probes3 && cat > /tmp/probes3/p_scope_local.py <<'EOF' import string  class Box:     def __init_

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review

**Change:** adds a per-scope receiver classifier (`collect_template_scopes`/`scope_of`/`kind_of_name`/`kind_of_value`, `receiver_kind`) so the `string.Template` method lowering is skipped only when a receiver is *known non-Template*; allows attribute assignment targets; adds 6 tests. It does not restrict lowering to receivers *known to be Templates*.

**Probes (HEAD, both builds; base = `work` = 0846cca):**
- `p_review_p8` (exact review probe): HEAD now named refusal (`the method .is_valid() (on a instance:Box)` / class has no `__init__`), base crashed. Acceptable per "or refuse when not".
- pass/match: `p_param_ok`, `p_known_other`, `p_no_feature` (generated C byte-identical to base), plus worker probes `pA_arg_call`, `pI_call_param`, `pK_call_unknown`, `pM_call_unknown`, `pN_false_other`, `pG_direct`.
- refused by name: `pE2_value_arg`, `pF_value_call`, `pH_value_ok`, `pJ_dict_value`; `p_class_lambda`, `p_setattr_init`.
- **crash on HEAD, named refusal on base**: `p_self_attr`, `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop`.

**Defect**
1. `_Surface.call` (`ail_syntax.py:2657-2662`) lowers when `receiver_kind(...) != 'other'`, so a receiver of *unknown* kind still goes to `template_method`. `p_self_attr.py`:
   ```python
   import string
   class Box:
       def __init__(self):
           self.substitute = lambda v: "SUB" + str(v)
       def run(self):
           return self.substitute(5)
   def main():
       t = string.Template("$x")
       print(t.substitute(x=1))
       print(Box().run())
   main()
   ```
   Expected (CPython, exit 0): `1` / `SUB5`. Actual (HEAD g and d, exit 1): `1` then `AttributeError: 'Box' object has no attribute 'template'`. Base refuses the same program by name (`string.Template.substitute used as a value`) on both builds, so this is a refusal→crash regression. Same root cause in the other five probes (receiver is `self`, a subscript, a call result, an attribute chain, a loop variable, or a tuple-unpack target). The review asked for lowering only on receivers actually known to be Templates (or refusing otherwise); that is still not implemented.

**Claims**
- Scope/parameter resolution: verified (`p_param_ok`, `pA_arg_call`, `pI_call_param`; code as described).
- Value gate refuses unknown receivers on reads, assignment targets allowed: verified.
- `pE2/pF/pH/pJ` refused by name; `pA/pI/pK/pM/pG` match: verified.
- `p3_collision2`, `p7_dataclass_flag`, `p9b_class_method`, `p_template_ok`: files not present, **unverified** (`p_class_lambda`/`p_setattr_init` equivalents refuse by name).
- `lab/compare` 10/10 C identical: 5/10 compile and are byte-identical; 5 fail on both trees here (e.g. `chain_relax` needs `--exact-int`), so **unverified**.
- Tests: re-ran `test_ail_std_string` + `test_ail_safetynet`, 0 failed (242 s, `-j 2`); `update_manifest.py --check` rc 0. `test_ail_files`, `test_ail_corpus_findings3` not re-run (not edited).

**Pre-existing:** none newly observed; `p_class_lambda`/`p_setattr_init` base crashes are now named refusals (improvement).

**Unverified:** speed (no runtime hot path; compile-time AST walk only); the 5 lab/compare tasks needing extra flags.

VERDICT: FIX
1. `_Surface.call` still hijacks `.substitute/.safe_substitute/.is_valid/.get_identifiers` calls on receivers whose kind is unknown (`self`, `d[k]`, `f()`, `h.b`, loop/tuple-unpack targets). Probe `/tmp/rprobes_r/p_self_attr.py`: expected CPython `1\nSUB5` (exit 0); actual HEAD both builds `1` then `AttributeError: 'Box' object has no attribute 'template'` (exit 1), while base refuses it by name. Restrict lowering to receivers known to be `string.Template` (or refuse/leave unknown receivers alone), as the review requested; `p_dict_sub`, `p_call_result`, `p_attr_chain`, `p_tuple_unpack`, `p_for_loop` show the same defect.
[cost $0.0212, opencode tokens {"total": 873442, "input": 41556, "output": 5506, "reasoning": 15372, "cache.write": 0, "cache.read": 811008}]
    tool time: bash 17.2 min
        395s bash   cd /tmp && rm -rf lc && mkdir lc && cd lc && n=0; same=0; for f in /home/runner/work/ail-ci/ail-ci/lab/compare
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        183s bash   cd /tmp/rprobes_r && for p in p_review_p8 p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_f
        120s bash   cd /tmp/rprobes && for p in pA_arg_call pI_call_param pK_call_unknown pM_call_unknown pN_false_other p3_collis
         48s bash   cd /tmp/rprobes_r && for p in p_class_lambda p_setattr_init; do for wt in /home/runner/work/ail-ci/ail-ci /tmp
         21s bash   cd /tmp/rprobes_r && for p in p_self_attr p_dict_sub p_call_result p_attr_chain p_tuple_unpack p_for_loop p_re
         18s bash   cd /tmp/rprobes_r && rm -rf dbg_head dbg_base exe_head exe_base && AIL_NO_CACHE=1 python3 /home/runner/work/ai
          0s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 tools/update_manifest.py --check; echo "rc=$?"; date

FINAL VERDICT: FIX  2026-11-01T15:05:41Z
