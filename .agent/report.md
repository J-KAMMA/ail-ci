# job job-pre352-10280028  started 2026-10-27T15:28:40Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"12354361-120a-47bf-9dc3-39ecfe7d778a","session_id":"92a0534e-f49d-40a3-9555-f267e493d414"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"16246b95-426a-4c78-991f-f8c95d726aa1","session_id":"7b32182d-fb05-41f8-8a49-0ec75cd59587"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre339 item: a class alias assigned inside `try` now reaches the bound-method-field refusal and is refused by name on both builds. The second pre-existing item (function use before a later ancestor rebinding) still prints the same `AttributeError` and is unchanged.

- Commit: `b70e500` on `job-pre352-10280028`
- Probes (`/tmp/probes/pre352`, both builds): 11 refused by name — `rv08_try*`, `alias_basic`, `chain`, `tuple_unpack`, `local_alias`, `alias_arg`, `alias_list`, `alias_attr`, `alias_dict`; 13 matched CPython — `no_feature`, `alias_to_d`, `reassigned_d`, `p2_reassign`, `p3_dead_if`, `p4_for_rebind`, `rv04`–`rv06`, `rv13`, `rv17`, `arg_other_class`, `list_other_class`; `rv09_before_later` remains the second pre-existing difference.
- Final-commit tests: `test_ail_pre352`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 351 s, 0 failed.
- `tools/update_manifest.py --check` passes; DEVLOG and DIFFERENCES updated.
[cost $0.0000, opencode tokens {"total": 6431033, "input": 176690, "output": 17358, "reasoning": 30137, "cache.write": 0, "cache.read": 6206848}]
    tool time: bash 18.4 min, edit 0.0 min
        353s bash   cd AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre352 test_ail_safetynet test_ail_
        108s bash   git add AIL_CURRENT/test_ail_pre352.py && python3 tools/update_manifest.py && python3 tools/update_manifest.py
        104s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre352.py') s=p.read_text() old='''    
         99s bash   for p in alias_arg.py alias_list.py alias_attr.py alias_dict.py arg_other_class.py list_other_class.py rv08_tr
         84s bash   for p in rv08_try_pass.py rv08_try_finally.py rv08_try.py alias_basic.py rv04_local_shadow.py rv05_param_shado
         79s bash   for p in rv08_try.py rv08_try_pass.py rv08_try_finally.py alias_basic.py rv09_before_later.py p2_reassign.py p
         74s bash   for p in rv13_kwonly.py rv04_local_shadow.py rv05_param_shadow.py rv06_module_rebind.py rv17_cond.py p2_reassi
         54s bash   pwd; for p in rv08_try_pass.py rv04_local_shadow.py rv05_param_shadow.py rv06_module_rebind.py rv13_kwonly.py 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `b70e500` (`work..HEAD`)**

**What the diff really does:** Rewrites `refuse_field_method_call`'s receiver analysis: adds `_unique_alias_classes` (resolves a `Name` from its own/outer scope's plain assignments, including chains and `try`), `_is_parameter`/`_other_binding`, maps bare class names to classes, and adds keyword-only params to `_param_names`. So it is broader than "alias assigned in a `try`": it changes receiver resolution for all alias/container routes, and can suppress as well as add refusals.

**Claims**
- Target `try: Alias = C; Alias().f()` now refused by name on both builds — **verified** (`p_try.py`).
- Second item (`rv09_before_later`) unchanged: same `AttributeError` on HEAD and base — **verified**.
- 11 refused / 13 matched cases — **verified** by reading and running `test_ail_pre352` (passes).
- `test_ail_pre352` + `test_ail_safetynet` on final commit, 0 failed — **verified** (131 s). `test_ail_files` / `test_ail_corpus_findings3` — **unverified** (out of reviewer scope, not re-run).
- `update_manifest.py --check` — **verified** (rc 0).
- Claim that only the collision construct is refused — **false**; see defects.

**Defects**

1. A pre-existing *correct named refusal* is now lost, and the program compiles then crashes at run time. `_unique_alias_classes` returns the non-owner `{C}` from the one `Name` assignment and ignores the later `D()` assignment, short-circuiting the old union that found owner `D`.
```python
class C:
    def f(self): return 7
class D:
    def __init__(self): self.f = self.g
    def g(self): return 55
    def f(self): return 102
x = C
x = D()
print(x.f())
```
Expected: CPython prints `55`, or a named refusal. Base: refused by name (`...stores an instance field named f`). HEAD: compiles, exits 1 with `AttributeError: 'D' object has no attribute 'g'`. This is a change-caused regression.

2. Change-caused over-refusal of programs the base compiled and that matched CPython (named refusals, so arguably acceptable under the rules, but they are regressions on the new alias/container path). `p_mutate_list.py` (`ks = [Alias]; ks[0] = D; print(ks[0]().f())`) and `p_mutate_dict.py` (`d = {"k": Alias}; d["k"] = D; ...`): CPython and base print `7`; HEAD refuses both builds. The stale container value is resolved without considering mutation.

**Pre-existing (identical on base, not blocking):** alias via walrus (`p_walrus.py`) and via `for` target (`p_loop.py`) still stop with the same `AttributeError` on HEAD and base; `rv09_before_later` likewise.

**Verified unaffected:** no-feature generated `program.c` is byte-identical between HEAD and `/tmp/base`.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; instruction counts (front-end only).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 504694, "input": 43512, "output": 4203, "reasoning": 21011, "cache.write": 0, "cache.read": 435968}]
    tool time: bash 4.6 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre3
         41s bash   cd /tmp/rprobes; for f in p_try p_nested p_walrus p_classes p_loop p_cond_mix p_mutate_list p_alias_arg_other 
         31s bash   cd /tmp/rprobes; for f in p_try p_walrus p_classes p_loop p_cond_mix p_mutate_list p_rebind_same; do echo "===
         26s bash   cd /tmp/rprobes && cat > p_mutate_dict.py <<'EOF' class C:     def __init__(self):         self.f = self.g    
         17s bash   cd /tmp/rprobes && cat > p_suppress.py <<'EOF' class C:     def f(self):         return 7 class D:     def __i
          9s bash   ls /tmp/probes/pre352 2>/dev/null | head -40; echo ===; if [ -f /tmp/probes/pre352/rv09_before_later.py ]; the
          8s bash   cd /tmp/rprobes; bash ~/tools/cmp.sh /tmp/rprobes/p_mutate_attr.py /tmp/base 2>&1 | tail -12; echo ====; bash 
          8s bash   cd /tmp/rprobes; echo "=== p_nested HEAD full"; bash ~/tools/cmp.sh /tmp/rprobes/p_nested.py /home/runner/work

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both reviewer defects and committed as `a3901b4`.

- Rebinding now considers every assigned value and the last definite binding: `x = C; x = D()` is refused again instead of compiling to `AttributeError`.
- List/dict writes before use are followed directly, through a container alias, and through a called function; writes after the use or conditional writes still refuse.
- Probes `/tmp/probes/pre352rev` `r01`-`r19` on both builds: 10 refused by name, 9 match CPython. `r20` remains the same pre-existing mismatch on both builds.
- `test_ail_pre352`: 15 refused / 19 matching cases.
- Final-commit tests: `test_ail_pre352`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 359 s, 0 failed.
- `tools/update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2873010, "input": 206710, "output": 12914, "reasoning": 36170, "cache.write": 0, "cache.read": 2617216}]
    tool time: bash 20.0 min
        362s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3600 python3 ../tools/par_check.py -j 2 test_ail_pre
        146s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && cd AIL_CURRENT && timeout 1200 pytho
        138s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         86s bash   cd /tmp/probes/pre352rev && for f in r*.py; do out=$(bash ~/tools/cmp.sh "$PWD/$f" /home/runner/work/ail-ci/ai
         86s bash   cd /tmp/probes/pre352rev && for f in r*.py; do echo "=== ${f%.py}"; bash ~/tools/cmp.sh "$PWD/$f" /home/runner
         85s bash   cd /tmp/probes/pre352rev && for f in r*.py; do echo "=== ${f%.py}"; bash ~/tools/cmp.sh "$PWD/$f" /home/runner
         60s bash   cd /tmp/rprobes && for f in p_suppress p_suppress2 p_mutate_list p_mutate_dict p_mutate_attr p_alias_arg_other
         56s bash   cd /tmp/rprobes && for f in p_suppress p_suppress2 p_mutate_list p_mutate_dict p_mutate_attr p_alias_arg_other

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: pre352 (work..HEAD, commits b70e500, a3901b4)

**What the change really does:** it extends the field/method collision screen in `pyfront.py` so a receiver name bound by assignments (including inside `try`, chains, tuple unpack, parameters, list/dict items, attributes) resolves to its class and reaches the by-name refusal. It adds statement-order/dominance tracking, container-alias and container-write tracking, and keyword-only parameters to the parameter list. The report describes this accurately, but omits the new parameter/ordering behaviour that causes the regressions below.

**Report claims**
- Try-alias case now refused by name, both builds: **verified** (`p_try.py`: base `AttributeError`, HEAD refused).
- Worker probes r01–r19 = 10 refused / 9 match; r20 same pre-existing mismatch: **verified** (rerun on HEAD: 10/9/1; r20 fails identically on `/tmp/base`).
- Rebinding and container-write follow-ups: **verified** for the listed cases (r01/r02/r07–r09/r11–r14/r19).
- `test_ail_pre352` 15 refused / 19 match: **verified by file contents and test run**.
- Final tests: `test_ail_pre352` + `test_ail_safetynet` on HEAD **verified, 0 failed**. `test_ail_files` / `test_ail_corpus_findings3` not re-run (reviewer scope) — **unverified**.
- `tools/update_manifest.py --check` passes: **verified**.
- No-feature C unchanged: **verified** (`program.c` identical base vs HEAD for `p_no_feature.py`).

**Defects (change-caused; base behaves acceptably)**
1. Ordering filter loses a refusal when the container assignment follows a function's *source* line but executes before its call. `p_sub_use_before_assign.py`: `def f(ks): return ks[0].f()` then `ks = [C()]`. CPython prints `55`; base refuses by name; HEAD compiles and exits 1 with `AttributeError: 'C' object has no attribute 'g'` (both builds).
2. Same bug for a dict: `p_dict_use_before_assign.py` (`def f(d): return d["k"].f()` then `d = {"k": C()}`). Expected `55`; base refuses; HEAD exits 1 with the same `AttributeError` (both builds).
3. `bool` list index is treated as non-constant and resolves to nothing. `p_bool_index.py`: `ks = [D(), C()]; print(ks[True].f())`. CPython prints `55`; base refuses; HEAD exits 1 with `AttributeError: 'C' object has no attribute 'g'` (both builds).
4. Over-refusal of a reassigned parameter: `p_param_reassign.py` (`def call(k): k = D; return k().f(); print(call(Alias))`). CPython/base print `7`; HEAD refuses by name on both builds. `p_walrus_comp.py` (`ks = [Alias := D for _ in range(1)]`) likewise: CPython/base print `7`, HEAD refuses.

**Pre-existing:** r20 (`try` assigning `C`, handler assigning `D`) still gives `AttributeError` on both builds and base — not counted. Call-alias use before a later module assignment is also wrong on base and HEAD.

Speed: front-end only; no benchmark/runtime edits, `program.c` for a no-feature program is byte-identical, so no icount run.

VERDICT: FIX
1. `p_sub_use_before_assign.py`: expected `55` (exit 0); actual `AttributeError: 'C' object has no attribute 'g'`, exit 1.
2. `p_dict_use_before_assign.py`: expected `55` (exit 0); actual same `AttributeError`, exit 1.
3. `p_bool_index.py`: expected `55` (exit 0); actual same `AttributeError`, exit 1.
4. `p_param_reassign.py` and `p_walrus_comp.py`: expected `7`; actual name-based compile refusal.
[cost $0.0000, opencode tokens {"total": 1268999, "input": 53661, "output": 5213, "reasoning": 21133, "cache.write": 0, "cache.read": 1188992}]
    tool time: bash 6.4 min
        149s bash   cd /home/runner/work/ail-ci/ail-ci && date && cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 
         85s bash   cd /tmp/probes/pre352rev; ref=0; same=0; diff=0; for f in r*.py; do out=$(bash ~/tools/cmp.sh "$PWD/$f" /home/
         62s bash   cd /tmp/rprobes; for f in p_param_reassign p_kwonly_reassign p_param_cond_reassign p_walrus_comp p_param_plain
         17s bash   cd /tmp/rprobes cat > p_dict_use_before_assign.py <<'EOF' class C:     def __init__(self):         self.f = se
         17s bash   cd /tmp/rprobes cat > p_sub_use_before_assign.py <<'EOF' class C:     def __init__(self):         self.f = sel
         10s bash   cd /tmp/rprobes cat > p_use_before_assign.py <<'EOF' class C:     def __init__(self):         self.f = self.g 
          9s bash   cd /tmp/rprobes cat > p_cond_mut.py <<'EOF' class C:     def __init__(self):         self.f = self.g     def g
          9s bash   cd /tmp/rprobes; echo BASE; bash ~/tools/cmp.sh p_dict_use_before_assign.py /tmp/base; echo HEAD; bash ~/tools

FINAL VERDICT: FIX  2026-10-27T16:45:34Z
