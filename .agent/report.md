# job job-prog11-11020732  started 2026-11-01T22:44:14Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `b62a9eb` on `job-prog11-11020732`.

**Typed reach result (8 programs)**

| Program | Hot functions | Typed |
|---|---|---|
| t256, t058, g11_006 | `main` / `jacobi_step` | already |
| g11_030 | `count_paths`, `main` | **new** (annotated tuple module constants) |
| t404 | `main`, key lambda | **new** (tuple key in `min`/`max`) |
| t310 | `main`, helpers | follow-up: typed `iter()` + str `zip` |
| g25_006 | `main`, `describe` | follow-up: typed `Enum` methods |
| t388 | `main` | follow-up: typed `datetime` |

Full profile/status table with exact refusal messages: `lab/progfix/prog11.md`.

**Probes** (all match CPython on both `cmp.sh` builds; all five also pass `--strict`):
`prog11_tupkey_minmax.py`, `prog11_tupkey_default.py`, `prog11_tupkey_keys.py`, `prog11_tupmod.py`, `prog11_tupkey_nan.py` — cover tuple-key arity 1/2/3, ties, `default=`, empty `ValueError`, negatives, `-0.0`, NaN, str keys, and values via argument/list item/attribute/dict; annotated tuple, tuple-of-tuples, list-of-tuples and tuple-of-floats constants.

**Checks**
- All 10 `lab/compare` `main.ail` generated C files: byte-identical to base.
- Tests on final commit: `test_ail_prog11`, `test_ail_modconst`, `test_ail_tuples`, `test_ail_typed_tuples`, `test_ail_list_ops`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8/8 modules passed.
- `tools/update_manifest.py --check`: clean.
[cost $0.1101, opencode tokens {"total": 14165147, "input": 232980, "output": 27290, "reasoning": 28525, "cache.write": 0, "cache.read": 13876352}]
    tool time: bash 39.5 min, edit 0.0 min
        707s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_modconst test_ail_tu
        592s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_modconst test_ail_tu
        282s bash   cd /tmp/base11 && rm -rf /tmp/cmp11base && mkdir -p /tmp/cmp11base && for d in lab/compare/src/*/; do n=$(base
        255s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmp11cur && mkdir -p /tmp/cmp11cur && for d in lab/compare/src/*/
         88s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmp11final && mkdir -p /tmp/cmp11final && for d in lab/compare/sr
         60s bash   cd /tmp/base11 && rm -rf /tmp/cmp11base && mkdir -p /tmp/cmp11base && for d in lab/compare/src/*/; do n=$(base
         59s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmp11cur && mkdir -p /tmp/cmp11cur && for d in lab/compare/src/*/
         58s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/hyb11b && mkdir -p /tmp/hyb11b && for f in lab/census/programs/de

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review — job-prog11 (`b62a9eb`)

**What the change really does.** `tuplib.py` routes an `AnnAssign` whose value is a tuple / non-empty list of tuples through the unannotated `module_assign` tuple-constant lowering. `iterlower.py` splits a tuple-returning lambda key in a hoisted `min`/`max` into per-component values and compares them lexicographically with `<`/`>` + `==`. This matches the report.

**Report claims**
- t256 / t058 / g11_006 already typed — **verified** (`--strict` exit 0).
- g11_030 / t404 newly typed — **verified** (`--strict` exit 0; `test_ail_prog11` passes).
- t310 / g25_006 / t388 follow-up messages — **verified** exactly as quoted.
- Worker's 5 probes match CPython on both builds — **verified**.
- 10 `lab/compare` `main.ail` generated C byte-identical to base — **verified** (all 10).
- 8/8 test modules — **partially verified**: I re-ran `test_ail_prog11`, `test_ail_safetynet`, `test_ail_modconst`, `test_ail_tuples` (4/4 ok); did not re-run `test_ail_typed_tuples`, `test_ail_list_ops`, `test_ail_files`, `test_ail_corpus_findings3`.

**Probes** (`/tmp/rprobes11`, both `cmp.sh` builds; 28 probes). Correct on both builds: arity 1/2/3, ties, `default=`, empty `ValueError`, negatives, `-0.0`, NaN, str/bool/tuple components, nested/starred/empty tuple bodies, `range`/dict/listcomp/genexpr sources, annotated tuple/list-of-tuples (ints, floats, str, bool, `None`, nested, reassigned, default arg, class body, dict value), non-hoisted `min`/`max`.

**Pre-existing** (same on `/tmp/rbase`): tuple key containing `None` raises `TypeError` (p7, p22); scalar key that mutates the list during iteration crashes the default build (p12); unannotated tuple constant referenced by a function defined before it fails to compile (p23b).

**Defects**
1. **Tuple-key lowering changes CPython behaviour when the key mutates the source list.** Probe `/tmp/rprobes11/p13_tuple_mut.py`:
   ```python
   def main() -> None:
       xs = [5, 3, 1, 4, 2]
       print(min(xs, key=lambda v: (xs.pop(), v)))
       print(xs)
   main()
   ```
   Expected (CPython, and base both builds): stdout `1\n[5, 3]\n`, exit 0. Actual HEAD default build: stdout empty, stderr `list index out of range`, exit 1. The lowered index loop fixes `count = len(xs)` before the key runs and re-reads `xs[index]` instead of binding the yielded element; the general build still matches. Base passes this probe, so the change caused it.
2. **Regression for annotated tuple constants referenced before their definition** (named refusal): `/tmp/rprobes11/p23_forward.py`
   ```python
   def f() -> int:
       return X[0] + X[1]
   X: tuple[int, int] = (4, 5)
   print(f())
   ```
   Expected/base: `9`, exit 0. Actual HEAD both builds: `not in the subset: name 'X' is not defined`, build fails. (The unannotated form already fails on base, so this may be treated as an acceptable named refusal, but the annotated form worked before the change.)

VERDICT: FIX
1. Tuple key in `min`/`max` is not correct under mutation during iteration: `/tmp/rprobes11/p13_tuple_mut.py` expected `1\n[5, 3]` exit 0, actual default build stdout empty, stderr `list index out of range`, exit 1 (base passes).
2. Annotated tuple module constant used by a function defined earlier regressed from compiling (`9`) to a hard named refusal (`not in the subset: name 'X' is not defined`) in `/tmp/rprobes11/p23_forward.py`.
[cost $0.0544, opencode tokens {"total": 1965633, "input": 151970, "output": 9964, "reasoning": 33843, "cache.write": 0, "cache.read": 1769856}]
    tool time: bash 20.8 min
        588s bash   date; cd /home/runner/work/_temp/w2 && timeout 1500 python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_s
        195s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/dcur /tmp/dbase && mkdir -p /tmp/dcur /tmp/dbase && for d in lab/
         77s bash   cd /tmp/rprobes11 && for p in p*.py; do echo "===== $p"; timeout 300 bash ~/tools/cmp.sh $p /home/runner/work/
         51s bash   cd /tmp/rprobes11 && for p in p12_scalar_mut.py p13_tuple_mut.py p14_listcomp.py p15_pairs.py p16_bool.py p17_
         51s bash   cd /tmp/probes && for p in prog11_tupkey_minmax.py prog11_tupkey_default.py prog11_tupkey_keys.py prog11_tupmo
         43s bash   cd /tmp/rprobes11 && for p in p6_mutation.py p7_sideeffects.py p2_nested.py p3_emptytuple.py p4_starred.py p5_
         37s bash   cd /tmp/rprobes11 && for p in p12_scalar_mut.py p13_tuple_mut.py p14_listcomp.py p15_pairs.py p16_bool.py p17_
         33s bash   cd /tmp/rprobes11 && for f in /home/runner/work/_temp/w2/lab/census/programs/dev/t256.py /home/runner/work/_te

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `609b68c` on `job-prog11-11020732`.

Fixed:
- Tuple `min`/`max` keys now bind the yielded element before running the key, re-read `len()` each step, and keep the best element itself; popping the source matches CPython (`1`, `[5, 3]`).
- Component comparison checks `==` before `<`/`>`, as CPython tuple ordering does.
- Tuple module constants are registered before functions are lowered, so forward annotated and unannotated references compile (`9`).

Verified:
- New regression probes (`prog11_review_key_mut.py`, `prog11_review_forward_const.py`, `prog11_review_key_arg.py`): match CPython on both builds.
- 26 reviewer probes rerun: all pass except the pre-existing `None` tuple-key failures (`p7`, `p22`), unchanged from base.
- All 10 `lab/compare` `main.ail` generated C byte-identical to base.
- Required 8 test modules on final commit: **8/8 passed, 0 failed** (`test_ail_prog11`, `safetynet`, `modconst`, `tuples`, `typed_tuples`, `list_ops`, `files`, `corpus_findings3`).
[cost $0.0476, opencode tokens {"total": 3886249, "input": 108759, "output": 12826, "reasoning": 20536, "cache.write": 0, "cache.read": 3744128}]
    tool time: bash 38.3 min
       1052s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_safetyn
        447s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_safetyn
        314s bash   mkdir -p /tmp/probes && cat > /tmp/probes/prog11_review_key_mut.py <<'EOF' def main() -> None:     xs = [5, 3,
        186s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc_cur /tmp/cmpc_base && mkdir -p /tmp/cmpc_cur /tmp/cmpc_base 
        156s bash   cd /tmp/rprobes11 && for p in p13_tuple_mut.py p6_mutation.py p19_bump.py p23_forward.py p23b_forward_unann.py
         66s bash   python3 - <<'PY' from pathlib import Path p=Path('/home/runner/work/_temp/w2/AIL_CURRENT/python/pkg-v12/iterlo
         16s bash   cd /home/runner/work/_temp/w2 && git worktree add --detach /tmp/wb62 b62a9eb >/tmp/wt.log 2>&1 && cat /tmp/wt.
         11s bash   cd /home/runner/work/_temp/w2 && git worktree add --detach /tmp/wbbase ffe21df >/tmp/wt2.log 2>&1 && cat /tmp/

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** `tuplib.py` pre-registers module-level tuple constants before lowering functions and routes annotated tuple values through `module_assign`; `iterlower.py` lowers tuple-returning `min`/`max` key lambdas to lexicographic component comparisons with CPython's `==`-first order, re-reading `len()` and binding the element before the key. That matches the report.

**Probes:** 22 in `/tmp/rprobes`. Mutation, nested/single/3-component keys, `default`, `range`, dict/comprehension/argument/attribute/slice sources, NaN/`-0.0`, side effects, forward annotated/unannotated constants all match CPython on both builds. Two new regressions and one new crash, all absent on base.

**Claims checked:** tuple-key mutation fix verified (`q5`, `q17`); `==`-before-`<` verified for lowered keys (`q2`, `q15`) though `None` keys still fail identically on base (`q1`, pre-existing); forward constants verified (`q7`, `q8`, `g11_030`); all ten `lab/compare` `program.c` byte-identical (verified all ten); 8/8 test modules pass (verified, 479 s); t310/g25_006/t388 follow-up messages match exactly. The claim “both changes affect only programs that previously were refused” is **false**.

**Pre-existing:** `q1` tuple key containing `None` fails identically on base; `q9` rebinding an annotated tuple constant to another tuple returns the old value on base and head.

VERDICT: FIX
1. Rebinding a module tuple constant after a function captured it now silently returns the stale tuple. Probe `q10`: `def f()->int: return X[0]` / `X: tuple[int,int]=(4,5)` / `X=9` / print `f()`. Expected `TypeError 'int' object is not subscriptable`; actual on both builds `4`. Base matches CPython. Same with `global X; X=9` (`q20`: expected `TypeError ...`, actual `4`).
2. Deleting a module tuple constant now crashes the compiler. Probe `q21`: `def f()->int: return X[0]` / `X: tuple[int,int]=(4,5)` / `del X` / print. Expected `NameError name 'X' is not defined`; actual compilation fails with an uncaught `KeyError: 'X'` from `pyboxed2.py:4029 name_ref`. Base compiles and matches CPython. The unannotated variant (`q22`) was a named refusal on base but also crashes on HEAD.
[cost $0.0490, opencode tokens {"total": 3159096, "input": 98930, "output": 9057, "reasoning": 32741, "cache.write": 0, "cache.read": 3018368}]
    tool time: bash 7.2 min
        120s bash   cd /home/runner/work/_temp/w2 && nohup timeout 2400 python3 tools/par_check.py -j 2 test_ail_prog11 test_ail_s
         81s bash   cd /tmp && rm -rf /tmp/cA /tmp/cB && mkdir -p /tmp/cA /tmp/cB; for t in ticket_audit tree_fold rail_transfer s
         56s bash   cd /tmp/rprobes && for p in q*.py; do echo "===== $p"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/$p /home/r
         38s bash   cd /tmp && rm -rf /tmp/cmpA /tmp/cmpB && mkdir -p /tmp/cmpA /tmp/cmpB; for t in ticket_audit tree_fold echo_pa
         30s bash   cd /tmp/rprobes && for p in q13_starred.py q14_nanmax.py q15_tuple_component.py q16_dict_mutate.py q17_list_mu
         17s bash   cd /tmp/rprobes cat > q19_rebind_after.py <<'EOF' X: tuple[int, int] = (4, 5) X = 9  def f() -> int:     retur
         17s bash   cd /tmp/rprobes && for p in q1_none.py q10_ann_scalar_rebind2.py q9_ann_scalar_rebind.py q11_ann_nonnum.py; do
         14s bash   cd /tmp && for f in lab/corpus/programs/deepseek-v4.1-flash-free/t310.py lab/census/programs/gdev/g25_006.py l

FINAL VERDICT: FIX  2026-11-02T01:05:17Z
