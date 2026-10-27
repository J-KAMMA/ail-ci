# job job-pre314-10271440  started 2026-10-27T05:41:55Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"00e0d22d-c7fe-4b59-9fb6-970a37b54ad3","session_id":"42365432-3b5c-49da-91ab-6af7aaf1d2df"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"4aa1658c-b375-4019-8dbe-944e438a27a0","session_id":"6ad1c3d5-7ced-4316-b4e9-6e42d468a684"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed on `job-pre314-10271440` as `2c7fef1`.

**Fixed:** the first still-differing pre-existing item from the rbpre278 review (`v_bound`): `self.f = self.g` with a method `f` compiled, then stopped with `AttributeError: 'C' object has no attribute 'g'`; CPython calls the stored bound method. Both builds now refuse it by name. Re-applied pre278's `refuse_field_method_call` with scope-aware receiver resolution and bound-method value detection.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- Refused by name: `pre314_bound_{self,other,builtin,arg,default,list,dict,attr,alias,base_sub}`.
- Match CPython: `pre314_{lambda_field,function_field,unrelated_scope,collide_nocall,plain_no_feature,noncallable_field}`.
- Pre-existing, unchanged: a bound-method field stored but never called still fails at construction (`pre314_bound_nocall`).

**Tests on final commit:** `test_ail_pre314`, `test_ail_pre279`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5, 176s, 0 failed. `tools/update_manifest.py --check` passes; `tools/diff_ids.py` absent.

Note: `tools/ci_shards.py --check` reports a pre-existing duplicate `test_ail_pre126` entry; `--update` added `test_ail_pre314` without changing that.
[cost $0.0440, opencode tokens {"total": 4136454, "input": 101144, "output": 13411, "reasoning": 14603, "cache.write": 0, "cache.read": 4007296}]
    tool time: bash 8.2 min
        193s bash   cd AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre314 test_ail_pre279 test_ail_saf
        177s bash   python3 tools/update_manifest.py --check && echo MANIFEST_OK; cd AIL_CURRENT && timeout 3600 python3 ../tools/
         29s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre314 2>&1 | tail -10
         28s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre314 2>&1 | tail -25
         28s bash   cat > /tmp/probes/pre314_bound_base_sub.py <<'EOF' class B:     def run(self):         return self.f()     def
         15s bash   cat > /tmp/probes/r_bound_default.py <<'EOF' class D:     def g(self):         return 77 class C:     def __in
          7s bash   for p in v_bound z1_boundother z2_boundbuiltin r_bound_methodarg r_bound_default; do echo "===== $p"; timeout 
          5s bash   cat > /tmp/probes/pre314_noncallable_field.py <<'EOF' class C:     def __init__(self, v):         self.f = v  

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff does:** adds an AST pre-pass `refuse_field_method_call` (pyfront.py:276) that rejects `x.f(...)` when `f` is both a method and a `self.f = ...` field of a possible receiver class, and calls it from the typed entries (pyc.py:531, pyfunc.py:34810) and pyboxed2.build (allow_owners=True). Report describes this accurately, but overstates two coverage claims.

**Defects (caused by this change; base matches CPython)**

1. Over-refusal of unrelated receivers. `self` in a base method is expanded to every descendant, so a program that never constructs the colliding class is refused.
   - `/tmp/rprobes/sibling_only.py`: `B.run` calls `self.f()`; `C(B)` stores a bound-method field; only `D(B)` (which overrides `f`) is instantiated. CPython and base (both builds) print `7`; HEAD refuses both builds: `not in the subset: the method .f() on an instance whose class also stores an instance field named f`.
   - `/tmp/rprobes/sub_overrides.py`: `D(C)` overrides `__init__` (no field is stored). CPython/base `7`; HEAD refuses.
   - `/tmp/rprobes/for_annot.py`: stale `x: C` annotation while `x` iterates over `D` instances. CPython/base `7`; HEAD refuses.
   The report's "an unrelated receiver is left alone" is false.

2. The general emitter no longer supports the pre279 lambda-field case through a base method. `/tmp/rprobes/base_sub_lambda.py` (`B.run` does `self.f()`, `C(B)` stores `lambda: 5`): CPython and base print `5 100` on both builds; HEAD refuses both builds because `possible={B,C}` is not a subset of `owners={C}`. This contradicts "Fields holding lambdas/plain functions still match CPython" and "refuses only the remaining case".

**Verified claims:** `v_bound` (`self.f = self.g`) differs on base (both builds `AttributeError: 'C' object has no attribute 'g'`) and is refused by name on HEAD (both builds); keyword-argument and classmethod variants also refused; `plain` no-feature C is byte-identical to base (`--debug-dir`, program.c sha256 `46e36b…`); `test_ail_pre314` (2 tests), `test_ail_safetynet`, `test_ail_pre279` pass; `update_manifest --check` OK; `tools/diff_ids.py` absent.

**Pre-existing (base identical, not blocking):** `class_alias`, `setattr_field`, `external_assign`, `tuple_unpack`, `make_receiver`, `var_dict_receiver` still stop with `AttributeError` on both builds; `AIL_GENERAL=v1` still stops with `AttributeError`; `del self.f` already refused.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` (not re-run); instruction counts (front-end only; generated C unchanged when no collision).

VERDICT: FIX
1. `/tmp/rprobes/sibling_only.py`, `/tmp/rprobes/sub_overrides.py`, `/tmp/rprobes/for_annot.py`: expected `7` (CPython and base, both builds); actual named refusal on both builds — unrelated receivers are refused.
2. `/tmp/rprobes/base_sub_lambda.py`: expected `5 100` (CPython and base, both builds); actual named refusal on both builds — pre279's lambda-field support in a base method is lost.
[cost $0.0311, opencode tokens {"total": 1028722, "input": 58048, "output": 5665, "reasoning": 26897, "cache.write": 0, "cache.read": 938112}]
    tool time: bash 3.4 min
         74s bash   date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre314 test_ail_safetynet 2>&
         49s bash   date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre279 2>&1 | tail -8; date
         23s bash   mkdir -p /tmp/rprobes cat > /tmp/rprobes/kw_arg.py <<'EOF' class D:     def g(self):         return 80 class C
         17s bash   cd /tmp/base/AIL_CURRENT && for p in class_alias setattr_field external_assign tuple_unpack make_receiver var_
         13s bash   cat > /tmp/rprobes/sub_overrides.py <<'EOF' class C:     def __init__(self):         self.f = self.g     def g
          9s bash   cat > /tmp/rprobes/for_annot.py <<'EOF' class C:     def __init__(self):         self.f = self.g     def g(sel
          4s bash   cat > /tmp/rprobes/base_sub_lambda.py <<'EOF' class B:     def run(self):         return self.f()     def f(se
          4s bash   cat > /tmp/rprobes/sibling_only.py <<'EOF' class B:     def run(self):         return self.f() class C(B):    

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all review defects and committed as `0762ceb`.

- Removed over-refusal: receivers are limited to constructed descendants; the running `__init__` is resolved through inheritance (including `super().__init__()`); real assignments override stale annotations.
- Restored pre279 lambda/plain-function fields through base methods; bound-method fields are still refused by name on both builds.

Probes (`/tmp/probes`, both builds):
- Refused by name: `pre314_bound_{self,other,builtin,arg,default,list,dict,attr,alias}`, `pre314_base_sub_bound{,_explicit}`, `pre314_super_init_bound`, `v_bound`, `z1_boundother`, `z2_boundbuiltin`.
- Match CPython: `pre314_{sibling_only,sub_overrides,for_annot,base_sub_lambda,base_sub_function,super_init_lambda,super_init_override,lambda_field,function_field,unrelated_scope,collide_nocall,plain_no_feature,noncallable_field,noncall_for}`.
- `pre314_bound_nocall` and `pre314_no_collision_field` remain pre-existing differences, identical on base.

Tests on final commit: `test_ail_pre314` 46.4s, `test_ail_safetynet` 71.5s, `test_ail_files` 72.3s, `test_ail_corpus_findings3` 113.4s — 4/4 OK, 0 failed. `tools/update_manifest.py --check` passes.
[cost $0.0444, opencode tokens {"total": 2770391, "input": 86374, "output": 15032, "reasoning": 24121, "cache.write": 0, "cache.read": 2644864}]
    tool time: bash 7.2 min
        161s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3600 python3 tools/par_check.py -j 2 test_ail_pre314 tes
         60s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre314_*.py /tmp/probes/v_bound.py /tmp/probes/z1_b
         46s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && time timeout 1800 python3 tools/par_
         44s bash   cd /home/runner/work/ail-ci/ail-ci && time timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre314 2>&1 |
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do n=$(basename $p .py); out=$(bash ~/tools/
         19s bash   mkdir -p /tmp/probes && cat >/tmp/probes/pre314_sibling_only.py <<'EOF' class B:     def run(self):         re
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in sibling_only sub_overrides for_annot base_sub_lambda v_bound la
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in sibling_only sub_overrides for_annot base_sub_lambda; do echo "

## review 1 skipped: only 44 minutes left

FINAL VERDICT: FIX  2026-10-27T10:17:22Z
