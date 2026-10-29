# job job-cov50-10291930  started 2026-10-29T10:53:28Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"3d65d27f-e5fb-46b7-bd27-d7b890572585","session_id":"5db5f00c-0a38-4fb1-bc0b-f8cec9cc0416"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"446c174f-c376-4a32-ac86-7147626e28ee","session_id":"30de6295-42a7-4638-bf1d-bb47b367f8a3"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `0c6b5bd` on `job-cov50-10291930`.

**Profile:** `lab/profile/run.py` is not present in this export, so I used the equivalent compile profile over all 219 `lab/corpus/programs/*/*.py` (default build, 2 workers).
- Refusals: **24 -> 21** total; imports **8 -> 7**.
- Most frequent non-import construct: nested generator expressions on the general path, **3 -> 0**.
- Newly accepted and CPython-matching on all 3 corpus inputs and both builds: `deepseek/t172`, `deepseek/t432`, `glm/t432`.

**Change:** nested generator chains are accepted only when every level is read by a full-consumer call (`join`, `list`, `sorted`, `sum`, `min`, `max`, `dict`, ...). `any`/`all`/`next`, saved values, user-function arguments, breakable `for` loops and lazy consumers such as `zip` stay named refusals.

**Probes** (`/tmp/probes/cov50`, both builds):
- Match CPython: `p_nested_join`, `p_nested_sum`, `p_nested_containers`, `p_nested_raise`, `p_nested_routes`.
- Refused by name: `p_nested_any_refused`, `p_nested_saved_refused`, `p_nested_user_refused`, `p_nested_for_refused`, `p_nested_zip_refused`.

**Tests passed:** `test_ail_cov50`, `test_ail_pre41`, `test_ail_pre116`, `test_ail_pre166`, `test_ail_pre211`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. Manifest and CI-shard checks pass.
[cost $0.0000, opencode tokens {"total": 6399129, "input": 228506, "output": 18177, "reasoning": 31614, "cache.write": 0, "cache.read": 6120832}]
    tool time: bash 24.9 min
        721s bash   sed -i "s|work=tmp/p.parent.name+'-'+p.stem;|work=tmp/(p.parent.name+'-'+p.stem);|" /tmp/prof.py && time pytho
        511s bash   cat > /tmp/cov50/run_tests.py <<'PY' import subprocess, sys, time from concurrent.futures import ThreadPoolExe
         43s bash   rm -rf /tmp/probes/cov50 && mkdir -p /tmp/probes/cov50 cat > /tmp/probes/cov50/p_nested_join.py <<'PY' def mar
         43s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_cov50.py') s=p.read_text() s=s.replace(
         38s bash   mkdir -p /tmp/probes/cov50 /tmp/cov50/corpus && cat > /tmp/probes/cov50/p_nested_join.py <<'PY' def mark(x: in
         36s bash   rm -f /tmp/probes/cov50/p_nested_list.py /tmp/probes/cov50/p_nested_zip_refused.py cat > /tmp/probes/cov50/p_n
         31s bash   cat > /tmp/cov50/recheck.py <<'PY' import json, os, subprocess, sys, tempfile, shutil, re from pathlib import 
         30s bash   cat > AIL_CURRENT/test_ail_cov50.py <<'PY' """cov50: nested generator expressions whose every level is read by

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `0c6b5bd` cov50

**What the diff really does:** It whitelists nested generator expressions for the general path's existing eager lowering whenever every generator in the AST subtree is a direct positional argument of a call whose *name* (or method name) is in the old eager-consumer sets minus `any`/`all`/`next`. This differs from the report's "full-consumer call" wording: `min`/`max` do not pre-consume, `extend`/`update` mutate incrementally, and the method check trusts user-defined methods named `join`/`extend`/`update`/`array`.

**Verified**
- Match on both builds: nested `join`, 3-level `join`, and the three claimed corpus programs (`deepseek/t172`, `deepseek/t432`, `glm/t432`) on all 3 inputs.
- Named refusals on both builds for nested `any`, `all`, `next`, saved value, `for`, `zip`, user-function argument.
- Non-feature `p_plain`: generated `program.c` identical to `/tmp/base` on both builds.
- `test_ail_cov50` + `test_ail_safetynet` pass; `update_manifest.py --check` and `ci_shards.py --check` pass.
- Unverified: full corpus refusal counts `24 -> 21`, `imports 8 -> 7` (not rerun); corpus profile not present.

**Defects** (each refused by `/tmp/base`, so newly introduced)

1. `extend` partial mutation is lost when the inner generator raises.
```python
xs: list[int] = []
def f(x: int) -> int:
    print("f", x)
    if x == 3: raise ValueError("boom")
    return x
def main() -> None:
    try: print(list(xs.extend(f(v) for v in row) for row in [[1,2,3],[4]]))
    except ValueError as e: print("caught", e)
    print(xs)
main()
```
Expected (CPython and base's named refusal, not this output): `f 1 / f 2 / f 3 / caught boom / [1, 2]`. Actual on both builds: same but final line `[]`.

2. `min`/`max` are treated as full consumers, but they compare while pulling.
```python
class Obj:
    def __init__(self, n: int) -> None: self.n = n
    def __lt__(self, other: "Obj") -> bool:
        print("lt", self.n, other.n); return self.n < other.n
def build(x: int) -> Obj:
    print("build", x); return Obj(x)
def main() -> None:
    print(min(tuple(build(v) for v in row)[0] for row in [[3],[1],[2]]).n)
main()
```
Expected: `build 3 / build 1 / lt 1 3 / build 2 / lt 2 1 / 1`. Actual on both builds: `build 3 / build 1 / build 2 / lt 1 3 / lt 2 1 / lt 1 2 / 1` (order differs and an extra comparison occurs).

3. User methods named like eager consumers are trusted.
```python
class Box:
    def join(self, g): return next(g)
def mark(x: int) -> int:
    print("mark", x); return x
def main() -> None:
    print(list(Box().join(mark(v) for v in row) for row in [[1,2,3],[4,5,6]]))
main()
```
Expected: `mark 1 / mark 4 / [1, 4]`. Actual on both builds: `mark 1 / mark 2 / mark 3 / mark 4 / mark 5 / mark 6 / [1, 4]`. Same for a user method named `update`.

VERDICT: FIX

1. Nested chain accepted when the inner consumer is `extend`: the eager inner list is built before `extend`, so a mid-iteration exception leaves the receiver unmodified instead of partially extended.
2. Nested chain accepted when the outer consumer is `min`/`max`: eager materialisation changes comparison interleaving (and adds a comparison), differing from CPython.
3. `_genexp_full_call_consumer` matches method names only, so a user-defined `join`/`extend`/`update` is lowered eagerly even when it is lazy. Either verify the receiver is the builtin type or refuse these method names.
[cost $0.0000, opencode tokens {"total": 1147358, "input": 89690, "output": 6813, "reasoning": 16487, "cache.write": 0, "cache.read": 1034368}]
    tool time: bash 4.0 min
        125s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov50 te
         22s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/check_corpus.sh <<'SH' set -u wt=$1 repo=$2 for prog 
         22s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/check_corpus.sh <<'SH' set -u wt=$1 for prog in lab/c
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh $p $
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_extend_partial.py /tmp/rprobes/p_update_partial.
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_method_spoof.py /tmp/rprobes/p_method_spoof_upda
          8s bash   cd /tmp/rprobes && cat > p_next_nested_refused.py <<'PY' def mark(x: int) -> int:     print("mark", x)     ret
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_extend_partial.py /tmp/rprobes/p_min_order.py; d

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `f6760e5` on `job-cov50-10291930`.

**Fixes**
- Removed nested `min`/`max` acceptance (they compare while pulling) — now refused by name.
- Removed nested `extend`/`update` acceptance (partial mutation lost on exceptions) — now refused by name.
- Method consumers now trusted only for `str.join` on a string literal; rebound builtin names (`list`, `sum`) are not trusted.
- Kept `list`/`tuple`/`sorted` and fused `sum` so `__add__`/`__radd__` interleave like CPython.

**Corpus:** 24 → 21 refusals (imports 8 → 7), unchanged; `deepseek/t172`, `deepseek/t432`, `glm/t432` still match CPython on all 3 inputs on both builds.

**Tests:** 8/8 passed — `test_ail_cov50`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_cov2`, `test_ail_builtin_syntax_forms`, `test_ail_genlib`, `test_ail_pre116`. `update_manifest.py --check` and `ci_shards.py --check` pass.

**Probes (both builds):** matching — `p_nested_valid`, `p_nested_containers`, `p_nested_sum_start`, `p_sum_order`, `p_matching_three`; refused by name — `p_extend_partial`, `p_update_partial`, `p_min_order`, `p_max_order`, `p_method_spoof`, `p_method_spoof_update`, `p_name_spoof_list`, `p_name_spoof_sum`, `p_join_var_refused`, `p_next_nested_refused`, `p_all_refused`. `p_min_simple` still shows the general path’s pre-existing reflected-`__lt__` extra call, unchanged from `/tmp/base`.
[cost $0.0797, opencode tokens {"total": 7967033, "input": 148225, "output": 22779, "reasoning": 34109, "cache.write": 0, "cache.read": 7761920}]
    tool time: bash 25.3 min, edit 0.0 min, read 0.0 min
        602s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov50 test_ail_s
        600s bash   cat > /tmp/probes/profile_corpus.sh <<'SH' #!/bin/bash set -u repo=$1 prog=$2 d=$(mktemp -d /tmp/cprofXXXX) cp
         72s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov50 2>&1 | tai
         71s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov50 2>&1 | tai
         31s bash   cd /home/runner/work/ail-ci/ail-ci && python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyboxed2.py && for p in
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_extend_partial p_update_partial p_min_order p_max_order p_met
         26s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_extend_partial p_update_partial p_min_order p_max_order p_met
         22s bash   cd /home/runner/work/ail-ci/ail-ci && bash /tmp/rprobes/check_corpus.sh $PWD $PWD 2>&1 | tail -20

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds a nested-generator whitelist (`_nested_genexp_allowed`, pyboxed2.py:12510) so a generator expression nested in another is accepted when every level is a direct argument of `list`/`tuple`/`sorted`/`sum` (or `str.join` on a string literal), and fuses `sum` over a generator argument (pyboxed2.py:9423). This matches the report except that the whitelist is looser than described: it accepts any positional argument of `sum`, not only the iterable.

**Claims**
- Nested `min`/`max` now refused: verified (`s3` refused by name).
- Nested `extend`/`update` refused, spoofed methods/names refused: verified by `test_ail_cov50` REFUSED cases passing.
- `list`/`tuple`/`sorted` and fused `sum` match CPython: verified (`s5`, `s6`).
- Corpus 24→21 and t172/t432 match: partially verified — `check_corpus.sh` printed `DONE` with no DIFF/BUILD-FAIL; I did not re-profile the 219 programs.
- `update_manifest.py --check`: verified (exit 0).
- Tests 8/8: verified `test_ail_cov50` (90s ok) and `test_ail_safetynet` (124s ok); the other six were not rerun.

**Defects**
1. A nested generator expression passed as `sum`'s **start** argument is accepted as if consumed, and silently materialised on both builds. `_genexp_full_call_consumer` (pyboxed2.py:12503) trusts any `node in par.args` for `sum`; it must require the iterable (`par.args[0]`).
   Probe `/tmp/rprobes/s10_min.py`:
   ```python
   def main() -> None:
       rows = [[1, 2], [3]]
       g = sum([], (sum(z for z in row) for row in rows))
       print(type(g).__name__)
   main()
   ```
   CPython 3.12: `generator`; HEAD general and default: `list` (exit 0 both). Base refuses by name, so this silent difference is introduced by the change. Same for an inner `sum` start (`s8`).
2. Minor: a program not using the feature (`plain1.py`, plain `sum(xs)`/`sum([...])`) no longer emits byte-identical C: `_b_sum` allocates `acc` before `_resolve_iter_src`, renumbering frame slots (72 diff lines). Outputs are identical, so this is cosmetic but fails the "C unchanged" check.

**Pre-existing**
- Non-nested `sum([], (z for z in [1, 2]))` materialises the start generator on the base too (probe `s9`): both base and HEAD print `list`, CPython `generator`.

**Unverified**
- Full corpus refusal counts (24→21).
- The six remaining test modules in the report.
- Speed/icount (change affects only the general compile path and the fused `sum` over a genexp; no hot runtime change observed).

VERDICT: FIX
1. Nested genexp as `sum`'s start is accepted and materialised instead of refused (`s10_min.py`: expected `generator`, actual `list`; base refuses by name). Restrict the whitelist to the consumed argument: `par.args[0] is node`.
2. Non-feature `sum` calls emit renumbered C versus base (cosmetic; restore the original temp-allocation order).
[cost $0.0315, opencode tokens {"total": 1294189, "input": 81349, "output": 6381, "reasoning": 19899, "cache.write": 0, "cache.read": 1186560}]
    tool time: bash 5.7 min
        125s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet 
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_cov50 test_ail_
         22s bash   cd /home/runner/work/ail-ci/ail-ci && bash /tmp/rprobes/check_corpus.sh $PWD $PWD 2>&1 | tail -20
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in s4_sum_start_nested s5_sum_iter_ok s6_list_ok s7_sum_start_simp
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in s1_sum_start s2_sum_start2 s3_min_nested; do echo "=== $p HEAD"
          9s bash   cd /tmp/rprobes && cat > s10_min.py <<'EOF' def main() -> None:     rows = [[1, 2], [3]]     g = sum([], (sum(
          9s bash   cd /tmp/rprobes && cat > s9_start_plain.py <<'EOF' def main() -> None:     g = sum([], (z for z in [1, 2]))   
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in s4_sum_start_nested s7_sum_start_simple; do echo "=== $p BASE";

FINAL VERDICT: FIX  2026-10-29T12:19:58Z
