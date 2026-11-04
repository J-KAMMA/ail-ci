**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
**Report — prog18 re-run, review**

What the diff really does (`work..HEAD`, 4 commits): it is the whole prog18 typed-reach batch — `_script_entry` searches the `__main__` guard, `_numeric_expression_needed` stops treating container displays as numeric bindings, `max`/`min(default=)`, and f-string nested width `f"{x:>{w}}"` — **plus** the two bool guards from the previous review. The worker report describes only the last commit (the two bool fixes), not the rest of the change.

Verified claims (of the report): bool nested width refused by name — **verified** (test refusal + `n5` falls back to the general path); bool `default=` refused — **verified** (`m4`, `p13`-style); 12 tests in `test_ail_prog18` — **verified**; DEVLOG/`prog18.md` updated — **verified**; `update_manifest.py --check` — **verified (rc=0)**; `test_ail_prog18` and `test_ail_safetynet` pass on HEAD (`-j 2`, 0 failed). Its "probes p10/p13/p19/p20/p21" — **unverified** (the p20/p21 files in `/tmp/rprobes` are empty). "test_ail_files + corpus_findings3 20 OK" — not re-run (out of the review's scope).

C identity: built all 10 `lab/compare/src/*/main.py` with `--debug-dir` on HEAD and on `/tmp/base`, same temp dir. 6 emit C and are byte-identical; `chain_relax`, `rail_transfer` fail identically on both; `tally_lang`, `tree_fold` fall back identically on both and emit no `program.c`. No regression there.

Probes (`bash ~/tools/cmp.sh`, default = typed, `g` = forced general): `n1 n2 n3 n6` (negative width, fill, precision/type, str ValueError), `n9` (width from list item/dict value), `m1 m2b m3 m5 m6 m9` (empty/non-empty, int/float, genexpr/slice, attribute/dict/list/param, mutation, order `src` then `default`), `c1` (container display), `s1`/`m2` (entry guard) all match CPython on both builds. Failures below.

**Defects (all introduced by the change; every one matches CPython on `/tmp/base`)**

1. `f"{v():>{w()}}"` — the typed path evaluates the nested width **before** the value; CPython evaluates the value first.
   Probe `/tmp/rprobes/n4.py`: `def w(): print("w",end=' '); return 5` / `def v(): print("v",end=' '); return 9` / `print(f"[{v():>{w()}}]")`.
   Expected (CPython, and base default build): `v w [    9]`; actual (HEAD default build): `w v [    9]`. C function-argument order.
2. A nested width field's own format spec is silently ignored; CPython splices the *formatted* text.
   Probe `/tmp/rprobes/n10.py`: `w = 5; print(f"[{9:>{w:>3}}]")`.
   Expected (CPython, base): `VE Invalid format specifier '>  5' for object of type 'int'`; actual (HEAD typed): `[    9]` (no error, exit 0).
3. `max`/`min(default=)` over **bool elements** with an int default returns the int, not the bool.
   Probe `/tmp/rprobes/m7.py`: `flags = [True, False]; print(max(flags, default=0)); print(min(flags, default=1))` (same with `flags: list[bool]`, `/tmp/rprobes/m10.py`).
   Expected (CPython, base): `True` / `False`; actual (HEAD typed): `1` / `0`. The guard only tests the default's kind, not the elements'.

Nit: commit `1856c22` adds two empty files `a.txt`, `b.txt` ("worker: uncommitted edits").

Pre-existing: none among the probes (all base builds matched CPython).

Unverified: the `test_ail_files`/`test_ail_corpus_findings3` claim; instruction counts (the change edits no runtime, only which programs take the typed path, so the affected programs get faster, not slower); the worker's p20/p21 probes (empty files).

VERDICT: FIX

1. Nested width is evaluated before the value operand; CPython evaluates the value first. `/tmp/rprobes/n4.py`: expected `v w [    9]`, actual `w v [    9]` (default build; base matches).
2. A nested width field carrying its own spec is accepted and its spec dropped. `/tmp/rprobes/n10.py`: expected `VE Invalid format specifier '>  5' for object of type 'int'` (exit 1), actual `[    9]` (exit 0).
3. `max`/`min(xs, default=<int>)` over bool elements loses the bool. `/tmp/rprobes/m7.py`: expected `True`/`False`, actual `1`/`0`.
[commandcode stop=end_turn turns=47 out_tokens=33626]


--- ORIGINAL TASK ---
**Typed reach: make the hot functions of these 8 real programs compile on the typed path.** With the CPython hybrid (docs/design/CPYTHON_HYBRID.md) only typed functions are accelerated; the rest runs in CPython. So what matters is that the functions where time is spent compile typed.

> Re-run of prog18, whose GitHub run was lost (no verdict 62.3 h after dispatch). If its branch job-prog18-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

Read `git log --oneline -40` first so you do not redo what another task just did.

- `lab/corpus/programs/deepseek-v4.1-flash-free/t391.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t443.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t198.py`
- `lab/census/programs/gdev/g11_014.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t219.py`
- `lab/census/programs/gdev/g02_038.py`
- `lab/corpus/programs/deepseek-v4.1-flash-free/t210.py`
- `lab/census/programs/gdev/g19_014.py`

1. Run each program under CPython 3.12 with cProfile and list its functions by own time. Take the functions that together hold 80% of the time.
2. For each such function, record whether AIL compiles it on the typed path (mixed mode lets one function be typed while others are general), and if not, the first reason. Write the table in `lab/progfix/prog18.md`.
3. Fix the reasons in the compiler, starting with the one that blocks the most hot functions; never edit the programs. A reason that needs a big new feature: leave it and record it as a follow-up with the exact message.
4. Default ints are int64 and overflow stops loudly; never wrap silently. Output must match CPython. The generated C of the 10 lab/compare tasks must stay byte-identical.
5. Add `AIL_CURRENT/test_ail_prog18.py`, registered in tests.d, compiling each newly typed function and comparing the program with CPython.

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
