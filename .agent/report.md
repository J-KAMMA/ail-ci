# job job-ex40-10291920  started 2026-10-29T10:59:02Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"1d547a84-0a93-4047-ae90-dfc5eb9de8f7","session_id":"810d5697-da60-4fcd-8344-02758098bcfa"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"e8c4e29a-8e72-4cfc-ae29-c37913f422db","session_id":"f129ee32-a926-4538-b1b2-540d8f023dc6"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `dced1a0`.

**Change:** `AIL_CURRENT/language_examples/c_export/geometry.py` was the refused Python-syntax example (`the decorator on def add ...`). `ail_ffi_lower` now removes the `@export` marker from accepted top-level functions (`@export`, `@export()`, `@ail_ffi.export`) and refuses invalid shapes by name. A later user binding of `export` is no longer stripped.

**Enumerated:** six Python-syntax `.ail` examples plus `geometry.py`; all build now. Other `.py` files under `language_examples` are benchmark/build harnesses, not AIL examples.

**Probes** in `/tmp/probes/ex40` on both builds:
- Match CPython: `p_ex40_geometry`, `p_ex40_forms`, `p_ex40_module`, `p_ex40_alias`, `p_ex40_future`, `p_ex40_more` (dataclass defaults/frozen), `p_ex40_types`, `p_ex40_no_ffi`.
- Refused by name: `p_ex40_call_args`, `p_ex40_invalid_ann`, `p_ex40_invalid_class`, `p_ex40_invalid_default`, `p_ex40_invalid_star`, `p_ex40_invalid_unannotated`, `p_ex40_shadow`.
- Pre-existing decorator behaviour, unrelated: `p_deco_effect` refused by name; `p_ex40_user_export` refused on general, matches on default.

**Tests:** `test_ail_ex40` (3 tests), `test_ail_ffi`, `test_ail_c_export`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet` all pass on the final commit. The Rust host test in `test_ail_c_export` is skipped in the final run because no Rust toolchain is installed. `update_manifest.py --check` passes.
[cost $0.0679, opencode tokens {"total": 6684918, "input": 167853, "output": 13336, "reasoning": 25521, "cache.write": 0, "cache.read": 6478208}]
    tool time: bash 18.6 min, write 0.0 min
        389s bash   cd AIL_CURRENT && PATH=$(printf '%s' "$PATH" | sed 's#:/home/runner/.cargo/bin##') python3 ../tools/par_check.
        370s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_ex40 test_ail_ffi test_ail_c_export test_ail_fil
         65s bash   export PYTHONPATH=$PWD/AIL_CURRENT; for f in /tmp/probes/ex40/*.py; do echo "##### $(basename $f)"; bash ~/too
         56s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_ex40.py') s=p.read_text() old='''NO_EXP
         51s bash   for f in /tmp/probes/ex40/*.py; do echo "##### $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD"; done > /tmp/e
         50s bash   export PYTHONPATH=$PWD/AIL_CURRENT; for f in /tmp/probes/ex40/*.py; do echo "##### $(basename $f)"; bash ~/too
         46s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_ex40 2>&1 | tail -60
         27s bash   export PYTHONPATH=$PWD/AIL_CURRENT; for f in /tmp/probes/ex40/p_ex40_shadow.py /tmp/probes/ex40/p_ex40_geometr

## review 0
[model opencode-go/deepseek-v4.1-flash]
Reviewer report — job ex40, HEAD `dced1a0` (base `/tmp/base` at `6ea14ca`).

**What the change really does.** `ail_ffi_lower` now recognises `@export`/`@export()`/`@<alias>.export` on top-level functions whose AST annotations look like the C-export types, blanks the decorator, and refuses other shapes with the new message; it also scans module-level statements to stop stripping a re-bound `export`. It does not emulate any run-time effect of the decorator and its annotation/dataclass checks are AST approximations of CPython's `typing.get_type_hints` check.

**Main deliverable.** `geometry.py` matches CPython on stdout/exit on both builds (`cmp.sh`: g/d exit 0, same stdout). `test_ail_ex40`, `test_ail_ffi`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet` pass; `test_ail_c_export` FAILS here in the Rust host test (rustup has no default toolchain), not skipped. `update_manifest.py --check` passes. A program with no `ail_ffi` has identical `program.c` in `--debug-dir` base vs HEAD.

**Probes (HEAD, both builds unless noted).**
- `p_geometry`, `p_star` (`from ail_ffi import *`): match.
- `p_exports` (`exports()`): named refusal (acceptable).
- `p_global`, `p_dataclass_rebind`, `p_attr_direct`, `p_del`: wrong (below).

**Report claims.** Commit, geometry refusal, the three decorator forms, refusal message, no-feature C unchanged: verified. “A later user binding of `export` is no longer stripped”: **false** (only direct module-level bindings; a `global export` set in a called function is missed). “`test_ail_c_export` … was skipped”: **false** here (it ran and failed for rustup). “Six Python-syntax `.ail` examples plus geometry.py; all build now”: **unverified** (I did not re-enumerate all examples).

**Pre-existing.** Rust host failure is environmental. `del export` after `from ail_ffi import …` crashes the compiler on base too when there is no decorator (`KeyError: 'export'`); the new stripping makes the @export probe reach that pre-existing crash instead of a named refusal.

VERDICT: FIX
1. User decorator installed through `global` before the definition is stripped. `from ail_ffi import export; def install(): global export; ...; export = wrap; install(); @export def add(x: int) -> int: return x; print(add(2))` — expected `12`, actual `2` (g and d); base refused by name.
2. Dataclass name rebound after the class, so CPython rejects the annotation but the AST scan still treats it as a dataclass parameter. `@dataclass class P: x: int; P = 3; @export def f(p: P) -> int: return 7; print(f(1))` — expected CPython exit 1 (TypeError at import, empty stdout), actual prints `7`, exit 0 (g and d); base refused by name.
3. Decorator side effect is lost silently. `@export def add(a: int, b: int) -> int: return a + b; print(add.__ail_export__)` — expected `True`, actual `AttributeError: 'function' object has no attribute '__ail_export__'`, exit 1 (g and d). The same file without `@export` matches CPython, so the change causes it.
4. `del` of the marker is not treated as a later binding. `@export def add(a,b): ...; del export; print(add(2,3))` — expected CPython `5`, exit 0; actual compiler build fails with an internal traceback `KeyError: 'export'` (not a named refusal) on both builds; base refused by name.
[cost $0.0276, opencode tokens {"total": 848317, "input": 67564, "output": 4599, "reasoning": 20698, "cache.write": 0, "cache.read": 755456}]
    tool time: bash 7.9 min
        387s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_
         26s bash   cd /tmp/rprobes && cat > p_dataclass_rebind.py <<'EOF' from dataclasses import dataclass from ail_ffi import e
         20s bash   cd /tmp/rprobes && cat > p_redef.py <<'EOF' from dataclasses import dataclass from ail_ffi import export   @da
         19s bash   cd /tmp/rprobes export PYTHONPATH=/tmp/base/AIL_CURRENT for f in p_del p_global p_attr p_star p_exports; do ec
         15s bash   cd /tmp/rprobes && cp /home/runner/work/_temp/w2/AIL_CURRENT/language_examples/c_export/geometry.py p_geometry
          4s bash   cd /tmp/rprobes && rm -rf dd_base dd_w2 && for wt in /tmp/base /home/runner/work/_temp/w2; do n=$(basename $wt
          0s bash   cd /tmp/rprobes && printf 'print(1 + 2)\n' > p_plain.py for wt in /tmp/base /home/runner/work/_temp/w2; do n=$
          0s bash   cd /tmp/base && git log --oneline -2; git status --short | head; echo ---; diff -q /tmp/base/AIL_CURRENT/ail_f

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `1a85e64` on `job-ex40-10291920`.

**Review defects**
1. `global export` install: now refused by name (`the decorator on def add ...`), no silent output.
2. Dataclass rebound before `@export`: now refused by name, no silent `7`.
3. `add.__ail_export__`: direct read now matches CPython (`True`); alias/argument/list/dict/assignment reads are refused by name. No runtime `AttributeError`.
4. `del export`: now refused by name (`deleting an ail_ffi name is not supported`), no internal `KeyError`/traceback.

**Probes**: 23 run with `bash ~/tools/cmp.sh` on both builds (g/d).
- Match CPython: `p_geometry`, `p_star`, `p_called`, `p_module`, `p_attr_direct`, `p_dataclass_defaults` (6).
- Refused by name: `p_attr_alias`, `p_attr_arg`, `p_attr_list`, `p_attr_dict`, `p_attr_assign`, `p_exports`, `p_global`, `p_dataclass_rebind`, `p_del`, `p_del_noexport`, `p_dataclass_after`, `p_dataclass_base_bad`, `p_scalar_rebind`, `p_scalar_rebind_after`, `p_module_attr_rebind`, `p_dataclass_import_after`, `p_dataclass_base_ok` (17).

**Tests** (final commit content)
- Pass: `test_ail_ex40`, `test_ail_ffi`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- Fail only environmental Rust tests: `test_ail_c_export::test_rust_host_matches_cpython` and `test_ail_cratebridge::test_rust_crate_cdylib_and_staticlib` — `rustup` has no installed/default toolchain.
- `python3 tools/update_manifest.py --check` passes.
- `test_ail_ex40` now covers all four review reproducers plus indirect marker routes.
[cost $0.0505, opencode tokens {"total": 3169597, "input": 106572, "output": 14462, "reasoning": 27891, "cache.write": 0, "cache.read": 3020672}]
    tool time: bash 15.4 min
        347s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_ffi test
        339s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_ffi test
         64s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_ex40 2>&
         61s bash   cd /tmp/probes && cat > p_module_attr_rebind.py <<'EOF' import ail_ffi   def wrap(fn):     def inner(x: int) -
         59s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_ex40 2>&
         43s bash   cd /tmp/probes && export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT && for f in p_geometry p_star p_cal
          8s bash   cd /tmp/probes && cat > p_star.py <<'EOF' from ail_ffi import *   @export def add(a: int, b: int) -> int:     
          0s bash   python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.read_text() entry = '''## 2026-10-29 -- 

## review 1
[model opencode-go/deepseek-v4.1-flash]
Findings below. No source files edited, nothing committed.

## What the change really does
`ail_ffi_lower.py` now (a) adds `export` to the star-import set, (b) scans module bindings (`total`/`other`/`global`/`nonlocal`/deletes/attribute stores/`setattr`) to decide whether `export` and annotation names are stable, (c) statically validates a top-level `@export` function's annotations and blanks the decorator, (d) rewrites a direct `name.__ail_export__` load to `True` and refuses other `__ail_export__` reads, plus the test/manifest/devlog/differences. This mostly matches the report, except the soundness claims below.

## Claims
- (1) `global export` install refused by name — **verified** (`p_global` → `the decorator on def add`, both builds).
- (2) Dataclass rebound before `@export` refused — **verified** (`p_dataclass_rebind` → `@export marks a top-level function...`).
- (3) Direct `add.__ail_export__` matches, alias/argument/list/dict/assignment refused, "no runtime `AttributeError`" — **partly false**. Direct read verified; the five routes are covered by `test_ail_ex40` (passes). But `getattr`/`hasattr`/`add.__dict__` reach the generic runtime limitation (pre-existing, see below), and `__dict__` raises `AttributeError`.
- (4) `del export` refused by name — **verified** (`deleting an ail_ffi name is not supported`).
- Tests: `test_ail_ex40 test_ail_ffi test_ail_safetynet test_ail_files test_ail_corpus_findings3` all **pass** (5 modules, 0 failed). `update_manifest.py --check` **passes**.
- Rust "environmental" failures — **unverified** (not run).

## Defects
1. **UTF-8 byte column corrupts the rewrite.** Probe (`p_uni`): `@export def add(a:int,b:int)->int:...` then `print('é', add.__ail_export__)`. Expected CPython: `é True`, exit 0. Actual both builds: `p.ail:9:6: '(' was never closed`; the lowering produces `print('é', aTrue`. `ast` `col_offset` is a UTF-8 byte offset but `offset()` slices a `str` by character.
2. **Local shadow of an exported name is silently rewritten.** Probe (`p_local`): exported `add`, then `def show(add): print(add.__ail_export__)` / `show(5)`. Expected CPython: `AttributeError: 'int' object has no attribute '__ail_export__'`, exit 1. Actual both builds: `True`, exit 0. The rewrite checks `value.id in exported` but not the enclosing scope.
3. **Dataclass field check ignores builtin rebinding.** Probe (`p_dc_rebind`): `int = str`; `@dataclass class P: x: int`; `@export def f(p: P) -> None: print(type(p.x).__name__)`; `f(P('a'))`. Expected CPython: `TypeError: @export f: parameter p needs ...`, exit 1. Actual both builds: `str`, exit 0 (`int = 5` variant prints `ran`). `structs` validates field names but never consults `scalar_ok`, and `-> None` bypasses it.

## Pre-existing (does not block)
`getattr`/`hasattr`/`func.__dict__` on any function already fail on base (`p_plain_getattr`, `p_plain_dict`); the change merely lets `@export` programs reach this generic limitation instead of refusing at the decorator (`p_getattr`, `p_hasattr`, `p_dict` give `NotImplementedError`/`AttributeError`, CPython prints `True`). No feature-free C changed: `--debug-dir` `program.c`/`entry.c` byte-identical to `/tmp/base`.

## Unverified
- Speed/icount: change is compile-time lowering only, no runtime hot path touched (`__ail_export__`→`True` is constant); not measured.
- Rust/`test_ail_c_export` environmental failures not reproduced.
- Worker's individual `/tmp/probes` files not re-run; equivalents are in `test_ail_ex40`, which passed.

VERDICT: FIX

1. `p_uni`: expected `é True` (exit 0), actual compile error `'(' was never closed` on both builds (UTF-8 byte-column offset bug).
2. `p_local`: expected `AttributeError` (exit 1), actual `True` (exit 0) on both builds; the `__ail_export__` rewrite ignores local shadowing.
3. `p_dc_rebind`: expected `TypeError` (exit 1), actual `str` (exit 0) on both builds; the dataclass field scan ignores rebinding of `int`/`float`/`bool` when the result is `-> None`.
[cost $0.0320, opencode tokens {"total": 977873, "input": 95661, "output": 5205, "reasoning": 19919, "cache.write": 0, "cache.read": 857088}]
    tool time: bash 9.2 min
        424s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_ex
         37s bash   cd /tmp/rprobes export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT for f in p_uni p_uni2 p_local p_same 
         36s bash   cd /tmp/rprobes export PYTHONPATH=/tmp/base/AIL_CURRENT for f in p_uni p_local p_dc_rebind p_getattr p_hasattr
         28s bash   cd /tmp/rprobes export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT for f in p_global p_dataclass_rebind 
          7s bash   cd /tmp/rprobes && cat > p_extern_plain.py <<'EOF' from ail_ffi import extern, c_double   @extern(lib="m", hea
          6s bash   cd /tmp/rprobes && cat > p_plain_getattr.py <<'EOF' def f(x: int) -> int:     return x   print(getattr(f, '__n
          5s bash   cd /tmp/rprobes && cat > p_plain_dict.py <<'EOF' def f(x: int) -> int:     return x   print(f.__dict__) EOF ex
          5s bash   cd /tmp/rprobes && cat > p_dc_int5.py <<'EOF' from dataclasses import dataclass from ail_ffi import export  in

FINAL VERDICT: FIX  2026-10-29T12:25:46Z
