# job job-ex41-10291929  started 2026-10-29T10:55:03Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"211820f6-65a6-4fcd-9692-d234497f8c07","session_id":"571d3386-bbdf-4304-bfb9-90a4a47925c3"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"ee51a0e5-9908-4ad0-b2c4-5f414cd603a4","session_id":"a63c3526-05bb-4b6f-9cf3-4c21a8957bc5"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done on branch `job-ex41-10291929` (HEAD `c7b16c9`).

**Result**
- Surveyed 20 Python-syntax examples (14 `.py`, 6 `.ail`): base refused 13; `c_export/geometry.py` now builds and matches CPython on both paths. Remaining 12 refusals are host/research harnesses (`__file__`, host imports, import collisions, int64-only probe).
- Added the `@export` identity implementation (already in `40947ad`); review-fixed two silent-difference gaps:
  - `exports()` called before a later module-level rebinding compiled but failed at run time where CPython succeeds — now refused by name.
  - `del export` crashed the general path with `KeyError` — now a clean named refusal.

**Probes** (`/tmp/probes/ex41b`, 26 total, both builds via `cmp.sh`)
- Match CPython: `p_attr_alias`, `p_dc_default`, `p_nested`, `p_star_import`, `p_trailing_comment`, `p_walrus`, plus `geometry.py`.
- Refused: the other 19, including exports-rebinding/delete forms, factory/async calls, bad annotations, dataclass `ClassVar`, aliases and module introspection.

**Tests**
- `test_ail_ex41`: 7/7 pass.
- `test_ail_ffi` + `test_ail_cratebridge`: 35 run, 34 pass, 1 environmental failure (`rustup` has no default toolchain), unrelated.
- `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 25 run, 24 pass, 1 skip.
- `update_manifest.py` and `--check` pass. DEVLOG entry added. Tests ran on the code of `85bd2ab`; final commit only fixes the DEVLOG wording.
[cost $0.0312, opencode tokens {"total": 1877151, "input": 61232, "output": 9471, "reasoning": 18288, "cache.write": 0, "cache.read": 1788160}]
    tool time: bash 22.2 min, edit 0.0 min
        747s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_safetynet test_ail_file
        168s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 -m unittest test_ail_ffi test_ail_cratebridg
        133s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/ex41b/*.py; do echo "===== $(basename $p) ====="; PYTHON
         81s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_ex41 2>&1 | tail -20
         54s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/ex41b/*.py; do echo "===== $(basename $p) ====="; PYTHON
         49s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_ex41 2>&1 | tail -30
         35s bash   cd /tmp/probes/ex41b && base='from ail_ffi import export\n\n\n@export\ndef add(a: int, b: int) -> int:\n    re
         24s bash   mkdir -p /tmp/survey && cd AIL_CURRENT && cat > /tmp/survey/run.sh <<'SH' #!/bin/bash export AIL_NO_CACHE=1 AI

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: ex41 `@export` identity in plain Python compiles

**What the change does (one line):** in `ail_ffi_lower.py`, a plain Python-syntax compile now recognises `@export`/`@export()`/`@ail_ffi.export`/star-import forms, validates the same annotation contract as CPython's decorator, and blanks the decorator; it refuses runtime marking (`__ail_export__`, `exports()`, introspection) and `del` of imported `ail_ffi` names.

### Defect (change-caused)

1. **`_binds_name` misses a module-level walrus rebinding, so the annotation-shadow check is unsound.** `AIL_CURRENT/ail_ffi_lower.py:259` handles `Assign`, `AnnAssign`, `AugAssign`, imports, `for`, `with`, `try`, `if` — but not `ast.NamedExpr` (nor tuple/list/starred `Assign` targets, nor `ast.Match` capture). Thus `shadowed` in `_strip_exports`/`_export_structs` does not contain `int`, `_export_kind` accepts the textual annotation, and the compiled program silently differs.

Probe `/tmp/rprobes/p_walrus_int.py`:
```python
from ail_ffi import export

(int := 1)

@export
def size(x: int) -> int:
    return 1

print(size(3))
```
- **Expected (CPython 3.12):** `TypeError: @export size: parameter x needs one of int float bool ...`, no stdout, **exit 1**.
- **Actual on HEAD (general and default builds):** stdout `1`, **exit 0**.
- **Base (`/tmp/base`):** both builds refuse it at compile time (named refusal), so this silent difference is introduced by the change.

The same missing-target weakness affects `bool`/`float`/dataclass-field shadowing. Fix: make `_binds_name` treat `NamedExpr`, `Tuple`/`List`/`Starred` assignment/for targets and `match` capture patterns as bindings (or refuse those forms when an `@export` exists).

### Pre-existing (base default build already differs; not blocking)

- `case int:` capture before `@export` (`p_match_shadow`): base default printed `1`, exit 0 vs CPython exit 1; HEAD reproduces on both builds.
- Tuple target `int, y = 1, 0` (`p_tuple_int`): base default already printed `1`, exit 0; HEAD reproduces.

### Report claims

| Claim | Status |
|---|---|
| `geometry.py` builds and matches CPython on both builds | verified |
| `exports()` before a later rebinding is now refused | verified (refused; message is `name 'exports' is not defined`) |
| `del export` is a clean named refusal | verified |
| Six named probes (`p_attr_alias`, `p_dc_default`, `p_nested`, `p_star_import`, `p_trailing_comment`, `p_walrus`) match | verified, all same stdout |
| `test_ail_ex41` 7/7; `safetynet`/`files`/`corpus_findings3` pass | verified (4 modules, 0 failed, 438 s, `-j 2`) |
| `update_manifest.py --check`, DEVLOG, final commit DEVLOG-only | verified (`rc=0`; `c7b16c9` touches only DEVLOG) |
| “20 examples surveyed, base refused 13”, “26 probes” beyond the six re-run | unverified |

Non-feature program: compiled `program.c` identical between HEAD and `/tmp/base` (`ordinary_join_price`/plain probe); only path-bearing `native_report.json` differs.

Speed: no instruction-count run; the change is compile-time only and does not alter the C of programs not using `@export`.

### Unverified
Full 20-example refusal survey; the remaining 19 `/tmp/probes/ex41b` probes; `test_ail_ffi`/`test_ail_cratebridge` (not re-run).

VERDICT: FIX
1. `int` rebound by a module-level walrus `(int := 1)` is not detected by `_binds_name` (`ail_ffi_lower.py:259`), so `/tmp/rprobes/p_walrus_int.py` compiles and prints `1` with exit 0, while CPython 3.12 raises the `@export` `TypeError` and exits 1 (base refused the program at compile time).
[cost $0.0339, opencode tokens {"total": 1621039, "input": 70473, "output": 8221, "reasoning": 23113, "cache.write": 0, "cache.read": 1519232}]
    tool time: bash 13.3 min
        441s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_ex41 tes
         44s bash   cd /tmp/rprobes && cat > p_exported_internal.py <<'EOF' import ail_ffi  @ail_ffi.export def add(a: int, b: int
         38s bash   cd /tmp/rprobes && cat > p_tuple_shadow.py <<'EOF' from ail_ffi import export  int, y = list, 0  @export def s
         37s bash   cd /tmp/base && for p in /tmp/rprobes/*.py; do echo "===== $(basename $p) ====="; PYTHONPATH=/tmp/base/AIL_CUR
         34s bash   ls /tmp/probes/ex41b | wc -l; cd /home/runner/work/_temp/w2 && for n in p_attr_alias p_dc_default p_nested p_s
         31s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > p_exports_alias.py <<'EOF' from ail_ffi import export, expor
         31s bash   date; cd /home/runner/work/_temp/w2 && PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh AIL_CURRENT/language_ex
         23s bash   cd /tmp/rprobes && cat > p_match_plain.py <<'EOF' from ail_ffi import export  @export def add(a: int, b: int) 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `24255d1`.

**Change:** `_binds_name` now detects module-level bindings through `NamedExpr`, tuple/list/starred assignment and `for`/`with` targets, and all `match` capture patterns. Walruses inside function/lambda bodies still do not shadow module names.

**Probes** (`/tmp/probes/ex41fix`, both builds via `cmp.sh`): 19 total — 15 refused by name with the `@export` message (`p_walrus_expr/if/while/try/comprehension`, tuple/list/starred/for/with targets, five match forms), 4 match CPython (`p_attr_subscript_targets`, `p_lambda_walrus`, `p_nested_function_walrus`, `p_values_routes`). No silent differences.

**Tests on final commit:** `test_ail_ex41`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; `test_ail_cratebridge` still fails only on the runner's missing rustup toolchain. `update_manifest.py --check` returns 0.
[cost $0.0246, opencode tokens {"total": 1147357, "input": 53042, "output": 7978, "reasoning": 14337, "cache.write": 0, "cache.read": 1072000}]
    tool time: bash 20.3 min, write 0.0 min, edit 0.0 min
        571s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_ffi test_ail_cratebridg
        525s bash   cd /home/runner/work/_temp/w2 && timeout 2600 python3 tools/par_check.py -j 2 test_ail_ex41 test_ail_ffi test_
         80s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
         40s bash   cd /home/runner/work/_temp/w2 && python3 -m py_compile AIL_CURRENT/ail_ffi_lower.py AIL_CURRENT/test_ail_ex41.
          0s bash   cd /home/runner/work/_temp/w2 && timeout 1200 python3 tools/par_check.py -j 2 test_ail_ex41
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
          0s write  /tmp/probes/ex41fix/p_match_mapping.py
          0s write  /tmp/probes/ex41fix/p_match_star.py

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of `work..HEAD` (4 commits, `24255d1`)**

What the change really does: `ail_ffi_lower` strips `@export`/`@export()`/`@ail_ffi.export` as CPython's identity decorator, re-validates the annotation contract, refuses runtime-marking reads/exports()/deletes, and tries to detect module-level rebinding of builtin names (walrus, unpacking, `for`/`with`, `match`) to avoid treating a shadowed annotation as the builtin.

Probes run via `cmp.sh` (HEAD and `/tmp/base`):
- `p_wa_default` (walrus in a function default), `p_wa_deco` (walrus in `@lru_cache` argument), `p_typealias` (`type int = str`) → **silent difference on HEAD; base refuses by name.**
- `p_wa_class_body` → named build refusal (acceptable).
- `p_wa_genexp`, `p_wa_except`, `p_match_kwd` → refused by name, matching base's class of behaviour.
- `p_dc_routes`, `p_wa_raise` → match CPython.
- `p_nofeature` `--debug-dir` `program.c` byte-identical to base; no-feature programs unchanged.
- Tests: `test_ail_ex41`, `test_ail_ffi`, `test_ail_safetynet` all pass (3 modules, 0 failed). `update_manifest.py --check` exits 0.

Claims:
- Detect walrus/unpacking/for/with/match: **partially false** — several module-level binding sites are missed (below).
- Walrus in function/lambda body does not shadow: verified.
- “19 probes, no silent difference”: count verified (19 files), **false** — silent differences exist.
- Added tests pass: verified.

Pre-existing: `exports()` with no `@export`, and using `export` as a value, are refused by name identically on base.

Unverified: `test_ail_files`/`test_ail_corpus_findings3` (not run; not added/edited); speed (front-end only, no runtime change).

**Defects**

1. Walrus in a function **default** is a module-level binding but `_binds_name` ignores `FunctionDef` defaults.
```
from ail_ffi import export
def helper(n=(int := 1)) -> int:
    return n
@export
def size(x: int) -> int:
    return 1
print(size(5), helper())
```
Expected (CPython): exit 1, empty stdout (`TypeError: @export size: parameter x ...`). Actual both builds: exit 0, stdout `1 1`. Base refused by name.

2. Walrus in a **decorator expression** (`@lru_cache(maxsize=(int := 1))`) is module-level but decorators are not walked.
```
from functools import lru_cache
from ail_ffi import export
@lru_cache(maxsize=(int := 1))
def helper(n: int) -> int:
    return n
@export
def size(x: int) -> int:
    return 1
print(size(5), helper(2))
```
Expected: exit 1, empty stdout. Actual both builds: exit 0, stdout `1 2`. Base refused by name.

3. A module-level `type int = str` (`ast.TypeAlias`) is not recognised as a binding.
```
from ail_ffi import export
type int = str
@export
def size(x: int) -> int:
    return 1
print(size(5))
```
Expected: exit 1, empty stdout. Actual both builds: exit 0, stdout `1`. Base refused by name.

All three are change-caused silent differences against CPython 3.12 (base was a named refusal), so the “never leave a silent difference” requirement is not met.

VERDICT: FIX
1. Function-default walrus shadowing missed (`p_wa_default`): expected exit 1/empty, actual exit 0/`1 1`.
2. Decorator-expression walrus shadowing missed (`p_wa_deco`): expected exit 1/empty, actual exit 0/`1 2`.
3. Module-level `type` alias shadowing missed (`p_typealias`): expected exit 1/empty, actual exit 0/`1`.
[cost $0.0203, opencode tokens {"total": 730914, "input": 53305, "output": 4446, "reasoning": 12683, "cache.write": 0, "cache.read": 660480}]
    tool time: bash 5.0 min
        209s bash   date; cd /home/runner/work/_temp/w2 && timeout 1200 python3 tools/par_check.py -j 2 test_ail_ex41 test_ail_saf
         39s bash   cd /tmp/rprobes && export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT; for p in p_wa_default p_wa_deco p
         21s bash   cd /tmp/rprobes && export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in p_wa_default p_wa_deco p_typealias; do ec
         18s bash   cd /tmp/rprobes cat > p_exports_plain.py <<'EOF' from ail_ffi import exports  print(exports()) EOF cat > p_exp
          8s bash   cd /tmp/rprobes for p in p_nofeature p_noexport; do   for w in head base; do     if [ $w = head ]; then d=/hom
          1s bash   cd /tmp/rprobes cat > p_noexport.py <<'EOF' from ail_ffi import length  def main() -> int:     s = "abc"     p
          0s bash   git -C /tmp/base log --oneline -1 && git -C /tmp/base status --short | head
          0s bash   ls /tmp/probes/ex41fix 2>/dev/null | wc -l; ls /tmp/probes/ex41fix 2>/dev/null | head -30; cd /home/runner/wor

FINAL VERDICT: FIX  2026-10-29T12:24:14Z
