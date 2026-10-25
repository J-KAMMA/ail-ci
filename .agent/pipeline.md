# job job-pre213-10252300  started 2026-10-25T14:01:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":555,"duration_api_ms":434,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":537,"duration_api_ms":419,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case, r10c: deep captured-name lookup.

- Commit `915e83c` on `job-pre213-10252300` (not pushed).
- `_register_nested` now includes deeper free names; shared names become cells and are forwarded through nested defs instead of copied. Also fixed missing nested-def flags in closure functions.
- Added `test_ail_pre213.py`; registered in `ail_check.MODULES`, `tools/ci_shards.json`, and manifest.

Probes (all on both builds):
- `p_deep_capture_append`, `alias`, `item_attr_dict`, `read`, `default`, `siblings`, `returned`, `rebind`, `three`: match CPython.
- `p_deep_capture_nonlocal`: refused by name.
- `r10c_nested_capture`: matches CPython.

Tests on final commit: `test_ail_pre213`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_functions` — 5 modules, 0 failed. Manifest `--check` passes.

Not addressed: r20 returned-sibling closure and r22 remain as before. Absolute instruction counts were not measured.
[cost $0.0000, opencode tokens {"total": 3313285, "input": 99059, "output": 11807, "reasoning": 26995, "cache.write": 0, "cache.read": 3175424}]
    tool time: bash 12.6 min
        285s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre213 test_ail_
        282s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre213 test_ail_
         44s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_deep_capture_*.py /tmp/probes/r10c_nested_capture
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_deep_capture_*.py; do echo "===== $(basename $p)"
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_deep_capture_*.py; do echo "===== $(basename $p)"
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r1*.py /tmp/probes/r2*.py; do echo "===== $p"; time
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/r10*.py /tmp/probes/r20*.py; do echo "===== $p"; ti
         14s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the diff really does:** `_register_nested` now takes `boxclosure.free_names(node)`, which includes the nested def’s own free names, not only names deeper down. It makes every such outer binding a cell and forwards external cells. It also declares nested-def flags inside closure functions. So the change is broader than “deeper free names”.

**Verified claims**
- Deep capture mutation/read/rebind/default/list-item/attribute/dict/aliasing/3-level/returned closure: matched CPython in my probes on both builds.
- Deep `nonlocal`: refused by name.
- `test_ail_pre213`, `test_ail_safetynet`, `test_ail_nested_functions`: 0 failed.
- Manifest `--check`: passes.
- r20/r22 remain refused; my r20-shaped probe’s refusing name changed versus base, but it is still refused.

**Pre-existing**
- Direct unbound **list** capture via the Python surface (`p11`, `p14a`) already prints `UnboundLocalError` on base where CPython prints `NameError`.
- `del xs` inside the intermediate function is refused the same on base/HEAD.
- `p9` already raises the same `NameError` on base/HEAD.

**Unverified**
- Instruction counts / hot-code speed.
- `test_ail_files` and `test_ail_corpus_findings3` were not re-run by me.
- The worker’s `/tmp/probes` were not available to inspect.

**Defect**

VERDICT: FIX

1. One-level direct nested functions now misreport an unbound captured scalar. The diff turns an ordinary captured local into a cell; `nctx.free_names` contains only `by_val`, not `by_cell`, so the read uses `ail_op_load` (`UnboundLocalError`) instead of `ail_op_load_free` (`NameError`). This is a regression: base matches CPython.

Probe `/tmp/rprobes/p21_scalar_one.py`:
```python
def before():
    def inner():
        return x
    try:
        inner()
    except Exception as e:
        print(type(e).__name__, str(e))
    x = 7
    print(inner())

before()
```

Expected / base / CPython:
```text
NameError cannot access free variable 'x' where it is not associated with a value in enclosing scope
7
```

Actual HEAD on both general and default builds:
```text
UnboundLocalError cannot access local variable 'x' where it is not associated with a value
7
```

`/tmp/rprobes/p22_scalar_unbound.py` (`del x` after the def) shows the same regression.
[cost $0.0000, opencode tokens {"total": 7599663, "input": 145417, "output": 17508, "reasoning": 37058, "cache.write": 0, "cache.read": 7399680}]
    tool time: bash 5.8 min
        168s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre213 tes
         38s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename "$p")"; bash
         33s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $(basename "$p")"; bash
         14s bash   cat > /tmp/rprobes/p18_class_capture.py <<'PY' def outer():     xs = [1]     def middle():         class C:   
         13s bash   cat > /tmp/rprobes/p16_r20_r22.py <<'PY' def r20():     def outer():         xs = 0         def middle():     
         10s bash   for n in before_outer_assign after_outer_delete after_middle_assign; do :; done cat > /tmp/rprobes/p15a.py <<'
          7s bash   cat > /tmp/rprobes/p11_unbound_msg.py <<'PY' def before_assign():     def middle():         def inner():      
          7s bash   cat > /tmp/rprobes/p14_direct_unbound.py <<'PY' def direct_before_assign():     def inner():         return ys

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review regression in commit `295ba87` (`pre213: unbound captured scalar keeps NameError`).

- Cause: `by_cell` captures were missing from `nctx.free_names`, so reads used `ail_op_load` (`UnboundLocalError`). They now use `ail_op_load_free` (`NameError`).
- Probes, both builds:
  - `p1_scalar_one_before.py`, `p2_scalar_del.py`, `p3_types_and_sources.py` (argument/list-item/attribute/dict; int/negative/zero/bool/None/float/str/list/tuple/dict), `p4_deep_unbound.py` (2/3 levels, delete, outer binding), `p5_mixed_alias_rebind.py`: all match CPython.
  - `p6a_r20.py`, `p6b_r22.py`, `p6c_deep_nonlocal.py`: still refused by name.
- Tests: `test_ail_pre213`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 174s.
- Manifest `--check`: passes.
- Added `UNBOUND_SCALAR` regression case to `test_ail_pre213.py`; DEVLOG updated.
- Instruction counts/hot-code speed were not measured.
[cost $0.0000, opencode tokens {"total": 1646358, "input": 67385, "output": 7019, "reasoning": 12530, "cache.write": 0, "cache.read": 1559424}]
    tool time: bash 3.7 min, edit 0.0 min
        175s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre213 t
         18s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p1_scalar_one_before.py /tmp/probes/p2_scalar_del.p
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p1_scalar_one_before.py /tmp/probes/p2_scalar_del.p
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p3_types_and_sources.py /tmp/probes/p4_deep_unbound
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' from pathlib import Path p = Path('test_ail
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && git status --short && git lo
          0s bash   pwd && git status && git log --oneline -10

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the diff does:** Captures names used by deeper nested defs in `_register_nested`, forces the enclosing binding into a cell (`NeedCells`), forwards that cell as `by_cell` through intermediate defs, skips recreating external cells, declares nested-def flags in closure functions, and adds `by_cell` names to the nested `free_names` so an unbound captured scalar raises `NameError` rather than `UnboundLocalError`.

**Probes (HEAD; both builds; base where noted):**
- `p01_deep_mut` (arg/list-item/attribute/dict): matches CPython; base refuses `name 'xs' is not defined`.
- `p02_unbound` (before assignment, after delete, 3 levels, mixed): matches CPython including the free-variable `NameError` message; base refuses.
- `p04b_shadow`, `p05_closure_deep`, `p06_types`, `p07_mutation_iter`, `p08_global`, `p11_param_cell`, `p12_loop_except`, `p13_sibling_nonlocal`, `p14_recursion`, `p15_method`, `p16_mid_binds`, `p17_nonlocal_after_cell`, `p20_returned_after_outer`, `p21_pooled`, `p22_triple_local`: all match CPython; base refuses the deep cases (`p05`, `p15`, `p20`, `p22`).
- `p03a`, `p03b`, `p6a_r20`, `p6b_r22`, `p6c_deep_nonlocal`: refused by name, same as base (`p6a` now refuses at `g` instead of `xs`; still a named refusal).
- `p19_global_shadow`: see Pre-existing.
- `p25_nofeat` (no nested def): generated C byte-identical to base in both builds.
- `p10_plain` (untyped one-level closure, general path): C differs from base (`step` is now `by_cell`, not `by_val`), outputs identical; typed gdev nested-def programs have identical C. Synthetic hot general-path loop was ~3% slower (not large; instruction counts unavailable).

**Claims:** commit `295ba87` fix — verified; cause `by_cell` missing from `free_names` — verified by diff and `p02`; worker probes `p1`–`p5` match — verified by rerunning them; `p6a/b/c` refused — verified; 4 test modules pass — verified (`test_ail_pre213` 10.9s, `test_ail_safetynet` 88.6s, `test_ail_files` 87.2s, `test_ail_corpus_findings3` 132.4s, 0 failed); manifest `--check` — verified; `UNBOUND_SCALAR` + DEVLOG — verified. Instruction counts were not measured (`perf_event_open` denied).

**Pre-existing:** `p19_global_shadow` (CPython prints `module`/`module`, AIL prints `local`/`local`), identical on base. Deep `nonlocal` and `r20` remain refused on both.

**Unverified:** absolute instruction counts; push state (irrelevant here).

VERDICT: ACCEPT
[cost $0.0637, opencode tokens {"total": 4250276, "input": 111744, "output": 16184, "reasoning": 41580, "cache.write": 0, "cache.read": 4080768}]
    tool time: bash 9.9 min, write 0.0 min
        140s bash   cd /tmp/g2 && for f in g15_012 g10_014 g10_024 g22_028 g25_016 g08_038 g10_010 g17_014 g10_036 g10_026 g20_038
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
         90s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre213 t
         38s bash   cd /tmp && rm -rf gchk && mkdir gchk && for f in g10_024 g10_010 g15_012; do cp ~/corpus/gdev/$f.py /tmp/gchk/
         28s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p13_sibling_nonlocal.py /tmp/rprobes/p14_r
         21s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p0*.py; do echo "=== $p"; bash ~/tools/cmp
         19s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p02_unbound.py /tmp/rprobes/p03a_nonlocal_
         18s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/probes/p6a_r20.py /tmp/probes/p6b_r22.py /tmp/prob

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T16:16:57Z
