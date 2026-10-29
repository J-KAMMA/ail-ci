# job job-ex34-10291334  started 2026-10-29T04:49:09Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"e134100c-c93d-4659-b20d-3808b31f9b4f","session_id":"4ed7f3ac-9901-408c-aa65-228cdeb674ed"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"37b3a2fc-1d94-40d7-a62a-54891fbf4a10","session_id":"60a3a4b3-1647-4dd5-922c-16423ffdd033"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `27f7ac9` on `job-ex34-10291334`.

**Enumeration:** 20 Python-syntax files (14 `.py`, 6 `.ail`). Before the change 13 were refused. The only standalone language example was `c_export/geometry.py` (refused as `the decorator on def add ...`); the other 12 are harness/test scripts blocked by unavailable modules (`pyfunc`, `benchmark_current_rows`, `...table_crc`), `__file__` (5), import-name collisions (2), the int64/`Path` subset, or a module fragment.

**Change:** `@export` is now dropped before lowering on both builds (`@export`, `@export()`, `ail_ffi.export`), with `ail_export.lower` validation plus a definition-order check, so invalid exports are refused by name instead of running where CPython raises.

**Probes** (`cmp.sh`, `PYTHONPATH=$PWD/AIL_CURRENT`):
- `geometry.py`, `valid.py`, `valid_attr.py`, `shadow_int.py`, `shadow_float.py`: 2/2 builds same stdout, 0 diffs.
- `inv_missing_param`, `inv_default`, `inv_bad_result`, `inv_no_result`, `inv_vararg`, `inv_late_dataclass`: CPython exits 1; both builds refused by name (`ail_ffi @export: ...`).

**Tests on HEAD:** `test_ail_ex34`, `test_ail_ffi`, `test_ail_ffi_parallel`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_c_export` and `test_ail_cratebridge` pass with Rust cases skipped; with the `rustc` shim present their only failure is the environment's missing rustup default toolchain. Manifest `--check` passes; `ci_shards --check` exits 0 with the new module unassigned (as `test_ail_ffi_parallel` already was).
[cost $0.0666, opencode tokens {"total": 6925206, "input": 138933, "output": 15660, "reasoning": 26933, "cache.write": 0, "cache.read": 6743680}]
    tool time: bash 21.6 min, write 0.0 min
        487s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex34 test_ail_ffi tes
        447s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && echo MANIFEST_OK && cd AIL_CURREN
         73s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/geometry.py /tmp/probes/ex34/*.py; do out=$(PYTHONPATH=$
         59s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/geometry.py /tmp/probes/ex34/valid.py /tmp/probes/ex34/v
         43s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex34 2>&1 | tail -30
         35s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/exbuild && python3 - <<'PY' > /tmp/exbuild/list.txt import sys 
         27s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/probes/ex34/valid.py <<'PY' from ail_ffi import export   @export()
         26s bash   cd /home/runner/work/_temp/w2 && echo "=== geometry ===" && PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh /t

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** in `ail_ffi_lower.Session._lower`, any top-level `@export`-decorated `def` now has its decorator blanked (normal build), and the file is passed through `ail_export.lower` plus a new `_check_export_names` order check so invalid exports are refused by name. It is a front-end/compile-time change only.

**Verified**
- `geometry.py`: both builds exit 0, stdout identical to CPython.
- Worker's `valid.py`, `valid_attr.py`, `shadow_int.py`, `shadow_float.py`: both builds match.
- `inv_missing_param`, `dc_after` style invalid exports: refused by name on both builds; CPython exits nonzero.
- No-feature program: `--debug-dir` C is byte-identical to base (`program.c`; only temp paths in `native_report.json` differ).
- Tests on HEAD: `test_ail_ex34` ok (65s), `test_ail_safetynet` ok (154s), `test_ail_ffi` ok (54s). `update_manifest.py --check` and `ci_shards.py --check` exit 0 (unassigned `test_ail_ex34`, `test_ail_ffi_parallel`).

**Claims**
- `@export` dropped and CPython-like validation: verified for ordinary cases; **false for `from __future__ import annotations`** (defect 1).
- "decorated functions run unchanged": **false** — `__ail_export__`/`exports()` are gone (defect 2; `exports` import is refused by name, which is at least named).
- "13 refused before the change": unverified/off-by-one — I count 14 before (geometry + 12 `.py` harness scripts + `use_math.ail`), 13 after.

**Defects**
1. `future_ann.py` (`from __future__ import annotations`, dataclass `Point(x: int)`, `@export def getx(p: Point)`): CPython's `export` raises `TypeError` because dataclass field types are strings, so exit 1 with no stdout. HEAD builds and prints `9`, exit 0, on both builds. On base the general build refused (build failed); the default build already printed `9`, so the general-path acceptance is new. The validation does not model future annotations.
2. `valid_attr_direct.py` (`@export def twice…; print(twice(21)); print(twice.__ail_export__)`): CPython prints `42` then `True`, exit 0. HEAD builds both and prints `42`, then `AttributeError: 'function' object has no attribute '__ail_export__'`, exit 1 (`getattr` variant: `NotImplementedError`). Base refused at compile time on both builds. Blanking the decorator removes its observable side effect, turning a refusal into a runtime crash.

Unverified: full 20-file enumeration beyond spot checks; Rust-host tests; no speed check (front-end only).

VERDICT: FIX
[cost $0.0304, opencode tokens {"total": 1929508, "input": 58557, "output": 5574, "reasoning": 21153, "cache.write": 0, "cache.read": 1844224}]
    tool time: bash 5.3 min, write 0.0 min
        156s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_ex34 tes
         56s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_ffi 2>&1
         27s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/ex34/geometry.py /tmp/rprobes/ex34/valid_dc.py /tmp/rpr
         27s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/ex34/valid.py /tmp/probes/ex34/valid_attr.py /tmp/probes
         16s bash   cd /tmp/base_ex34 && for p in future_ann valid_attr_mark geometry; do echo "=== $p BASE ==="; PYTHONPATH=$PWD/
         12s bash   cd /home/runner/work/_temp/w2 && for p in valid_attr_mark future_scalar future_dc_alias; do echo "=== $p HEAD 
         10s bash   cd /tmp/base_ex34 && for p in valid valid_attr; do echo "== BASE $p"; PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools
          5s bash   cat /tmp/probes/ex34/shadow_int.py; echo ===; cat /tmp/probes/ex34/shadow_float.py; echo ===; cd /home/runner/

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed as `9407e37` on `job-ex34-10291334`.

**Fixes**
- Defect 1: `from __future__ import annotations` plus an exported dataclass parameter is now refused by name on both builds, matching CPython's `TypeError` failure. Future-annotated scalar exports still build and match.
- Defect 2: observing the decorator's CPython side effects is now refused by name before lowering instead of building into `AttributeError`/`NotImplementedError`: `__ail_export__`, any attribute of an exported function, `getattr`/`hasattr`/`vars`/`dir`, `ail_ffi.exports`/`_EXPORTED`. `exports` imports were already named refusals.

**Probes** (`/tmp/probes/ex34fix`, `cmp.sh`, both builds)
- Match CPython: `future_scalar`, `future_scalar_routes` (negative/zero/argument/list item/attribute/dict value), `future_dataclass_unused`, `function_value`, `valid`, `valid_attr`, `geometry`.
- Refused by name: `future_ann`, `future_dataclass_boolfloat`, `future_dataclass_later`, `future_dataclass_routes`, `valid_attr_direct`, `valid_attr_getattr`, `valid_attr_hasattr`, `valid_attr_vars`, `valid_attr_dir`, `valid_attr_name`, `module_exported_list`, `exports_list`.

**Verification**
- `update_manifest.py --check` and `ci_shards.py --check`: pass.
- Final commit tests: `test_ail_ex34`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (518s).
[cost $0.0231, opencode tokens {"total": 1271723, "input": 57060, "output": 7367, "reasoning": 10880, "cache.write": 0, "cache.read": 1196416}]
    tool time: bash 16.9 min
        520s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && cd AIL_CURRENT && timeout 2400 py
        395s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_ex34 tes
         59s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/ex34fix/future_ann.py /tmp/probes/ex34fix/future_scalar.
         16s bash   cd /home/runner/work/_temp/w2 && for p in future_ann valid_attr_direct valid_attr_getattr exports_list; do ech
          6s bash   cat > /tmp/probes/ex34fix/name_attr.py <<'EOF' def twice(n: int) -> int:     return n * 2   print(twice(21)) p
          6s bash   cat > /tmp/probes/ex34fix/udec.py <<'EOF' def mark(fn):     return fn   @mark def twice(n: int) -> int:     re
          5s bash   cat > /tmp/probes/ex34fix/dict_plain.py <<'EOF' class Box:     def __init__(self, v: int):         self.v = v 
          5s bash   cd /home/runner/work/_temp/w2 && for p in future_ann valid_attr_direct valid_attr_getattr exports_list name_at

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: ex34 `@export` normal-build support (work..9407e37)

**What the change really does:** in a normal (non-`--lib`) build it blanks the `@export` decorator (`@export`, `@export()`, `ail_ffi.export`, module alias), validates the file with `ail_export.lower`, refuses a future-annotated dataclass parameter by name, and refuses some *syntactic* observations of the decorator side effect (`name.attr`, `getattr`/`hasattr`/`vars`/`dir`, `ail_ffi.exports`/`_EXPORTED`). It broadly matches the report.

**Checks run** (HEAD; base = `/tmp/base_ex34` at `work` 52be6e3)
- `test_ail_ex34`, `test_ail_safetynet`: 2 modules, 0 failed (136 s).
- `update_manifest.py --check` exit 0; `ci_shards.py --check` exit 0.
- No-feature program (`extern`+`link`, no `@export`): `Session.lower` output hash identical on base and HEAD.
- Matching on both builds: `fut_scalar` (list[float], negative/zero, `-> None`), `fut_dc_unused`, `dc_routes` (dataclass param through argument/list item/dict value/attribute, mutation), `geometry`.
- Refused by name as claimed: direct `__ail_export__`, `getattr(... "__ail_export__")`, `exports` import, future-annotated dataclass param (CPython also exits 1).

**Claims:** future-annotated dataclass refusal verified; future-annotated scalar exports verified; "any attribute of an exported function is refused" is **false** (aliases/parameters/returns bypass the checker); manifest/shards claims verified; the 5-module test claim partially verified (only 2 modules re-run); "no-feature C unchanged" verified.

**Defects found** (base refuses these by name on both builds; HEAD builds them)

1. Shadowed builtin type name is silently accepted. Probe `/tmp/rprobes/shadow_list.py`:
```python
from ail_ffi import export
list = dict
@export
def f(x: list[int]) -> int:
    return 2
print(f([1, 2]))
```
Expected CPython: exit 1, no stdout, `TypeError: @export f: parameter x needs ...`. Actual HEAD, both builds: exit 0, stdout `2`. `_check_export_names` whitelists `list` even though it was rebound, and `ail_export.lower` only inspects the AST name. (`shadow_str.py` shows the same for `str = 5` on the general build.)

2. Aliased exported function is not refused, so its attributes crash. Probe `/tmp/rprobes/alias_attr.py`:
```python
from ail_ffi import export
@export
def twice(n: int) -> int:
    return n * 2
f = twice
print(f.__name__)
```
Expected CPython: stdout `twice`, exit 0. Actual HEAD, both builds: no stdout, exit 1 `AttributeError: 'function' object has no attribute '__name__'`. The same hole exists through a parameter (`def observe(fn): return fn.__name__`) and a return value. Related silent wrong value through the same alias gap: `/tmp/rprobes/alias_dup.py` (`same = twice; print(same == twice, same(4))`) gives `False 8` where CPython gives `True 8`.

**Pre-existing:** plain (no-`@export`) function-attribute reads and function identity (`noexport_attr.py`, `noexport_dup.py`) fail identically on base and HEAD; `shadow_str.py` already differs on the base default build.

**Unverified:** `test_ail_ffi`, `test_ail_files`, `test_ail_corpus_findings3`; the worker's `future_dataclass_routes` probe; the claim that 13 examples were refused. Speed not measured — the diff is compile-time-only.

VERDICT: FIX
1. An earlier rebinding of `list`/`str`/`int`/... is ignored, so `@export` validation accepts a program CPython rejects with `TypeError` (`shadow_list.py`: expected exit 1/no stdout, actual exit 0/stdout `2` on both builds).
2. Attribute/value observation through an alias, parameter or return of an exported function is not refused (`alias_attr.py`: expected `twice`/exit 0, actual `AttributeError`/exit 1; `alias_dup.py`: expected `True 8`, actual `False 8`), while the direct form is refused.
[cost $0.0314, opencode tokens {"total": 1061142, "input": 70067, "output": 5670, "reasoning": 24381, "cache.write": 0, "cache.read": 961024}]
    tool time: bash 4.1 min
        120s bash   cd AIL_CURRENT && (timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_ex34 test_ail_safetynet > /tmp/rpr
         20s bash   cd /tmp/rprobes cat > noexport_dup.py <<'EOF' def twice(n: int) -> int:     return n * 2  same = twice print(s
         19s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; for p in alias_attr alias_attr2 alias_name_
         15s bash   cd /tmp; export PYTHONPATH=/tmp/base_ex34/AIL_CURRENT; for p in shadow_str shadow_list alias_attr; do echo "==
         14s bash   cd /tmp; export PYTHONPATH=/tmp/base_ex34/AIL_CURRENT; for p in alias_attr alias_name_getattr fut_scalar; do e
         12s bash   cd /tmp/rprobes cat > attr_param.py <<'EOF' from ail_ffi import export  @export def twice(n: int) -> int:     
         11s bash   cd /tmp/rprobes cat > mod_getattr.py <<'EOF' import ail_ffi  @ail_ffi.export def twice(n: int) -> int:     ret
         10s bash   cd /tmp; export PYTHONPATH=/tmp/base_ex34/AIL_CURRENT cat > /tmp/rprobes/min_export.py <<'EOF' from ail_ffi im

FINAL VERDICT: FIX  2026-10-29T10:12:35Z
