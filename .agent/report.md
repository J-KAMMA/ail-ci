# job job-pre255-10260535  started 2026-10-25T20:38:01Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":513,"duration_api_ms":396,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":528,"duration_api_ms":411,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `89d450d`.

- Reproduced the first pre227-review item: `N=2**62; xs=[N]; class C: X=xs[0]*4` printed the CPython bignum but both builds stopped with `integer overflow`.
- Fix: `fold_constants` now refuses class-level arithmetic using a list item, attribute or dict value by name on both builds; method bodies and non-route arithmetic are unchanged.
- Probes: list/dict/attribute, in-range, empty, nested/argument, string route refused by name; non-route class arithmetic, route arithmetic outside a class, and direct module name match CPython. Class-local rebinding and class-body import remain pre-existing/refused separately.
- Tests: `test_ail_pre255`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 3213268, "input": 100723, "output": 9624, "reasoning": 24777, "cache.write": 0, "cache.read": 3078144}]
    tool time: bash 5.4 min, edit 0.0 min
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         17s bash   cd /tmp/probes && cat > pre255_inrange_list.py <<'EOF' N = 2**61 xs = [N] class C:     X = xs[0] * 2 - 1 print
         17s bash   grep -o '.\{0,500\}already present before that job.\{0,1500\}' /home/runner/work/_temp/work0.jsonl | head -5
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre255_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PW
         16s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > pre255_list.py <<'EOF' N = 2**62 xs = [N] class C:     X = xs[
          5s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre255 2>&1 | ta
          3s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import ast, pathlib hits=[] for p in pathlib.Path('.').
          1s bash   cd /home/runner/work/ail-ci/ail-ci && cat .agent/task.md; echo ===; grep -o '.\{0,300\}pre227.\{0,500\}' /home

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete (time used ~13 min).

**What the change does:** adds an AST pre-scan in `fold_constants` that raises a named `SyntaxErrorAIL` for any class-body assignment value containing a `BinOp`/`UnaryOp` with a `Load` `Subscript`/`Attribute` anywhere beneath it; codegen is otherwise untouched.

**Claims:**
- Reproduced the recorded case: verified (base both builds `integer overflow`, CPython bignum).
- Direct list-item/dict/attribute forms now refused by name on both builds: verified.
- In-range, empty and string routes also refused: verified (in-range/`strsub`; empty/nested via the new test).
- Non-route class arithmetic, route arithmetic outside a class, method body: verified unchanged vs base.
- "Without descending into … lambdas": **false**. A lambda used as an expression value (`handlers = [lambda xs: xs[0] * 4]`) is walked and refused. The `Lambda` guard only applies to a statement, which cannot be a lambda.
- "Class-local rebinding/class-body import pre-existing": verified (`name 'X' is not defined` on base and HEAD).
- Tests (`test_ail_pre255`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) and `update_manifest.py --check`: verified, 0 failed, rc 0.

**Pre-existing (identical on base, not blocking):** method-body bignum arithmetic (`values[0]*4` via `f(xs[0])`) overflows; route arithmetic in a method default (`x=xs[0]*4`) overflows; class-level call argument (`mul4(xs[0])`) overflows; walrus assignment `(X := xs[0]*4)` drops the attribute; lambda-call probes hit the pre-existing `RecursionError`.

**Defect**

1. Over-broad lambda refusal: a deferred lambda body is not a class-level constant, yet the new scan refuses it. Base compiles and matches CPython; HEAD refuses.
```
class C:
    handlers = [lambda xs: xs[0] * 4]
print(C.handlers[0]([2]))
```
Expected (CPython and base, both builds): `8`, exit 0. Actual (HEAD, both builds): exit 2, `not in the subset: a class-level constant built through a list item, attribute or dict value`. Same for `table = {"f": lambda xs: xs[0] * 4}; print(C.table["f"]([2]))`. Related over-broad case: `class C: X = "abc".upper() * 2` (base `ABCABC`) is also refused because the method attribute is scanned. Fix: prune `Lambda` (and call-attribute) subtrees in `_class_route_arithmetic`/`_class_body_expressions`.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 752850, "input": 41592, "output": 5821, "reasoning": 22173, "cache.write": 0, "cache.read": 683264}]
    tool time: bash 5.5 min
        188s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         31s bash   cd /tmp/rprobes && date && for p in exact.py inrange.py smallattr.py dictsmall.py strsub.py indirect.py noarit
         18s bash   cd /tmp/rprobes && cat > iftest.py <<'EOF' N = 2**62 xs = [N] class C:     if xs[0] * 4:         X = 1 print(C
         16s bash   cd /tmp/rprobes && date && for p in *.py; do echo "===== $p HEAD"; bash /home/runner/tools/cmp.sh "$p" /home/r
         12s bash   cd /tmp/rprobes && date && for p in lambda_ok.py staticlambda.py lambda_arg.py func_arg.py; do echo "===== $p 
         10s bash   cd /tmp/rprobes && cat > lambdalist.py <<'EOF' class C:     handlers = [lambda xs: xs[0] * 4] print(C.handlers
          9s bash   cd /tmp/rprobes && date && for p in default.py methodbody.py exprstmt.py; do echo "===== $p BASE"; bash /home/
          9s bash   cd /tmp/rprobes && date && for p in lambdasub.py strmeth.py intattr.py; do echo "===== $p BASE"; bash /home/ru

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the over-broad class-route scan in `AIL_CURRENT/ail_syntax.py:782`: it now prunes deferred `Lambda` bodies and excludes a call's attribute callee (including its receiver) while still scanning call arguments.

Committed as `c35df58` on `job-pre255-10260535`.

Probes (both builds):
- Refused by name: list/dict/attribute out-of-range, in-range, negative, empty, nested class, builtin-call argument.
- Match CPython: lambda-in-list, lambda-in-dict, `"abc".upper() * 2`, `["xyz"][0].upper() * 2`, non-route class arithmetic, route arithmetic outside a class.
- Pre-existing unchanged: method-body/module-level bignum overflow, lambda-call `RecursionError`.

Final-commit tests (`-j 2`): `test_ail_pre255`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 162s. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 564889, "input": 29893, "output": 4183, "reasoning": 7933, "cache.write": 0, "cache.read": 522880}]
    tool time: bash 6.2 min, edit 0.0 min
        164s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre255 test_ail_sa
        164s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && timeout 1500 python3 tools/p
         46s bash   cd /tmp/probes && for p in pre255_*.py; do echo "===== $p"; bash /home/runner/tools/cmp.sh "$p" /home/runner/w
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -8 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_syntax.py AIL_CURRENT/test_ail_pre255.py AIL_CUR
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import pathlib entry = """## 2026-10-25 - pre255 fix: p
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import re, pathlib p = pathlib.Path('AIL_CURRENT/ail_sy

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a class-body pre-scan in `fold_constants` that refuses (named `SyntaxErrorAIL`) arithmetic using a `Load` list item / attribute / dict value, prunes deferred `Lambda` subtrees, and ignores a call's attribute callee while still scanning its arguments. Codegen is otherwise untouched.

**Claims**
- Recorded case reproduced: base both builds `integer overflow`, CPython `18446744073709551616` — verified (`p1`).
- List/dict/attribute out-of-range, in-range, negative, builtin-argument routes now refused by name on both builds — verified (`p1`–`p4`, `p11`, `p23`, `p24`).
- Deferred lambda in list/dict, string method, list-receiver method now match CPython on both builds — verified (`p9`, `p10`, `p25`, `p26`).
- Non-route class arithmetic and route arithmetic outside a class unchanged; method bodies unchanged — verified (`p7`, `p8`, `p13`).
- Two commits, `Co-Authored-By` present; manifest `--check` rc 0 — verified.
- Tests on HEAD: `test_ail_pre255`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed — verified.
- Non-feature programs: `program.c` identical to base in both builds (`p7`–`p9`) — verified.
- "Nested class refused" is true, but the base also refused it (different message); not a new capability.

Intentional broadening: in-range routes that previously matched are now refused (`p4`, `p16` `A.n * 4`); this is permitted by the task and documented in the new DIFFERENCES row.

**Pre-existing (identical on base, non-blocking):** method-body/direct/max-module bignum overflow (`p13`, `p17`, `p33`); `d.get(...) * 4`, `max(xs) * 4`, `xs.pop() * 4` overflow (`p14`, `p15`, `p21`); lambda-default/immediate-lambda `RecursionError` (`p12`, `p31`, `p32`); pure-constant class overflow refusal (`p18`), generator-expression refusal (`p27`).

**Unverified:** whether this was literally the first item of the pre227 list (the list is absent from the supplied task); the prior review already verified the recorded case.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 817382, "input": 45641, "output": 5514, "reasoning": 16403, "cache.write": 0, "cache.read": 749824}]
    tool time: bash 6.2 min
        134s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; t
         81s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre255 test_
         35s bash   date; cd /tmp/rprobes && for p in p14_dict_get p15_max_list p16_attr_class p17_direct_class p18_pure_const_cla
         31s bash   cd /tmp/rprobes && cat > p31_lambda_immediate.py <<'EOF' N = 2**62 xs = [N] class C:     X = (lambda: xs[0] * 
         29s bash   date; cd /tmp/rprobes && for p in p1_list_oob p4_inrange p5_if_route p6_if_after_func p7_plain_class p9_lambda
         17s bash   date; cd /tmp/rprobes && for p in p1_list_oob p2_dict_oob p3_attr_oob p4_inrange p5_if_route p6_if_after_func 
         17s bash   date; cd /tmp/rprobes for p in p7_plain_class p8_no_class p9_lambda; do   for m in g d; do     for wt in head 
         16s bash   cd /tmp/rprobes && cat > p29_callarg_receiver_route.py <<'EOF' N = 2**62 xs = [N] def f(v):     return v class

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T22:04:31Z
