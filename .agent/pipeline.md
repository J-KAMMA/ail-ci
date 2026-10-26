# job job-pre275-10262319  started 2026-10-26T14:21:34Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":546,"duration_api_ms":432,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":502,"duration_api_ms":389,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first still-differing case: `def take(x=1e300): print(int(x)); take()` reproduced on both builds (exit 1 `integer overflow`; CPython prints the bignum). A new front-end check refuses a statically known finite float outside int64 before C emission with `int64 constant expression out of range`, including through defaulted parameters, module/local constants, aliases, list/dict literal items, class attributes and arguments. `r_kw_attr` was not needed for the first case and was left alone.

Probes in `/tmp/probes` (19, both builds):
- Refused by name: `p275_default`, `p275_default_expr`, `p275_literal`, `p275_negative`, `p275_boundary_hi`, `p275_boundary_min_out`, `p275_expr`, `p275_module_local`, `p275_routes` (argument route).
- Refused by the existing builtin-shadow rule: `p275_shadow`.
- Match CPython: `p275_boundary_hi_in`, `p275_boundary_min`, `p275_in_range`, `p275_override`, `p275_default_unused`, `p275_nonfloat`, `p275_dict_dup`, `p275_nan`, `p275_nan_inf`.
- List-item, attribute and dict-value routes are covered individually by `test_ail_pre275.py` (the combined route probe stops at its first refusal).

Final commit `c132cb4` (implementation `97e6bfc`). Tests on the final commit: `test_ail_pre275`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 158 s, 0 failed. `tools/update_manifest.py --check` passes.
[cost $0.0683, opencode tokens {"total": 6625888, "input": 141149, "output": 15363, "reasoning": 30976, "cache.write": 0, "cache.read": 6438400}]
    tool time: bash 9.5 min, edit 0.0 min
        208s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre275 test_ail_safetynet test_ail_files test_ai
        159s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre275 test_ail_safetynet test_ail_files test_ai
         76s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre275 test_ail_safetynet 2>&1 | tail -50
         29s bash   cd /tmp/probes && for f in p275_*.py; do out=$(bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci 2>&1);
         29s bash   cd /tmp/probes && for f in p275_*.py; do echo "### $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-
         22s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_
         21s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/ail_chatg
          8s bash   cat > /tmp/probes/default_print.py <<'EOF' def take(x=1e300):     print(x)   take() EOF cat > /tmp/probes/defa

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: pre275 `int(<big float>)` refusal

**What the diff really does:** adds a front-end AST pass `_check_int64_int_float_constants` (ail_chatgpt.py:1174-1297, called at :1574) that folds constant numeric expressions into `int(...)` and raises the existing `int64 constant expression out of range` error for finite floats outside ±2**63; adds `test_ail_pre275.py`, registers it, and logs the change. This is broader than the report admits: the fold is unsound for dict keys and for shadowed class names.

**Probes (both builds, `/tmp/rprobes`, `cmp.sh`)**
- Original case `r_orig.py`: base → `integer overflow` (exit 1), HEAD → compile refusal; CPython prints the bignum. Fix works.
- In-range, boundary, bool index, list mutation/aliasing, dict mutation/aliasing, list-item/attribute/dict simple routes: match CPython (`r_in_range_expr`, `r_list_bool`, `r_list_mutate`, `r_dict_mutate`, `r_dict_bool`, …).
- Worker's 19 `p275_*` probes reproduce their classifications; `p275_shadow` is the same builtin-shadow refusal on base.
- C unchanged: `g00_000.py` `program.c` byte-identical base vs HEAD.
- Tests: `test_ail_pre275`, `test_ail_safetynet` → 2 modules, 0 failed (82 s). `update_manifest.py --check` passes.

**Defects (new, caused by the change; base matches CPython)**
1. Dict key resolution assumes equal keys must have the same type. Probe `/tmp/rprobes/r_dict_mixed1.py`: `print(int({1: 1e300, 1.0: 2.0}[1]))` — CPython/base print `2`; HEAD refuses: `p.ail:1:7: int64 constant expression out of range: too large`. Same for `r_dict_mixed2.py`, `r_dict_mixed3.py`, `r_dict_knownfloatkey.py`, `r_dict_mixed4.py`. Python treats `1 == 1.0 == True` as one key; the fold keeps the earlier `1e300` because `type(candidate) is type(key)` fails.
2. Dict key resolution skips non-constant keys that can collide with the subscript key. Probe `/tmp/rprobes/r_dict_dynkey.py`: `def f(K): print(int({1: 1e300, K: 2.0}[1]))` / `f(1.0)` — CPython/base print `2`; HEAD refuses (same message). A `None` key from `**` is skipped the same way.
3. Attribute folding ignores shadowing by a parameter. Probe `/tmp/rprobes/r_attr_param.py`: `class Box: v = 1e300` / `class Other: v = 1.0` / `def main(Box): print(int(Box.v))` / `main(Other)` — CPython/base print `1`; HEAD refuses `p2.ail:10:11: int64 constant expression out of range: too large`. The `Attribute` branch of `_constant_number` reads global `classes` without checking that the name is shadowed.

**Claims check**
- Fixed the first differing case: **verified**.
- Refuses through defaults/constants/aliases/list/dict/attribute/argument: **verified for simple routes, false for the dict-key and shadowed-attribute cases above**.
- In-range floats and compiling programs unchanged / "no new defect": **false** (defects 1–3).
- `r_kw_attr` left alone: consistent with the diff.
- Tests and manifest: **verified** for `test_ail_pre275` + `test_ail_safetynet`; `test_ail_files`/`test_ail_corpus_findings3` not run (review rules say not to run them).
- Dead uncalled default (`r_dead_default.py`) is refused while base prints `ok`; I treat that as the sanctioned compile-time refusal, not a blocker.

**Pre-existing:** class-attribute assignment (`r_class_mutate*`) already fails on base with `AttributeError`; `p275_shadow` refusal is identical on base. Not counted.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; instruction-count speed (front-end-only change, no runtime hot path edited).

VERDICT: FIX
1. Dict-literal folding keeps an earlier out-of-range value when a later equal key has a different numeric type (`/tmp/rprobes/r_dict_mixed1.py`: expected `2`, actual compile refusal `int64 constant expression out of range`). Require constant keys of a type that Python considers equal, or refuse to fold when key types differ.
2. Dict-literal folding ignores unknown/`**` keys that can replace the subscript key (`/tmp/rprobes/r_dict_dynkey.py`: expected `2`, actual compile refusal). Only fold when every key is constant and no key can alias the subscript.
3. Attribute folding ignores parameter shadowing (`/tmp/rprobes/r_attr_param.py`: expected `1`, actual compile refusal). Check the attribute base name against the function-local `known` map before using `classes`.
[cost $0.0265, opencode tokens {"total": 1478443, "input": 27692, "output": 7099, "reasoning": 22980, "cache.write": 0, "cache.read": 1420672}]
    tool time: bash 3.1 min, write 0.0 min
         83s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_pre2
         29s bash   cd /tmp/probes; ls p275_*.py | wc -l; for f in p275_*.py; do r=$(bash ~/tools/cmp.sh "$f" /home/runner/work/ai
         13s bash   cd /tmp/rprobes; date; for f in r_*.py; do echo "### $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ai
         11s bash   cd /tmp/rprobes; date; for f in r_dict_mixed1.py r_dict_mixed2.py r_dict_mixed3.py r_dict_mixed4.py; do echo "
         10s bash   cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "=== $wt"; for f in r_list_mutat
          9s bash   cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "=== $wt"; for f in r_attr_param
          7s bash   cd /tmp/rprobes; date; for f in r_class_mutate.py r_class_mutate_fn.py r_dead_default.py; do echo "### $f"; ba
          6s bash   cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "=== $wt"; for f in r_dict_dynke

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `20a5dae`.

- Dict folding now uses Python key equality (`1 == 1.0 == True`) and does not fold literals with dynamic/`**` keys.
- Attribute folding now ignores class names shadowed by parameters, locals, lambda/comprehension targets, class-body names, or enclosing scopes.
- Added regression coverage to `test_ail_pre275.py`.

Verification: 15 `p275r_*` probes plus the reviewer's 22 `r_*` probes match CPython or are refused by name; 2 remaining probes match the pre-change base exactly. Final tests: `test_ail_pre275`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 168 s, 0 failed. `update_manifest.py --check` passes.
[cost $0.0282, opencode tokens {"total": 1257081, "input": 75699, "output": 10385, "reasoning": 11829, "cache.write": 0, "cache.read": 1159168}]
    tool time: bash 10.5 min, edit 0.0 min, read 0.0 min
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
        168s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
        160s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         43s bash   cd /tmp/rprobes && for f in r_*.py; do echo "### $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail-ci
         35s bash   cd /tmp/probes && for f in p275r_*.py; do printf '%s: ' "$f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-c
         28s bash   cd /tmp/probes && for f in p275r_*.py; do echo "### $f"; bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail
          8s bash   cd /tmp/probes && for f in p275r_attr_classbody.py p275r_dict_star.py p275r_attr_nested.py; do echo "### base 
          6s bash   cd /tmp/probes && cat > p275r_attr_comprehension.py <<'EOF' class Box:     v = 1e300   class Other:     v = 1.

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of `20a5dae` (3 commits, 6 files)** — started 15:00, ended 15:13.

**What the change really does:** adds a front-end pass `_check_int64_int_float_constants` that folds numeric constants through literals/arithmetic/names/defaults/list/dict/class-attribute routes and refuses a statically known `int(float)` outside int64 with `int64 constant expression out of range`; it also adjusts its own constant folder for Python dict-key equality, dynamic/`**` keys, and class names shadowed in the current scope. Codegen is untouched (`program.c` identical to base on an in-range probe).

**Defects**

1. Compiler crash (unguarded compile-time string/bytes repetition). Probe `/tmp/rprobes/strdos/p.ail`:
```python
print(int("x" * 2**40))
```
Expected: the base compiles this (exit 0); at worst a named refusal. Actual on HEAD (both builds, run under `ulimit -v 2000000`): Python traceback ending `MemoryError` at `ail_chatgpt.py:994` in `_constant_number` (`return left * right`), exit 1. Without the limit it attempts a ~1 TB allocation. `_constant_number` folds `str`/`bytes` constants and performs `*` on them without any size guard, unlike the int and class-attribute paths.

2. Unsound "lambda target" shadowing — false refusal of an in-range program. Probe `/tmp/rprobes/q9_nested_lambda.py`:
```python
class Box:
    v = 1e300

class Other:
    v = 1.0

g = lambda: (lambda Box: int(Box.v))(Other)
print(g())
```
Expected: CPython and the base both print `1`. Actual HEAD (both builds): `p.ail:9:26: int64 constant expression out of range: too large`. The `walk` Lambda branch only calls `check` on its body and never recurses, so the inner lambda's `ast.arg Box` never enters `shadowed`; the checker folds the module class `Box.v = 1e300` even though the runtime value is `1.0`. The report's claim that lambda targets are handled is false for nested lambdas (same result inside a function, `/tmp/rprobes/q10_lambda_in_func.py`).

**Pre-existing (identical on base, not blocking)**
- `/tmp/probes/p275r_attr_classbody.py` and `p275r_attr_comp_global.py`: `integer overflow` on both HEAD and base.
- `r_class_mutate*`, `q2_class_mutate`: base exits 1 `AttributeError`; HEAD now refuses by name (not a regression).
- `r_kw_attr.py` and `q1/q3/q4/q12`: already refused/differing on base for other reasons.

**Claims**
- Dict equality (`1 == 1.0 == True`) and dynamic/`**` keys: verified (probes `r_dict_*`, `p275r_dict_*`).
- Attribute shadowing: verified for parameters, locals, direct lambdas, comprehension targets, class-body names and enclosing scopes; **false** for nested lambdas (defect 2).
- Primary task: `p_default.py` is now refused by name; `r_kw_attr.py` was already refused on base, so no second difference remained. Verified.
- "15 `p275r_*` + 22 `r_*` probes": ran them; 2 `p275r_*` differ identically to base, remainder match or are refused. Only 20 files exist in `/tmp/rprobes`, so the count is slightly off.
- Tests: `test_ail_pre275`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (0 failed); `update_manifest.py --check` exits 0. Verified.

**Unverified**
- CPython oracle for the 1 TB repetition probe (would OOM); compile-only comparison used.
- No runtime benchmark/icount: no emitted-code change (C identical).
- Wider suite not run, per instructions.

VERDICT: FIX
1. `print(int("x" * 2**40))`: expected compile/refusal without a traceback (base compiles); actual `MemoryError` traceback in `_constant_number`.
2. `g = lambda: (lambda Box: int(Box.v))(Other); print(g())`: expected `1` (CPython and base); actual compile-time refusal `int64 constant expression out of range: too large` because nested-lambda shadowing is not tracked.
[cost $0.0438, opencode tokens {"total": 1109804, "input": 74272, "output": 5789, "reasoning": 43759, "cache.write": 0, "cache.read": 985984}]
    tool time: bash 6.0 min
        133s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_fil
         83s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         46s bash   cd /tmp/rprobes && for f in r_*.py; do out=$(timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/ail
         37s bash   cd /tmp/probes && for f in p275r_*.py; do out=$(timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/work/ail-ci/
         13s bash   cd /tmp/rprobes && for f in q1_class_cond.py q2_class_mutate.py q3_globals_call.py q4_nested_class.py q5_dead_
          8s bash   cd /tmp/rprobes && for f in r_class_mutate.py r_class_mutate_fn.py r_dead_default.py; do echo "##### $f BASE";
          7s bash   cd /tmp/rprobes && cat > q11_inrange.py <<'EOF' V = 1e18   class Box:     v = 1.5   def f(x=2.5):     return i
          6s bash   cd /tmp/rprobes && cat > q9_nested_lambda.py <<'EOF' class Box:     v = 1e300   class Other:     v = 1.0   g =

FINAL VERDICT: FIX  2026-10-26T15:13:22Z
