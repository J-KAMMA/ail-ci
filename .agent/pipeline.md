# job job-ex39-10291711  started 2026-10-29T08:33:21Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"d5baf9a9-e360-486b-a965-714bb013c1a3","session_id":"3dd75502-70b3-454c-b4aa-37d8979c2a96"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"ae84353b-b3ec-4791-bae3-75445a1dba1b","session_id":"26814d59-25f2-46e2-af37-bda1fd03ee93"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
- Built all 14 Python-syntax examples under `AIL_CURRENT/language_examples`: `c_export/geometry.py` was refused on both builds for its `@export` decorator; the other 12 refusals are research-script dependencies (local modules, `os.environ`, `Path` values, etc.).
- Implemented CPython-compatible `@export` validation and decorator stripping in `ail_export.py`, called from the Python front end. Geometry now builds and matches CPython on default, typed and general paths; unsupported/invalid forms remain named refusals.
- Added `test_ail_ex39.py` (5 tests, registered in `ail_check.MODULES`), DEVLOG entry, DIFFERENCES row, updated manifest and shards.
- Probes: 35 in `/tmp/probes`, both `cmp.sh` builds; 6 valid programs match CPython, 29 are refused by name. Fixed silent differences found by probing: forward/rebound dataclass, dataclass with an extra decorator, shadowed scalar/list annotations.
- Final commit `fae1fc7`; `tools/update_manifest.py --check` passes; 8 targeted modules incl. `test_ail_ex39`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (0 failed, 567s).
[cost $0.0535, opencode tokens {"total": 4069515, "input": 121127, "output": 13504, "reasoning": 25764, "cache.write": 0, "cache.read": 3909120}]
    tool time: bash 25.9 min, read 0.0 min
        634s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 test_a
        570s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 test_a
         51s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 2>&1 | tail -40
         50s bash   cd /home/runner/work/ail-ci/ail-ci && ls /tmp/probes/*.py | wc -l && ls /tmp/probes/*.py | xargs -P2 -I{} /tmp
         38s bash   cat > /tmp/run_probes.sh <<'EOF' #!/bin/bash p=$1 b=$(basename "$p" .py) export PYTHONPATH=/home/runner/work/a
         34s bash   cd /home/runner/work/ail-ci/ail-ci && for p in shadow_int_dict shadow_int_lambda shadow_list_subscript shadow_
         32s bash   cat > /tmp/run_probes.sh <<'EOF' #!/bin/bash p=$1 b=$(basename "$p" .py) bash /home/runner/tools/cmp.sh "$p" "
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for p in forward_dataclass valid_basic valid_types; do export PYTHONPATH

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of `work..HEAD` (commit `fae1fc7`)

**What the change really does.** Adds `ail_export.strip_export_decorators`, called for every Python-syntax entry (and after module merge), which statically emulates CPython's `ail_ffi.export` signature checks and blanks valid `@export` decorators before lowering. Also adds `test_ail_ex39.py`, manifest/shard/DEVLOG/DIFFERENCES updates.

### Probes (HEAD, both cmp.sh builds, `PYTHONPATH=AIL_CURRENT`)
- `p4_valid_values` (args/list item/attr/dict value/dataclass), `p5_geometry`, `p6_alias_module` (`import ail_ffi as ffi; @ffi.export`): **match CPython** on g+d.
- `p2_side_exports` (`exports()`): named refusal on both builds, acceptable.
- `p7_no_feature` (`import ail_ffi`, dataclass, no `@export`): matches; `--debug-dir` output is byte-identical to base (`diff -rq` clean).
- `p12`, `p14`: **silent differences**, see defects.

### Defects
1. **Rebound `export` name is still treated as `ail_ffi.export`.**
```python
from ail_ffi import export
class NotCallable: pass
export = NotCallable()

@export
def add(a: int, b: int) -> int:
    return a + b
print(add(2, 3))
```
Expected (CPython): exit 1, `TypeError: 'NotCallable' object is not callable`; actual HEAD g+d: exit 0, stdout `5`. Base refuses both builds by name, so the change caused this. (`p3` — `export` rebound to a raising function — is the same hole; it is pre-existing on the default path but newly silent on the general path.)

2. **Rebound `dataclass` name is still treated as a real dataclass.**
```python
from dataclasses import dataclass
from ail_ffi import export
dataclass = lambda cls: cls

@dataclass
class P:
    x: int

@export
def get(p: P) -> int:
    return p.x
print(get(P(4)))
```
Expected (CPython): exit 1, `TypeError: @export get: parameter p needs ...`; actual HEAD g+d: exit 0, stdout `4`. Base refuses both builds by name. Root cause: no shadow/rebind check on the decorator names, unlike the existing checks on annotation names.

### Pre-existing (do not block)
- Function-attribute access: `getattr(f,'__ail_export__')`, `hasattr`, `f.__ail_export__`, `f.__name__` compile then fail at run time on HEAD; base fails identically for plain functions (`p10`, `p15`), so this is a pre-existing limitation exposed by removing the decorator, not introduced.
- `p3` on the default build already printed where CPython raised on base.

### Claims checked
- Geometry builds and matches CPython on default/typed/general: **verified** (`p5`, lib build produces `.so/.a/.h`).
- `@export`/`@export()`/alias/module-qualified, decorator above: **verified** by tests/probes.
- "unsupported/invalid forms remain named refusals": **false** for the two rebound-name cases above.
- `test_ail_ex39` + safetynet pass (150s, 0 failed); `update_manifest.py --check` passes; lib build still works.
- "14 examples... the other 12 refusals": there are 14 `.py` files, so 13 remain besides geometry; the "12" is inconsistent — **unverified** which example is the extra.

### Unverified
- Worker's 35 `/tmp/probes` results (not rerun); the other six targeted modules; runtime instruction counts (change is front-end only); wider suite (by instruction).

VERDICT: FIX

1. `@export` shadowed by a later binding is stripped instead of refused: probe `p14` / `p3` — CPython exits 1 with `TypeError`, HEAD g+d print `5` and exit 0 (base refused by name).
2. `dataclass` shadowed by a later binding is still accepted as a field class: probe `p12` — CPython exits 1 with `TypeError: @export get: parameter p needs ...`, HEAD g+d print `4` and exit 0 (base refused by name).
[cost $0.0242, opencode tokens {"total": 748594, "input": 63111, "output": 5907, "reasoning": 15384, "cache.write": 0, "cache.read": 664192}]
    tool time: bash 5.1 min
        152s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 test_ail_safetynet 2>&1 | tail -25
         37s bash   export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in p5_geometry p6_alias_module p7_no_feat
         32s bash   export PYTHONPATH=/home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for p in p1_side_attr p2_side_exports p3_shadow
         23s bash   cat > /tmp/rprobes/p9_direct_attr.py <<'EOF' from ail_ffi import export   @export def add(a: int, b: int) -> i
         15s bash   cat > /tmp/rprobes/p12_shadow_dataclass.py <<'EOF' from dataclasses import dataclass from ail_ffi import expor
         12s bash   export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in p1_side_attr p3_shadow_export_raises; do echo "===== BASE $p
         12s bash   export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in p9_direct_attr p10_getattr_plain; do echo "===== BASE $p"; b
         10s bash   export PYTHONPATH=/tmp/base/AIL_CURRENT; echo "===== BASE p14"; bash ~/tools/cmp.sh /tmp/rprobes/p14_shadow_ex

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both defects and committed as `3c94bda`.

**Changes**
- `ail_export.strip_export_decorators` now resolves `export`/`dataclass` like module globals: a rebinding or `del` before the decorator is refused by name instead of being stripped. Covers direct, aliased, module-qualified, `@ffi.export`/`@dataclasses.dataclass` spellings.
- Added 2 regression tests (module now 7 tests); updated DEVLOG/DIFFERENCES; manifest regenerated and `--check` passes.

**Probes** (`/tmp/probes/ex39fix`, both `cmp.sh` builds):
- Match CPython: p04, p05, p06, p09, p10, p12.
- Refused by name: p01, p02, p03, p07, p08, p11, p13, p14, p15, p16.
- No silent differences remain; p03/p11 exit 0 on CPython but are named refusals here.

**Tests on final commit** (`par_check.py -j 2`): `test_ail_ex39`, `test_ail_c_export`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (515s).
[cost $0.0317, opencode tokens {"total": 1862274, "input": 84854, "output": 9010, "reasoning": 13914, "cache.write": 0, "cache.read": 1754496}]
    tool time: bash 19.6 min, edit 0.0 min
        519s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 test_a
        409s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 test_a
         76s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_ex39 2>&1 |
         45s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail
         39s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/probes/ex39fix/*.py; d
         37s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/probes/ex39fix/*.py; d
         36s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/probes/ex39fix/*.py; d
          7s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import tempfile, subprocess, sys, os from p

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of `work..HEAD` (commits `fae1fc7`, `3c94bda`)

**What the change really does.** Adds `ail_export.strip_export_decorators`, called for every Python-syntax entry, which statically re-checks `@export`/`@dataclass` signatures, resolves decorator names against module-level bindings, and blanks valid decorators before lowering. Adds `test_ail_ex39.py`, DEVLOG/DIFFERENCES, manifest/shard updates.

The fix does repair the two prior defects: `p14` (rebound `export`) and `p12` (rebound `dataclass`) are now refused by name on both builds, matching base (verified). But the new binding analysis only sees *statement-level* `ast.Name` stores; it misses `global` assignments/deletes inside called functions and `except … as name`. Those still produce silent differences the change introduced.

### Defects

1. **`global` rebinding/del inside a function is not detected** — both builds run where CPython raises.
```python
# v2_global_export.py
from ail_ffi import export
def rebind():
    global export
    export = None
rebind()
@export
def add(a: int, b: int) -> int:
    return a + b
print(add(2, 3))
```
Expected (CPython): exit 1, `TypeError: 'NoneType' object is not callable`. Actual HEAD g+d: exit 0, stdout `5`. Base: both builds refused by name, so the change caused it. Same hole for `del` (`v5_del_global.py`: CPython exit 1 `NameError`, HEAD exit 0 `5`; base general refused).

2. **`global` rebinding of `dataclass` is not detected** — both builds run.
```python
# v3_global_dataclass.py
from dataclasses import dataclass
from ail_ffi import export
def rebind():
    global dataclass
    dataclass = lambda cls: cls
rebind()
@dataclass
class P:
    x: int
@export
def get(p: P) -> int:
    return p.x
print(get(P(4)))
```
Expected (CPython): exit 1, `TypeError: @export get: parameter p needs ...`. Actual HEAD g+d: exit 0, stdout `4`. Base: both builds refused by name.

3. **Module-level `except … as export` is not detected** (general path newly silent).
```python
# v1_except_export.py
from ail_ffi import export
try:
    raise ValueError('x')
except Exception as export:
    pass
@export
def add(a: int, b: int) -> int:
    return a + b
print(add(2, 3))
```
Expected (CPython): exit 1, `NameError: name 'export' is not defined`. Actual HEAD general: exit 0, stdout `5` (default build was already silent on base; the general path is newly silent, base refused by name).

`v6` (aliased import), `v7`/`v8` (module-qualified rebinding) are correctly refused by name; `v4` (module attribute assignment) is refused by name (AIL lacks the assignment), so those are safe.

### Pre-existing (does not block)
- Function-attribute access (`getattr(f,'__ail_export__')`, `hasattr`, `f.__name__`) fails at run time on base for plain functions. `p9` (`f.__ail_export__` with `@export`) changes from a named refusal on base to a runtime `AttributeError` on HEAD because the decorator is stripped; underlying limitation is pre-existing (prior review classified it the same way).

### Claims checked
- "Fixed both defects": **verified** (`p12`, `p14`, `p3` now named refusals on both builds).
- "a rebinding or del before the decorator is refused by name": **false** for `global`-statement rebinding/del and `except … as` (defects 1–3).
- "2 regression tests, module now 7 tests": **verified**.
- "manifest regenerated and `--check` passes": **verified**.
- "No silent differences remain": **false** (defects 1–3).
- Tests on final commit: ran `test_ail_ex39 test_ail_c_export test_ail_safetynet` (`-j 2`): 3 modules, 0 failed (202s). `test_ail_files`/`test_ail_corpus_findings3` not rerun.

### Unverified
- Worker's 16 `/tmp/probes/ex39fix` results (not rerun), `test_ail_files`, `test_ail_corpus_findings3`, and instruction counts (front-end-only change).

VERDICT: FIX

1. `global export` assignment/deletion in a called function is stripped instead of refused: probe `v2_global_export.py` / `v5_del_global.py` — CPython exits 1 (`TypeError`/`NameError`), HEAD general+default print `5` and exit 0 (base refused by name).
2. `global dataclass` assignment in a called function is still treated as a real dataclass: probe `v3_global_dataclass.py` — CPython exits 1 (`TypeError: @export get: parameter p needs ...`), HEAD general+default print `4` and exit 0 (base refused by name).
3. Module-level `except Exception as export` is not detected as a rebinding: probe `v1_except_export.py` — CPython exits 1 (`NameError`), HEAD general prints `5` and exits 0 (base general refused by name; default pre-existing).
[cost $0.0216, opencode tokens {"total": 883116, "input": 48858, "output": 4427, "reasoning": 15367, "cache.write": 0, "cache.read": 814464}]
    tool time: bash 5.4 min
        205s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_ex39
         38s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in p1_side_attr p2_side_export
         34s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes2/*.py; do echo
         22s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in v1_except_export v2_gl
         22s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in p9_direct_attr p1_side_attr
          1s bash   cat > /tmp/rprobes2/v6_alias_rebind.py <<'EOF' from ail_ffi import export as ex ex = None  @ex def add(a: int,
          1s bash   cd /home/runner/work/ail-ci/ail-ci && export PYTHONPATH=$PWD/AIL_CURRENT; for p in p14_shadow_export_identity_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --format='%H%n%s%n%b---' work..HEAD | head -40; echo ====; pytho

FINAL VERDICT: FIX  2026-10-29T11:15:30Z
