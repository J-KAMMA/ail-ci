# job job-pre398-10281024  started 2026-10-28T01:25:34Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"cfc45640-9308-4546-a257-dc3ed8e45073","session_id":"61469d19-966f-4bee-9829-ef5634e49d6a"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"b1946622-45c0-4fac-8d46-a4494f316b2b","session_id":"39d840ec-32a7-49c5-a634-66e390673bf0"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `223cbf2` on `job-pre398-10281024`.

The task's pre382 item list was blank, so I used the first pre-existing item from the pre382 reviewer: indirect class-body self-read (`def get(): return C`; `class C: x = get()`). It now refuses by name on both builds, including nested function chains and list/dict/tuple/argument routes.

Probes (`cmp.sh`, both builds): `q1_indirect`, `q1_list`, `q1_dict`, `q1_attr`, `q1_nested_arg`, `q1_wrapper` refused by name; `m1_plain`, `m3_param_shadow`, `m5_after`, `m6_other_class`, `m7_local_c`, `m9_reader_not_called` match CPython. Pre-existing unchanged: `q2_exprstmt`, `q3_savedgen`, `q3b_savedgen_next`, `q4_direct`, `m4_class_shadow`, `m8_deferred_lambda_attr`.

Tests: test_ail_pre398, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — 27 tests, 0 failed, 1 skipped (358.4 s). `update_manifest.py --check` rc=0.
[cost $0.0000, opencode tokens {"total": 4467178, "input": 107839, "output": 11957, "reasoning": 17782, "cache.write": 0, "cache.read": 4329600}]
    tool time: bash 7.7 min
        358s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_pre398 test_ail_safetynet test_ail_files test_ail_corpus_fin
         35s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_pre398 2>&1 | tail -20
         27s bash   cat > /tmp/probes/pre398/m1_plain.py <<'EOF' def get():     return 1 class C:     x = get() print(C.x) EOF cat
         23s bash   cat > /tmp/probes/pre398/q1_wrapper.py <<'EOF' def get():     return C def wrap():     return get() class C:  
         15s bash   mkdir -p /tmp/probes/pre398 cat > /tmp/probes/pre398/q1_indirect.py <<'EOF' def get():     return C class C:  
          2s bash   timeout 60 git fetch --no-tags origin refs/heads/job-pre382-10280718:refs/pre382tmp 2>&1 | tail -5; git show r
          0s bash   timeout 30 git ls-remote --heads origin 2>&1 | tail -20
          0s bash   timeout 30 git ls-remote --heads origin 2>/dev/null | grep -E "job-pre(37[0-9]|38[0-9]|39[0-9])" | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
Diff: adds a front-end pass `_refuse_class_body_indirect_self_read` that refuses a class-attribute assignment whose value calls a module function (directly or via module-function chain) that loads the class name; plus test/registration/manifest/DEVLOG.

Verified:
- `q1_indirect` now refused by name on both builds; base returns the class. Direct/list/dict/tuple/nested-argument/wrapper cases are in `test_ail_pre398` and pass.
- Plain function, other class, parameter/local shadow, call after the class body, and function-argument controls match CPython.
- Spot-checked pre-existing items `q2_exprstmt`, `q3_savedgen`, `q3b_savedgen_next`, `q4_direct`, `m4_class_shadow`, `m8_deferred_lambda_attr`: identical on base and HEAD.
- Targeted tests: `test_ail_pre398`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` rc=0.

Defects caused by the change (both programs matched CPython and the base, now fail to compile):

1. Prior binding of the class name is ignored.
```
C = 5
def get():
    return C
class C:
    x = get()
print(C.x)
```
Expected CPython: stdout `5`, exit 0. Actual HEAD (g and d): build fails with “…CPython raises NameError because C is not bound yet”. `C` is bound; the message and refusal are wrong.

2. Control flow is ignored; a dead reference is enough to refuse.
```
def get():
    if False:
        return C
    return 1
class C:
    x = get()
print(C.x)
```
Expected CPython: stdout `1`, exit 0. Actual HEAD (g and d): build fails with the same refusal. Base prints `1` on both builds.

The check should only refuse when the read actually occurs and the name is not already bound; as written it regresses valid non-feature programs.

Unverified: speed (not applicable), wider suite, remaining pre-existing probes.

VERDICT: FIX
1. Refuses a valid program where the class name is already bound (`C = 5` then `class C: x = get()`); expected `5`, actual compile-time refusal on both builds.
2. Refuses a valid program whose function only mentions the class on an unreachable path (`if False: return C`); expected `1`, actual compile-time refusal on both builds.
[cost $0.0000, opencode tokens {"total": 310487, "input": 27606, "output": 2747, "reasoning": 12102, "cache.write": 0, "cache.read": 268032}]
    tool time: bash 7.8 min
        264s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 850 python3 ../tools/par_check.py -j 2 test_
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         33s bash   cd /tmp/probes/pre398 2>/dev/null && for p in q2_exprstmt q3_savedgen q3b_savedgen_next q4_direct m4_class_sha
         19s bash   date && cd /tmp/rprobes && for p in p_if p_for p_trycatch p_prior_value p_prior_class p_unreachable p_alias_ca
         14s bash   cd /tmp/rprobes && for p in q1_indirect q2_exprstmt; do true; done; cat > p_import_binding.py <<'EOF' from mat
          7s bash   cd /tmp/rprobes && cp /tmp/probes/pre398/q1_indirect.py . 2>/dev/null; date && for wt in /home/runner/work/ail
          6s bash   date && cd /tmp/rprobes && for p in p_prior_value p_prior_class p_unreachable; do echo "######## $p BASE"; bas
          6s bash   date; cd /tmp/rprobes && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "#### p_trycatch $(basen

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed as `263ad63`.

- Prior binding now respected (`C = 5`, `None`, `""`, `-7`, lists, unpacking, `for`, containers).
- Dead reads no longer refused (`if False`, `if 0`, `while False`, dead `if`/`else`, ternaries, boolean short-circuit, code after `return`, wrapper chains, unknown conditions, empty loops, class-value expressions).
- Unconditional/live reads still refused by name on both builds.

Probes: 27 in `/tmp/probes/pre398fix`; 24 match CPython, 2 live cases refused by name, 1 (`prior_class`) is the pre-existing `duplicate AIL name: C` on base and HEAD alike.

Tests on final commit: `test_ail_pre398`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 2032075, "input": 87341, "output": 13478, "reasoning": 35704, "cache.write": 0, "cache.read": 1895552}]
    tool time: bash 7.7 min
        251s bash   cd AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre398 test_ail_safetynet t
         76s bash   cd /tmp/probes/pre398fix && for f in *.py; do out=$(bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci 2
         71s bash   cd /tmp/probes/pre398fix && cat > dead_class_ifexp.py <<'EOF' def get():     return C class C:     x = get() i
         58s bash   cd /tmp/probes/pre398fix && for f in *.py; do echo "######## $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/a
          5s bash   mkdir -p /tmp/probes/pre398fix && cat > /tmp/probes/pre398fix/prior_value.py <<'EOF' C = 5 def get():     retu
          0s bash   ls /tmp/base 2>/dev/null && cd /tmp/probes/pre398fix && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; d
          0s bash   cd /tmp/probes/pre398fix && bash ~/tools/cmp.sh prior_class.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
          0s bash   cd AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre398 test_ail_safetynet t

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a compile-time pre-pass `_refuse_class_body_indirect_self_read` in `pyc.py` that parses the source, finds class-attribute values which definitely evaluate a call to a module function that definitely reads the class name, and raises `Unsupported` unless that name was already bound at module scope; plus `test_ail_pre398`, DIFFERENCES/DEVLOG/manifest/CI registration. This matches the report.

**Claims**
- Prior binding respected: verified (`C = 5` → 5; `C = [1,2]` → `[1, 2]`; both builds).
- Dead reads not refused: verified for `if False` and code after `return`; **false** for other dead reads (below).
- Core pre-existing difference addressed: verified (`class C: x = get()` was `<class '__main__.C'>` on base, CPython `NameError`; now refused by name on both builds).
- `prior_class` duplicate-name failure pre-existing: verified on base and HEAD.
- 27 probes: 27 files present; I did not rerun all, so the 24/2/1 split is unverified.
- Tests: `test_ail_pre398` and `test_ail_safetynet` pass (0 failed); `update_manifest.py --check` passes.
- No-feature C unchanged: verified identical `--debug-dir` `program.c` against `/tmp/base`.

**Defects (new false refusals; base matched CPython)**
1. `r_assert_msg.py`: `def get(): assert True, C; return 1` / `class C: x = get()` / `print(C.x)`. Expected `1` (assert message not evaluated), actual both builds refuse "class attribute value in C calls get()…".
2. `r_local_annotation.py`: `def get(): y: C = 5; return y` / `class C: x = get()` / `print(C.x)`. Expected `5` (function-local annotations are not evaluated), actual both builds refuse.
3. `r_generator.py`: `def get(): yield C` / `class C: x = get()` / `print(type(C.x).__name__)`. Expected `generator` (calling a generator does not execute the body), actual both builds refuse.

**Pre-existing:** `prior_class.py` (`duplicate AIL name: C` on base and HEAD). `r_builtin_shadow.py` already printed the wrong value on base; HEAD turns it into a named refusal, so not counted.

**Unverified:** exact worker probe tally; icount speed (runtime C is identical); full suite (not run by instruction).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1332703, "input": 98786, "output": 5035, "reasoning": 19026, "cache.write": 0, "cache.read": 1209856}]
    tool time: bash 2.1 min
         72s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         14s bash   cd /tmp/rprobes && for f in r_builtin_shadow.py r_same_name.py r_dead_if_false.py r_prior_value.py r_live_if_t
         13s bash   cd /tmp/rprobes && cat > r_assert_msg.py <<'EOF' def get():     assert True, C     return 1 class C:     x = g
         10s bash   cd /tmp/rprobes && for f in r_assert_msg.py r_local_annotation.py r_generator.py; do echo "######## $f BASE"; 
          8s bash   cd /tmp/rprobes && cat > r_core_indirect.py <<'EOF' def get():     return C class C:     x = get() print(C.x) 
          3s bash   cd /tmp/rprobes && for f in r_builtin_shadow.py r_same_name.py; do echo "######## $f BASE"; bash ~/tools/cmp.s
          2s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh r_match_shadow.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -20; echo
          1s bash   cd /tmp/rprobes && cat > r_nofeature.py <<'EOF' class Box:     def __init__(self, v):         self.v = v     d

FINAL VERDICT: FIX  2026-10-28T02:07:42Z
