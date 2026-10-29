# job job-ex25-10290857  started 2026-10-29T00:03:06Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"3297ff81-c7ff-4398-b0c1-ce93ef4efc3e","session_id":"aa05047b-0054-47af-ba77-4fb193d6dae4"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"ec8285cb-9a4b-4182-8f39-e9d295b261c9","session_id":"5b3f42bd-c26e-4168-8f4f-e0ad28adcfd9"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Job ex25 complete — commits on `job-ex25-10290857`:** `0caadcc`, `ccdb76c` (no push).

**Python-syntax examples in `AIL_CURRENT/language_examples` (7)**
- Built: `hello.ail`, `integer_series.ail`, `stdin_sum.ail`, `sum.ail`
- Refused: `math.ail` (`the first parameter must be the sequence read from the file`), `use_math.ail` without `--module math.ail` (`the name 'sum_to' is not a known function/class/builtin`), `c_export/geometry.py` (`not in the subset: the decorator on def add ...`)
- Chose `geometry.py`: the only refused standalone program with a CPython oracle. It now builds on both builds and matches CPython: `5 3 HÉLLO! [1, 4, 9] 3.0`, exit 0.

**Change**
- `@export`, `@export()`, an alias, and `@ail_ffi.export` are no-ops on top-level functions in normal builds (CPython returns the decorated function unchanged; `--lib` still lowers separately).
- `@extern` lowering keeps the `export` import only when an export decorator is actually used.
- Invalid export signatures are refused by name via `ail_export.lower`; `__ail_export__` introspection is refused by name.

**Probes (`/tmp/probes/ex25`, both builds via `cmp.sh`)**
- Match CPython: `p01_basic`, `p02_call_and_alias`, `p03_module_attribute`, `p04_routes` (argument/list/dict), `p05_dataclass`, `p06_import_only`, `p07_no_feature`
- Refused by name: `p04b_attribute` (pre-existing instance `.fn()` limit), `p08_invalid_list_str`, `p09_invalid_default`, `p10_invalid_missing_return`, `p11_second_decorator`, `p12_method`, `p13_export_attribute`, `p14_export_registry`, `p15_mixed_extern`

**Verification on final commit `ccdb76c`**
- `test_ail_ex25`, `test_ail_c_export`, `test_ail_ffi`, `test_ail_python_syntax`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **8 modules, 0 failed** (707 s).
- `tools/update_manifest.py --check` and `tools/ci_shards.py --check` pass.
- `.agent/pipeline.md` remains untracked (pipeline artifact); nothing else uncommitted.
[cost $0.0000, opencode tokens {"total": 9848329, "input": 168878, "output": 21211, "reasoning": 41216, "cache.write": 0, "cache.read": 9617024}]
    tool time: bash 50.3 min, edit 0.0 min
        851s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_ffi test_ail_pyt
        708s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_ffi test_ail_pyt
        697s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_ffi test_ail_pyt
        387s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_python_syntax te
         72s bash   git add AIL_CURRENT/ail_ffi_lower.py && python3 tools/update_manifest.py && cd AIL_CURRENT && python3 ../tools
         44s bash   mkdir -p /tmp/probes/ex25 cat > /tmp/probes/ex25/p01_basic.py <<'PY' from ail_ffi import export  @export def a
         41s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ex25 2>&1 | tail -40
         40s bash   for p in p01_basic p02_call_and_alias p03_module_attribute p04_routes p05_dataclass p06_import_only p07_no_fea

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: ex25 `@export` support

**What the change actually does:** adds a normal-build path (`ail_chatgpt.py`) that treats `ail_ffi.export` decorators as no-ops, refuses `__ail_export__` reads, and runs `ail_export.lower` as a validator whenever a source merely contains `@` + `export` + `ail_ffi`; `ail_ffi_lower.py` now preserves the `export` import on `@extern` lowering; `pyboxed2.py` skips the decorator check; new `test_ail_ex25.py`.

**Defect found (regression, both builds):** the validation gate is a substring test, so an unrelated `@extern` program that contains the word "export" is now refused by `ail_export.lower`.

Probe `/tmp/rprobes/r03_extern_explicit_wordexport.py`:
```python
from ail_ffi import extern, c_char_p, c_size_t

@extern(lib="c", header="string.h", symbol="strlen")
def c_strlen(s: c_char_p) -> c_size_t: ...

def main():
    print("export", c_strlen("abc"))

main()
```
- Base: both builds exit 0, output `export 3` (matches CPython).
- HEAD: both builds fail with `C libraries use only \`export\` from ail_ffi, not extern`.
Same with `from ail_ffi import *` (`r02`): HEAD fails with `... not *`; base matches CPython. This program uses no `@export` at all, so its C must be unchanged.

**Claims:**
- geometry builds/matches CPython: verified (`r01`, both builds, exit 0).
- `@export`, `@export()`, alias, `@ail_ffi.export`, bool/bytes/list/None paths: verified (`r01`, `r05`, `r07`, `r09`; test_ail_ex25 passes).
- C unchanged for `@extern`-only program: verified (`r04` `--debug-dir` entry.c identical base vs HEAD, same cwd).
- invalid signatures / `__ail_export__` read refused by name: verified (`test_ail_ex25`; `r06` read-refusal). Note `r06` also refuses a *write* to `__ail_export__` calling it a "reading", but base refused that file too, so not a regression.
- 8 modules 0 failed: only `test_ail_ex25` + `test_ail_safetynet` re-run (`-j 2`, 151s, 0 failed); other 6 unverified.
- `update_manifest.py --check`, `ci_shards.py --check`, commit trailers: verified.
- `math.ail`/`use_math.ail` refusal messages: match report.

**Pre-existing:** none blocking; `r06` write-refusal and `r08` (`f = export(f)` call form) are refusals that base also cannot build.

**Unverified:** worker's p01–p15 probes individually; the 6 other test modules; speed (no hot-path change).

VERDICT: FIX
1. Over-broad `uses_export` substring gate: `/tmp/rprobes/r03_extern_explicit_wordexport.py` (and `r02_extern_star_wordexport.py`) builds and prints `export 3` on the base, but HEAD refuses both builds with `C libraries use only \`export\` from ail_ffi, not extern` / `not *`. Restrict detection to an actual `@export`/`export(...)` use of an `ail_ffi` import, and don't surface `ail_export.lower` errors for files that have no export function.
[cost $0.0000, opencode tokens {"total": 966728, "input": 54103, "output": 5433, "reasoning": 18360, "cache.write": 0, "cache.read": 888832}]
    tool time: bash 4.0 min
        153s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         25s bash   cd /tmp/rprobes && cat > r05_export_contracts.py <<'PY' from ail_ffi import export  @export def flag(v: bool) 
         18s bash   cd /tmp/rprobes && rm -rf ex && mkdir ex && for f in math.ail use_math.ail c_export/geometry.py; do cp /home/r
         15s bash   cd /tmp/rprobes; for f in r02_extern_star_wordexport r03_extern_explicit_wordexport r04_extern_plain; do echo 
          6s bash   cd /tmp/rprobes && cat > r01_geometry.py <<'PY' from dataclasses import dataclass from ail_ffi import export  
          5s bash   tail -5 /tmp/rprobes/same/log; cd /tmp/rprobes && rm -rf same dbg_h dbg_b && mkdir same && cp r04_extern_plain
          5s bash   cd /tmp/rprobes && rm -rf dbg_h dbg_b && mkdir -p hsrc bsrc && cp r04_extern_plain.py hsrc/p.ail && cp r04_ext
          4s bash   cd /tmp/rprobes && cat > r08_export_call_form.py <<'PY' from ail_ffi import export  def f(x: int) -> int:     

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `7759dac`.

**Change:** `ail_export.uses_export` no longer substring-matches; it parses the file and detects only real `@export` / `@export()` / `export(...)` uses of an `ail_ffi` import (direct, aliased, module-attribute, star). Unrelated `@extern` files with the word "export" build again with unchanged C. Added an actual `@extern` regression case to `test_ail_ex25.py`.

**Probes** (`/tmp/probes/ex25fix`, both builds via `cmp.sh`):
- Match CPython: `g01_extern_comment_word`, `g02_extern_string_word`, `g03_star_word`, `g04_no_ffi_word`, `g05_import_unused`, `g06_alias_values` (negative/empty/bytes/lists/dataclass via argument, list item, dict value, attribute), `g07_module_attr`.
- Refused by name: `g08_alias_invalid` (`unsupported type list[str]`), `g09_attr_invalid` (`reading __ail_export__`).
- Re-ran reviewer probes `r01`–`r09`: r01–r05, r07–r09 match CPython on both builds; r06/r08 remain pre-existing refusals.

**Final-commit tests** (`-j 2`, 439s): `test_ail_ex25`, `test_ail_c_export`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0156, opencode tokens {"total": 1109115, "input": 36994, "output": 6064, "reasoning": 5321, "cache.write": 0, "cache.read": 1060736}]
    tool time: bash 15.0 min, edit 0.0 min
        441s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_ffi test_ail_safetyne
        332s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_ex25 test_ail_c_export test_ail_ffi test_ail_safetyne
         39s bash   for f in /tmp/rprobes/r0*.py; do echo "=== $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E '^(cpython|buil
         38s bash   export PYTHONPATH="$PWD/AIL_CURRENT${PYTHONPATH:+:$PYTHONPATH}"; for f in /tmp/rprobes/r0*.py; do echo "=== $(
         31s bash   export PYTHONPATH="$PWD/AIL_CURRENT${PYTHONPATH:+:$PYTHONPATH}"; for f in /tmp/probes/ex25fix/g*.py; do echo "
         17s bash   cd /tmp/probes/ex25fix && python3 - <<'PY' from pathlib import Path p=Path('g06_alias_values.py') s=p.read_tex
          0s bash   git show --stat HEAD~2..HEAD; echo ---; git show --stat 73fd670; echo ---DEVLOG; find AIL_CURRENT -maxdepth 2 
          0s bash   python3 tools/update_manifest.py --check && python3 tools/ci_shards.py --check && git status --short

## review 1 skipped: only 34 minutes left

FINAL VERDICT: FIX  2026-10-29T04:24:01Z
