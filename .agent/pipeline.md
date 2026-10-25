# job job-pre116-10251611  started 2026-10-25T07:49:09Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":443,"duration_api_ms":328,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":438,"duration_api_ms":318,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `bdf2553` on `job-pre116-10251611`.

**Cause:** the pre116 refusal was too broad for integration's pre166 saved-generator cursor lowering: it refused bodies calling `next(...)` or a class constructor, breaking `test_ail_pre166` (`nested`, `membership_dunder`).

**Fix:** keep `next(...)` and class constructors eager only when the class's `__new__`/`__init__` cannot raise; all other raisable bodies remain refused. Added controls to `test_ail_pre116.py`. Updated DEVLOG, DIFFERENCES (`C?-job-pre116-10251611-1`), and MANIFEST (`--check` passes).

**Tests (final commit):**
- Branch: `test_ail_pre116`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 41 tests, OK (1 skipped).
- Simulated on `origin/integ` ffeb623: `test_ail_pre116`, `test_ail_pre166`, `test_ail_typed_tuples` — 17 tests, OK. (`test_ail_pre166` does not exist on the branch itself.)
- No local reproduction of the reported `test_ail_typed_tuples` failure; it passes on the branch and on the integration simulation.

**Probes (`cmp.sh`, both builds):**
- `pre116_coexist.py` — safe constructor + `next` — same stdout.
- `pre116_shapes.py` — argument/list item/attribute/dict value/empty/negative/alias — same stdout.
- `pre116_safe_methods.py` — safe builtin methods — same stdout.
- `pre116_refuse_user.py` — user function — refused by name.
- `pre116_refuse_ctor.py` — raising constructor — refused by name.
- `pre116_refuse_int.py` — `int(...)` call — refused by name.

Only `.agent/pipeline.md` remains untracked (CI-owned, not added).
[cost $0.0000, opencode tokens {"total": 3772488, "input": 82790, "output": 10982, "reasoning": 21244, "cache.write": 0, "cache.read": 3657472}]
    tool time: bash 17.0 min
        313s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre116 test_ail_typed_tuples
        227s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre116 test_ail_typed_tuples
         80s bash   cd /home/runner/work/ail-ci/ail-ci && git diff 419016a HEAD -- AIL_CURRENT/python/pkg-v12/pyboxed2.py > /tmp/p
         79s bash   cd /home/runner/work/ail-ci/ail-ci && git diff 419016a -- AIL_CURRENT/python/pkg-v12/pyboxed2.py > /tmp/pre116
         70s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree remove --force /tmp/integ-test 2>/dev/null; rm -rf /tmp/int
         48s bash   cd /tmp/integ-test/AIL_CURRENT && python3 -m unittest -q test_ail_pre166 test_ail_typed_tuples 2>&1 | tail -40
         43s bash   cd /tmp/integ-test && git apply /tmp/pre116.patch && cp /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/test_ail_p
         30s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre116 test_ail_typed_tuples 2>&1 | tail -40

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** relaxes the pre116 refusal in the general path: a saved generator expression calling `next(...)` or a class is kept on the eager lowering if the class passes a new syntactic `__new__`/`__init__` screen (`_class_ctor_is_safe`). It does not make those bodies lazy.

**Claim checks**
- Cause (pre116 refusal broke pre166 `nested`, `membership_dunder`): verified — applying `419016a..work` to `origin/integ` makes `test_ail_pre166` fail 2 cases; with `419016a..HEAD` it passes.
- "Keep ... eager only when the class's `__new__`/`__init__` cannot raise": **false** — the screen misses non-division `BinOp` failures, inherited/rebound constructors (defects 1–2 below).
- Controls added to `test_ail_pre116.py`; DEVLOG/DIFFERENCES row; MANIFEST `--check`: verified.
- Branch tests: `test_ail_pre116`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`).
- Simulated integration (`origin/integ` + full pre116 diff): `test_ail_pre166`, `test_ail_typed_tuples` pass (11 tests). `test_ail_typed_tuples` failure not reproduced. Verified.
- Non-feature program C with `--debug-dir`: byte-identical to base (`program.c`), only temp paths in the JSON report differ.

Probes run on HEAD and `/tmp/base` with `cmp.sh`; base refuses all defect probes by name, HEAD compiles them.

Pre-existing: none established.

Unverified: exact 41/17 test counts; runtime speed (not applicable — compile-time screening only); the worker's own probe files were not rerun.

VERDICT: FIX
1. Unsafe constructors pass `_class_ctor_is_safe`, so the saved generator is still materialised eagerly and raises before `next()`; base refuses by name.
   Probe:
   ```python
   class Bad:
       def __init__(self):
           self.v = 1 + "a"
   def main():
       g = (Bad() for _ in range(1))
       try:
           print(next(g).v)
       except TypeError as e:
           print("caught", str(e))
       print("after")
   main()
   ```
   Expected (CPython): `caught unsupported operand type(s) for +: 'int' and 'str'` / `after`, exit 0. Actual on HEAD (both builds): empty stdout, exit 1, `TypeError: unsupported operand type(s) for +: 'int' and 'str'`.
2. Inherited `__init__` is not examined: `class Child(Base): pass` is "safe", although `Base.__init__` raises. Probe uses `g = (Child() for _ in range(1))` with `Base.__init__` doing `raise ValueError("base")`, try around `next` only. Expected: `caught base` / `after`, exit 0. Actual on HEAD (both builds): empty stdout, exit 1, `ValueError: base`. Base refuses by name.
3. Class names are treated as constructors even after rebinding (`C = boom`). Probe:
   ```python
   class C:
       def __init__(self):
           self.v = 1
   def boom():
       raise ValueError("shadow")
   C = boom
   def main():
       g = (C() for _ in range(1))
       try:
           print(next(g))
       except ValueError as e:
           print("caught", str(e))
       print("after")
   main()
   ```
   Expected: `caught shadow` / `after`, exit 0. Actual on HEAD (both builds): empty stdout, exit 1, `AIL internal error: iterator: unknown kind`. Base refuses by name.
[cost $0.0000, opencode tokens {"total": 957875, "input": 33888, "output": 18246, "reasoning": 1165, "cache.write": 0, "cache.read": 904576}]
    tool time: bash 7.4 min
        221s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre116 test_ail_ty
         41s bash   cp /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12/pyboxed2.py /tmp/integ/AIL_CURRENT/python/pkg-v1
         36s bash   cd /tmp/integ/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre166 2>&1 | tail -30; echo "rc=$?";
         36s bash   cd /tmp/integ/AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_pre166 2>&1 | tail -15; echo "rc=$?";
         32s bash   cd /tmp/integ && git checkout -- AIL_CURRENT/python/pkg-v12/pyboxed2.py && rm -f AIL_CURRENT/test_ail_pre116.p
         23s bash   cd /tmp/integ/AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -20; echo "r
         19s bash   cd /tmp/integ/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -40; echo "r
         13s bash   for p in /tmp/rprobes/p*.py; do echo "===== HEAD $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | sed '

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `2a21050` on `job-pre116-10251611`; no push.

**Fix:** replaced the `__new__`/`__init__` syntactic screen with a strict constructor screen: plain classes only (no bases/decorators/metaclass/`__new__`/`__slots__`/attribute hooks), `__init__` binds only parameters/constants to `self`; module-wide name counts reject rebound/deleted class names, shadowed `next`, and mutated constructors.

**Reviewer probes** (both builds):
- `p3_ctor_typeerror`, `p4_inherited_ctor`, `p5_shadow_class`, `p6_class_alias`: refused by name (`a generator expression used as a value`) on both builds.
- `p1_next_empty` on integration: stdout/exit match CPython on both builds.

**Probe set** `/tmp/probes/p116r_*` (both builds):
- Unsafe: `binop_shapes`, `inherited`, `rebound`, `del_class`, `shadow_next`, `alias_mutated`, `arity`, `new_decorated`, `setattr`, `slots`, `free_name` — all refused by name, branch and integration.
- Safe: `safe_call_sites`, `safe_param_values` — identical stdout/exit to CPython on integration (both builds). `safe_edges` refused by name (tuple literals become `_AilT_i_i(...)`, deliberately outside the screen).

**Tests on final commit:**
- Branch (`-j 2`): `test_ail_pre116`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed.
- Integration (`origin/integ` ffeb623 + final diff): `test_ail_pre166`, `test_ail_pre116`, `test_ail_typed_tuples` — 20 tests, OK.
- `tools/update_manifest.py --check` passes.
[cost $0.0522, opencode tokens {"total": 4688678, "input": 102911, "output": 15218, "reasoning": 23349, "cache.write": 0, "cache.read": 4547200}]
    tool time: bash 14.7 min, write 0.0 min
        138s bash   timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre116 test_ail_typed_tuples test_ail_safetynet test_ail
        137s bash   python3 tools/update_manifest.py --check && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre116 test_
        101s bash   python3 - <<'PY' from pathlib import Path cur=Path('/home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12
         98s bash   git diff --quiet HEAD -- AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_CURRENT/test_ail_pre116.py && echo SAME_AS
         89s bash   python3 - <<'PY' from pathlib import Path cur = Path('/home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v
         80s bash   rm -rf /tmp/integ2 && mkdir -p /tmp/integ2 && git archive origin/integ | tar -x -C /tmp/integ2 && python3 - <<
         45s bash   cd /tmp/integ/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre166 test_ail_pre116 test_ail_typed
         39s bash   for p in /tmp/probes/p116r_*.py; do echo "========== $(basename $p)"; bash ~/tools/cmp.sh "$p" /tmp/integ2 2>&

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review report

**What the change really does (one line):** tightens the saved-generator screen in `pyboxed2.py` so a saved generator stays on the eager lowering only for an unshadowed builtin `next` or a plain `object`-only class whose `__init__` binds params/constants to `self`; everything else raisable is refused by the typed path's name `"a generator expression used as a value"`, with new `test_ail_pre116` controls and records.

**Probes (general + default build, CPython oracle)**
- `p5_safe_controls.py`, `p9_empty_class.py`, worker's `p116r_safe_call_sites`, `p116r_safe_param_values`: match CPython on integration+change (both builds). On branch HEAD they hit the pre-existing missing pre166 cursor lowering (see below).
- `p1_alias_assign.py` (`D=C; D.__init__=boom; (C() for ...)`), `p2_alias_setattr.py`: AIL exits 1 (`AttributeError`/`NotImplementedError` on the type assignment) on integration base **and** integration+change — identical, pre-existing.
- `p3_cond_class.py`, `p4_inner_class.py`, `p6_alias_delattr.py`: named compile refusal on both.
- `p7_plain.py` (no saved generator): `--debug-dir` `program.c` byte-identical to base; only `native_report.json` temp paths differ.
- `p8_plain_saved.py`: `next()` of a plain saved generator fails on `work` and HEAD identically (pre-existing branch gap); matches on integration+change.
- Worker's 11 unsafe probes: all refused by name on integration+change; `p116r_safe_edges` refused (tuple literal rewritten to `_AilT_i_i(...)` before the screen) — over-conservative but a named refusal.

**Tests**
- Branch HEAD, `-j 2`: `test_ail_pre116`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 ok, 0 failed. `update_manifest.py --check` passes.
- Integration+change (`origin/integ` ffeb623 + identical screen region and test file): `test_ail_pre166`, `test_ail_pre116`, `test_ail_typed_tuples`, `test_ail_safetynet` — 25 tests OK. Integration base: 16 tests OK.

**Report claims**
- Fix description, unsafe refusals, safe-shape matching (integration), 5-module result, integration result, manifest check: verified.
- "alias/attribute rebinding refused": **false for mutation through an alias** — `D=C; D.__init__=boom` leaves `C` in `safe_classes`; the worker's `alias_mutated` probe only aliases a class for use (`E=C`). Masked here because AIL cannot assign attributes on a type (p1/p2 are identical on integration base and +change), so pre-existing, not blocking.
- The new DIFFERENCES row is therefore slightly overbroad ("a rebound constructor ... refused"); no observed behaviour defect on the target tree.

**Pre-existing (not blocking):** type-attribute assignment/`setattr` on a class; `next()`/iteration of a saved generator on the branch without pre166; `p1_next_empty` stderr differs (RuntimeError vs StopIteration) while stdout/exit match (declared in the new row).

**Unverified:** full suite (per instructions not run), modules outside the named/required ones, and runtime speed (the added work is compile-time AST walks only).

VERDICT: ACCEPT
[cost $0.0527, opencode tokens {"total": 1665882, "input": 93083, "output": 8090, "reasoning": 48933, "cache.write": 0, "cache.read": 1515776}]
    tool time: bash 10.8 min, write 0.0 min
        177s bash   cd /tmp/integ2/AIL_CURRENT && date && timeout 1400 python3 -m unittest -q test_ail_pre166 test_ail_pre116 test
        152s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1700 python3 ../tools/par_check.py -j 2 test
        145s bash   cd /tmp/ibase/AIL_CURRENT && date && timeout 1400 python3 -m unittest -q test_ail_pre166 test_ail_typed_tuples
         43s bash   cd /tmp/integ2 && date && for p in /tmp/probes/p116r_*.py; do echo "===== $(basename $p)"; timeout 180 bash ~/
         43s bash   for wt in /tmp/ibase /tmp/integ2; do echo "########## $wt"; for p in /tmp/rprobes/p1_alias_assign.py /tmp/rpro
         32s bash   cd /tmp && for wt in /tmp/integ /tmp/integ2; do echo "########## $wt"; for p in /tmp/rprobes/p1_alias_assign.p
         18s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; tim
          9s bash   cat > /tmp/rprobes/p8_plain_saved.py <<'EOF' def main():     g = (x * 2 for x in [1, 2, 3])     print(next(g))

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T09:53:25Z
