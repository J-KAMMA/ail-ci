# job job-prog30-11021835  started 2026-11-02T09:41:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `6e08fd6` on `job-prog30-11021835`.

- Profiled all 8 programs; 5 are now typed: `g11_022`, `g09_034`, `g02_012`, `t244`, `t266`.
- Fixed `t266` by lowering local `it = iter(seq)` / `next(it)` to an index cursor in `iterlower.py` (`main` 40.5%, `dfs` 15.6%).
- Found and fixed a silent wrong-output bug in already-typed `t244`: `nested_lists.py` freed a hoisted comprehension temp before its `extend` consumer.
- 3 remain general with recorded exact reasons: `g23_004` (comprehension tuple targets), `g03_008` (function-valued parameter), `t172` (dict of dicts / generator unpacking).
- `lab/progfix/prog30.md`, DEVLOG, and one DIFFERENCES row added; `lab/compare` generated C is byte-identical 10/10.
- `test_ail_prog30` (13 tests) passes; targeted modules plus `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass (95 tests across the two runs).
- Probes in `/tmp/probes/p30_*` match CPython stdout/exit on both `cmp.sh` builds; only the uncaught exhausted-cursor stderr name differs (`list index out of range` vs `StopIteration`), recorded as `C?-job-prog30-11021835-1`.
[cost $0.2480, opencode tokens {"total": 16537537, "input": 1081423, "output": 28189, "reasoning": 37845, "cache.write": 0, "cache.read": 15390080}]
    tool time: bash 36.0 min
       1199s bash   cd /home/runner/work/_temp/w2 && timeout 3600 python3 -m unittest AIL_CURRENT.test_ail_prog30 AIL_CURRENT.test
        196s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 -m unittest test_ail_nested_lists test_ail_l
        188s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc/cur /tmp/cmpc/base && for t in berth_s
         77s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 -m unittest AIL_CURRENT.test_ail_prog30 -v 2>&1 | tail -
         64s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_prog3
         54s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p30_iter_empty.py /tmp/probes/p30_iter_exhausted.py /tmp
         52s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_prog3
         52s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_prog3

## review 0
[model opencode-go/deepseek-v4.1-flash]
# Review: job-prog30 (commit `6e08fd6`)

**What the change really does (one line):** `iterlower.py` lowers a proven-simple local `it = iter(seq)` + `next(it)` (list/str/bytes) to an index cursor, and `nested_lists.py` marks a hoisted comprehension temp `_ail_synth` so `_last_use_free_points` keeps it until return. Matches the report.

## Defect

1. **Augmented-assignment target is reordered past `next`.** The order guard (`next_chain`/`before_safe`) vets the receiver and arguments of a call but never the *target* of an `AugAssign`. CPython evaluates `a[index()] += rhs` as target (including `index()`) then RHS; the rewrite hoists the cursor read before the whole statement. A target expression that mutates the iterator source therefore produces different output.

Probe `/tmp/rprobes/aug_target.py`:
```python
def main() -> None:
    items = [10, 20, 30]
    it = iter(items)
    a = [0, 0]
    a[items.pop(0) % 2] += next(it)
    print(a, items)
main()
```
CPython / general build / base default: `[20, 0] [20, 30]`
HEAD default build: `[10, 0] [20, 30]`

This is introduced by the change (base compiled this program general and matched CPython). Fix: refuse the lowering when an `AugAssign` target may run code (or hoist after target evaluation).

## Report claims

- **Verified:** commit `6e08fd6`; `t266` now typed with an index cursor (`program.c` shows `_il1_i`); `t244` base output is wrong and HEAD matches CPython; `g11_022`/`g09_034`/`g02_012`/`t244`/`t266` typed, `g23_004`/`g03_008` general, `t172` refused by the recorded message; 10/10 `lab/compare` generated C byte-identical to `work`; `test_ail_prog30`, `test_ail_nested_lists`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pool_iter_capture`, `test_ail_str_iter_fast` all pass (7 modules, 0 failed).
- **Incomplete:** the claim that no effectful evaluation happens before `next` omits augmented-assignment targets (defect 1).
- **Documented difference:** exhausted cursor prints `list index out of range` instead of `StopIteration` on stderr; stdout/exit match. Consistent with `C?-job-prog30-11021835-1`.
- **Probes I ran:** `aug_target` (fails), `iter_shadow`, `iter_mutate`, `iter_assign_order`, `iter_extend`, `iter_dictval`, `iter_str_alias`, `iter_bytes_alias`, `iter_str_realloc`, `iter_pure_side` all match CPython.
- **Unverified:** the worker's full `/tmp/probes/p30_*` set; side effects inside `_PURE_CALLS` (`str`/`int`/`bool` on user objects); instruction-count/speed measurement (not run—the change moves code onto the typed path).

`VERDICT: FIX` — 1. effectful `AugAssign` target is evaluated after the hoisted `next` instead of before it (probe and expected/actual above).
[cost $0.0429, opencode tokens {"total": 1492284, "input": 114435, "output": 7592, "reasoning": 28561, "cache.write": 0, "cache.read": 1341696}]
    tool time: bash 14.3 min
        568s bash   cd /home/runner/work/_temp/w2 && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_prog30 test_ail
        176s bash   cd /tmp && rm -rf cmpc && mkdir -p cmpc/cur cmpc/base && for wt in /home/runner/work/_temp/w2 /tmp/base; do ta
         58s bash   cat > /tmp/rprobes/iter_str_alias.py <<'EOF' def main() -> None:     items = ["aa", "bb", "cc"]     it = iter(
         25s bash   cd /tmp && for p in iter_shadow iter_mutate iter_assign_order iter_extend iter_dictval; do echo "########## $p
         10s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/aug_target.py /tmp/base 2>&1 | tail -20
          5s bash   cd /tmp && bash ~/tools/cmp.sh /tmp/rprobes/aug_target.py /home/runner/work/_temp/w2 2>&1 | tail -20
          5s bash   cd /tmp && mkdir -p t244 && cd t244 && cp /home/runner/work/_temp/w2/lab/census/programs/dev/t244.py . && for 
          3s bash   cd /tmp/leak && for wt in /home/runner/work/_temp/w2 /tmp/base; do tag=$(basename $wt); rm -rf d_$tag; AIL_NO_

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `2fe4f99`.

- Defect: `AugAssign` target is evaluated before its value in CPython, so the cursor lowering now only hoists `next` past a plain-name target; subscript/attribute targets stay general.
- Probes: all `/tmp/probes/p30_*` match CPython on both builds. New `p30_aug_target{,_2,_name,_arg,_attr,_dict_value,_next_in_target,_pop_index}.py` all match; `p30_aug_target_name.py` stays typed, effectful targets stay general.
- Regression test added to `test_ail_prog30.py`.
- `lab/compare`: generated `program.c` byte-identical for 10/10 tasks.
- Required tests on the final commit: 6 modules, 0 failed (`test_ail_prog30`, `test_ail_pool_iter_capture`, `test_ail_str_iter_fast`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet`).
- Manifest updated and `--check` clean.
[cost $0.0534, opencode tokens {"total": 2970846, "input": 220840, "output": 9404, "reasoning": 10746, "cache.write": 0, "cache.read": 2729856}]
    tool time: bash 13.9 min, edit 0.0 min
        323s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_prog30 test_ail_pool_it
        273s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_prog30 test_ail_pool_it
        103s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p30_*.py; do echo "########## $(basename $p)"; bash ~/to
         81s bash   cd /home/runner/work/_temp/w2 && for tag in w2base w2; do if [ "$tag" = w2base ]; then wt=/tmp/w2base; else wt
         28s bash   cd /tmp/tgchk && for p in p30_aug_target p30_aug_target2 p30_aug_target_arg p30_aug_target_attr p30_aug_target
          5s bash   cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/p30_aug_target.py $PWD 2>&1 | tail -15 && ech
          4s bash   cd /tmp && rm -rf augchk && mkdir augchk && cp /tmp/probes/p30_aug_target.py augchk/p.ail && cd augchk && for 
          4s bash   cd /tmp && rm -rf tgchk && mkdir tgchk && cd tgchk && for p in p30_aug_target_name p30_aug_target p30_aug_targ

## review 1
[model opencode-go/deepseek-v4.1-flash]
# Review: prog30 typed reach (`work..2fe4f99`)

**What the change really does:** `iterlower.py` lowers a local `it = iter(seq)` + one-arg `next(it)` into an index cursor (`t = seq[i]; i += 1`) when it can prove the binding/uses/order are simple, refusing `next` inside an `AugAssign` whose target is not a plain name; `nested_lists.py` marks hoisted comprehension results `_ail_synth` so their temp is not freed before the consuming statement. This matches the report.

## Defects

1. **The lowering assumes `iter`/`next` are the builtins.** A local, parameter, or nested `def` named `iter` or `next` is ignored: the cursor rewrite still fires, so the user binding is never called. This is a regression (base matches CPython on all four probes).

   `rv_next_nested_shadow.py`
   ```python
   def main() -> None:
       def next(x):
           return 42
       it = iter([1, 2])
       print(next(it))
   main()
   ```
   Expected (CPython, base default build): `42`, exit 0. Actual (HEAD default build): `1`, exit 0 (`-j` general build matches).

   `rv_iter_nested_shadow.py`
   ```python
   def main() -> None:
       def iter(x):
           return [9]
       xs = [1, 2, 3]
       it = iter(xs)
       print(next(it))
   main()
   ```
   Expected: `TypeError: 'list' object is not an iterator`, exit 1. Actual: prints `1`, exit 0.

   Same wrong result for `rv_iter_local_shadow.py` (`iter = 5`) and `rv_iter_param_shadow.py` (`def main(iter: int)`): CPython raises `TypeError: 'int' object is not callable` (exit 1); HEAD prints `1`, exit 0. `rv_next_local_shadow.py` likewise (`next = 5`).

   Fix direction: refuse the rewrite when `iter`/`next` are bound anywhere in scope, or resolve them to the builtin first.

## Claims checked

- t266 and t244 compile typed; t266 typed with `AIL_IR=1` too: **verified**.
- t244 fix: HEAD matches CPython on `in0/in1/in2`; base was wrong on all three: **verified**.
- g23_004 / g03_008 / t172 first refusals: **verified** (messages match `prog30.md`; t172 rc 3).
- `lab/compare/src/*/main.ail` 10/10 generated C byte-identical to base (`--debug-dir`): **verified**.
- `python3 tools/update_manifest.py --check`: **verified clean**.
- New `test_ail_prog30` registered in `tests.d`: **verified**.
- Required tests: `test_ail_prog30` + `test_ail_safetynet` pass (`-j 2`, 0 failed); the other four modules in the report were not re-run: **unverified**.
- Worker's full probe list: not re-run; my ~28 probes cover the same boundaries: **unverified** for theirs.

## Pre-existing / documented

- None of my mismatches occur on the base; the shadowing cases above are new.
- Exhausted cursor on the typed path reports `list index out of range` instead of `StopIteration` on stderr (stdout/exit match). This is new but recorded as `C?-job-prog30-11021835-1`; not the blocking defect.
- `chain_relax`, `rail_transfer`, `scar_life`, `tally_lang`, `tree_fold` `main.py` fail to compile identically on base and HEAD (pre-existing).
- Non-feature programs (`rv_plain`, `rv_comp_loop`, `rv_comp_concat`) produce identical C on base and HEAD.

## Unverified

- The four required test modules other than `test_ail_prog30`/`test_ail_safetynet`.
- Instruction counts (`perf_event_paranoid=4`); the assigned gdev programs' generated C is unchanged, so no hot-code change is expected.

VERDICT: FIX
1. `iterlower.py` must not lower `iter(seq)`/`next(it)` when `iter` or `next` is shadowed by a local, parameter, or nested definition. Probe `rv_next_nested_shadow.py` prints `1`/exit 0 instead of `42`/exit 0; `rv_iter_nested_shadow.py` prints `1`/exit 0 instead of a `TypeError`/exit 1.
[cost $0.0679, opencode tokens {"total": 2303029, "input": 263117, "output": 11092, "reasoning": 26260, "cache.write": 0, "cache.read": 2002560}]
    tool time: bash 13.7 min, write 0.0 min
        483s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc && for src in lab/compare/src/*/main.a
        170s bash   date; cd /home/runner/work/_temp/w2 && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog30 test_ail_s
         39s bash   date; cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/rv_*.py; do echo "##### $(basename $p)"; bash ~/too
         36s bash   cd /tmp && rm -rf gcmp && mkdir gcmp && for n in g11_022 g09_034 g02_012 g23_004 g03_008 g01_014 g07_004 g08_0
         18s bash   date; cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/rv_iter_shadow2.py /tmp/rprobes/rv_next_shadow2.py 
         12s bash   date; cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/rv_comp_return.py /tmp/rprobes/rv_comp_dictval.py /
         11s bash   cd /tmp && rm -rf cdtest && mkdir cdtest && cp /home/runner/work/_temp/w2/lab/compare/src/berth_sim/main.py cd
         10s bash   cd /tmp && rm -rf ccmp && mkdir ccmp && for n in rv_plain rv_comp_loop rv_comp_concat rv_iter_boolop rv_iter_m

FINAL VERDICT: FIX  2026-11-02T12:14:38Z
