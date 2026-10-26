# job job-pre297-10270441  started 2026-10-26T19:42:44Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":441,"duration_api_ms":317,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":415,"duration_api_ms":285,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first difference: one-argument `round()` of a statically known float whose result leaves int64 is now refused by name at compile time on both builds (`int64 constant expression out of range`), including module/local constants and `abs(round(-(2.0**63)))`.

Commit: `9704858 pre297: refuse round() of an out-of-int64 constant float`

Probes in `/tmp/probes`:
- Refused by name on both builds: `p297_round_const`, `round_var`, `round_local`, `round_module`, `round_peeled`, `round_hi`, `round_huge`, `round_abs`, `round_abs2`, `round_neg`, `round_arg`, `round_list`, `round_attr`, `round_dict`, `round_default`, `round_class`, `round_routes2`.
- Match CPython on both builds: `round_min`, `round_inrange`, `round_inbound`, `round_lo`, `round_twoarg`, `round_shadow`, `p297_shadow`.

Runtime values that only reach `round` as a parameter or container read keep the existing int64 trap, documented in DIFFERENCES. `r_shadow_param` was not touched.

Final commit tests: `test_ail_pre297`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 270 s, 0 failed. `update_manifest --check` and `ci_shards --check` pass.
[cost $0.0759, opencode tokens {"total": 8433720, "input": 141731, "output": 18284, "reasoning": 31529, "cache.write": 0, "cache.read": 8242176}]
    tool time: bash 16.9 min, edit 0.0 min
        353s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 test_ail_
        272s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 test_ail_
        269s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && python3 tools/update_mani
         32s bash   for p in /tmp/probes/p297_*.py; do echo "=== $p ==="; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1; done
         26s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 2>&1 | ta
         18s bash   for p in /tmp/probes/p297_round_const.py /tmp/probes/p297_round_var.py /tmp/probes/p297_round_min.py /tmp/prob
         12s bash   cat > /tmp/probes/p297_round_default.py <<'EOF' def show(x=round(2.0**63)):     print(x) show() EOF cat > /tmp
         12s bash   cat > /tmp/probes/p297_round_arg.py <<'EOF' def show(x):     print(x) show(round(2.0**63)) EOF cat > /tmp/prob

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds a front-end `_constant_number` folder plus `_check_int64_round_constants` (threaded into the `abs` check) that refuses one-argument `round()` when the *final* module-scope map or a function's single-assignment map folds the argument to an out-of-int64 float. It also registers a test, DIFFERENCES row and DEVLOG entry.

**Defects (false compile-time refusals of valid programs).** The module-name map is built from the *final* value and ignores rebinding through `if`/`for`/`AugAssign`/`global`, so in-range calls are rejected. Base (`/tmp/base`) compiles and matches CPython for all five probes.

1. Call before a later module rebind (`r9_order.py`):
```
v = 2.5
print(round(v))
v = 2.0 ** 63
```
Expected CPython: `2`, exit 0. Actual HEAD: build fails on both builds, exit 2, `p.ail:2:7: int64 constant expression out of range: 9223372036854775808`.

2. Module rebind inside `if`/`for`/`AugAssign` (`r1_rebind_if.py`):
```
v = 2.0 ** 63
if True:
    v = 2.5
print(round(v))
```
Expected: `2`. Actual: compile refusal `p.ail:4:7: ... out of range` (exit 2). Identical failure for `r2_rebind_for.py` (expected `2`) and `r3_rebind_aug.py` (`v //= 2.0`, expected `4611686018427387904`), lines 4/4/3.

3. Module rebind through `global` in a called function (`r4_rebind_global.py`):
```
v = 2.0 ** 63
def reset():
    global v
    v = 2.5
reset()
print(round(v))
```
Expected: `2`. Actual: compile refusal at line 6, exit 2.

The DIFFERENCES row says only out-of-int64 values are refused and that runtime names keep the old trap; these in-range runtime values are refused instead.

**Pre-existing (not counted):** genuinely out-of-range `round(v)`/`round(2.0**63)` still traps on base (`r7_nested.py`: base `integer overflow` / `round() result does not fit ...`, HEAD now refuses by name — the intended fix), as does the runtime parameter/container route.

**Claims:** fixed first difference — verified (`r11_abs.py` refused by name on both builds; base trapped). Probe lists — sampled `p297_round_{attr,dict,arg,list,hi,huge}` all refused by name; `round_{min,inrange,inbound,lo,twoarg,shadow}` and `p297_shadow` all match CPython. `r_shadow_param` untouched — true. `test_ail_pre297` + `test_ail_safetynet` on HEAD: 2 modules, 0 failed (128s). `update_manifest --check` and `ci_shards --check`: pass. No-feature `program.c` from `--debug-dir` is byte-identical to base (only temp paths in `native_report.json` differ).

**Unverified:** speed (front-end only, no hot-path change; not measured).

VERDICT: FIX
1. `r9_order.py`: module-name map uses the final binding, so an earlier in-range `round(v)` is refused; expected `2`, got compile error `int64 constant expression out of range`.
2. `r1_rebind_if.py`, `r2_rebind_for.py`, `r3_rebind_aug.py`: rebinding a module constant through a nested/loop/AugAssign statement is ignored; expected `2`, `2`, `4611686018427387904`, got compile refusals (lines 4, 4, 3).
3. `r4_rebind_global.py`: a `global` reassignment performed by a called function is ignored; expected `2`, got compile refusal at line 6.
[cost $0.0161, opencode tokens {"total": 464123, "input": 31152, "output": 3709, "reasoning": 13262, "cache.write": 0, "cache.read": 416000}]
    tool time: bash 3.6 min, read 0.0 min
        130s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 test_ail_
         30s bash   date; cd /tmp/probes && for p in p297_round_min.py p297_round_inrange.py p297_round_inbound.py p297_round_lo.p
         18s bash   cd /tmp/rprobes && for p in r1_rebind_if.py r2_rebind_for.py r3_rebind_aug.py r4_rebind_global.py r7_nested.py
         14s bash   cd /tmp/rprobes && for p in r*.py; do echo "===== $p HEAD ====="; bash ~/tools/cmp.sh "$p" /home/runner/work/a
         14s bash   cd /tmp/rprobes && cat > r9_order.py <<'EOF' v = 2.5 print(round(v)) v = 2.0 ** 63 EOF cat > r10_func_shadow.p
          5s bash   cd /tmp/rprobes && cat > r11_abs.py <<'EOF' print(abs(round(-(2.0 ** 63)))) EOF cat > r12_abs_rebind.py <<'EOF
          3s bash   cd /tmp && rm -rf dbg_h dbg_b && mkdir dbg_h dbg_b && for d in dbg_h dbg_b; do wt=/home/runner/work/ail-ci/ail
          1s bash   cd /tmp/probes && for p in p297_round_attr.py p297_round_dict.py p297_round_arg.py p297_round_list.py p297_rou

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the false refusals by folding module constants only when they have a single module-scope store, a top-level assignment, and no `global` declaration. Rebound names now keep runtime/CPython behaviour; out-of-int64 single bindings are still refused by name.

- Probes (both builds): `p297r9_order`, `p297r1_rebind_if`, `p297r2_rebind_for`, `p297r3_rebind_aug`, `p297r4_rebind_global`, `p297r_rebind_routes`, `p297r_rebind_while` match CPython. `p297r_shadow_function`, `p297_round_const`, `p297_round_module`, `p297_round_local` refused by name. `p297_round_inrange`, `p297_round_twoarg`, `p297_round_shadow` match CPython.
- Tests on final commit: `test_ail_pre297`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 266s, 0 failed.
- `update_manifest.py --check`: pass. Commit `16a4314`.
[cost $0.0181, opencode tokens {"total": 751967, "input": 40814, "output": 4880, "reasoning": 11617, "cache.write": 0, "cache.read": 694656}]
    tool time: bash 5.4 min, write 0.0 min, edit 0.0 min
        268s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 test_ail_
         39s bash   cd /tmp/probes && for p in p297r9_order.py p297r1_rebind_if.py p297r2_rebind_for.py p297r3_rebind_aug.py p297r
         18s bash   cd /tmp/probes && for p in p297r9_order.py p297r1_rebind_if.py p297r2_rebind_for.py p297r3_rebind_aug.py p297r
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s write  /tmp/probes/p297r2_rebind_for.py
          0s bash   pwd; git status; git log --oneline -8; ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest check exit $?";
          0s write  /tmp/probes/p297r3_rebind_aug.py

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review complete.

## What the change does

`git diff work..HEAD` adds a compile-time numeric folder (`_constant_number`) and refuses a one-argument `round()` of a statically known float whose result leaves int64, by name; the same fold reaches `abs(round(...))`. It also stops folding a module constant that is stored more than once / non-top-level / declared `global`. No generated-C change. Report matches this, except its claim that user-bound `round` always matches CPython.

## Probes (HEAD vs `/tmp/base`)

| probe | HEAD | base | CPython |
|---|---|---|---|
| `p1_abs_round_shadow` (`def round(x): return 0.0; print(abs(round(2.0**63)))`) | **compile exit 2**, `int64 constant expression out of range` (both builds) | exit 0, matches | `0.0`, exit 0 |
| `p2_round_global_after` (call before a later `global` write) | runtime `integer overflow` | same | bignum, exit 0 |
| `p3_round_rebind_global_before` | matches | matches | matches |
| `p4_round_order_before_rebind` | matches | matches | matches |
| `p5_round_boundary_inrange` (`round(-(2.0**63))`, `2**62`, `2**63-1024`, half cases) | matches | matches | matches |

No-feature program: `program.c` identical between HEAD and base (only temp paths differ in `native_report.json`).

## Tests / records

- `test_ail_pre297 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 267 s, 0 failed (claim verified).
- `update_manifest.py --check`: pass. HEAD is `16a4314`.
- Speed not applicable: no emitted-code change.

## Claims

- Module-constant rebinding guard / single-store top-level / no `global`: **verified** (p3, p4; code).
- Out-of-int64 single bindings refused by name: **verified** (tests, p1 error).
- "A program that binds its own `round` still matches CPython": **false** for `abs(round(...))` (p1). The round guard checks `_binds_name('round')`, but the new abs fallback calls `_constant_number` which evaluates `round` as the builtin regardless.

## Pre-existing (identical on base, not blocking)

- Global-declared constant not written before the call still traps `integer overflow` (`p2`).
- Module `AnnAssign` constants and constants whose name is any parameter are not folded; they still trap.

VERDICT: FIX

1. The change introduces a false compile-time refusal when `round` is user-bound and its result reaches `abs()`. Probe (`/tmp/rprobes/p1_abs_round_shadow.py`):
```python
def round(x):
    return 0.0

def main():
    print(abs(round(2.0 ** 63)))

main()
```
Expected (CPython): `0.0`, exit 0. Actual on HEAD (both builds): exit 2, `p.ail:6:11: int64 constant expression out of range: 9223372036854775808`. Base matches CPython. Fix: `_check_int64_abs_constants` must not evaluate `round` via `_constant_number` when `round` is bound anywhere (mirror the guard in `_check_int64_round_constants`, or make `_constant_number` respect a `round` binding), and add this case to `test_ail_pre297.py`.
[cost $0.0232, opencode tokens {"total": 566936, "input": 41829, "output": 3880, "reasoning": 21899, "cache.write": 0, "cache.read": 499328}]
    tool time: bash 5.2 min
        269s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre297 tes
         19s bash   cd /tmp/rprobes && for p in p1_abs_round_shadow p2_round_global_after p3_round_rebind_global_before p4_round_o
         16s bash   cd /tmp/rprobes && for p in p1_abs_round_shadow p2_round_global_after p3_round_rebind_global_before p4_round_o
          2s bash   cd /tmp && rm -rf dbgH dbgB plain_head plain_base && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AI
          1s bash   tail -20 /tmp/nh.log; echo ===; cd /tmp && AIL_NO_CACHE=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/
          0s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir -p dbg_head dbg_base && cp /tmp/rprobes/r8_nofeature.py /tmp/nofe
          0s bash   cd /tmp && printf 'def add(a, b):\n    return a + b\n\nxs = [1, 2, 3]\nprint(add(len(xs), 4))\n' > /tmp/plain.
          0s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/ail_chatgpt.py compile --help 2>&1 | grep -i -

FINAL VERDICT: FIX  2026-10-26T20:32:56Z
