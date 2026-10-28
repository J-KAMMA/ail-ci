# job job-cov27-10290510  started 2026-10-28T20:28:05Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"83847442-61cf-48e4-bbb5-d9d97a671c67","session_id":"290ecc76-ace2-468b-9941-33d84f561655"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"2b9388cc-bf48-45f1-a1bd-ecf184033bb6","session_id":"c3235f1f-1543-4507-b903-47804ab2f0a4"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `2ca6562` on `job-cov27-10290510`.

**Coverage:** census of all 221 corpus programs (442 compiles, both builds): compile-time refusals **24 → 21** default and **24 → 21** unified. Most frequent non-import construct, nested generator expressions: **3 → 0** (deepseek `t172`, `t432`, glm `t432`, matching CPython on all 3 inputs and both builds).

**Change:** nested generators passed to fully-consuming calls (`sum`, `str.join`, `list`, `sorted`, `min`/`max`, …) are materialised at that call; `any`/`all`/`next`, outer elements, outer iterables and saved values stay named refusals.

**Probes** (`/tmp/probes/cov27`, both builds via `cmp.sh`):
- Match CPython: `p_t172`, `p_repr`, `p_sumzip`, `p_empty`, `p_routes` (argument/list item/attribute/dict value), `p_negative` (int64-width), `p_alias`.
- Refused by name: `p_refuse_value`, `p_refuse_anyiter`, `p_refuse_nextiter`, `p_next_short` (both builds); `p_any_short` (unified; default matched).

**Tests:** `test_ail_cov27`, `test_ail_pre42`, `test_ail_fuzz83`, `test_ail_pre116`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on the final commit: **41 run, OK, 1 skipped**. `update_manifest.py --check` passes. Note: the repository has no `lab/profile/run.py`; I used `lab/corpus/check.py`’s compile/run layout and the corpus tasks directly.
[cost $0.0743, opencode tokens {"total": 7659219, "input": 152557, "output": 19042, "reasoning": 29444, "cache.write": 0, "cache.read": 7458176}]
    tool time: bash 69.2 min
        888s bash   python3 tools/update_manifest.py --check && echo manifest-ok; cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAG
        807s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-types' python3 -m unittest tes
        175s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import json seen=set() recs=[json.loads(l) for l in open('/t
        120s bash   mkdir -p /tmp/census /tmp/probes && cat > /tmp/census/run.py <<'PY' import json, os, subprocess, sys, tempfile
        120s bash   sleep 240; tail -2 /tmp/census/log.txt; wc -l /tmp/census/results.jsonl
        120s bash   cd /tmp/census && setsid nohup python3 run.py > log.txt 2>&1 < /dev/null & disown; sleep 1; echo ok; ps aux | 
        120s bash   sleep 120; tail -2 /tmp/census/log.txt; wc -l /tmp/census/results.jsonl
        115s bash   sleep 115; wc -l /tmp/census/results.jsonl; tail -1 /tmp/census/log.txt

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review of `2ca6562` (job-cov27), worktree `/home/runner/work/_temp/w2`.

**What the change really does:** it relaxes the nested-generator screen in `pyboxed2.py` so a nested `GeneratorExp` is allowed only when it and its enclosing `GeneratorExp` are direct positional arguments of a fixed name/method list (`sum`, `list`, `sorted`, `join`, …). Otherwise the old named refusal is raised. No runtime change; C for a non-feature program (`t010`) is byte-identical to base.

**Probes run** (`~/tools/cmp.sh`, both builds): `p_order`, `p_routes2`, `p_empty_big`, `p_t172`, `p_t432` match CPython; `p_saved`, `p_any`, module-level `def sum` are refused by name. Tests on HEAD: `test_ail_cov27`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.

**Defects (new: base refuses these by name; HEAD builds and silently differs on g and d):**

1. Local shadowing of a consumer name. `_genexp_fully_consumed` trusts the bare name; `shadowing.rename_all` only renames module-level definitions, so a local `sum` binding is ignored.
```python
def main():
    log = []
    def side(i):
        log.append(i); return i
    def mysum(it):
        for v in it: return v
        return 0
    sum = mysum
    rows = [[1, 2], [3, 4]]
    print(list(sum(side(v) for v in row) for row in rows))
    print(log)
main()
```
Expected CPython (and base: named refusal): `[1, 3]` / `[1, 3]`. Actual HEAD (`g` and `d`): `[1, 2, 3, 4]` / `[1, 2, 3, 4]`.

2. User method named like an eager consumer. Attribute names are never renamed, and the receiver type is not checked, so a custom partial `join` is treated as fully consuming.
```python
log = []
def side(i):
    log.append(i); return str(i)
class C:
    def __init__(self): self.first = ""
    def join(self, it):
        for v in it:
            self.first = v; return v
        return "z"
def main():
    c = C()
    print(list(c.join(side(v) for v in row) for row in [[1,2],[3,4]]))
    print(log)
main()
```
Expected: `[1, 3]` / `[1, 3]`. Actual HEAD (`g` and `d`): `[1, 2, 3, 4]` / `[1, 2, 3, 4]`. Base refuses both builds.

Root cause: `pyboxed2.py:12477` decides “fully consumed” from a name string alone. Fix by resolving the callee (scope-aware, as `_bound_names` does) and trusting method attributes only on known builtin receivers; otherwise keep the named refusal. `test_ail_cov27.py` does not cover either boundary.

**Report claims:** commit, test module, manifest and t172/t432 behaviour verified; the universal claim that a nested generator passed to a “fully-consuming call” matches CPython is **false** (above); the 24→21 census and the “all three corpus inputs” detail are **unverified** (full corpus not run). No pre-existing differences found for these probes.

VERDICT: FIX
[cost $0.0334, opencode tokens {"total": 1801529, "input": 68219, "output": 7013, "reasoning": 23001, "cache.write": 0, "cache.read": 1703296}]
    tool time: bash 10.7 min
        494s bash   date && python3 ../tools/par_check.py -j 2 test_ail_cov27 test_ail_safetynet test_ail_files test_ail_corpus_fi
         45s bash   cd /tmp/rprobes && date && for p in p_shadow_sum p_shadow_join p_shadow_max p_order p_routes2 p_three p_saved 
         20s bash   cd /tmp/rprobes && cp /home/runner/work/_temp/w2/lab/corpus/programs/deepseek-v4.1-flash-free/t172.py p_t172.p
         13s bash   cd /tmp/rprobes && echo BASE && bash ~/tools/cmp.sh /tmp/rprobes/p_shadow_join.py /tmp/base_cov27 2>&1 | tail 
         10s bash   cd /tmp/rprobes && cat > p_any_inner_full.py <<'EOF' def main():     rows = [[1, 2], [3]]     print(any(sum(v 
          8s bash   cd /tmp/rprobes && cat > p_join_init.py <<'EOF' log = [] def side(i):     log.append(i)     return str(i) clas
          8s bash   cd /tmp && rm -rf cA cB && mkdir -p cA cB && cd cA && cp /home/runner/work/_temp/w2/lab/corpus/programs/glm-5.
          8s bash   cd /tmp/rprobes && cat > p_any_inner_full.py <<'EOF' def main():     rows = [[1, 2], [3]]     print(any(sum(v 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects in `cbcd23a`.

- Bare consumer names are trusted only when `_bound_names` finds no binding; attribute consumers only on provably builtin receivers.
- Local `sum`/`max`/`list`, parameters, user `.join`/`.extend` now keep the named nested-generator refusal on both builds.
- Full corpus census, 221 programs × 2 builds (442 compiles): refusals **24 → 21** both builds; nested-generator refusals **3 → 0**; deepseek t172/t432 and glm t432 match CPython on all 3 inputs. No DIFFs; limit counts unchanged.
- Probes on final commit: `p_good_sum`, `p_good_join`, `p_good_sorted`, `p_saved_inner` match both builds; `p_shadow_sum`, `p_shadow_join`, `p_shadow_max`, `p_shadow_list`, `p_shadow_param`, `p_user_extend`, `p_inner_value` refused both builds; `p_any_inner` matches default, refused unified.
- Final tests: `test_ail_cov27`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing` — 5 modules, 0 failed.
- `update_manifest.py` run; `--check` passes; DEVLOG entry added. Commit is local only.
[cost $0.0495, opencode tokens {"total": 2826585, "input": 167302, "output": 10154, "reasoning": 17321, "cache.write": 0, "cache.read": 2631808}]
    tool time: bash 19.1 min
        730s bash   cd /tmp/census && cp results.jsonl base_results.jsonl && cp after.jsonl prev_after.jsonl && python3 run.py > f
        293s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov27 te
         47s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov27 2>
         35s bash   cd /tmp/probes && for p in p_shadow_sum p_shadow_join p_shadow_max p_shadow_list p_shadow_param p_user_extend 
         33s bash   cd /tmp/probes && for p in p_shadow_sum p_shadow_join p_shadow_max p_shadow_list p_good_join p_good_sum p_good
          4s bash   cd /tmp/probes && cat > p_inner_value.py <<'EOF' def main():     def first(g):         return next(iter(g))   
          0s bash   cd /home/runner/work/_temp/w2 && python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_CURRENT/test
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: cov27 nested generator expressions (HEAD `cbcd23a`)

**What the change really does.** It removes the blanket nested-generator refusal, then re-refuses a nested genexp unless *both* the outer genexp and every inner one are direct positional arguments of a statically trusted “full consumer” (`sum`, `list`, `join`, `min`/`max`, …), with bare names trusted only if unbound and attribute receivers only if their builtin type is inferable (`pyboxed2.py:12487`, `:12554`, `:12571`). This matches the report’s description, but the equivalence claim (“reads every element”) is not true for all call shapes.

**Probes** (`bash ~/tools/cmp.sh …`; HEAD both builds unless noted):

| probe | result |
|---|---|
| `p_triple`, `p_routes`, `p_join_global`, `p_min_key_order` | match CPython, both builds |
| `p_shadow_module_def`, `p_shadow_module_assign`, `p_user_join`, `p_str_subclass_join`, `p_inner_refused_next`, `p_inner_out_iter_refused` | named refusal both builds |
| corpus `deepseek/t172`, `deepseek/t432`, `glm/t432` | match CPython (no stdin) |
| `c_no_feature` | `program.c` byte-identical base vs HEAD (md5 equal) |
| `p_widths` | DIFF, pre-existing (bigint overflow; control `c_bigint_plain` also fails on base) |
| `p_consumers` | DIFF, pre-existing (set display order; control `c_set_plain` also fails on base) |
| `p_max_multi`, `p_sum_start_global` | **new silent DIFFs; base refuses them** |

**Claim check.**
- Bare-name/attribute guards added: **verified** (code + shadow/user-method probes).
- Local/param/user-method refusals: **verified** via `test_ail_cov27` (passed).
- Census 24→21 both builds, nested 3→0: **unverified** (did not rerun the 442-compile census).
- “No DIFFs”: **false** as stated for the feature boundary (two silent DIFFs below); corpus no-DIFF not re-run.
- 5 test modules 0 failed: **verified only** `test_ail_cov27` + `test_ail_safetynet` (0 failed); other 3 unverified.
- Manifest `--check` and DEVLOG: **verified**.

**Pre-existing.** Bigint-width sums (`p_widths` / `c_bigint_plain`) and set display order (`p_consumers` / `c_set_plain`) differ on base too. The two defects below also have the same root cause for a *non-nested* genexp (controls `c_max_single`, `c_sum_start_single` differ on base), but the base **refuses** the nested programs, so the change newly turns them into silent differences.

**Unverified.** Census counts; worker’s `/tmp/probes` results; `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing`; speed (compile-time-only change, generated C unchanged, so not run).

VERDICT: FIX

1. `p_max_multi.py` — `max`/`min` are trusted as full consumers even with extra positional arguments, where CPython never consumes the generator:
```python
def main():
    rows = [[1, 2], [3, 4]]
    print(list(max((v for v in row), [0]) for row in rows))
main()
```
Expected: CPython raises `TypeError: '>' not supported between instances of 'list' and 'generator'`, empty stdout, exit 1. Actual HEAD both builds: stdout `[[1, 2], [3, 4]]`, exit 0. Base: named nested-generator refusal both builds. Fix: trust `min`/`max` only when they have exactly one positional argument (and no other iterable).

2. `p_sum_start_global.py` — the nested genexp is materialised during argument evaluation, before the call’s later arguments, while CPython creates the generator object first and consumes it only inside the call:
```python
log = []
def note(tag):
    log.append(tag)
    return 0
def val(v):
    log.append(v)
    return v
def main():
    rows = [[1, 2], [3]]
    print(list(sum((val(v) for v in row), note("start")) for row in rows))
    print(log)
main()
```
Expected CPython: `[3, 3]` / `['start', 1, 2, 'start', 3]`, exit 0. Actual HEAD both builds: `[3, 3]` / `[1, 2, 'start', 3, 'start']`, exit 0. Base: refused both builds. Fix: only take the eager shortcut when the trusted consumer has no other argument/keyword whose evaluation order would move (at minimum treat `sum` with a second argument and any keyword argument as not “same point”), otherwise keep the named refusal.
[cost $0.0445, opencode tokens {"total": 1017577, "input": 127569, "output": 6291, "reasoning": 31749, "cache.write": 0, "cache.read": 851968}]
    tool time: bash 4.5 min
        136s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov27 te
         35s bash   cd /tmp/rprobes && date && for p in p_triple p_routes p_widths p_join_global p_shadow_module_def p_shadow_modu
         24s bash   cd /tmp/rprobes && for f in /home/runner/work/_temp/w2/lab/corpus/programs/deepseek-v4.1-flash-free/t172.py /h
         20s bash   cd /tmp/rprobes && cat > c_max_single.py <<'EOF' def main():     xs = [1, 2]     print(max((v for v in xs), [0
         19s bash   cd /tmp/rprobes && for p in p_max_multi p_sum_start_order p_min_key_order c_bigint_plain c_set_plain; do echo 
         10s bash   cd /tmp/rprobes && date && for p in p_widths p_consumers; do echo "=== $p BASE ==="; bash ~/tools/cmp.sh /tmp/
         10s bash   cd /tmp/rprobes && for p in p_max_multi p_sum_start_order; do echo "=== $p BASE ==="; bash ~/tools/cmp.sh /tmp
          9s bash   cd /tmp/rprobes && cat > p_sum_start_global.py <<'EOF' log = [] def note(tag):     log.append(tag)     return 

FINAL VERDICT: FIX  2026-10-28T22:42:54Z
