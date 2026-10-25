# job job-pre208-10252257  started 2026-10-25T13:57:58Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":466,"duration_api_ms":335,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":443,"duration_api_ms":320,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `af3f7ad` on `job-pre208-10252257`.

Reproduced `p4_scope` as `next = next` (also read-before-binding and `del` forms): both builds raised `NameError: name 'py_next' is not defined` (or compiler `KeyError`). Fixed by refusing those module-level builtin-shadow fallback shapes by name; ordinary rebinds still match CPython. `p8_edge` was not touched and still differs.

Probes after the change:
- Refused by name on both builds: `p4_self`, `p4_before`, `p4_before_fn`, `p4_del`, `p4_delafter`, `p4_del_then`, `p4_alias_del`.
- Match CPython on both builds: `p4_const`, `p4_c1`, `p4_def`, `p4_globalonly`.
- `p8_setgen` still shows the recorded pre-existing set/genexpr difference.

Tests on the final commit (`par_check.py -j 2`): `test_ail_pre208` 20.2s, `test_ail_safetynet` 104.0s, `test_ail_files` 103.2s, `test_ail_corpus_findings3` 162.8s — 4/4 passed. Manifest and `ci_shards` checks pass.
[cost $0.0000, opencode tokens {"total": 4303492, "input": 143637, "output": 13385, "reasoning": 31526, "cache.write": 0, "cache.read": 4114944}]
    tool time: bash 7.8 min
        268s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre208 test_ail_safetynet test_ail_files test_ai
         35s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p4_const.py <<'EOF' next = lambda xs: -1 print(next([1, 2])) EOF cat
         35s bash   cat > /tmp/probes/p4_c1.py <<'EOF' next = 3 print(next + 1) EOF cat > /tmp/probes/p4_c2.py <<'EOF' next = 3 x 
         20s bash   cd AIL_CURRENT && python3 -m unittest test_ail_pre208 -v 2>&1 | tail -15
         20s bash   cat > /tmp/probes/p4_scope_a.py <<'EOF' def main():     next = lambda x: x     g = (next(x) for x in range(2))
         18s bash   for p in /tmp/probes/p4_self.py /tmp/probes/p4_before.py /tmp/probes/p4_before_fn.py /tmp/probes/p4_del.py /tm
         18s bash   cat > AIL_CURRENT/test_ail_pre208.py <<'PY' """pre208: a module-level shadow of a built-in keeps Python's fall
         17s bash   cat > /tmp/probes/p4_before.py <<'EOF' print(next(iter([1]))) next = lambda x: 0 EOF cat > /tmp/probes/p4_befo

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds an AST pre-check in `shadowing.rename` (`AIL_CURRENT/python/pkg-v12/shadowing.py:316`, using `_find_load:250` and `_module_delete:281`) that refuses a module-level builtin shadow when the name is read before its first binding, read in its own RHS, or deleted. `p4_scope` (`next = next`) is now refused by name on both builds; base gives `NameError: py_next`. That part works, but the check has no scope analysis and rejects valid programs.

**Defects (new, base compiles and matches CPython):**

1. Parameter/local named like the shadow is treated as a fallback read.
```
def f(next):
    return next + 1
print(f(1))
next = lambda x: 0
print(next(1))
```
CPython/base stdout `2\n0\n`, exit 0; HEAD refuses both builds: `'next' ... is read before that binding`. Same for `fp_local.py` (local `next = 5; return next`) and `fp_comp.py` (comprehension variable `next`): base matches CPython, HEAD refuses.

2. Any module-scope `del` is refused even when nothing reads the builtin afterwards.
```
next = lambda x: 5
print(next([1]))
del next
```
CPython/base stdout `5\n`, exit 0; HEAD refuses with `but it is deleted`. Same for `fp_del_rebind.py` (delete, rebind, use): CPython/base `7\n`, HEAD refuses.

3. Dead-code reads are refused: `if False: print(next([1]))` before `next = ...`; base matches CPython (exit 0), HEAD refuses.

**Remaining same-cause differences (identical on base, listed as pre-existing):** closure `f = lambda: next(iter([1])); print(f()); next = ...` and indirect `g()->f()->next` still give `NameError: name 'py_next' is not defined` (CPython prints `1`); `next += 1` gives `NameError: next` where CPython raises `TypeError`. The fix is incomplete for these variants.

**Checks:** `test_ail_pre208` 21.1s, `test_ail_safetynet` 106.5s, `test_ail_builtin_shadowing` 11.0s: all pass. `update_manifest.py --check` rc 0; `ci_shards.json` has `test_ail_pre208`. Worker claim `p4_scope` verified; the `p8_edge` claim was not reproduced (my simple set/genexpr probes matched on both). No speed check needed.

VERDICT: FIX
1. Over-broad read-before-binding refusal: `_find_load` ignores local/parameter/comprehension bindings, rejecting `fp_param.py`/`fp_local.py`/`fp_comp.py` (expected `2\n0\n`, actual compile refusal).
2. Unconditional `del` refusal rejects `fp_del_last.py` (`5\n`) and `fp_del_rebind.py` (`7\n`), which base compiles and matches.
3. Dead-code (`if False:`) reads are refused although CPython never evaluates them (`gap_cond.py`).
[cost $0.0000, opencode tokens {"total": 464196, "input": 35538, "output": 3629, "reasoning": 10309, "cache.write": 0, "cache.read": 414720}]
    tool time: bash 3.3 min
        108s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         22s bash   cd /tmp/rprobes; for p in fp_class.py fp_comp.py fp_local.py fp_param.py gap_cond.py; do echo "===== BASE $p";
         17s bash   cd /tmp/rprobes cat > fp_del_last.py <<'EOF' next = lambda x: 5 print(next([1])) del next EOF cat > fp_del_reb
         15s bash   cd /tmp/rprobes; for p in gap_lambda2.py gap_indirect2.py fp_inner.py; do echo "===== BASE $p"; bash ~/tools/c
         15s bash   date; cd /tmp/rprobes; for p in *.py; do echo "===== HEAD $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runne
         11s bash   cd /tmp/rprobes cat > p4_scope.py <<'EOF' next = next print(next is not None) EOF cat > p8_setgen.py <<'EOF' s
          7s bash   cd /tmp/rprobes cat > gap_lambda2.py <<'EOF' f = lambda: next(iter([1])) print(f()) next = lambda x: 0 EOF cat
          0s bash   ls ~/tools; echo ---; cat ~/tools/cmp.sh | head -80; echo ---; git worktree add /tmp/base work 2>&1 | tail -3

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed in `079e2d1`.

- Made the built-in-shadow refusal scope-aware: parameters/locals/comprehension variables, reads after binding, `del` with no later read, and constant-false dead code now match CPython.
- Followed binding/`del` order, direct/indirect function and lambda calls, and aliases; added refusal for `del` before binding and `next += 1`.
- Probes matching CPython on both builds: `fp_param`, `fp_local`, `fp_comp`, `fp_del_last`, `fp_del_rebind`, `gap_cond`, `lambda_after`, `b_alias_valid`, `b_aug_valid2`, dead-code variants.
- Probes refused by name on both builds: `p4_scope`, `p4_del_read`, `gap_lambda`, `gap_indirect`, `after_del_fn`, `gap_aug`, `b_alias_before`, `b_ann_self`, `b_rich_reads`, `b_tuple_self`, `b_del_before`.
- Tests on final commit: `test_ail_pre208`, `test_ail_builtin_shadowing`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 passed (224s). `update_manifest.py --check` rc 0. `p8_edge` was not reproduced or touched.
[cost $0.0000, opencode tokens {"total": 2997675, "input": 88790, "output": 13381, "reasoning": 32528, "cache.write": 0, "cache.read": 2862976}]
    tool time: bash 10.0 min, edit 0.0 min
        225s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre208 test_ail_builtin_shadowing t
         60s bash   for p in /tmp/probes2/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/
         57s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_pre208 2>&1 | tail -30
         55s bash   mkdir -p /tmp/probes2 && cd /tmp/probes2 && cat > fp_param.py <<'EOF' def f(next):     return next + 1 print(f
         55s bash   cd /tmp/probes2 && cat > b_rich_reads.py <<'EOF' def f(x):     return x d = {"k": next} xs = [next] t = (next,
         32s bash   for p in b_tuple_self b_del_before b_aug_valid gap_aug fp_param fp_local fp_comp fp_del_last fp_del_rebind gap
         32s bash   for p in /tmp/probes2/b_*.py; do echo "===== HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" /home/runner/work/
         31s bash   for p in fp_param fp_local fp_comp gap_lambda gap_indirect after_del_fn lambda_after fp_del_last fp_del_rebind

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds a static AST pre-check (`_check_rebound_builtin_fallback` in `AIL_CURRENT/python/pkg-v12/shadowing.py:316`) that refuses a module-level builtin shadow when a load appears to resolve to the built-in before the first binding/after `del`; also widens `_HEAD` to augmented and tuple targets (not mentioned in the report).

**Verified report claims**
- `p4_scope` now refused by name on both builds (base gives `NameError: py_next`): verified.
- Parameter/local/comprehension shadows, `del` with no later read, delete-then-rebind, constant-false dead code match CPython: verified (`ok_param`, `ok_local`, `ok_comp`, `ok_del_last`, `ok_del_rebind`, `ok_dead`).
- `del` before binding and `next += 1` refused: verified (`ref_del_before`, `ref_aug`). Indirect call refusal verified (`ref_indirect`).
- `p8_edge` untouched: true by inspection.
- Tests: `test_ail_pre208` 57.5s and `test_ail_safetynet` 103.5s both pass (`-j 2`).
- Non-feature program: `--debug-dir` `program.c` byte-identical to base (only temp paths differ).

**Defects (new: base compiles and matches CPython, HEAD refuses)**
The binding tracker `_binding_effects` only models plain assign/def/class/delete and `if`/`while`. Bindings made by `for`, `try`, `with`, and `match` are invisible, so `bound` stays `False` and later reads are wrongly refused as built-in fallback:

1. `reg_for.py`
```
for next in [1, 2]:
    print(next)
next = 5
print(next)
```
Expected CPython/base `1\n2\n5\n`, exit 0. Actual HEAD both builds: refusal "read while Python still resolves it to the built-in".

2. `reg_try.py`
```
try:
    next = 5
except Exception:
    next = 6
print(next)
next = 7
```
Expected CPython/base `5\n`, exit 0. Actual HEAD: refusal at line 5.

3. `reg_with.py` (`with C() as next: print(next)` then `next = 8`) — expected CPython/base `4\n8\n`, exit 0; HEAD refusal at the `print`.

4. `reg_match.py` (`match 5: case next: print(next)` then `next = 9`) — expected CPython/base `5\n`, exit 0; HEAD refusal.

Fix: recognize `For`/`Try`/`With`/`Match` target bindings in `_binding_effects` (and keep the conservative handling of their branch/loop effects).

**Pre-existing (identical on base, not blocking):** `reg_for_read.py` (`for x in [1]: print(next)` before `next = 5`) differs on base too; refusal is acceptable. `p8_edge` untouched.

**Unverified:** the worker's extra test modules (`test_ail_builtin_shadowing`, `test_ail_files`, `test_ail_corpus_findings3`) were not re-run; no speed check (gdev programs do not shadow built-ins).

VERDICT: FIX
1. `reg_for.py` — expected `1\n2\n5\n` (exit 0), actual compile refusal.
2. `reg_try.py` — expected `5\n` (exit 0), actual compile refusal.
3. `reg_with.py` — expected `4\n8\n` (exit 0), actual compile refusal.
4. `reg_match.py` — expected `5\n` (exit 0), actual compile refusal.
[cost $0.0000, opencode tokens {"total": 400393, "input": 25196, "output": 2964, "reasoning": 13577, "cache.write": 0, "cache.read": 358656}]
    tool time: bash 2.7 min
        105s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         27s bash   cd /tmp/rprobes; for p in reg_for reg_try reg_match reg_with reg_for_read ok_containers ok_param ok_local ok_c
         18s bash   cd /tmp/rprobes; for p in reg_for reg_try reg_match reg_with reg_for_read; do echo "===== BASE $p"; bash ~/too
         11s bash   cd /tmp/rprobes cat > ok_containers2.py <<'EOF' def bump(x):     return x + 1 next = bump xs = [next] d = {"k"
          2s bash   cd /tmp/rprobes; cat > plain.py <<'EOF' def f(xs):     return [x * 2 for x in xs if x > 0] d = {"a": 1} print(
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ail_chatgpt.py compile --help 2>&1 | grep -i -A1 'de
          0s bash   grep -rn "p4_scope\|p8_edge" --include=*.py --include=*.md . | head -20; echo ---; sed -n 1,200p AIL_CURRENT/t
          0s bash   date; pwd; git log --oneline work..HEAD; echo ---; git diff --stat work..HEAD

FINAL VERDICT: FIX  2026-10-25T14:43:34Z
