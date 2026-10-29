# job job-cov40-10291030  started 2026-10-29T01:34:53Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"8fa8cc9d-e85d-43c8-8024-af5a985240e2","session_id":"f5c7d766-b9b9-4f35-9064-380bfc8fdb25"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"d7eb9c77-fc9f-42e1-8ece-9512606dc6de","session_id":"38d388c4-4c4a-4723-9cb6-e0039757f659"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `d5108eb`.

- **Census:** 219 corpus programs; compile-time refusals **24 → 21** (188 ok, 10 declared, 0 new DIFF/crash).
- **Construct:** nested generator expressions — the most frequent non-import general-path refusal. Safe in-place consumption now builds; unsafe shapes remain named refusals.
- **Flipped:** `deepseek/t172`, `deepseek/t432`, `glm/t432` now match CPython on both builds.
- **Probes:** `p_join_nested`, `p_sum_nested`, `p_routes`, `p_order_arg`, `p_order_direct`, `p_side_effects` match; `p_unsafe_iterable`, `p_unsafe_element`, `p_unsafe_next`, `p_unsafe_any` are refused by name; `p_saved_nested` keeps the existing saved-generator refusal.
- **Tests:** added `test_ail_cov40.py` (registered in `ail_check.MODULES`), updated `test_ail_pre42.py`. Passed `test_ail_cov40`, `test_ail_pre42`, `test_ail_pre41`, `test_ail_pre116`, `test_ail_pre166`, `test_ail_pre245`, `test_ail_pre381`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- `update_manifest.py --check` passes; no push.
[cost $0.0820, opencode tokens {"total": 8978670, "input": 176560, "output": 19810, "reasoning": 29020, "cache.write": 0, "cache.read": 8753280}]
    tool time: bash 47.2 min
        762s bash   mkdir -p /tmp/probes /tmp/census && cat > /tmp/census/run_census.py <<'PY' import collections, concurrent.futu
        759s bash   python3 /tmp/census/run_census.py /tmp/census/after.jsonl && python3 - <<'PY' import json,collections for name
        653s bash   python3 tools/par_check.py -j 2 test_ail_cov40 test_ail_pre42 test_ail_pre41 test_ail_pre116 test_ail_pre166 t
        276s bash   python3 tools/par_check.py -j 2 test_ail_cov40 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&
         58s bash   cat > /tmp/census/dump_refused.py <<'PY' import json,os,subprocess,sys,tempfile,shutil from pathlib import Pat
         50s bash   cat > /tmp/probes/cov40/p_order_direct.py <<'PY' def inner(i: int) -> int:     print("inner", i)     return i 
         45s bash   mkdir -p /tmp/probes/cov40 cat > /tmp/probes/cov40/p_join_nested.py <<'PY' def show(rows: list[list[int]]) -> 
         38s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre42.py') s=p.read_text() s=s.replace(

## review 0
[model opencode-go/deepseek-v4.1-flash]
**Review of d5108eb (cov40: nested generator expressions)**

**What the change really does.** In `pyboxed2.py` it replaces the unconditional "nested generator expression" refusal with `_nested_genexp_unsafe()`, which allows a nested genexp only when its immediate parent is a `Starred`, a tuple/list unpack target, or an argument to a hard-coded set of "eager" builtins/methods (`list sum min max sorted dict set ...`, `.join .extend .update .array`). Adds `test_ail_cov40.py`, updates `test_ail_pre42.py`, DEVLOG/DIFFERENCES/MANIFEST.

**Claims checked**
- Nested genexp is the construct; safe shapes now build: **verified** (`p_safe_basic`, `p_routes2`, `p_next_safe` match CPython both builds).
- `deepseek/t172`, `deepseek/t432`, `glm/t432` now match both builds: **verified**; on `/tmp/base40` all three are refused by name.
- Tests (`test_ail_cov40`, `test_ail_pre42`, `pre41/116/166/245/381`, `safetynet`, `files`, `corpus_findings3`): **verified**, 10/10 pass. `update_manifest.py --check`: **verified** clean.
- No-feature C unchanged: **verified** (`program.c` md5 identical for `p_no_feature.py`; only `native_report.json` paths differ).
- No push: **verified** (branch ahead of `origin` by 1).
- Full census 24→21: **unverified** (did not run all 219); only the three flipped programs verified.

**Defects (new silent differences; base refuses these by name)**

1. A user method named `join` (also `extend`/`update`/`array`) is trusted as consuming, so the nested generator is materialised and its side effects run. Probe `p_defect_join.py`:
```python
class J:
    def __init__(self) -> None: self.n = 0
    def join(self, it):
        print("no consume"); return 0
def inner(x: int) -> int:
    print("inner", x); return x
def main() -> None:
    print(list(J().join(inner(y) for y in range(2)) for z in range(1)))
main()
```
Expected (CPython, exit 0): `no consume` / `[0]`. Actual HEAD (both builds, exit 0): `inner 0` / `inner 1` / `no consume` / `[0]`. Base: refused by name (`nested inside another generator expression`).

2. Constructors that can reject an element partway (`dict`, `set`, `frozenset`, `Counter`, `bytes`, `bytearray`) are treated as fully consuming, so elements CPython never reaches are evaluated. Probe `p_dict_unhash.py`:
```python
def side(i: int) -> list[int]:
    print("side", i); return [i]
def main() -> None:
    list(dict((side(i), i) for i in [1, 2, 3]) for z in [1])
    print("done")
main()
```
Expected CPython stdout: `side 1` then `TypeError: unhashable type: 'list'`. Actual HEAD (both builds): `side 1` / `side 2` / `side 3`, then the same `TypeError`. Base: refused by name.

**Pre-existing (not counted).** The same eager-materialisation difference already appears on base for the non-nested forms `dict(genexp)` and `obj.join(genexp)`; only the nested spellings are newly accepted, so the change is what turns those from a named refusal into a silent difference.

**Unverified.** Full 219-program refusal census; speed (compile-time-only screen, generated C for non-feature programs is byte-identical).

VERDICT: FIX
1. Restrict the `.join/.extend/.update/.array` branch (and the builtin branch) so user-defined methods/names are not treated as consuming — e.g. use `_bound_names`/`user_method_names`, otherwise keep the nested refusal. Probe `p_defect_join.py`: expected `no consume\n[0]`, actual `inner 0\ninner 1\nno consume\n[0]`.
2. Remove the partway-rejecting constructors (`dict`, `set`, `frozenset`, `Counter`, `bytes`, `bytearray`) from `_NESTED_GENEXP_EAGER_CALLS`, or refuse those shapes by name. Probe `p_dict_unhash.py`: expected stdout `side 1` before `TypeError`, actual `side 1\nside 2\nside 3`.
[cost $0.0406, opencode tokens {"total": 2474254, "input": 77822, "output": 9312, "reasoning": 27056, "cache.write": 0, "cache.read": 2360064}]
    tool time: bash 8.5 min
        366s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         30s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p_safe_basic p_shadow_sum p_shadow_list p_custom_join p
         18s bash   cd /home/runner/work/ail-ci/ail-ci && date && for f in lab/corpus/programs/deepseek-v4.1-flash-free/t172.py la
         14s bash   cd /tmp/rprobes cat > p_next_safe.py <<'PY' def inner(x: int) -> int:     print("inner", x)     return x  def 
         12s bash   cd /tmp/base40 && date && for f in /home/runner/work/ail-ci/ail-ci/lab/corpus/programs/deepseek-v4.1-flash-fre
          8s bash   cd /tmp/base40 && date && for p in p_custom_join p_dict_unhash; do echo "===== $p on BASE ====="; bash ~/tools
          8s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_custom_join p_dict_unhash p_join_typeerr; do echo "=== $p ===
          8s bash   cat > /tmp/rprobes/p_defect_join.py <<'PY' class J:     def __init__(self) -> None:         self.n = 0      de

## fix round skipped: only 69 minutes left

FINAL VERDICT: FIX  2026-10-29T05:20:44Z
