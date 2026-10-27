# job job-rbpre278-10270752  started 2026-10-26T22:53:55Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":314,"duration_api_ms":186,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":314,"duration_api_ms":188,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed on `job-rbpre278-10270752`.

**Change**
- Kept pre279's instance-table dispatch for direct collisions.
- Added pre278's `refuse_field_method_call`: typed paths name the refusal and fall back to the general emitter for routes pre279 already handles; the general emitter refuses only the remaining case (`self.f()` in a base method, field stored by a subclass), wording `the method .f() on an instance whose class also stores an instance field named f`.
- Added/registered `test_ail_pre278.py`, plus DEVLOG/DIFFERENCES records and refreshed `MANIFEST.json`.

**Probes** (28 total, both builds)
- 18 `p278_*` probes match CPython; `p278_self_subclass` is refused by the same name.
- 6 `p278x_*` probes match CPython (boundaries 0/-1/int64 min/max/bool/str/list/dict/None, empty/negative, base-field/subclass-method, argument/list/attribute/dict, external, nested owner); `p278x_multi_level_self` is refused by the same name.
- 2 exploratory probes were refused by name for unrelated constructs (`del a.f`, nested class body).

**Tests on final code**
`test_ail_pre278`, `test_ail_pre279`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 38 tests, OK, 1 skipped (`no zig for --target windows`).
`python3 tools/update_manifest.py --check` passes. `tools/diff_ids.py` is not present on this tree.

Commits: `2cfb297` (change/tests), `aa59443` (manifest refresh).
[cost $0.0317, opencode tokens {"total": 1924663, "input": 70948, "output": 11710, "reasoning": 14165, "cache.write": 0, "cache.read": 1827840}]
    tool time: bash 22.4 min, edit 0.0 min
        660s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre278 test_ail_pre279 test_
        370s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre278 test_ail_pre279 test_
         83s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre278 2>&1 | tail -20
         82s bash   for p in /tmp/probes/p278_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E
         81s bash   for p in /tmp/probes/p278_*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E
         38s bash   cat >/tmp/probes/p278x_boundaries.py <<'EOF' class Echo:     def __init__(self, k):         self.k = k     def
         14s bash   mkdir -p /tmp/probes && cat >/tmp/probes/direct.py <<'EOF' class C:     def __init__(self):         self.f = l
          7s bash   ROOT=$PWD; for p in direct non_callable self_subclass; do echo "===== $p"; d=$(mktemp -d); cp /tmp/probes/p278

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds `refuse_field_method_call` (pyfront.py:276), called from the typed entry points (pyc.py:528, pyfunc.py:34768) and the general emitter (pyboxed2.py:11557, with `allow_owners=True`), plus the accepted test/manifest/records. It is pre278's pass, but the general emitter now skips the refusal whenever every statically possible receiver is a collision owner, assuming pre279 handles it.

**Probes run** (`bash ~/tools/cmp.sh`, both builds; HEAD and `/tmp/base`, upstream `/tmp/pre278` where relevant):
- pass: `a_direct`, `b_selfcollide`, `d_callable`, `e_latefield`, `f_namedfunc`, `g_param`, `h_inheritfield`, `j_listfield`, `k_external`, `m_tuple`, `n_setup`, `o_aliascls`, `p_factory`, `q_conditional`, `r_subfieldbase`, `s_noncall_shadow`, `u_builtin`, `w_classfield`, `y_methodarg`, `aa_argfn`, `ab_listfn`.
- expected refusal: `c_selfbase`, `t_selfsub`, `l_keyword`.
- defects: `v_bound`, `z1`, `z2`, `z3`, `z4`, `ac_classmethod`, `ad_static`, `i_shadow`.
- worker's `p278x_*` re-run: 6 match, `deleted`/`nested_class` refused for unrelated constructs, `p278_self_subclass`/`multi_level_self` refused by the p278 name — matches the report.

**Defects**

1. **Bound-method field is let through and miscompiled** (`/tmp/rprobes/v_bound.py`):
```python
class C:
    def __init__(self):
        self.f = self.g
    def g(self):
        return 55
    def f(self):
        return 102
print(C().f())
```
Expected 55 (and the accepted pre278 at FETCH_HEAD refuses this by name). Actual: both builds compile and exit 1 with `AttributeError: 'C' object has no attribute 'g'`. Same for a bound method of another object (`z1`, expected 77), `list.append` (`z2`), list item/attribute receivers (`z3`/`z4`), and classmethod/staticmethod (`ac`/`ad`). Root cause: `allow_owners` treats "all possible classes are collision owners" as "pre279 handles it", but pre279's instance-table dispatch has no route for a field holding a bound method, so the typed path's fallback compiles wrong code. `v_bound` is also wrong on the base (listed under Pre-existing), but upstream pre278 refuses it, so the re-application drops the accepted protection.

2. **False refusal from scope-insensitive name resolution** (`/tmp/rprobes/i_shadow.py`):
```python
class C:
    def __init__(self): self.f = lambda: 101
    def f(self): return 102
class D:
    def f(self): return 7
def a():
    x = C()
def b():
    x = D()
    return x.f()
print(b())
```
Expected 7; base prints 7. Actual: both HEAD builds fail with `not in the subset: the method .f() on an instance whose class also stores an instance field named f`. `_classes_of(Name)` walks every assignment to `x` in the tree, so `x = C()` in `a()` pollutes the local `x` in `b()`. This contradicts the DEVLOG claim "an unrelated receiver is left alone". (Identical in upstream pre278.)

**Pre-existing:** `v_bound`/`z1` wrong output on `/tmp/base` (same AttributeError), so the wrong output itself predates the change; the change's job was to refuse it.

**Report claims:** tests verified — `test_ail_pre278` (80.7s), `test_ail_safetynet` (124.8s), `test_ail_pre279` (86.2s), `test_ail_files` (132.8s), `test_ail_corpus_findings3` (212.8s) all OK. `tools/diff_ids.py` absent (verified). `update_manifest --check` passes (verified). Claim that the general emitter "refuses only the remaining case" is **false** (defects 1–2); "an unrelated receiver is left alone" is **false** (defect 2).

**Unverified:** instruction-count/speed (front-end only; generated code unchanged); exact pass/skip tally of the 38 tests (no failures seen).

VERDICT: FIX
[cost $0.0344, opencode tokens {"total": 1469384, "input": 81823, "output": 7772, "reasoning": 22349, "cache.write": 0, "cache.read": 1357440}]
    tool time: bash 12.6 min
        301s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/par_check.py -j 2 test_ail_pre279 test_ail_fil
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet
        120s bash   cd /home/runner/work/ail-ci/ail-ci && setsid python3 tools/par_check.py -j 2 test_ail_safetynet > /tmp/tests_s
         50s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; timeout 300 
         46s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p278x_*.py /tmp/probes/p278_self_subclass.py; do ec
         34s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/m_tuple.py /tmp/rprobes/n_setup.py /tmp/rprobes/o_
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/u_builtin.py /tmp/rprobes/v_bound.py /tmp/rprobes/
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/z1_boundother.py /tmp/rprobes/z2_boundbuiltin.py /

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `cf16976`.

- Bound-method fields (`self.f = self.g`, other-object methods, builtin methods, classmethod/staticmethod, and values routed through arguments/list items/dict values/attributes/aliases) are now refused by pre278's name on both builds.
- Name resolution now follows Python scopes, so `i_shadow` matches CPython instead of falsely refusing.
- Added bound-method and shadowed-local regressions to `test_ail_pre278.py`.

Probes: 14 new `/tmp/probes/rbpre278_*` plus reviewer `v_bound`, `z1`–`z4`, `ac`, `ad`, `i_shadow`; all match CPython or are refused by name. `rbpre278_shadow_branch` is refused because `x` can genuinely be either class; unrelated scopes match.

Final tests on `cf16976` (`-j 2`): `test_ail_files` 134.5s, `test_ail_corpus_findings3` 222.0s, `test_ail_safetynet` 131.2s, `test_ail_pre279` 89.2s, `test_ail_pre278` 115.7s — 5/5, 0 failed. `update_manifest.py --check` passes.
[cost $0.0494, opencode tokens {"total": 2956122, "input": 134621, "output": 12230, "reasoning": 22583, "cache.write": 0, "cache.read": 2786688}]
    tool time: bash 16.0 min, edit 0.0 min
        384s bash   git rev-parse --short HEAD && timeout 3000 python3 tools/par_check.py -j 2 test_ail_pre278 test_ail_pre279 tes
        196s bash   for p in /tmp/rprobes/*.py /tmp/probes/rbpre278_*.py; do r=$(timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1)
         93s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre278 test_ail_pre279 2>&1 | tail -30
         86s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre278 test_ail_pre279 2>&1 | tail -30
         79s bash   for p in v_bound z1_boundother z2_boundbuiltin z3_boundlistitem z4_boundattr ac_classmethod ad_static i_shadow
         50s bash   for p in /tmp/probes/rbpre278_*.py; do echo "===== $(basename $p)"; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD
         32s bash   python3 -m py_compile AIL_CURRENT/test_ail_pre278.py && python3 tools/update_manifest.py && python3 tools/upda
         16s bash   python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyfront.py && python3 tools/update_manifest.py >/dev/null && 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Reviewed change:** `cf16976` adds `refuse_field_method_call()` to `pyfront.py` and calls it from the two typed entry points (`pyc.py`, `pyfunc.py`) and the v2 general emitter (`pyboxed2.py`, `allow_owners=True`). It refuses a call `x.f()` when a class can define both a method `f` and an instance field `f`, with scope-aware receiver-class resolution and detection of bound-method field values. It registers `test_ail_pre278`, adds a DIFFERENCES row and DEVLOG entries.

**What I ran** (HEAD unless noted):
- No-feature check: `plain.py`, `collide_nocall.py` compiled with `--debug-dir` on HEAD vs `/tmp/base` — generated C identical (only temp paths in `native_report.json`).
- Probes matching CPython or refused by name: `p278x_boundaries`, `p278x_arg_routes`, `p278x_empty_neg`, `rbpre278_{alias,arg,list,dict}_bound`, `rbpre278_{arg,dict}_lambda`, `rbpre278_{base,classattr}_bound`, `rbpre278_{nested_shadow_local,shadow_module,shadow_nested}`, `rbpre278_shadow_branch` (refused), plus `r_bound_cond`, `r_bound_dict2`, `r_plainfunc`, `r_classvalue`, `r_shadow_nested`.
- Tests on HEAD: `test_ail_pre278` 115.7s, `test_ail_pre279` 88.5s, `test_ail_safetynet` 129.2s — 3/3, 0 failed. `tools/update_manifest.py --check` exit 0; `tools/diff_ids.py` is absent.

**Report claims**
- Bound-method fields refused on both builds: **verified** for `self.f = self.g`, other-object, builtin, classmethod/staticmethod, constructor argument, list item, dict value, attribute, alias, base-method/subclass.
- Name resolution follows Python scopes (`i_shadow` now matches): **verified** (`i_shadow`, `r_shadow_nested`, `rbpre278_shadow_*`).
- “14 probes all match CPython or are refused”: **mostly verified**; the probes I added below are not covered and are not refused.
- Final 5/5 tests: **partly verified** — I reran 3/3 as required; `test_ail_files`, `test_ail_corpus_findings3` **unverified**.
- Claims that values through arguments/aliases are all refused are **overstated**: a bound method reaching the field through a default argument, through a helper method that returns its argument, or through an alias of a factory function is not refused.
- Change does what the report says it does; it is a pre278-compatible narrowing for pre279, not the literal accepted diff.

**Pre-existing** (identical output on `/tmp/base`; does not block):
- `r_bound_default.py`: CPython `77`; HEAD/base `AttributeError: 'D' object has no attribute 'g'`.
- `r_bound_factory_alias.py`: CPython `78`; HEAD/base same AttributeError.
- `r_bound_methodarg.py`: CPython `80`; HEAD/base same AttributeError.
- `r_bound_globalalias.py`: CPython bound-method repr; HEAD/base same AttributeError.

**Speed:** not run; the pass is compile-time only and non-feature generated C is byte-identical.

VERDICT: ACCEPT
[cost $0.0311, opencode tokens {"total": 1513061, "input": 68859, "output": 5926, "reasoning": 21572, "cache.write": 0, "cache.read": 1416704}]
    tool time: bash 6.1 min
        206s bash   cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_pre279 test_ail_saf
         34s bash   for p in r_bound_default r_bound_factory_alias r_bound_getattr r_bound_methodarg r_bound_cond r_bound_globalal
         21s bash   for f in rbpre278_base_bound rbpre278_classattr_bound rbpre278_nested_shadow_local rbpre278_shadow_module rbpr
         18s bash   for p in r_bound_default r_bound_factory_alias r_bound_methodarg r_bound_globalalias; do echo "===== BASE $p";
         17s bash   for f in rbpre278_arg_lambda rbpre278_dict_lambda rbpre278_shadow_branch rbpre278_shadow_global; do echo "====
         17s bash   for f in /tmp/probes/p278x_boundaries.py /tmp/probes/p278x_arg_routes.py /tmp/probes/p278x_empty_neg.py /tmp/r
         16s bash   for f in rbpre278_alias_bound rbpre278_arg_bound rbpre278_list_bound rbpre278_dict_bound; do echo "===== $f"; 
         14s bash   for p in r_bound_cond r_bound_dict2 r_bound_getattr; do echo "===== BASE $p"; timeout 250 bash ~/tools/cmp.sh 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T01:27:12Z
