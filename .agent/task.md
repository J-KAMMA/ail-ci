**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/census/programs/dev/t256.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t310.py`
- `lab/census/programs/gdev/g11_030.py`
- `lab/census/programs/gdev/g25_006.py`
- `lab/census/programs/dev/t058.py`
- `lab/census/programs/gdev/g11_006.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t404.py`
- `lab/census/programs/dev/t388.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog11.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog11.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
