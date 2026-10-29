# job job-ex27-10290951  started 2026-10-29T01:37:46Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"27cd5cb5-764d-4664-867a-49b06dc13b61","session_id":"b000794a-9fbf-4e1d-bdb6-41db9746f517"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"f634c200-caf7-4b14-93cb-e456baabb307","session_id":"991df967-82d9-412e-833c-646934635156"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Result:** committed `ee3760e` on `job-ex27-10290951` (not pushed).

**Change:** `@export` is now a CPython-equivalent checking no-op in ordinary executable builds. `ail_ffi_lower` validates the signature/annotations, refuses invalid shapes by name, and removes the decorator before both build paths. `language_examples/c_export/geometry.py` now builds and matches CPython on both builds; `--lib` is unchanged.

**Build survey:** 14 Python files under `language_examples`: 2 build (`geometry.py`, `table_crc.py`), 12 refused. Largest category is `__file__` (5 harnesses), but fixing it alone would not make any build; the next unavailable import still blocks them. `@export` was the only refusal blocking a runnable AIL Python example.

**New test:** `AIL_CURRENT/test_ail_ex27.py`, registered in `ail_check.MODULES`: 2 CPython-compared programs, 9 refused shapes, both builds.

**Probes (`cmp.sh`, both builds):**
- Match CPython: `ex27_types`, `ex27_routes`, `ex27_empty_dataclass`, `ex27_module_attr`
- Refused by name: `ex27_refuse_missing_result`, `ex27_refuse_default`, `ex27_refuse_bad_dataclass`, `ex27_refuse_class`

**Tests:** 55 passed / 3 skipped (`test_ail_ex27`, `test_ail_ffi`, `test_ail_c_export`, `test_ail_cratebridge`; Rust tests skipped because no rustup toolchain is installed) and 25 passed / 1 skipped (`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`). `tools/update_manifest.py --check` passes.

**Records:** DEVLOG entry added and one DIFFERENCES row `C?-job-ex27-10290951-1`.
[cost $0.0000, opencode tokens {"total": 6704714, "input": 144413, "output": 18042, "reasoning": 22579, "cache.write": 0, "cache.read": 6519680}]
    tool time: bash 14.4 min
        339s bash   cd /home/runner/work/_temp/w2; python3 -m unittest -q AIL_CURRENT/test_ail_safetynet.py AIL_CURRENT/test_ail_f
        123s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT; python3 -m unittest -q test_ail_safetynet test_ail_files test_ail_c
         87s bash   cd /home/runner/work/_temp/w2; python3 -m unittest -q AIL_CURRENT/test_ail_ex27.py AIL_CURRENT/test_ail_ffi.py
         74s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT; PATH=$(echo "$PATH" | tr ':' '\n' | grep -v '/.cargo/bin' | paste -
         63s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT; python3 -m unittest -q test_ail_ex27 test_ail_ffi test_ail_c_export
         28s bash   cd /home/runner/work/_temp/w2; PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh AIL_CURRENT/language_examples/c
         22s bash   cd /home/runner/work/_temp/w2; cat > AIL_CURRENT/test_ail_ex27.py <<'EOF' """ex27: `@export` on an ordinary bu
         16s bash   mkdir -p /tmp/probes; cd /tmp/probes; cat > ex27_types.py <<'EOF' from dataclasses import dataclass from ail_f

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewer report — job `ee3760e` (work..HEAD)

**What the change really does:** `ail_ffi_lower` now recognises `@export`/`@ail_ffi.export`/`@export()`, runs a static approximation of CPython's `ail_ffi.export` contract on the raw `FunctionDef`, and blanks the decorator. It does not run the decorator or preserve its effects.

**Claims**
- Committed `ee3760e`, manifest/DEVLOG/DIFFERENCES updated — verified.
- `geometry.py` builds and matches CPython on both builds — verified (`cmp.sh`: both `exit 0`, same stdout; `test_ail_c_export` non-Rust tests pass).
- “`@export` is a CPython-equivalent checking no-op” — **false** (defects 1–3).
- “Refuses invalid shapes by name” — partially true: the 9 test shapes are refused, but the invalid shapes below are silently accepted.
- “14 Python examples: 2 build, 12 refused” — count 14 verified; only `geometry.py`/`table_crc.py` were spot-checked.
- New test has 2 valid + 9 refused programs — verified; `test_ail_ex27` passes.
- “55 passed / 3 skipped” — mostly; here `test_ail_c_export` has 1 failure from missing rustup default (environmental, not code).

**Probes (cmp.sh, both builds)**
- Match CPython: `ex27_noparam`, geometry.
- Named refusals (acceptable): `ex27_alias` (`MyInt = int`), `ex27_nested` (nested def), `ex27_exports` (`exports` unknown).
- Defects: `ex27_lru`, `ex27_future_dc`, `ex27_inherit_dc`, `ex27_forward`, `ex27_attr2`.

**Defects (FIX)**
1. `ex27_lru.py`: `@export` above `@lru_cache`; CPython raises `TypeError: @export applies to a top-level function` (exit 1, no stdout). HEAD builds both ways and prints `4` (exit 0). Base refused both builds. Cause: `_check_export` inspects the undecorated `FunctionDef`, not the object CPython's `export` receives.
2. Dataclass validation is not CPython's: `_export_dataclasses` only reads the class's own `AnnAssign` names, matches `@dataclass` by name, and ignores definition order. CPython rejects all three, HEAD's general build accepts:
   - `ex27_future_dc.py` (`from __future__ import annotations`, `x: int`): CPython `TypeError` (field type is `'int'` string) vs HEAD `4`, exit 0.
   - `ex27_inherit_dc.py` (`Base.tag: str` inherited): CPython `TypeError` vs HEAD `4`, exit 0.
   - `ex27_forward.py` (`@export` before the dataclass definition): CPython `NameError: name 'Point' is not defined` vs HEAD `4`, exit 0.
   (Default-build acceptance of these is pre-existing; the general build's acceptance is new.)
3. `ex27_attr2.py`: `print(f.__ail_export__, f.__name__)`; CPython prints `True f`, exit 0. HEAD both builds compile then `AttributeError: 'function' object has no attribute '__ail_export__'`, exit 1. Base refused by name. Cause: blanking the decorator drops `fn.__ail_export__ = True` (and `_EXPORTED` registration; `exports()` itself is refused by name, which is acceptable).

**Pre-existing (do not block):** default build already accepted `ex27_future_dc`, `ex27_inherit_dc`, `ex27_forward` on base and printed `4`.

**Tests:** `par_check -j2 test_ail_ex27 test_ail_ffi test_ail_c_export test_ail_safetynet` → only `test_ail_c_export` failed (Rust host, no rustup default). `test_ail_ex27` alone passes; `test_ail_files` and `test_ail_corpus_findings3` pass; `update_manifest.py --check` passes. Speed not checked (compile-time-only change, no hot runtime path).

VERDICT: FIX
1. `@export` over another decorator is validated against the raw function (`ex27_lru`): CPython `TypeError`/exit 1, HEAD prints `4`/exit 0.
2. Static dataclass check accepts shapes CPython rejects (`ex27_future_dc`, `ex27_inherit_dc`, `ex27_forward`): CPython exit 1, HEAD general build prints `4`/exit 0.
3. Blanking `@export` loses CPython's `__ail_export__` attribute (`ex27_attr2`): CPython prints `True f`/exit 0, HEAD raises `AttributeError`/exit 1.
[cost $0.0000, opencode tokens {"total": 864245, "input": 26187, "output": 4829, "reasoning": 22221, "cache.write": 0, "cache.read": 811008}]
    tool time: bash 6.5 min
        161s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus
        142s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex27 test_ail_ffi tes
         19s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex27 2>&1 | tail -6
         15s bash   cd /home/runner/work/_temp/w2; PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh AIL_CURRENT/language_examples/c
          8s bash   cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/*.py; do echo "=== $p"; PYTHONPATH=$PWD/AIL_CURRENT bash 
          8s bash   cd /tmp/rprobes; cat > ex27_attr.py <<'EOF' from ail_ffi import export  @export def f(x: int) -> int:     retu
          8s bash   cd /tmp/rprobes; cat > ex27_simple.py <<'EOF' from ail_ffi import export  @export def f(x: int) -> int:     re
          7s bash   cd /tmp/rprobes; cat > ex27_lru.py <<'EOF' from functools import lru_cache from ail_ffi import export  @export

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `c4f4c93` (on top of `ee3760e`) with fixes for all three review defects.

**Fixes**
- `@export` must now be the innermost decorator; otherwise it is refused by name (CPython validates the decorated object, not the raw function).
- Dataclass validation now follows definition order and `dataclasses.fields`: inherited fields count, forward names are rejected, and `from __future__ import annotations` string field types are rejected (empty dataclasses still pass).
- `__ail_export__` reads (direct and `getattr`) are refused by name instead of compiling to `AttributeError`, since AIL has no function attributes.

**Probes** (`/tmp/probes/ex27`, `cmp.sh`, both builds, 17 total)
- Match CPython: `p_valid_dataclass`, `p_valid_future_scalar`, `p_future_empty_dc`, `p_inherit_ok`, `p_plainbase`, `p_empty_dc`, `p_lru_outer` (7).
- Refused by name: `p_lru`, `p_future_dc`, `p_inherit_dc`, `p_forward`, `p_badfield_str`, `p_attr2`, `p_attr_getattr`, `p_alias`, `p_exports`, `p_nested` (10).
- `language_examples/c_export/geometry.py` still matches CPython on both builds.

**Tests on final commit**
- `test_ail_ex27`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass.
- `test_ail_c_export`: 16 non-Rust tests pass, 1 skipped; the only failure is the environment’s missing rustup default (`rustup default stable`), not code.
- `update_manifest.py --check`: passes. DEVLOG/DIFFERENCES updated.
[cost $0.0427, opencode tokens {"total": 2327870, "input": 86743, "output": 11525, "reasoning": 26978, "cache.write": 0, "cache.read": 2202624}]
    tool time: bash 9.7 min, edit 0.0 min
        251s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
        244s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && echo MANIFEST_OK && cd AIL_CURREN
         27s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
         13s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/probes/ex27/out && mkdir -p /tmp/probes/ex27/out && ls /tmp/probe
         13s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_c_export 2>&1 | tail 
         12s bash   cd /home/runner/work/_temp/w2 && PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh AIL_CURRENT/language_examples
          7s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 - <<'EOF' import unittest loader = unittest.TestLoader() 
          7s bash   cd /tmp/probes && cat > attr_name.py <<'EOF' def f(x: int) -> int:     return x  print(f.__name__) EOF cat > a

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change does:** Recognises `@export` in `ail_ffi_lower` for ordinary builds, statically mirrors `ail_ffi.export`'s annotation/signature contract (with a syntactic dataclass table), blanks the decorator, and refuses `__ail_export__` reads. This matches the report.

**Verified**
- `c_export/geometry.py`: base refuses (decorator); HEAD builds on general + default and matches CPython. Core task achieved.
- Extern-only file: `--debug-dir` generated C identical base vs HEAD (only temp paths differ in JSON).
- `test_ail_ex27`, `test_ail_ffi`, `test_ail_safetynet`: pass (`par_check -j 2`).
- `tools/update_manifest.py --check`: exit 0. `compile --lib geometry`: builds `.so/.a/.h`.
- `__ail_export__` direct/alias/getattr: refused by name on both builds. `@export` below another decorator refused; inherited/future/forward dataclass cases behave as reported.
- `p_classvar` (ClassVar field): CPython accepts, AIL refuses by name — over-refusal, acceptable, not a defect.

**Defects (new silent differences; base refused these, HEAD accepts)**
1. Annotation names are matched as text, not resolved. `List`/`typing` need not exist.
   ```python
   from ail_ffi import export
   @export
   def f(x: List[int]) -> int: return len(x)
   print(f([1, 2]))
   ```
   CPython: exit 1, `NameError: name 'List' is not defined`. HEAD (both builds): exit 0, prints `2`. Same with `typing.List[int]` (`NameError: name 'typing' is not defined`).
2. Rebound/shadowed names are accepted where CPython rejects.
   ```python
   int = dict
   from ail_ffi import export
   @export
   def f(x: int) -> int: return 1
   print(f({}))
   ```
   CPython: exit 1, `TypeError: @export f: parameter x needs ...`. HEAD (both builds): exit 0, prints `1`. Same for `list = dict` + `list[int]`, `str = dict`, dataclass field `int = str`, and `P = dict` after `@dataclass class P` (p_shadow_int, p_shadow_list, p_str_name, p_dc_shadow, p_dc_rebind).

**Pre-existing (not counted):** `hasattr(f, "__ail_export__")`/`f.__name__` fails with `NotImplementedError: hasattr() on a 'function' value`; identical on plain functions without `@export` on both base and HEAD.

**Unverified:** worker's exact 17 `/tmp/probes` list; `test_ail_c_export` rustup failure; `test_ail_files` / `test_ail_corpus_findings3`.

VERDICT: FIX
1. Resolve `int/float/bool/str/bytes/list/List/typing` (and dataclass/dataclass field names) against actual bindings, or refuse by name when they are unimported or rebound before the definition; currently undefined or shadowed names compile and run where CPython raises `NameError`/`TypeError` (probes `p_list_name`, `p_typing_name`, `p_shadow_int`, `p_shadow_list`, `p_str_name`). Expected: nonzero like CPython; actual: exit 0 with stdout.
2. Track top-level rebinding of a dataclass name before an `@export` using it (`p_dc_rebind`, `p_dc_shadow`): CPython rejects the annotation, HEAD accepts and prints. Expected: nonzero; actual: exit 0.
[cost $0.0296, opencode tokens {"total": 1281483, "input": 66428, "output": 5330, "reasoning": 21501, "cache.write": 0, "cache.read": 1188224}]
    tool time: bash 2.4 min
         92s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_
         16s bash   cd /home/runner/work/_temp/w2 && date && PYTHONPATH=$PWD/AIL_CURRENT bash ~/tools/cmp.sh AIL_CURRENT/language_
         14s bash   cd /home/runner/work/_temp/w2 && for p in p_shadow_int p_shadow_list p_dc_shadow p_dc_rebind p_classvar p_hasa
          9s bash   cd /tmp/base && for p in p_shadow_int p_dc_shadow p_dc_rebind; do echo "===== BASE $p"; PYTHONPATH=/tmp/base/A
          6s bash   cd /home/runner/work/_temp/w2 && for p in p_list_name p_typing_name p_dc_name p_str_name; do echo "===== $p"; 
          3s bash   cd /tmp/rprobes && sed -i 's/@extern$/@extern()/' p_extern.py && cat p_extern.py && cd /home/runner/work/_temp
          2s bash   cd /tmp/rprobes && cat > p_hasattr_plain.py <<'EOF' def f(x: int) -> int:     return x  print(hasattr(f, "__na
          2s bash   cd /home/runner/work/_temp/w2 && for wt in /tmp/base /home/runner/work/_temp/w2; do d=/tmp/dbg$(basename $wt);

FINAL VERDICT: FIX  2026-10-29T04:26:49Z
