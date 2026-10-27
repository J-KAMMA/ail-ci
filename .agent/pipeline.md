# job job-pre304-10270748  started 2026-10-26T22:49:44Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":388,"duration_api_ms":258,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":321,"duration_api_ms":194,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first pre-existing item from the rbrbfuzz28 review: class-body attributes can now read earlier class-body names, so `class C: x = 3; ys = [i for i in range(x)]` matches CPython through an instance, `C()`, inheritance and empty comprehensions. A comprehension body still does not see class locals, matching CPython.

- Commit: `2b7244d`
- Probes (both builds): 21 feature probes match CPython (`pre304_inst`, `call`, `instance_read`, `inherit`, `inherit_call`, `empty`, `comps`, `shadow_global`, `comp_body_global`, `arith`, `dup`, `later`, `routes`, `args`, `negative_bool`, `nested`, `class_read`, `alias`, `method`, `override`, `plain`); `pre304_comp_body_noglobal` is refused by name (`name 'x' is not defined`). Two exploratory probes (`lambda_global`, `array_entry`) hit unrelated pre-existing named refusals.
- Final-commit tests: `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 218 s, 0 failed.
- Additional class coverage: `test_ail_pre279`, `pre283`, `fuzz29`, `dunders`, `typed_inherit`, `virtual_dispatch` — 6 modules, 191 s, 0 failed.
- `tools/update_manifest.py --check` passes; DEVLOG and DIFFERENCES updated; not pushed.
[cost $0.0741, opencode tokens {"total": 8153466, "input": 155375, "output": 17018, "reasoning": 27793, "cache.write": 0, "cache.read": 7953280}]
    tool time: bash 13.9 min, edit 0.0 min, write 0.0 min
        277s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre304 test_ail_safetynet test_ail_files test_ai
        219s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre304 test_ail_safetynet test_ail_files test_ai
        193s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre279 test_ail_pre283 test_ail_fuzz29 test_ail_
         72s bash   cat > /tmp/probes/pre304_comps.py <<'PY' class C:     x = 3     a = [i for i in range(x)]     b = {i for i in 
         25s bash   mkdir -p /tmp/probes && cat > /tmp/probes/pre304_inst.py <<'PY' class C:     x = 3     ys = [i for i in range(
         24s bash   for p in /tmp/probes/pre304_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tail -120
         18s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import re p='AIL_CURRENT/python/pkg-v12/pyboxed2.py' s=
          2s bash   d=$(mktemp -d /tmp/dbg304XXXX); cp /tmp/probes/pre304_inst.py $d/p.py; cd $d; AIL_NO_CACHE=1 AIL_QUIET_FALLBAC

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** adds `Ctx.class_locals` (name → module slot) in `pyboxed2.py`, populated from the class's earlier `Assign`/`AnnAssign` attributes while compiling each class-attribute value (`_init_class_attrs`, lazy `_class_attr_value`, `C.attr` reads), and cleared after a comprehension's outermost iterable. Also drops the map's class body after that iterable. New `test_ail_pre304.py`, manifest/DEVLOG/DIFFERENCES/shard entries.

**Claims**
- Target fix (comprehension reading an earlier class attribute; instance, `C()`, inheritance, empty) — verified: base refuses `name 'x' is not defined`; HEAD matches CPython on both builds.
- Comprehension body does not see class names — verified (refused by name, both builds).
- 21 named probes / 4-module and 6-module test runs — not rerun (unverified); manifest `--check` passes; I reran `test_ail_pre304` + `test_ail_safetynet` on HEAD: 2 modules, 0 failed.
- "class-body attributes can now read earlier class-body names" — **overstated/false**: only earlier attribute assignments are mapped. Earlier methods/properties are still invisible, and a method that rebinds an earlier attribute name is ignored.

**Defect introduced by the change** (base refuses by name, which is acceptable; HEAD now compiles and is wrong):
1. A method/property that rebinds an earlier class attribute is ignored by `_class_attr_locals` (`pyboxed2.py:6611`), so later class-attribute expressions read the stale assignment instead of the function.
   Probe `/tmp/rprobes/method_shadows_attr_plain.py`:
   ```python
   class C:
       x = 3
       def x(self):
           return 9
       y = x + 1
   print(C().y)
   ```
   CPython: `TypeError: unsupported operand type(s) for +: 'function' and 'int'`, exit 1. HEAD (both builds): prints `4`, exit 0. Same with `ys = [i for i in range(x)]` → HEAD prints `[0, 1, 2]`, exit 0; CPython TypeError, exit 1.

**Pre-existing (identical on base and HEAD, not blocking):** calling an earlier function-valued attribute (`f = lambda…; g = f(3)`) refused by name; class name in a comprehension body (`xs`/`n`) refused; lambda body reading a class attr refused; nested class definitions refused; inherited name without a global refused. All are named compile-time refusals where CPython raises at run time.

**Other checks:** `--debug-dir` generated C is byte-identical to base for a no-class-attr program and a class with attrs but no cross-name references. No runtime/hot-path change; speed not measured (compile-time only).

**Unverified:** worker's own 21 probes, `test_ail_files`/`test_ail_corpus_findings3`, full suite, speed.

VERDICT: FIX
1. `_class_attr_locals` ignores method/property rebindings of an earlier class attribute. Probe `/tmp/rprobes/method_shadows_attr_plain.py` (and `method_shadows_attr.py`): expected CPython `TypeError`, exit 1; actual HEAD both builds prints `4` (`[0, 1, 2]`), exit 0. Base refused by name, so the change introduced this wrong output.
[cost $0.0194, opencode tokens {"total": 750255, "input": 37012, "output": 5131, "reasoning": 14480, "cache.write": 0, "cache.read": 693632}]
    tool time: bash 3.9 min, write 0.0 min, read 0.0 min
        105s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_pre3
         40s bash   cd /tmp && for p in /tmp/rprobes/lambda_default.py /tmp/rprobes/fstring_str.py /tmp/rprobes/list_attr_iter.py 
         33s bash   for p in /tmp/rprobes/method_shadows_attr.py /tmp/rprobes/method_shadows_attr_plain.py /tmp/rprobes/lambda_sco
         29s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/method_shadows_attr.py /tmp/rprobes/method_shadows
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== HEAD $(basename $p)"; bash ~/
          7s bash   cd /tmp/rprobes && rm -rf dbg_h dbg_b && mkdir dbg_h dbg_b && for w in h b; do if [ $w = h ]; then W=/home/run
          0s bash   git worktree add /tmp/base work >/dev/null 2>&1; echo base=$?; mkdir -p /tmp/rprobes; date
          0s bash   python3 - <<'PY' class C:     x = 3     ys = [i for i in range(x)] print(C().ys) class D:     x = 3     ys = [

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect in commit `dd40ef3` (branch `job-pre304-10270748`): class-body names are now built from statement order, and a method/property rebinding an earlier attribute is refused by name instead of reading the stale slot or a same-named global. Added regression cases to `test_ail_pre304.py`.

Probes (`bash ~/tools/cmp.sh`, both builds):
- Refused by name as intended (CPython raises TypeError): `pre304rev_method_plain`, `pre304rev_method_comp`, `pre304rev_property`, `pre304rev_static_class`, `pre304rev_global_same_name` — 5/5.
- Match CPython: `pre304rev_method_before_attr`, `pre304rev_rebind_after_method`, `pre304rev_method_after_use`, `pre304rev_unrelated_method`, `pre304rev_inherited_method` — 5/5.
- Existing `pre304_*` probes: all unchanged, except `pre304_array_entry` which was already an invalid probe (defines `main()` without calling it). 

Final-commit tests: `test_ail_pre304`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 236 s, 0 failed. `tools/update_manifest.py --check` passes.
[cost $0.0256, opencode tokens {"total": 1074469, "input": 92411, "output": 7391, "reasoning": 7371, "cache.write": 0, "cache.read": 967296}]
    tool time: bash 6.6 min
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre
         74s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PW
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304rev_*.py; do echo "===== $(basename $p)"; bas
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304rev_*.py; do echo "===== $(basename $p)"; bas
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/method_shadows_attr_plain.py /tmp/rprobes/method_s
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304rev_global_same_name.py /tmp/probes/pre304rev
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail
          0s bash   cd /home/runner/work/ail-ci/ail-ci && cat /tmp/probes/pre304_array_entry.py; echo ====; bash ~/tools/cmp.sh /t

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** `pyboxed2.py` adds `Ctx.class_locals` (earlier class-body binding → module slot), populated in statement order while compiling each class-attribute value (`_init_class_attrs`, lazy `_class_attr_value`, `C.attr` reads), cleared after a comprehension's outermost iterable; a method/property rebinding a name becomes `None`, so a later attribute reading it is refused by name. New `test_ail_pre304.py`, shard/manifest/DEVLOG/DIFFERENCES rows.

**Target fix verified:** p01 (instance, `C()`, inherited, empty) base refuses `name 'x' is not defined`, HEAD matches CPython on both builds. p02 (list/dict/instance-attribute routes, then via argument/list/attr/dict), p13, p14, p28, p30, p31 match.

**Review-0 defect fixed:** p07 (method rebinds earlier attr, same-named global) now refused by name on both builds; base printed `101` (wrong). p08 method/attr ordering, p24, p27, p06, p09, p10, p20–p23 match CPython. The 10 worker `pre304rev_*` probes reproduce exactly: 5 refused, 5 matching.

**No-feature C unchanged:** `--debug-dir` `program.c`/`program_mix0.c` byte-identical to base for p11 and p12 (only temp paths in `native_report.json` differ).

**Claims:** statement-order map — verified; method/property refusal — verified; 5/5 + 5/5 probe split — verified; original `pre304_*` probes unchanged — verified (only pre-existing `array_entry` and `lambda_global` refusals, identical on base); 4-module 236 s/0-failed — runs pass (pre304+safetynet 103 s, files+corpus_findings3 169 s, 0 failed); exact timing/count — unverified; `update_manifest.py --check` — verified rc 0.

**Pre-existing (identical on base, not blocking):** p18 `def m(self, a=x)` reads global `x` not class `x`; p05 nested-comprehension body `x` refused; p15 lambda-call/nested-class refusals; `pre304_array_entry` main-never-called refusal.

**Unverified:** speed (compile-time-only change; generated C for non-feature programs identical, so not measured).

VERDICT: ACCEPT
[cost $0.0310, opencode tokens {"total": 1512223, "input": 71048, "output": 6708, "reasoning": 20195, "cache.write": 0, "cache.read": 1414272}]
    tool time: bash 9.2 min
        170s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        105s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre304 tes
         72s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304_*.py; do out=$(bash ~/tools/cmp.sh "$p" "$PW
         60s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p0*.py /tmp/rprobes/p1[0-4]*.py; do echo "===== $(
         48s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; bash ~/tool
         35s bash   cd /tmp/rprobes && cat > p16_enclosing.py <<'EOF' def mk():     x = 7     class C:         y = x + 1         x
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre304rev_*.py; do out=$(bash ~/tools/cmp.sh "$p" "
          8s bash   cd /tmp/rprobes && cat > p30_multifor.py <<'EOF' x = 100 class C:     x = 3     ys = [i for i in range(x) for 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T00:54:19Z
