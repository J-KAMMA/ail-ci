**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/dev/t396.py`
- `lab/census/programs/gdev/g03_018.py`
- `lab/census/programs/gdev/g23_032.py`
- `lab/census/programs/gdev/g03_020.py`
- `lab/census/programs/gdev/g04_010.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t176.py`
- `lab/census/programs/gdev/g09_012.py`
- `lab/census/programs/gdev/g05_014.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog8.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog8.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

Run `python3 tools/update_manifest.py`, then only the new test module, the test modules of the files you touched, and `test_ail_safetynet`. Then commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
