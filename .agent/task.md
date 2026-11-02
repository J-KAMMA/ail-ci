**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/gdev/g11_022.py`
- `lab/census/programs/gdev/g09_034.py`
- `lab/census/programs/gdev/g23_004.py`
- `lab/census/programs/gdev/g02_012.py`
- `lab/census/programs/gdev/g03_008.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t266.py`
- `lab/census/programs/dev/t244.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t172.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog30.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog30.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
