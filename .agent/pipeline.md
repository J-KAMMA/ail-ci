# job job-rbpre289-10270940  started 2026-10-27T00:42:42Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"0a9bbcd9-ff4d-43ba-b525-1f921ab87016","session_id":"9817629b-657f-49b4-b5ba-df69ead67a5a"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"82e5f186-4bdb-457a-a8cf-0fc54da26b5b","session_id":"bd610c2b-c12e-4965-9b56-4fcf41a97d23"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done on branch `job-rbpre289-10270940`, commit `f980589`.

- pre289’s refusal was already superseded by pre279’s instance-table lookup; kept pre279 and added `test_ail_pre289.py` checking CPython match on both builds.
- Registered the test, added DIFFERENCES row `C?-job-rbpre289-10270940-1` and a DEVLOG entry. No compiler/runtime code changed.
- Probes in `/tmp/probes/p289` (`direct`, `v1`, `annotated`, `chain`, `assigned`, `argument`, `list`, `dict`, `attribute`, `alias`, `subclass`, `conditional`, `boundaries`, `arguments`, `field_absent`, `noncallable_return`, `mixed`, `method_args_types`, `unrelated`, `unrelated_conditional`, `non_class`) all match CPython on both builds. `deleted` is refused by name for the unrelated pre-existing `del` on an attribute.
- Tests: `test_ail_pre289`, `test_ail_pre279`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (427 s).
- `tools/diff_ids.py` does not exist on this tree; `tools/update_manifest.py` was run and `--check` passes.
[cost $0.0000, opencode tokens {"total": 1328290, "input": 58772, "output": 8591, "reasoning": 5119, "cache.write": 0, "cache.read": 1255808}]
    tool time: bash 9.2 min, edit 0.0 min, write 0.0 min
        429s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre289 test_ail_pre279 test_ail
         67s bash   cd /tmp/probes/p289 && W=/home/runner/work/ail-ci/ail-ci; for p in *.py; do case $p in _pair.py) continue;; es
         33s bash   cd /tmp/probes/p289 && W=/home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path import i
         14s bash   mkdir -p /tmp/probes && cat > /tmp/probes/cur_direct.py <<'EOF' class C:     def __init__(self, k):         se
          4s bash   cd /tmp/probes/p289 && W=/home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/p289/deleted.py $W
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre289-10270338 2>&1 | tail -5 && git log --oneline -3 FET
          1s bash   mkdir -p /tmp/probes/p289 && cd /tmp/probes/p289 && cat > _pair.py <<'EOF' class C:     def __init__(self, k):
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_pre289.py AIL_CURRENT/ail_check.py DEVLOG.m

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job-rbpre289 (commit f980589)

**What the diff really does:** adds `AIL_CURRENT/test_ail_pre289.py` (CPython-match tests for the field/method collision through function-return receivers), registers it in `ail_check.MODULES`, adds a DIFFERENCES row, a DEVLOG entry, and the manifest hashes. No compiler/runtime code changed. The accepted pre289 *refusal* is deliberately not applied because pre279's instance-table lookup already compiles these calls correctly.

**Probes** (HEAD and `/tmp/base`, general + default builds):

| probe | covers | HEAD | base |
|---|---|---|---|
| p1 | direct, return, `-> C`, chain, assigned; 0, ±7, ±2**58 | match | match |
| p2 | parameter pass-through, list/dict/tuple index return, nested, mixed C/A conditional | match | match |
| p3 | field set in non-`__init__` method, subclass, subclass method override | match | match |
| p4 | callable object field, lambda, builtin `len`, arity-mismatched named function | match (arity case refused by name) | same |
| p5 | program not using the feature | match | match |

No behaviour differs from base; no C-code change is possible (only test/docs/manifest touched). The arity-mismatched field (`def f(self)` with field `h(x)`) is refused by name on both trees — pre-existing/named, not blocking.

**Claims:**
- “Refusal superseded by pre279” — verified: every route I tried matches CPython on both builds.
- “No compiler/runtime code changed” — verified (`git diff --stat work..HEAD`).
- “`tools/diff_ids.py` absent; `update_manifest.py --check` passes” — verified (file absent, check rc=0, test hash matches).
- “test_ail_pre289 + test_ail_safetynet pass” — verified: 2 modules, 0 failed (125 s).
- Other three modules in the report — not re-run (out of reviewer scope).
- Minor: DEVLOG says “7 tests”; the module defines 6 test methods (subtests aside). Cosmetic only.

**Pre-existing:** none observed beyond the named arity refusal above.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 664970, "input": 25612, "output": 4707, "reasoning": 9115, "cache.write": 0, "cache.read": 625536}]
    tool time: bash 3.7 min
        127s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         25s bash   cd /tmp/rprobes && for p in p1 p2 p3 p4 p5; do echo "===== $p BASE ====="; bash ~/tools/cmp.sh /tmp/rprobes/$p
         18s bash   cd /tmp/rprobes && W=/home/runner/work/ail-ci/ail-ci; for p in p1 p2 p3 p4; do echo "===== $p HEAD ====="; bas
         15s bash   cd /tmp/rprobes && sed -i 's/4611686018427387904/288230376151711744/g; s/-4611686018427387904/-288230376151711
         11s bash   cd /tmp/rprobes && sed -i 's/Callable/Fn/g' p4.py && echo "=== HEAD ==="; bash ~/tools/cmp.sh /tmp/rprobes/p4.
          9s bash   cd /tmp/rprobes && cat > p4.py <<'EOF' def g():     return 55  def h(x):     return x + 1  class C:     def __
          8s bash   cd /tmp/rprobes && cat > p4.py <<'EOF' def g():     return 55  class C:     def __init__(self, v, has):       
          7s bash   cd /tmp/rprobes && cat > p4.py <<'EOF' class Callable:     def __init__(self, n):         self.n = n     def _

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T02:15:57Z
