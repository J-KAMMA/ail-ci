# job job-ex21-10290616  started 2026-10-28T21:19:20Z  worker=oc reviewer=oc (GitHub)
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
Failed to fetch model list: catalog init completed without available models
DeepSeek-Flash -> fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your authentication has expired. Please sign in again."],"error_code":105,"fast_mode_state":"off","uuid":"8c34f5b0-ab3f-422f-b681-2b09d9688a0b","session_id":"75ad74ff-9f4b-49c3-8c36-f81ba45b5e01"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Task work was already present on this branch at `aaee662` (`ex21: compile @export as the CPython identity decorator`); I verified it end-to-end rather than redoing it.

**Survey (14 Python-syntax examples under `language_examples`)**
- Build on both builds: `c_export/geometry.py`, `c_headers_workflow/table_crc.py`.
- 12 refused: 5 by `__file__ is not available` (row scripts), 3 by import-name collisions, 2 by unavailable local imports, 1 by `import of 'pyfunc'`, 1 by `Path` used as a value / `2 ** 64` beyond int64.
- The `@export` refusal blocked `c_export/geometry.py`; it is fixed in `ail_ffi_lower.py` + `pyboxed.py`/`pyboxed2.py`, with compile-time checks matching CPython's decorator. Real example matches CPython on both builds (exit 0, same stdout); `table_crc.py` likewise.

**Verification**
- `test_ail_ex21`, `test_ail_safetynet`, `test_ail_ffi`, `test_ail_unified`: 46 tests, OK (684 s).
- `test_ail_files`: 18 tests, OK (1 skipped). `test_ail_corpus_findings3`: 2 tests, OK.
- `tools/update_manifest.py` and `--check`: rc 0.
- Re-ran 13 `/tmp/probes/ex21_*` via `cmp.sh`: 6 match CPython on both builds; 5 refused by name where CPython itself errors; 2 refused by name (`alias_import`, function value called through an instance attribute). No silent differences.
- Working tree clean except untracked `.agent/pipeline.md`; no new commit was needed.
[cost $0.0240, opencode tokens {"total": 1637216, "input": 73149, "output": 3999, "reasoning": 9988, "cache.write": 0, "cache.read": 1550080}]
    tool time: bash 14.1 min
        684s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest -q test_ail_ex21 test_ail_safetynet test_ail_
         51s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/ex21_*.py; do echo "##### $(basename $p)"; PYTHONPATH=$P
         44s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest -q test_ail_corpus_findings3 2>&1 | tail -30
         31s bash   mkdir -p /tmp/ex21survey; cd /tmp/ex21survey; for f in $(find "$OLDPWD/AIL_CURRENT/language_examples" -name '*
         20s bash   cd /home/runner/work/_temp/w2 && for f in AIL_CURRENT/language_examples/c_export/geometry.py AIL_CURRENT/langu
         16s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest -q test_ail_files 2>&1 | tail -30
          0s bash   sed -n '120,260p' AIL_CURRENT/test_ail_ex21.py; echo ====; git show --stat HEAD; echo ====; git show --stat HE
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py; echo "update rc=$?"; python3 tools/update_m

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does.** It stops `ail_ffi_lower` blanking an `ail_ffi` import line whenever the name `export` is imported (or a module alias appears in `@x.export`), accepts `ail_ffi.export` as a no-op decorator in `pyboxed.py`, and adds an AST-based signature check in `pyboxed2.py`. This differs from the report only in scope: the lower keeps the import on the *presence* of `export`, not on the decorator being used.

**Observed.** `geometry.py` matches CPython on both builds. `test_ail_ex21` (17.5 s), `test_ail_safetynet` (130 s) and `test_ail_ffi` (56 s) pass; `update_manifest.py --check` rc 0. I did not re-run `test_ail_unified`, `test_ail_files` or `test_ail_corpus_findings3`.

**Probes that changed behaviour.** Invalid decorators with defaults/missing return/bad types are refused by name on both builds (good). Module alias `@f.export`, `@export()`, bytes/str/bool results, dataclass params and `-> None` match CPython.

**Pre-existing (also wrong on base):** function attribute access (`add.__name__`, `add.__ail_export__`) fails on base too; `reversed(bytes)` fails on base without any decorator; class decorators are ignored on base (`@lru_cache class C`).

`VERDICT: FIX`

1. **Unused `from ail_ffi import export` silently drops the default build off the typed path (C changed, ~20x slower).** Probe `p24_unused_main.py`:
   ```
   from ail_ffi import export
   def main() -> None:
       xs = [3, 1, 2]; xs.sort(); print(xs[0] + xs[-1])
   main()
   ```
   It never applies `@export`. Expected: same C as base (typed path, 16,792-byte `program.c`, no note). Actual: default build prints `note: ... built on the general path (about 20x slower) because import of 'ail_ffi' is not available`; `program.c` is 111,976 bytes and differs completely. Cause: the lower keeps the import whenever `export` is imported, instead of only when a decorator uses it.

2. **`from __future__ import annotations` + dataclass parameter is accepted where CPython raises.** Probe `p13_future_dc.py`:
   ```
   from __future__ import annotations
   from dataclasses import dataclass
   from ail_ffi import export
   @dataclass
   class P: x: int
   @export
   def w(p: P) -> int: return p.x
   print(w(P(2)))
   ```
   Expected (CPython): exit 1, `TypeError: @export w: parameter p needs one of ...` (dataclass fields are strings under future annotations). Actual: general build exit 0, stdout `2` (AST check sees `int`). On base the general build refused by name; the default build already printed `2`, so that half is pre-existing.

3. **Rebinding the imported decorator is accepted where CPython raises.** Probe `p23_reassign.py`:
   ```
   from ail_ffi import export
   export = 5
   @export
   def f(x: int) -> int: return x
   print(f(2))
   ```
   Expected: exit 1, `TypeError: 'int' object is not callable`. Actual: general build exit 0, stdout `2` (check uses `from_imports` and ignores the later rebinding). The default build printed `2` on base too (pre-existing there); the general build used to refuse the decorator by name.
[cost $0.0323, opencode tokens {"total": 1411265, "input": 63621, "output": 8091, "reasoning": 23201, "cache.write": 0, "cache.read": 1316352}]
    tool time: bash 8.9 min
        132s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 850 python3 ../tools/par_check.py -j 2 test_ail_s
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_ex21 test_ail_s
         79s bash   date; cd /tmp/rprobes cat > b18_norev.py <<'EOF' def rb(data: bytes) -> bytes:     return bytes(reversed(data)
         58s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 400 python3 ../tools/par_check.py -j 2 test_ail_f
         36s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/p1[3-9]*.py /tmp/rpro
         31s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/p*.py; do echo "#####
         18s bash   cd /home/runner/work/_temp/w2; export PYTHONPATH=$PWD/AIL_CURRENT; bash ~/tools/cmp.sh AIL_CURRENT/language_ex
         13s bash   date; cd /tmp/rprobes cat > p24_unused_main.py <<'EOF' from ail_ffi import export  def main() -> None:     xs 

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `6d8d2cc`.

- Unused `from ail_ffi import export` / `import ail_ffi` now leaves the default build on the typed path: no fallback note (previously 111,976-byte general-path `program.c`).
- `@export` with a dataclass parameter under `from __future__ import annotations` is refused by name on both builds, matching CPython’s `TypeError`.
- Rebinding the imported decorator or module alias before the decorated `def` is refused by name on both builds; rebinding after the decorator still matches CPython.

Probes (all via `cmp.sh`, both builds):
- Match CPython: `p24_unused_main`, `ex21_unused_module`, `ex21_used_call`, `ex21_module_alias`, `ex21_dataclass_ok`, `ex21_future_scalar`, `ex21_future_dataclass_plain`, `ex21_ann_only`, `ex21_rebind_after`, `ex21_routes`, `ex21_geometry`.
- Refused by name: `p13_future_dc`, `p23_reassign`, `ex21_rebind_ann`, `ex21_rebind_loop`, `ex21_rebind_module_alias`, `ex21_walrus_rebind`, plus the earlier invalid-export probes.

Tests on `6d8d2cc`:
- `test_ail_ex21` 7 tests OK (~94 s).
- Passed: `test_ail_ffi`, `test_ail_python_syntax`, `test_ail_dunders`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- `test_ail_c_export` and `test_ail_cratebridge`: only their Rust-host tests failed initially because `rustc` is a rustup proxy with no installed toolchain; with `rustc` removed from `PATH`, both modules pass and those tests skip. No code failure.
- `tools/update_manifest.py` updated; `--check` rc 0.
[cost $0.0631, opencode tokens {"total": 6267954, "input": 120578, "output": 17537, "reasoning": 26927, "cache.write": 0, "cache.read": 6102912}]
    tool time: bash 30.3 min, edit 0.0 min
       1261s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 --timeout 1200 test_ail_ex21 t
        176s bash   cd /tmp/probes cat > ex21_unused_module.py <<'EOF' import ail_ffi def main() -> None:     xs = [3, 1, 2]; xs.s
         94s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_ex21.p
         80s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 400 python3 -m unittest -v test_ail_ex21 2>&1 | tail -30
         78s bash   cd /home/runner/work/_temp/w2 && export PYTHONPATH=$PWD/AIL_CURRENT for p in p24_unused_main p13_future_dc p23
         43s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && PATH=$(echo "$PATH" | tr ':' '\n' | grep -v '/.cargo/' | paste -s
         18s bash   cd /home/runner/work/_temp/w2 && export PYTHONPATH=$PWD/AIL_CURRENT for p in p24_unused_main p13_future_dc p23
         14s bash   cd /home/runner/work/_temp/w2 && export PYTHONPATH=$PWD/AIL_CURRENT && bash ~/tools/cmp.sh /tmp/probes/p13_fut

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: `work..HEAD` (2 commits)

**What the change does:** keeps the `ail_ffi` import line when `@export`/`@x.export` is written; makes `@export` an identity decorator on top-level `def`s in both compilers; adds a static signature check (`pyboxed2.py:3828`, `:3847`, `:3869`); writes ` future` into the dataclass marker (`ail_syntax.py:2769`) and refuses dataclass parameters under `from __future__ import annotations`.

### Probes (`/tmp/rprobes/rv`, `cmp.sh`, `PYTHONPATH=AIL_CURRENT`)

| probe | CPython | HEAD g / d |
|---|---|---|
| a_scalars, b_dataclass, n_plain_module, d_rebind_after, g_future_scalar | ok | both match |
| i_unused_from, j_unused_module | ok | match; `program.c` byte-identical to base, no fallback note |
| r_future_noexport (control) | ok | `program.c` byte-identical to base |
| geometry.py | `5 3 HÉLLO! [1, 4, 9] 3.0` | both match |
| e_rebind_cond, c_alias_call_nested, h_future_dc, o_attr_rebind | exit != 0 | refused by name (acceptable) |
| s_future_fieldless | ok (fieldless dataclass) | refused by name (over-refusal, allowed) |
| l_lru_export, u_rebind_call, w_initfalse, t_export_arg, v_alias_export_arg | exit != 0 / other value | **wrong output, see below** |
| q_export_class | exit 1 | accepted on both (identical on base → pre-existing) |

### Defects

1. **Decorator arguments ignored.** `from ail_ffi import export` / `@export(5)` / `def f(x: int) -> int: return x` / `print(f(3))`. CPython: `TypeError`, exit 1. HEAD: `3`, exit 0 on general (default was already wrong on base). Same with `import ail_ffi as ffi; @ffi.export(5)`.
2. **Non-function decorator result accepted.** `@export` above `@lru_cache(maxsize=None)` (applied to `_lru_cache_wrapper`). CPython: `TypeError: @export applies to a top-level function`, exit 1. HEAD: `6`, exit 0 on both builds. Base refused both.
3. **Rebinding through a call escapes `_export_rebound_before`.** `def setup(): global export; export = lambda fn: (lambda *a: 99)` … `setup()` … `@export def f(x: int) -> int: return x`; `print(f(3))`. CPython: `99`. HEAD: `3` on both builds. Base refused.
4. **`field(init=False)` type not validated.** Dataclass `P(x: int, hidden: str = field(init=False, default="z"))`, `@export def w(p: P) -> int`. CPython: `TypeError`, exit 1. HEAD general: `2`, exit 0 (default pre-existing on base; general is new).
5. **Newly reachable compiler crash.** `from ail_ffi import export; del export; @export def f(x: int) -> int: return x; print(f(3))`. CPython: `NameError`, exit 1; base: named `@export` refusal. HEAD: `KeyError: 'export'` traceback from `pyboxed2.py:3797` on both builds. Root cause (`del` of the name) reproduces without `@export` on base too, so the underlying bug is pre-existing; the change makes it reachable here.

### Claims

- Unused `from ail_ffi import export` / `import ail_ffi` stays typed: **verified** (no fallback note; C identical to base). The quoted byte sizes were not reproduced.
- Future-annotation dataclass parameter refused by name on both builds: **verified** (it also refuses a fieldless dataclass CPython accepts — allowed named refusal).
- "Rebinding the imported decorator … before the decorated def is refused by name": **partially false** — only direct syntactic stores are caught (defect 3).
- Probe list in the report: **unverified** (not re-run; my own probes used instead).
- `test_ail_ex21` and `test_ail_safetynet` observed: `test_ail_ex21 ok 108.5s`, `test_ail_safetynet ok 280.3s`, 0 failed. `tools/update_manifest.py --check` rc 0. Other listed modules were not re-run (per instructions).
- The change is compile-time only; no hot-path instruction-count check needed.

### Pre-existing

- `@export` on a class silently accepted (base identical, both builds).
- Default-build acceptance of `@export(5)`, `@export` above a non-function, and `field(init=False)` bad types (base default already wrong; only the general path is new).
- `del <imported name>` KeyError root cause (reproduces on base without `@export`).

VERDICT: FIX
[cost $0.0289, opencode tokens {"total": 1343449, "input": 55915, "output": 7564, "reasoning": 20322, "cache.write": 0, "cache.read": 1259648}]
    tool time: bash 9.8 min, write 0.0 min
        284s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT; date; timeout 900 python3 ../tools/par_check.py -j 2 test_ail_ex21 
        107s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/rv/*.py; do ech
         40s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/rv/m_stacked.py
         35s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=$PWD/AIL_CURRENT; bash ~/tools/cmp.sh AIL_CURRENT/langu
         27s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in /tmp/rprobes/rv/q_expor
         20s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=$PWD/AIL_CURRENT; for p in /tmp/rprobes/rv/t_export_arg
         18s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in /tmp/rprobes/rv/t_expor
         17s bash   cd /home/runner/work/_temp/w2; date; export PYTHONPATH=/tmp/base/AIL_CURRENT; for p in /tmp/rprobes/rv/x_del_e

FINAL VERDICT: FIX  2026-10-28T23:28:22Z
