# job job-ex42-10291945  started 2026-10-29T10:51:26Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"aefc9b93-8066-4ee4-adb2-4248e9768277","session_id":"4a380994-91e6-4bc6-b7b9-576bbccc98c3"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"20480c29-f15b-4423-95d1-7fa28a07510b","session_id":"d2cd3e97-e671-472a-8cc4-870bc03634ac"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `684a6a5`.

**Findings**
- 6 Python-syntax `.ail` examples; all build when `use_math.ail` gets its documented `--module math.ail`.
- 14 `.py` examples under `language_examples`; 13 were refused by plain `compile`.
- Chosen: `c_export/geometry.py`, refused with `a decorator on def add`. In an executable, `@export` is an identity check, so it now validates the signature like CPython and removes only the decorator.
- The example now builds on both paths and prints CPython’s `5 3 HÉLLO! [1, 4, 9] 3.0`.

**Probes** (`/tmp/probes/ex42`, both builds)
- 6 matching: `p01`–`p06`.
- 7 refused by name: `p10`–`p16`.
- `geometry.py` itself matches CPython on both builds.

**Tests**
- `test_ail_ex42`, `test_ail_c_export`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 6 modules, 0 failed.
- `tools/update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 7035049, "input": 280414, "output": 14867, "reasoning": 22328, "cache.write": 0, "cache.read": 6717440}]
    tool time: bash 15.1 min
        666s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         63s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/ex42/p*.py; do echo "##### $(basename $p)"; PYTHONP
         47s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_ex42.py && python3 tools/update_manifest.py
         35s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_e
         28s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/exbuild && for f in hello integer_series math stdin_sum su
         16s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgp
         14s bash   cd /home/runner/work/ail-ci/ail-ci && PYTHONPATH=AIL_CURRENT python3 AIL_CURRENT/language_examples/c_export/ge
         12s bash   cd /home/runner/work/ail-ci/ail-ci && cp AIL_CURRENT/language_examples/c_export/geometry.py /tmp/geom_noexport

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds `ail_export.lower_executable`, called from `_load_sources` for non-library Python sources containing `ail_ffi`; it finds top-level `@export`/`@ail_ffi.export` decorators, runs the library `lower()` checks, then blanks only the decorator text. Library and `@extern` paths are untouched.

**Claims checked**
- `geometry.py` builds and matches CPython on both builds: **verified** (`test_ail_ex42` passes, including the example).
- `p01`–`p06` match, `p10`–`p16` refused by name: **verified** (ran all 13 probes).
- `test_ail_ex42`, `test_ail_c_export`, `test_ail_ffi`, `test_ail_safetynet`: **verified**, 4 modules, 0 failed.
- `update_manifest.py --check`: **verified**, exit 0.
- "validates the signature like CPython" and DIFFERENCES' "a signature CPython's decorator rejects is refused by name … instead of being silently accepted": **false** (see defects).
- "13 of 14 `.py` refused", "6 Python-syntax `.ail` build": **unverified** (counts match the file listing, but I did not rebuild all).

**Probes without the feature:** `r08_comment.py` and `p05_no_export.py` produce byte-identical `--debug-dir` C on HEAD vs `/tmp/base`.

**Defects (all on the general path; base general path refused these by name, which was acceptable)**
1. Forward-referenced annotation. Probe `r01_point_after.py`: `@export def weight(p: Point) -> float` before `class Point` is defined. CPython 3.12: `NameError`, exit 1, empty stdout. HEAD general build: exit 0, stdout `6.0`. Base general path: named refusal, exit 3. (Default build was already wrong on base, so that part is pre-existing.)
2. `from __future__ import annotations` + dataclass parameter. Probe `r02_future_dc.py`: CPython raises `TypeError` from `export()` (field types are strings), exit 1, empty stdout; HEAD general build prints `5`, exit 0.
3. Shadowed builtin annotation. Probe `r15_shadow.py`: `int = list` then `@export def f(x: int) -> int`. CPython `TypeError`, exit 1, empty stdout; HEAD general build prints `ok`, exit 0.

Common root cause: validation uses AST annotation names (`lower()`), not CPython's runtime `typing.get_type_hints`, so forward references, future annotations and shadowing are silently accepted instead of reproducing CPython's import-time failure.

**Pre-existing (identical on base)**
- `r12_class_export.py`: `@export` on a class; CPython `TypeError` exit 1, but both base and HEAD builds already compile/run it (exit 0).
- `r04_marker.py`: `getattr(f, '__ail_export__')`; CPython prints `True 2`, AIL fails with `NotImplementedError: getattr() on a 'function' value` (unsupported getattr, not the decorator removal).
- Default-build behaviour of `r01`/`r02`/`r15` (already exit 0 on base).
- `r03` (`exports()`), `r05` (aliased import), `r06` (star import), `r11` (nested `@export`) are named refusals, acceptable.

**Unverified**
- Full refusal list of all 14 `.py` and 6 Python-syntax `.ail` examples.
- `test_ail_files` / `test_ail_corpus_findings3` (not re-run; reviewer scope).
- Speed: front-end-only change, no `icount` run.

VERDICT: FIX
1. `r01_point_after.py`: expected CPython `NameError`, exit 1, no stdout; actual HEAD general build exit 0 with stdout `6.0`.
2. `r02_future_dc.py`: expected CPython `TypeError`, exit 1, no stdout; actual HEAD general build exit 0 with stdout `5`.
3. `r15_shadow.py`: expected CPython `TypeError`, exit 1, no stdout; actual HEAD general build exit 0 with stdout `ok`.
[cost $0.0000, opencode tokens {"total": 1142864, "input": 70702, "output": 6582, "reasoning": 26476, "cache.write": 0, "cache.read": 1039104}]
    tool time: bash 7.2 min
        171s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_ex42 tes
         63s bash   cd /tmp/probes/ex42 && export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in p*.py; do r=$(b
         55s bash   cd /tmp/rprobes && for p in r*.py; do echo "##### $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
         41s bash   cd /tmp/rprobes && export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in r01_point_after.py 
         24s bash   cd /tmp/rprobes && export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in r01_point_after.py r02_future_dc.py r12_c
         23s bash   cd /tmp/rprobes && cat > r13_dc_container.py <<'EOF' from dataclasses import dataclass from ail_ffi import exp
         15s bash   cd /tmp/rprobes && export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in r03_exports.py r05_alias.py r06_star.py r
          9s bash   cd /tmp && rm -rf o2 && mkdir o2 && cd o2 && export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; fo

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Fixed:** the three review defects (forward reference → `NameError`, future-annotated dataclass → `TypeError`, shadowed builtin → `TypeError`) are refused by name on both builds. Also closed the same gap for module bindings the walker missed: walrus targets, `match` captures, and PEP 695 type aliases.

**Probes** (`cmp.sh`, both builds):
- `r01/r02/r15`: refused by name (CPython exits 1). `r03/r05/r06/r11`: named refusals. `r07-r10,r13,r14`: match CPython. `r04` (`getattr` on function) and `r12` (`@export` on class) remain the reviewer’s pre-existing differences.
- `a01-a10`: all named refusals; `a06` differs only in that CPython runs it while AIL refuses by name.
- `p01-p06`: match CPython. `p10-p16`: refused by name. `f02/f03/f05-f08/f10/f12`: refused; `f04/f09/f11`: match.

**Tests on final commit:** `test_ail_ex42`, `test_ail_c_export`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` exit 0.

**Commit:** `078818f` (no push).
[cost $0.0403, opencode tokens {"total": 2481057, "input": 87835, "output": 9123, "reasoning": 24291, "cache.write": 0, "cache.read": 2359808}]
    tool time: bash 33.3 min, edit 0.0 min, read 0.0 min
        588s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_ex42 tes
        585s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_ex42 tes
        508s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_ex42 tes
         56s bash   export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; cd /tmp/rprobes; for p in r*.py; do echo "#####
         50s bash   cd /tmp/probes/ex42 && export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in p01_valid_datac
         46s bash   cd /tmp/rprobes && export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in r*.py; do echo "###
         42s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 1 test_ail_ex42 2>&1 | tail
         28s bash   mkdir -p /tmp/probes/ex42adv && cd /tmp/probes/ex42adv && cat > a01_walrus_shadow.py <<'EOF' from ail_ffi impo

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed the change in this worktree against `work` (`/tmp/base`, base `d94b630`). `date` at start 12:42, tests done 12:49, final 12:52.

**What the change really does:** adds `ail_export.lower_executable` and calls it from `_load_sources` for non-library Python sources containing `ail_ffi`; it validates exported signatures with `lower()` plus an order-aware module-binding walk, then blanks the `@export` decorator text so the functions remain ordinary executable definitions.

**Probes** (`/tmp/rprobes`, `cmp.sh`, `PYTHONPATH=AIL_CURRENT`, both builds, same probes on base):
- `geo.py` (the example): head matches CPython on both builds; base refused it. Good.
- `r01_point_after`, `r02_future_dc`, `r15_shadow`: named refusals on both head builds; `r14_future_scalar`, `r07_void`: match CPython. Report claims verified.
- `n01_plain`, `n02_mentions`: `--debug-dir` `program.c` byte-identical head vs base (non-feature C unchanged).
- `s02_rebound`, `s01_before_import`, `s07_rebind_attr`: **silent differences, see defects**.
- `s03_del`, `n03_del_noexport`: same `KeyError: 'export'` compiler crash in base, so pre-existing (not counted).

**Tests:** `test_ail_ex42` and `test_ail_safetynet` on HEAD: 2 modules, 0 failed (208s). `update_manifest.py --check` exit 0.

**Defects (introduced by this change):**

1. A decorator is stripped even when the name no longer denotes `ail_ffi.export` at that point. Probe `s02_rebound.py`:
   ```
   from ail_ffi import export
   export = lambda fn: None

   @export
   def f(x: int) -> int:
       return x + 1

   print(f(1))
   ```
   Expected (CPython): exit 1, `TypeError: 'NoneType' object is not callable`. Actual (both builds): exit 0, prints `2`. Base refused both builds by name, so this is caused by the change.

2. Same class of defect with use-before-import and module aliasing. `s01_before_import.py` (imports `export` after the `@export` def) and `s07_rebind_attr.py` (`import ail_ffi; ail_ffi = 3; @ail_ffi.export`) both expected CPython exit 1 (`NameError` / `AttributeError`) but both head builds exit 0 printing `2` (`s01` default build was already like this on base; the general build newly diverges).

**Claim check:** "three review defects refused by name" — verified; "walrus/match/type-alias gaps closed" — verified by `test_ail_ex42` passing; "test modules 6, 0 failed" — I re-ran only `test_ail_ex42`+`test_ail_safetynet` (both pass), the other four are unverified; "geometry matches CPython on both builds" — verified; "`--check` exit 0" — verified; `a01-a10`/`p01-p16`/`r04`/`r12` results — not re-run (unverified).

**Unverified:** `test_ail_c_export`, `test_ail_ffi`, `test_ail_files`, `test_ail_corpus_findings3`; the worker's full probe matrix beyond the files left in `/tmp/rprobes`.

VERDICT: FIX, followed by defects 1 and 2 above (silent success where CPython exits 1 due to `export` being used before import, rebound, or reached through a rebound `ail_ffi` module).
[cost $0.0306, opencode tokens {"total": 921287, "input": 95716, "output": 4206, "reasoning": 18805, "cache.write": 0, "cache.read": 802560}]
    tool time: bash 5.8 min, read 0.0 min
        210s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         22s bash   cd /tmp/rprobes; export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in s01_before_import.py s02_rebound.py s03_del
         20s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes cat > s01_before_import.py <<'EOF' @export def f(x: int) -> int:     
         20s bash   cd /tmp/rprobes; export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in s01_before_import.py 
         20s bash   export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; bash ~/tools/cmp.sh /tmp/rprobes/geo.py $PWD 2>
         20s bash   mkdir -p /tmp/rprobes; cp AIL_CURRENT/language_examples/c_export/geometry.py /tmp/rprobes/geo.py; bash ~/tools
         12s bash   cd /tmp/rprobes cat > s06_paren.py <<'EOF' @(     export ) def f(x: int) -> int:     return x + 1  from ail_ff
         11s bash   cd /tmp/rprobes; export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in r01_point_after.py r0

FINAL VERDICT: FIX  2026-10-29T12:51:41Z
