# job job-prog8-11021227  started 2026-11-02T03:28:39Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the review defect and committed as `175d047`.

- Empty float-list `sum` now returns CPython's int `0` instead of `0.0`, via a new `NSUM` typed kind (tracks whether the fold actually added an element; `-0.0` is the empty sentinel). `f4_emptyslice.py` now gives `0 0 0 0` on both builds.
- Also closed silent NSUM truncations found by probing: list/dict/set storage, `append`/`insert`/`extend`, list/dict comprehensions, filtered generator sums, indices/keys/slice bounds, and call arguments. Explicit float formatting (`:.2f`, `e`, `g`, `%`) stays typed and exact; default/int formatting is refused by name.
- Ran 35 probes; all match CPython on both `cmp.sh` builds (unsafe forms fall back by named refusal). Hot `g03_020`, `g05_014`, `g09_012` compile with 0 general-path notes. `ledger_bin` C remains byte-identical; `tree_fold` still fails as on base.
- Tests pass on final commit: `test_ail_prog8`, `test_ail_safetynet`, `test_ail_spec_fixes`, `test_ail_nested_lists`, `test_ail_boolfield`, `test_ail_files`, `test_ail_corpus_findings3`. `tools/update_manifest.py --check` is 0.
[cost $0.1313, opencode tokens {"total": 17113012, "input": 239698, "output": 28475, "reasoning": 46375, "cache.write": 0, "cache.read": 16798464}]
    tool time: bash 19.3 min, edit 0.0 min
        324s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pro
        283s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pro
        152s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pro
         57s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add --detach /tmp/head HEAD >/dev/null 2>&1; echo wt=$?; fo
         56s bash   cd /home/runner/work/ail-ci/ail-ci && for p in f4_emptyslice n1_basic n2_arith n3_aug n4_refuse n5_unaffected 
         55s bash   cd /home/runner/work/ail-ci/ail-ci && for p in f4_emptyslice n1_basic n2_arith n3_aug n5_unaffected q1a_dictun
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q11_extend q13_dictmethods q14_setupdate q15_folds q16_nestedst
         46s bash   cd /home/runner/work/ail-ci/ail-ci && for p in f4_emptyslice n1_basic n2_arith n3_aug n4_refuse n5_unaffected 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## What the change does
Adds an `NSUM` scalar kind for `sum()` over float sequences: the typed fold counts elements and returns `-0.0` as the sentinel for CPython's int `0`; all uses that cannot keep int-or-float exact are named refusals, and explicit float format specs stay typed.

## Probes (HEAD default / forced-general vs base)
| probe | covers | HEAD | base |
|---|---|---|---|
| `f4_emptyslice` | review's original defect | both match | (refused before) |
| `p1_empty`, `p2c_negzero_typed` | empty/non-empty, bare/slice/gen/listcomp, comparisons, int/bool/float, direct `-0.0` sums | match, typed | n/a |
| `p3a_fmt_ok`, `p3b_fmt_bad` | explicit float specs; default/int specs | match, typed / named refusal | n/a |
| `p4_containers`, `p11_nested_lit`, `p16_nested` | list/dict/set/tuple storage, nested literals | match (general) | same set-order diff |
| `p5b_arith_bad`, `p6b_calls_bad`, `p14*` | int arithmetic, calls, indices/keys/repeat/slice bounds | match (general) | n/a |
| `p7_annot`, `p8_mutate` | annotated local/attr, slice alias/mutation | match (general or typed) | n/a |
| `p9_flow`, `p10_return`, `p15a_min`, `p17_branch_min` | NSUM later widened by a float assignment in a branch/loop, or in a return | **default build wrong** | wrong differently (0.0) |
| `p19_negzero_min` | genuine `-0.0` merged with NSUM | **wrong; base correct** | correct |
| `nf`, `n5_unaffected` | programs not using the feature | `program.c` byte-identical to base | same |

`test_ail_prog8` and `test_ail_safetynet` pass on HEAD; `tools/update_manifest.py --check` = 0. Hot `g03_020`, `g05_014`, `g09_012` have 0 general-path notes; `ledger_bin` C is byte-identical and `tree_fold` fails identically on both.

## Report claims
- Original empty-slice defect fixed (`f4`): **verified**.
- NSUM refusals/formatting: **verified for the representative probes above** (some valid forms over-refuse, which is allowed).
- “35 probes all match”: **false as a completeness claim** — the flow-merge cases below were missed.
- Hot programs typed; ledger/tree; manifest: **verified**.
- Other five test modules in the report: **unverified** (not in scope here).

## Defects
1. **NSUM widened to a definitely-float local.** `declare` changes the local's kind to `FLT` after a later float assignment, even when a branch/loop may not execute it; the sentinel is then printed as a float.
```python
def main() -> None:
    xs: list[float] = []
    s = sum(xs)
    for v in xs:
        s += v
    print(s)
main()
```
Expected (CPython): `0`. HEAD default: **`-0.0`** (base: `0.0`, also wrong). Same with `if n > 0: s = 1.5` and the function-return variant (`f(empty, False)` → `-0.0` vs `0`, `p10_return`).

2. **Genuine `-0.0` merged into NSUM is misread as the empty-sum int 0.** This one is a regression: base is correct.
```python
def main() -> None:
    empty: list[float] = []
    s = -0.0
    if False:
        s = sum(empty)
    print(s)
main()
```
Expected (CPython) and base: `-0.0`. HEAD default (typed): **`0`**.

The sentinel cannot distinguish these cases once NSUM and FLT can reach the same read; a companion emptiness flag or a refusal when NSUM merges with a float across control flow is needed.

## Pre-existing
- `p4_containers`: set iteration order `{0, 1.5}` vs `{1.5, 0}` is identical on base.
- `average()`'s `if n else 0` printing `0.0` instead of `0` is identical on base.

## Unverified
- Instruction counts: `perf_event_open` is not permitted in this container.
- Worker's remaining claimed test modules and the wider suite (not run per instructions).

VERDICT: FIX
1. Branch/loop widening of an NSUM local to `FLT` prints `-0.0` where CPython prints `0` (`p15a_min`, `p17_branch_min`, `p10_return`).
2. A genuine `-0.0` merged with NSUM prints `0` where CPython prints `-0.0` (`p19_negzero_min`); base was correct.
[cost $0.0474, opencode tokens {"total": 2940120, "input": 98513, "output": 15010, "reasoning": 25317, "cache.write": 0, "cache.read": 2801280}]
    tool time: bash 6.5 min, write 0.0 min
        157s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pro
         59s bash   cd /home/runner/work/ail-ci/ail-ci && R=/home/runner/work/ail-ci/ail-ci; for t in ledger_bin tree_fold; do hd=
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_empty p2_negzero p3a_fmt_ok p4_containers p5a_arith_ok p5b_a
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for t in ledger_bin tree_fold; do for s in main.py; do hd=$(mktemp -d /t
         19s bash   cd /home/runner/work/ail-ci/ail-ci && d=$(mktemp -d /tmp/typed2XXXX); for p in p1_empty p2_negzero p3a_fmt_ok 
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q17_boolop q15_folds q2a_multialloc q21_builtinargs n1_basic; d
         12s bash   cd /home/runner/work/ail-ci/ail-ci && d=$(mktemp -d /tmp/typedXXXX); for p in p1_empty p2_negzero p3a_fmt_ok p
         10s bash   cd /tmp/rprobes && cat > p11_nested_lit.py <<'EOF' def main() -> None:     empty: list[float] = []     xs: lis

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both NSUM defects and committed as `076fdec`.

- Defect 1: NSUM now carries `{value, is_int0}` instead of a `-0.0` sentinel, so non-running branches/loops keep CPython's int `0`.
- Defect 2: a genuine `-0.0` merged with conditional `sum()` prints `-0.0`; the reverse float-first merge is a named refusal and matches via the general path.
- Probes: `f4`, `p9`, `p10`, `p15a`, `p15_loop`, `p17`, `p19`, plus `/tmp/probes/nsum_flow_typed.py`, `nsum_float_merge.py`, `nsum_convert.py` all match CPython on both builds.
- Tests: `test_ail_prog8` (8 tests), `test_ail_nested_lists`, `test_ail_boolfield`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_float_argument_widening` all pass.
- `update_manifest.py --check` exits 0; generated C for all buildable `lab/compare` sources is byte-identical (the three pre-existing `main.py` failures remain).
[cost $0.1221, opencode tokens {"total": 18687194, "input": 230145, "output": 24777, "reasoning": 29200, "cache.write": 0, "cache.read": 18403072}]
    tool time: bash 34.0 min, write 0.0 min
        431s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ccur /tmp/cbase /tmp/cout_cur /tmp/cout_base && mkdir -p /tm
        429s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ccur /tmp/cbase /tmp/cout_cur /tmp/cout_base && mkdir -p /tm
        254s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog8 test_ail_nes
        250s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_prog8 test_ail_nes
        247s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && timeout 1800 python3 tools/p
        219s bash   cd /home/runner/work/ail-ci/ail-ci && fail=0; for f in /tmp/rprobes/*.py; do p=$(basename "$f" .py); out=$(bas
         47s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ccur /tmp/cbase && mkdir -p /tmp/ccur /tmp/cbase && fail=0; 
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in f4_emptyslice p9_flow p10_return p13_return_negzero p15a_min p1

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review complete.

## What the change does
Replaces the `-0.0`-sentinel `NSUM` scalar with a C struct `ail_nsum { double v; int64_t is_int0; }`, threads the flag through folds/assignments/`+=`/returns/`print`/formatting/conversions/truthiness, and turns uses that cannot stay exact into named refusals.

## Probes (HEAD, both `cmp.sh` builds)
| probe | covers | result |
|---|---|---|
| `p1_f4` | review's empty float-slice `sum` | both match; base default `0.0` |
| `p2_flow` | `-0.0` merged with conditional `sum`, dead/taken loop branch | both match |
| `p3_func` / `p14_mixedreturn` | function with `return sum(xs)` and `return <float>` | **default build fails to compile**; general matches |
| `p4_arith`, `p26_cmp` | `+ * / -`, compares, `int`/`float`/`bool`, `if` | both match |
| `p5_fmt`, `p25_fconv` | `:.2f/e/g`, `%`, `.format`, `!r/!s`, plain `print` | both match |
| `p6_containers`, `p20_literals`, `p27_callret_store` | attr/dict/list/set/list-literal storage | both match (named refusal or general) |
| `p7_gen` | filtered generator/listcomp sums, empty and non-empty | both match |
| `p8_mutate`, `p9_edge` | slice alias + mutation, `-0.0`, `0.0`, `1e308` overflow | both match |
| `p11`–`p13`, `p15`–`p19`, `p21a`, `p22` | bool ops, slice bounds, `in`/`is`, `+=`, annotated local, return use, globals, `print(end=)`, unpack, attribute | both match |
| `p10_nofeature` | program using no new feature | C byte-identical to base in both builds (`--debug-dir`) |

Named worker probes `p9_flow`, `p10_return`, `p15a_min`, `p15_loop_empty`, `p17_branch_min`, `p19_negzero_min`, and `/tmp/probes/nsum_{flow_typed,float_merge,convert}.py` all match on both builds.

## Report claims
- Both review defects fixed — **verified** (`p1_f4`, `p2_flow`).
- Named probes match — **verified**.
- `test_ail_prog8`, `test_ail_nested_lists`, `test_ail_float_argument_widening`, `test_ail_safetynet` pass — **verified** (8 tests). `test_ail_files`/`test_ail_corpus_findings3` not run (**unverified**).
- `update_manifest.py --check` exits 0 — **verified**.
- `lab/compare` C byte-identical — not fully re-run (**unverified**); the no-feature probe's C is identical, and `lab/compare` sums are ints.
- “NSUM is a struct with a flag” — true in code, but **false in the docs** (`SEMANTICS.md`/`DIFFERENCES.md` still describe the old `-0.0` sentinel).

## Defects
1. Mixed `NSUM`/float return paths produce a raw C compile error. Probe `/tmp/rprobes/p14_mixedreturn.py` (same shape in `p3_func.py`):
```python
def g(xs: list[float], n: int) -> float:
    if n > 0:
        return sum(xs)
    return 1.5
```
Expected CPython: `1.5 0 2.5` / `1.5 0 2.5`. Actual HEAD default build: `build d failed` — `error: incompatible types when returning type 'double' but 'ail_nsum' was expected` (`return (1.5);`). General path matches; base default builds. Cause: `_signatures`/`_reconcile_return_kinds` (`pyfunc.py:31275`, `:29444`) allow `NSUM`+`FLT` returns and set the C return type to `ail_nsum`, but the `ast.Return` path (`pyfunc.py:22225`) does not wrap a float value with `ail_nsum_from_float` (only `Assign`/`AugAssign` do). Fix: wrap float returns when `ctx.ret == NSUM`, or make the mixed-return case a named refusal.
2. `SEMANTICS.md:9525-9528` and the C1 row of `docs/spec/DIFFERENCES.md` still document `NSUM` as “a `double` with `-0.0` as the empty-sum sentinel”; the implementation now uses the explicit `is_int0` flag. Documentation contradicts the code and the worker report.

## Pre-existing
- Chained assignment `c = d = sum(empty)` fails to build on both HEAD and base (`v_d` undeclared); a plain `c = d = 1.5` fails identically, so the chained-assignment bug predates this change (`p21b`, `p23`).
- A function with an explicit return on one path and fallthrough returns `0`/`0.0` instead of `None` on both trees (`p24_fallthrough`).

## Unverified
- Full `lab/compare` C identity and the two test modules not run (time/scope).
- Wider suite and instruction counts (not run per instructions; no hot program returns `sum` directly on a mixed path).

VERDICT: FIX

1. Mixed `NSUM`/float returns: `/tmp/rprobes/p14_mixedreturn.py`; expected `1.5 0 2.5` twice, actual default build fails (`incompatible types when returning type 'double' but 'ail_nsum' was expected`). Wrap float returns when the return kind is `NSUM`, or refuse the mix by name.
2. Update `SEMANTICS.md` and `DIFFERENCES.md` to describe the `{double v; int64_t is_int0}` struct instead of the obsolete `-0.0` sentinel.
[cost $0.0433, opencode tokens {"total": 3415468, "input": 86057, "output": 11023, "reasoning": 23156, "cache.write": 0, "cache.read": 3295232}]
    tool time: bash 6.9 min
        157s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest exit $?"; date;
        120s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rprobes && (cd AIL_CURRENT && nohup python3 ../tools/par_c
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_f4 p2_flow p3_func p4_arith p5_fmt p6_containers p7_gen p8_m
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_f4 p2_flow p3_func p4_arith p5_fmt p6_containers p7_gen p8_m
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p9_flow.py /tmp/rprobes/p10_return.py /tmp/rprobes
         15s bash   cd /tmp/rprobes && cat > p11_boolop.py <<'EOF' def main():     empty: list[float] = []     xs: list[float] = [
         12s bash   cd /tmp/rprobes && cat > p24_fallthrough.py <<'EOF' def f(xs: list[float], n: int):     if n > 0:         retu
          8s bash   cd /tmp/rprobes && cat > p20_literals.py <<'EOF' def main():     empty: list[float] = []     xs: list[float] =

FINAL VERDICT: FIX  2026-11-02T05:40:21Z
