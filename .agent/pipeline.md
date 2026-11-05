# job job-pyreachs7-11051933  started 2026-11-05T10:34:28Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `655a25a1` on `job-pyreachs7-11051933`.

**Cause/fix** (`AIL_CURRENT/python/pkg-v12/aliasrefuse.py`)
- `test_ail_prog5`: returned `list[list[int]]` was treated as a second-reference container, forcing `rows`/`alias = rows` to the general path. Nested row-list returns are shared row by row on the typed path, so they are no longer treated that way; scalar-list returns still are.
- `test_ail_pyperf_lab` (`scimark_sor`): `gi = grid[i]` loweres as `grid[i].v`, and the row-field special case hid the alias, so the typed path copied the row (`38.000000000`). That special case is removed, so the program is refused by name and stays on the sharing general path (`0.412217351`).

**Final-commit tests** (`par_check.py -j 2`, 0 failed):
- `test_ail_prog5` 7/7, `test_ail_pyperf_lab` 3/3, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
- Also passing: `test_ail_optional_locals`, `test_ail_unbound`, `test_ail_fuzz_findings`, `test_ail_refusal_messages`, `test_ail_ir_rulex`

**Probes** (all match CPython on both default and `AIL_UNIFIED_FORCE=1`): `p_alias_rows_whole`, `p_alias_rows_return`, `p_alias_rows_element`, `p_alias_return_element`, `p_alias_scalar_list`, `p_alias_rows_shapes` (argument, list item, attribute, dict value, empty, negative). Manifest updated and `--check` passes.
[cost $0.0000, opencode tokens {"total": 7529683, "input": 149946, "output": 15588, "reasoning": 21173, "cache.write": 0, "cache.read": 7342976}]
    tool time: bash 17.2 min
        307s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_a
        286s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_prog5 test_ail_p
        231s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/tmp/manifest.log 2>&1; tail -5 /tmp/m
         42s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_prog5 test_ail_pyperf_lab 2>
         34s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pyperf_lab 2>&1 | tail -80
         17s bash   for c in 8228ab97 697c57ad f95b7ce5 66eb186e; do d=/tmp/ail_$c; rm -rf $d; mkdir -p $d; (cd /home/runner/work/
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_alias_rows_whole.py /tmp/probes/p_alias_rows_retu
         10s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_prog5 2>&1 | tail -60

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the diff really does.** `aliasrefuse.py` (1) stops treating a returned `list[<container>]` (nested subscript or `_AilRow_*`) as a container so returned row-lists stay on the typed path, and (2) removes the row-field exemption so `gi = grid[i]` (lowered to a field read) counts as an alias of `grid`, sending `scimark_sor` to the general path. It also refreshes the manifest pin.

**Report claims**
- `test_ail_prog5` cause/fix — verified: base fails (`fell back to the general path` at `alias = rows`), HEAD passes 7/7.
- `test_ail_pyperf_lab` / `scimark_sor` — verified: base prints `38.000000000`, HEAD refuses by name and stays general (`0.412217351`), module 3/3.
- “Nested row-list returns are shared row by row on the typed path” — **false in general** (see defect); true only when every returned row is a distinct object.
- Manifest `--check` — verified exit 0.
- Worker probes (`p_alias_*`) — reran all 6, both builds match CPython.
- Tests I reran on HEAD: `test_ail_prog5`, `test_ail_pyperf_lab`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_fuzz_findings`, `test_ail_refusal_messages` — all 0 failed.
- `test_ail_optional_locals`, `test_ail_unbound`, `test_ail_ir_rulex` — not rerun (unverified).

**Defect (new, change-caused).** A returned row-list whose rows contain the *same object twice* is now silently compiled on the typed path, which duplicates that row. Base refuses (general path) and matches CPython; HEAD's default build is wrong.

Probe `/tmp/rprobes/p18_repeated_row.py`:
```python
def build() -> list[list[int]]:
    r: list[int] = []
    rows: list[list[int]] = [r, r]
    return rows

def main() -> None:
    rows = build()
    alias = rows
    alias[0].append(7)
    print(rows[0], rows[1])
    alias[1].append(8)
    print(rows[0], rows[1])
main()
```
Expected (CPython, and base general path):
```
[7] [7]
[7, 8] [7, 8]
```
Actual (HEAD default/typed build; general `AIL_UNIFIED_FORCE=1` matches):
```
[7] []
[7] [8]
```
`/tmp/rprobes/p19_repeated_row_param.py` shows the same identity loss when the repeated row came through a function argument. The blanket “nested return = rows are shared” exemption needs to account for duplicated/aliased row objects (refuse or stay general).

**Pre-existing.** Base (`work`) has a stale manifest pin for `aliasrefuse.py`, so `par_check.preflight` fails there; base modules were run with `python3 -m unittest` instead. Unrelated to this change.

**Unverified.** Runtime speed impact of the removed row-field exemption (it only sends more programs to the general path); the three test modules listed above.

VERDICT: FIX
1. Returned `list[list[int]]` with repeated/aliased row objects is silently miscompiled on the typed path (`/tmp/rprobes/p18_repeated_row.py`, `p19_repeated_row_param.py`): expected `[7] [7]` / `[7, 8] [7, 8]`, actual `[7] []` / `[7] [8]`; base general path matches CPython.
[cost $0.0000, opencode tokens {"total": 1864754, "input": 70254, "output": 9597, "reasoning": 18375, "cache.write": 0, "cache.read": 1766528}]
    tool time: bash 12.0 min
        214s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        196s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test
        139s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         33s bash   cd /tmp/base/AIL_CURRENT && date && timeout 900 python3 -m unittest -q test_ail_pyperf_lab 2>&1 | tail -30
         24s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in /tmp/rprobes/p9_list_dict.py /tmp/rprobes/p10_list_bytear
         23s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.s
         16s bash   cd /home/runner/work/ail-ci/ail-ci && date; for p in /tmp/probes/p_alias_rows_whole.py /tmp/probes/p_alias_row
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for n in 9 10 11; do d=/tmp/probe$n; rm -rf $d; mkdir $d; cp /tmp/rprobe

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect.

- `nested_lists.py`: refuses repeated/aliased row sources by name — duplicate list-display entries, repeated `append`/`insert`, element stores, and loop-invariant row sources — so they stay on the sharing general path instead of being silently copied.
- Updated `aliasrefuse.py` comment scope and added two regression cases to `test_ail_nested_lists.py`.
- Probes: `/tmp/rprobes/p18`–`p30` (13) plus 6 `p_alias_*` all match CPython on both builds.
- Final required tests: 8/8 modules passed (`prog5`, `pyperf_lab`, `nested_lists`, `prog7`, `prog8`, `safetynet`, `files`, `corpus_findings3`); earlier expanded run 13/13 passed.
- Manifest `--check` exit 0. Commit `777fce1d`.
[cost $0.0000, opencode tokens {"total": 5027235, "input": 152108, "output": 12295, "reasoning": 26736, "cache.write": 0, "cache.read": 4836096}]
    tool time: bash 18.0 min
        531s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        321s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        115s bash   cat > /tmp/rprobes/p26_attribute_repeated.py <<'EOF' class Box:     def __init__(self) -> None:         self.r
         54s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p18_repeated_row.py /tmp/rprobes/p19_repeated_row_
         31s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest -q test_ail_nested_lists 2>&
          8s bash   cat > /tmp/rprobes/p23_append_single.py <<'EOF' def build(r: list[int]) -> list[list[int]]:     rows: list[lis
          8s bash   cat > /tmp/rprobes/p20_single_row_param.py <<'EOF' def build(r: list[int]) -> list[list[int]]:     return [r] 
          4s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/p18_repeated_row.py <<'EOF' def build() -> list[list[int]]:     r:

## review 1
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review: `777fce1d` + `655a25a1` (`work..HEAD`)

**What the change really does:** stops treating a *returned* `list[list[int]]` value as a container second-reference site (so `alias = rows` after a call returning rows stays on the typed path, which shares the outer list object), restores row-field element-alias detection in `refs`, and adds two compile-time refusals in `nested_lists.row_call` (a non-fresh row source stored at two places, and a non-fresh row source copied inside a loop that does not rebind it). Matches the report.

**Probes** (`/tmp/rprobes/`, `cmp.sh` both builds, HEAD vs `/tmp/base`): 30 probes, all match CPython.
- outer-name alias of returned rows, via name / annotation / parameter / attribute / dict value / negative index / empty rows / pop: `a1`–`a5`, `c3`–`c5`, `e1`, `e2` — all same; default build verified typed (no fallback note) for `c1,c3,e1`–`e5`.
- duplicate row source: display `d1`, append `d2`, element store `e6`, insert (`p28`) → refused by name (`r is stored as more than one row…`).
- loop-invariant source: `p30`, `c8` → refused (`does not rebuild it each iteration`); `c1` (base rebound only in an `if`) compiles typed and matches (7 7 7 3) — the wrap is hoisted, so the guard's syntactic looseness costs nothing.
- iteration/aliasing during walk `e3`, fresh rows in loop `e4`, extend `e5`, two names `f3`, two calls `c7` → match.
- `f2` (same list via `holder[0]`, different spelling): base's default build printed `1 1 1 2`, HEAD prints CPython's `1 1 2 2` → the change fixes a case base got wrong.
- non-feature programs: `corpus/gdev/g00_026.py`, `g22_024`, `g07_040` compile to byte-identical `program.c` (`--debug-dir`) on base and HEAD.

**Tests** on HEAD (`par_check -j 2`): `test_ail_prog5`, `test_ail_pyperf_lab`, `test_ail_nested_lists`, `test_ail_safetynet` 4/4 passed; `test_ail_files`, `test_ail_corpus_findings3` 2/2 passed. `tools/update_manifest.py --check` exit 0; DEVLOG entry at top dated 2026-11-05; commit trailer correct.

**Claims:** refusal shapes (display, append, insert, element store, loop) verified; the two new REFUSED cases behave as asserted; prog5/pyperf_lab pass. One nit: several of the worker's probes end with `print(rows[0], r)`, which is itself a named refusal, so they validate the general-path fallback rather than the typed path — the `c`/`e` probes above cover the typed path.

**Pre-existing (not blocking):** nested-list comprehension element `[[r] for _ in range(3)]` is refused ("comprehension elements are unsupported") on base too (`f1`); base refusals like `alias = rows` after a call are what this change removes.

**Unverified:** `test_ail_prog7/8` and the other modules in the 8/8 claim were not re-run; speed via `icount` not run — the diff adds only compile-time analysis and leaves the generated C of non-feature programs identical, so runtime is unaffected.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=50 out_tokens=33610]

## full suite
test_ail_stdlib5
test_ail_stdlib_batch3
test_ail_stdlib_batch4

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Committed `211584d7`.

What broke and the fix, all in `nested_lists.py`:

- **`test_ail_stdlib5`** — `calendar`'s `weeks.append(days[i:i + 7])`: a slice makes a *fresh* list each evaluation, so copying it into a row is correct. Slices now count as fresh sources (`_fresh_source`), skipped by both refusals.
- **`test_ail_stdlib_batch3`** — `chain.from_iterable([xs, ys, xs])`: the iterator pass leaves the argument in a generated `_il*_s` pool. Those `_ail_synth` rows lists are read-only machinery; sharing is unobservable, so they're exempt (`self.temporary`).
- **`test_ail_stdlib_batch4`** — `csv`'s `rows.append(fields); fields = []` state machine: rebinding `fields` gives it a new list, so the earlier row no longer aliases. `wrapped` records are now dropped when a source is rebound (`forget`, applied to assignments and loop targets), with `if` branches processed separately and merged so a wrap on either path stays flagged.

The original refusals and both added regression tests still hold (verified `[r, r]`, repeated append, loop-invariant, and the risky `if`-rebind still exit 3). Manifest updated; `--check` passes.

Results: `test_ail_stdlib5`, `test_ail_stdlib_batch3`, `test_ail_stdlib_batch4`, `test_ail_nested_lists`, `test_ail_prog5`, `test_ail_pyperf_lab`, `test_ail_safetynet`, `test_ail_corpus_findings3` all pass.
[commandcode stop=end_turn turns=80 out_tokens=48141]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T14:55:08Z
