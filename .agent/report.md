# job job-pre250-10260445  started 2026-10-25T19:46:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":397,"duration_api_ms":279,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":384,"duration_api_ms":267,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing difference from the pre208 review: `for x in [1]: print(next)` before `next = 5` used to give `NameError: name 'py_next' is not defined` (general path) or print only `5` (default), where CPython reads the built-in in the loop.

The shadowing pass now refuses a module-level built-in-shadow read by name at compile time when Python still resolves it to the built-in. The scan is execution-order aware: deferred function/lambda bodies, constant-false branches, `for`/`try`/`with`/`match` bindings, parameters/locals/comprehensions, `del`, and augmented assignments.

Records: new DIFFERENCES row, DEVLOG entry, manifest pins, shard entry. Commits: `fa69a38`, `c7bec38` (not pushed).

Probes: 30 `/tmp/probes/p250_*` programs run on both builds. Target cases match CPython or are refused by the named shadowing error; `p8_edge` matches. Two pre-existing lambda/indirect-call-before-binding variants still differ and were not fixed. No speed check.

Final-commit tests (`-j 2`, commit `c7bec38`): `test_ail_pre250`, `test_ail_builtin_shadowing`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 passed (185s). `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0000, opencode tokens {"total": 5468285, "input": 92389, "output": 42648, "reasoning": 0, "cache.write": 0, "cache.read": 5333248}]
    tool time: bash 12.5 min, edit 0.0 min
        215s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
        186s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         77s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p250_*.py; do echo "===== $(basename $p)"; bash ~/t
         75s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p250_*.py; do echo "===== $(basename $p)"; bash ~/t
         55s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         54s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/test_ail_pre250.py && python3 tools/update_manifest.
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for n in p250_for_bind p250_with_bind p250_match_bind p250_try_bind p250
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p250_*.py; do echo "===== $(basename $p)"; bash ~/t

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** before renaming a module-level builtin shadow to `py_<name>`, a new AST walk (`shadowing.py:_check_rebound_builtin_fallback`) refuses any module-level load of that name that occurs before the first recognized binding, and the head prefilter now also matches augmented assignments. The reported `for x in [1]: print(next)` case is fixed by refusal (base: general path `NameError: py_next`, default prints only `5`; HEAD: named refusal on both builds). Records, manifest and shard entries are consistent.

**Claims:** report facts (commits, tests, manifest/shard checks, the recorded difference) verified. "Execution-order aware" is false in the cases below: the scan over-approximates evaluation (all `and`/`or`/comparison operands, dead code) and does not model walrus bindings.

**Defects**

1. Walrus bindings are not recognised, so a read that is after the binding is refused with a false message. Probe `/tmp/rprobes/r20_walrus_if.py`:
```
if (next := 5):
    print(next)
next = 6
print(next)
```
Expected (CPython, and base on both builds): `5\n6`, exit 0. Actual HEAD: compile refusal `... the name is read while Python still resolves it to the built-in ...` (both builds). Same for `/tmp/rprobes/r11_walrus_bind.py`, `r12_walrus_del_rebind.py`, `r13_walrus_comp.py` (all matched on base).

2. Loads in short-circuited/non-evaluated operands are treated as reads. Probe `/tmp/rprobes/r15_shortcircuit_or.py`:
```
x = True or next
next = 5
print(x, next)
```
Expected: `True 5`, exit 0 (base: same on both builds). Actual HEAD: refusal. Same for `r16` (`False and next`), `r17` (`1 == 2 < next`).

3. Dead code after `break` is treated as a read. Probe `/tmp/rprobes/r18_while_break_dead.py`:
```
while True:
    break
    print(next)
next = 5
print(next)
```
Expected: `5`, exit 0 (base: same on both builds). Actual HEAD: refusal.

These are change-caused regressions of previously correct programs (base matches CPython on both builds); the refusal text is also factually wrong in 1–3.

**Pre-existing (identical on base, not blocking):** `r2` (non-constant false branch), `r3` (empty `for` target), `r7` (`try` raises before the binding) still produce `NameError: py_next` on both base and HEAD; the same-cause fix is therefore partial.

**Tests:** `test_ail_pre250 test_ail_builtin_shadowing test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 5/5 pass on HEAD (`-j 2`, 188s). `update_manifest.py --check` and `ci_shards.py --check` pass. C output for two non-shadowing programs is byte-identical to base.

**Unverified:** full suite (not run by design), speed (compile-time-only change; no runtime codegen difference), the worker's 30 `/tmp/probes` not re-run. The new test module has no walrus/short-circuit/dead-code case.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1440732, "input": 56977, "output": 5620, "reasoning": 30551, "cache.write": 0, "cache.read": 1347584}]
    tool time: bash 4.8 min
        189s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         23s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/r{1,2,3,4,5,6,7,8,9,10}_*.py; do echo "###
         12s bash   cd /tmp/base && for p in /tmp/rprobes/r1[5-9]_*.py; do echo "##### BASE $(basename $p)"; timeout 240 bash ~/to
         11s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/r1[5-9]_*.py; do echo "##### HEAD $(basena
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/r1[1-4]_*.py; do echo "##### HEAD $(basename $p)";
         10s bash   cd /tmp/base && date && for p in /tmp/rprobes/r{1,2,3,7}_*.py; do echo "##### $(basename $p)"; timeout 240 bas
          8s bash   cd /tmp/base && for p in /tmp/rprobes/r1[1-3]_*.py; do echo "##### BASE $(basename $p)"; timeout 240 bash ~/to
          5s bash   cd /tmp/base && for p in /tmp/rprobes/r4_lambda_kwdefault.py /tmp/rprobes/r5_class_body_before.py; do echo "##

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects in `shadowing.py` (commit `c091b67`):

- Walrus bindings (including comprehension walrus and delete/rebind) now count as bindings.
- Short-circuited `and`/`or`/chained-comparison operands that are never evaluated are not scanned.
- Code after `break`/`continue`/`raise` is not scanned.
- Reads that genuinely reach the built-in before binding are still refused by name.

Probes (both builds; `bash ~/tools/cmp.sh`):
- Reviewer r11-r18, r20: 9/9 match CPython.
- `p250_walrus_{bind,if,del_rebind,comp,call,arg,list,attr,dict}`: 9/9 match.
- `p250_sc_{or,and,chain,chain_true,nested}`: 5/5 match.
- `p250_dead_{break,continue,raise}`: 3/3 match.
- `p250_live_after_if_read` (real early read): refused by name on both builds.
- r19 was replaced by `p250_dead_raise` with `ValueError`, because `raise SystemExit` is refused earlier for an unrelated pre-existing reason.

Tests: `test_ail_pre250 test_ail_safetynet test_ail_files test_ail_corpus_findings3 test_ail_builtin_shadowing` — 5/5 pass (`-j 2`, 219s); `test_ail_pre250` and `test_ail_safetynet` re-run on the commit, 2/2 pass (82s). `update_manifest.py --check` and `ci_shards.py --check` pass. Added the regression cases to `test_ail_pre250.py`; DEVLOG and the DIFFERENCES row updated.

Not covered: a read before a later walrus in the *same* statement is conservatively skipped rather than refused; r3/r7 remain the reviewer's pre-existing non-blocking cases.
[cost $0.0000, opencode tokens {"total": 1747526, "input": 54496, "output": 9049, "reasoning": 15501, "cache.write": 0, "cache.read": 1668480}]
    tool time: bash 5.8 min, edit 0.0 min
        220s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
         84s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         42s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/cmpout && ls /tmp/probes/p250r_*.py /tmp/probes/p250_w*.py
          2s bash   cat > /tmp/probes/p250_dead_raise.py <<'EOF' try:     if True:         raise ValueError("stop")         print(
          0s bash   cd /tmp/cmpout && for f in *.log; do n=${f%.log}; first=$(grep -m1 '^cpython exit' "$f"); g=$(grep -m1 '^g exi
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_p

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** `shadowing.py` now refuses, by name, any module-level load of a built-in-shadowing name before its first recognized binding (and after `del`), using a new execution-order-ish AST scan; `_HEAD` also recognizes augmented assignments. The recorded `for x in [1]: print(next)` case is indeed fixed by refusal (base: `NameError: py_next` / default prints only `5`; HEAD: named refusal on both builds).

**Defects (change-caused false refusals; all match CPython and base on both builds):**

1. Loop `else` is scanned even when `break` makes it unreachable. Probe `p_for_else_break`:
```
for i in [1]:
    break
else:
    print(next)
next = 5
print(next)
```
Expected CPython/base: `5`, exit 0. Actual HEAD: compile refusal (`... read while Python still resolves it to the built-in ...`) on both builds. Same for `p_while_else_break`.

2. `assert` message that is never evaluated is scanned. Probe `p_assert_true_msg`:
```
assert True, next
next = 5
print(next)
```
Expected: `5`, exit 0. Actual HEAD: refusal.

3. `try` body always raises, so `else` never runs, but is scanned. Probe `p_try_else_raise`:
```
try:
    raise ValueError("x")
except ValueError:
    pass
else:
    print(next)
next = 5
print(next)
```
Expected: `5`, exit 0. Actual HEAD: refusal.

4. Comprehension element never evaluated because the iterable is an empty literal. Probe `p_empty_comp`:
```
xs = [next for i in []]
next = 5
print(xs, next)
```
Expected: `[] 5`, exit 0. Actual HEAD: refusal.

**Claims:** Verified: main case fixed (`r1`: HEAD refusal, base `py_next` NameError); `r11`–`r18`, `r20` all match CPython on both builds; `test_ail_pre250 test_ail_safetynet` pass (`-j 2`, 87s); `update_manifest.py --check` and `ci_shards.py --check` pass. Records/DIFFERENCES/DEVLOG present.

**Pre-existing, not blocking:** `r3` (empty `for` target) and `r7` (`try` raises before binding) remain mismatches on base; I did not re-run them.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_builtin_shadowing`; speed (compile-time-only change); full suite (by design).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 708986, "input": 43576, "output": 4070, "reasoning": 17500, "cache.write": 0, "cache.read": 643840}]
    tool time: bash 2.8 min
         88s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         25s bash   date; cd /home/runner/work/ail-ci/ail-ci; for n in r11_walrus_bind r12_walrus_del_rebind r13_walrus_comp r14_w
         21s bash   date; cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/revout/head; for f in p_for_else_break p_while_else_br
         19s bash   git -C /tmp/base log --oneline -1; date; cd /tmp/base; mkdir -p /tmp/revout/base; for f in p_for_else_break p_
          6s bash   cat > /tmp/rprobes/p_walrus_same_stmt.py <<'EOF' print(next, (next := 5)) EOF date; cd /home/runner/work/ail-c
          5s bash   date; cd /home/runner/work/ail-ci/ail-ci; echo HEAD-r1; timeout 120 bash ~/tools/cmp.sh /tmp/rprobes/r1_for_re
          3s bash   cat > /tmp/rprobes/p_match_live.py <<'EOF' match 5:     case _:         print(next) next = 6 print(next) EOF d
          2s bash   cd /tmp/revout/head && cat p_match_guard_false.log | head -40; echo ====; cd /home/runner/work/ail-ci/ail-ci &

FINAL VERDICT: FIX  2026-10-25T20:31:20Z
