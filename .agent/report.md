# job job-pre403-10281055  started 2026-10-28T01:55:55Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"7db22ddf-0f99-4fc5-8c60-511163f5352e","session_id":"9ba7e23a-6004-4c9e-924b-c6c3cbdcdab5"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"03194976-eca2-43fe-9b6a-b18d1bc00169","session_id":"bc8f4b51-12b1-4508-b13a-87f010c4756a"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. The first still-differing pre-existing item from the pre381 review was the class-body annotation read: `class C: x: C = 1` printed `1`, where CPython raises `NameError`.

Fixed by refusing the construct by name at compile time on both builds, including annotation-only stores, method parameter/return annotations, and reads through subscripts, list items, dict values, arguments and attributes. String annotations, `from __future__ import annotations`, and earlier bindings still match CPython.

Probes (`/tmp/probes`, both builds via `cmp.sh`):
- Refused by name: `p30_ann_self`, `p30_ann_only`, `p30_method_ann`, `p403_ref_subscript`, `p403_ref_listitem`, `p403_ref_dictvalue`, `p403_ref_argument`, `p403_ref_attribute`, `p403_ref_return`, `p403_ref_later`.
- Match CPython: `p30_ann_plain`, `p30_ann_other`, `p30_ann_func`, `p30_ann_future`, `p30_ann_shadow_prior`, `p30_ann_shadow_local`, `p403_match_string`, `p403_match_listvalue`, `p403_match_empty_neg`.

Tests: `test_ail_pre403 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4 modules, 0 failed, 299s. `update_manifest.py --check` exit 0. Commit `82df10d`. Tree clean except untracked `.agent/pipeline.md`. Instruction counts and the wider suite were not run.
[cost $0.0000, opencode tokens {"total": 5117574, "input": 120971, "output": 13266, "reasoning": 27561, "cache.write": 0, "cache.read": 4955776}]
    tool time: bash 8.3 min
        300s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre403 test_ail_safetynet test_ail_files test_ai
         33s bash   cd /tmp/probes && for p in p30_*.py p403_*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ai
         30s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre403.py') s=p.read_text(encoding='utf
         30s bash   grep -rn "def _future_annotations\|_future_annotations(" AIL_CURRENT | head; cd AIL_CURRENT && python3 ../tool
         26s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre403 2>&1 | tail -30
         21s bash   for p in /tmp/probes/p30_*.py; do echo "=== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E 'c
         17s bash   cat > /tmp/probes/p30_method_ann.py <<'EOF' class C:     def m(self, x: C):         return x print("ok") EOF c
         17s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p30_ann_self.py <<'EOF' class C:     x: C = 1 print(C.x) EOF cat > /

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds `_check_class_body_annotations` to `ail_chatgpt._load_sources`: for Python syntax, any class-body annotation (attribute, method arg/return) that syntactically mentions the class's own name is refused by name unless *some* earlier-line binding of that name exists anywhere in the file; plus test module, manifest, DEVLOG/DIFFERENCES entry.

**Probes** (`bash ~/tools/cmp.sh`, HEAD and `/tmp/base`):

| probe | CPython | base | HEAD |
|---|---|---|---|
| `rp1_direct` (`class C: x: C = 1`) | NameError exit 1 | prints 1 (DIFF) | refused by name |
| `rp2_builtin` (`class list: x: list = 1`) | 1 | refused (builtin-shadow check) | refused |
| `rp3_unrelated_func` (local `C` in a function, then `class C: x: C = 1`) | NameError | prints 1 | prints 1 |
| `rp4_if_false` (`if False: C = 5` then same) | NameError | prints 1 | prints 1 |
| `rp5_comprehension` (below) | 1 | 1 (match) | **refused** |
| `rp6_lambda` (below) | 1 | 1 (match) | **refused** |
| `rp7_plain` (no feature) | 1 2 | match | match; `--debug-dir` `program.c` byte-identical to base |

**Defects (new, caused by this change):**

1. Valid comprehension-shadow program now rejected.
```
class C:
    x: [C for C in range(3)][0] = 1
print(C.x)
```
Expected (CPython, and base on both builds): stdout `1`, exit 0. Actual HEAD (both builds): `p.ail:2:9: a class body annotation reads the class name C before it is bound: ...` exit 2. The comprehension target `C` is mistaken for a read of the class name.

2. Valid lambda-parameter-shadow program now rejected.
```
class C:
    x: (lambda C: C)(7) = 1
print(C.x)
```
Expected (CPython, and base on both builds): stdout `1`, exit 0. Actual HEAD: `p.ail:2:19: a class body annotation reads the class name C before it is bound: ...` exit 2.

**Pre-existing (identical on base, not blocking).** `rp3`/`rp4` print `1` where CPython raises `NameError` on both base and HEAD: the "earlier binding" test is not scope-aware, so an unrelated function-local or a never-executed `if False:` binding suppresses the refusal and the original difference survives.

**Report claims.**
- Direct case, annotation-only, method param/return, subscript/list/dict/argument/attribute refusal: verified (HEAD probes + `test_ail_pre403` pass).
- String annotation / `future` / a visible earlier binding match CPython: verified for the tested cases; the general claim that "an earlier binding ... match[es]" is false for `rp3`/`rp4`.
- Tests (4 modules, 0 failed): I reran `test_ail_pre403` + `test_ail_safetynet` on HEAD: 2 modules, 0 failed, 104s. `test_ail_files`/`test_ail_corpus_findings3` not rerun.
- Manifest `--check` exit 0, tree clean except untracked `.agent/pipeline.md`: verified.
- `tools/ci_shards.json` weight 38.8: verified.
- Instruction counts / wider suite: not run (change is front-end only, not hot code).

VERDICT: FIX
1. `rp5_comprehension` — refusal of a program CPython runs: expected `1` exit 0, got named compile refusal (both builds); base matched CPython.
2. `rp6_lambda` — refusal of a program CPython runs: expected `1` exit 0, got named compile refusal (both builds); base matched CPython.
[cost $0.0000, opencode tokens {"total": 432201, "input": 30918, "output": 3238, "reasoning": 13405, "cache.write": 0, "cache.read": 384640}]
    tool time: bash 2.6 min
        105s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre403 test_ail_safetynet 2>&1 | tail -15
         23s bash   date; cd /tmp/rprobes && for p in rp1_direct.py rp2_builtin.py rp3_unrelated_func.py rp4_if_false.py rp5_compr
         11s bash   date; cd /tmp/rprobes && for p in rp*.py; do echo "########## HEAD $p"; bash ~/tools/cmp.sh "$p" /home/runner/
          7s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh rp3_unrelated_func.py /home/runner/work/ail-ci/ail-ci 2>&1 | sed -n '1,
          6s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh rp2_builtin.py /tmp/base 2>&1 | tail -20; echo ======; bash ~/tools/cmp
          5s bash   cd /tmp && rm -rf dbg_h dbg_b && mkdir dbg_h dbg_b && cp /tmp/rprobes/rp7_plain.py dbg_h/p.py && cp /tmp/rprob
          0s bash   mkdir -p /tmp/base && git worktree add /tmp/base work 2>&1 | tail -5; ls /tmp/base | head
          0s bash   cd /tmp/rprobes; for p in rp3_unrelated_func rp4_if_false rp5_comprehension rp6_lambda; do echo "== $p"; pytho

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `498d1ed`.

- Defect 1 (`rp5_comprehension`) and defect 2 (`rp6_lambda`) now match CPython (stdout `1`, exit 0) on both builds. Added `_annotation_reads`, which honors lambda-parameter and comprehension-target scopes while still refusing reads in the first comprehension iterable and lambda defaults.
- Probes in `/tmp/probes403` via `cmp.sh`: `rp5_comprehension`, `rp6_lambda`, `nested_comprehension`, `dict_comprehension`, `set_comprehension`, `genexp`, `lambda_nested`, `comprehension_two_targets`, `prior_binding_comprehension` match CPython; `comprehension_iterable`, `lambda_default`, `lambda_param_shadowing_default` refused by name (CPython exit 1). 12 probes, 0 unclassified DIFF.
- Added matching/refusal cases to `test_ail_pre403.py`; DEVLOG, DIFFERENCES, MANIFEST updated.
- Final commit tests: `test_ail_pre403 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 4 modules, 0 failed, 247s. `update_manifest.py --check` exit 0; tree clean except untracked `.agent/pipeline.md`.
- Not verified: instruction counts / wider suite (not run). Pre-existing `rp3`/`rp4` scope-unaware earlier-binding behaviour remains unchanged.
[cost $0.0000, opencode tokens {"total": 406343, "input": 23926, "output": 4432, "reasoning": 3841, "cache.write": 0, "cache.read": 374144}]
    tool time: bash 5.5 min, edit 0.0 min
        249s bash   cd AIL_CURRENT && date; python3 ../tools/par_check.py -j 2 test_ail_pre403 test_ail_safetynet test_ail_files t
         51s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre403 2>&1 | tail -15
         31s bash   cd /tmp/probes403 && for p in *.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci
          0s bash   python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.read_text() entry = """## 2026-10-28 -- 
          0s bash   git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/ail_chatgpt.py AIL_CURRENT/test_ail_pre403.py DEVLOG.md DIFFEREN
          0s bash   cd AIL_CURRENT && date; python3 ../tools/par_check.py -j 2 test_ail_pre403 2>&1 | tail -15
          0s bash   python3 tools/update_manifest.py --check; echo check=$?; git status --short; git log --oneline -3
          0s bash   pwd; git status; git log --oneline -8; ls

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** `ail_chatgpt.py` gains `_check_class_body_annotations`, run on every `python` source before translation. It refuses, by name, a class-body annotation (attr, method arg/return) that reads the class name unless some node with a smaller `lineno` binds that name. `_annotation_reads` adds lambda/comprehension shadow scopes. Tests, DIFFERENCES/DEVLOG, MANIFEST and shard entry are added.

**Report claims checked.**
- rp5/rp6 now match CPython on both builds: verified (stdout `1`, exit 0).
- 12 probes in `/tmp/probes403`: verified all 12 — 9 match, 3 refused by name, 0 unclassified DIFF.
- Comprehension/lambda scoping: verified (target/parameter shadow matches; first iterable/default refused).
- `test_ail_pre403 test_ail_safetynet`: 2 modules, 0 failed. Did not rerun files/corpus. `update_manifest.py --check` exit 0; tree clean except `.agent/pipeline.md`: verified.
- "Earlier module or class-body binding keeps CPython's result" and "a plain/type annotation … keep CPython's result": **false** for same-line bindings and for a PEP 695 type parameter named like the class.
- rp3/rp4 scope-unaware behaviour: verified identical on base.

**Defects.**
1. A PEP 695 class type parameter that shares the class name is not treated as a binding (multi-line, normal program):
```python
class C[C]:
    x: C = 1
print(C.x)
```
CPython 3.12 stdin: stdout `1`, exit 0. HEAD: compile refusal on both builds, `p.ail:2:8: a class body annotation reads the class name C ... raises NameError`. Base: stdout `1`, exit 0. New regression.
2. A binding earlier on the *same source line* is ignored because only `lineno < read.lineno` counts:
```python
class C:
    C = 5; x: C = 1
print(C.x)
```
Expected stdout `1`, exit 0; actual compile refusal at `2:15`.
```python
class C:
    x: ((C := 1), C)[1] = 5
print(C.x)
```
Expected stdout `5`, exit 0; actual compile refusal at `2:19`. Base matches CPython for both.

**Pre-existing (identical on base).** `rp3_unrelated_func`, `rp4_if_false` (an earlier binding in an unrelated scope suppresses refusal; still prints `1` where CPython raises); classes shadowing builtins (base already refuses for another reason); nested class / class-body `for` / `type` statement refused as "not in the subset" (`p_nested_class`, `p_loop_target`, `p_typealias`).

**No-change check.** `--debug-dir` build of a program whose annotation does not read the class name: `program.c` byte-identical between base and HEAD (only report paths differ).

**Unverified.** Full suite; worker's `test_ail_files`/`test_ail_corpus_findings3` runs. Instruction counts: not applicable (front-end only).

VERDICT: FIX

1. PEP 695 type-parameter binding ignored: `class C[C]: x: C = 1` + `print(C.x)` must print `1` (exit 0); HEAD refuses at compile time.
2. Same-line ordering not modeled: `class C:\n    C = 5; x: C = 1` must print `1`, and `class C:\n    x: ((C := 1), C)[1] = 5` must print `5`; HEAD refuses both at compile time.
[cost $0.0000, opencode tokens {"total": 670951, "input": 61332, "output": 4033, "reasoning": 26386, "cache.write": 0, "cache.read": 579200}]
    tool time: bash 3.9 min
        110s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre403 t
         31s bash   cd /tmp/probes403 && for p in *.py; do echo "########## $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci
         28s bash   cd /tmp/rprobes && for p in p_basic p_semicolon p_walrus p_comp_shadow p_lambda_shadow p_comp_iterable p_lambd
         20s bash   cd /tmp/rprobes && for p in p_semicolon p_walrus p_nested_class p_loop_target p_comp_shadow p_lambda_shadow; d
         14s bash   cd /tmp/rprobes && python3 p_semicolon.py; echo "exit=$?"; python3 p_walrus.py; echo "exit=$?"; echo ---; ls /
         11s bash   cd /tmp/rprobes && cat > p_typeparam.py <<'EOF' class C[C]:     x: C = 1 print(C.x) EOF cat > p_typealias.py <
          6s bash   cd /tmp/rprobes && cat > p_builtin_shadow.py <<'EOF' class list:     x: list = [1] print(list.x) EOF cat > p_b
          6s bash   cd /tmp/rprobes && rm -rf /tmp/dh /tmp/db && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURREN

FINAL VERDICT: FIX  2026-10-28T02:31:44Z
