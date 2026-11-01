**Parallel per-function front end, `AIL_FE_JOBS=N` (compile time). Owner: a 1.2x whole-build gain is worth having.**
An earlier attempt on an old tree measured a 1.208x faster build for 10 lab/compare tasks (48.99 s to 40.56 s with 4 workers). Its design:
- fork a multiprocessing Pool;
- compile each function and its clones through the legacy emitter in the workers;
- in the parent, replay name ordering, merge ClassInfo specialisations, re-attach shared tables and the AST, then apply the IR and alias checks serially.

The review of that attempt found defects. Avoid all of them:
1. jobs=4 C differed from jobs=1, e.g. `_ail_finally_cleanup1_handled_` against `_ail_finally_cleanup1_handled`. Generated names must come from deterministic per-function counters, never from a replay regex or str.replace over a hash-ordered set.
2. A user local named `_handled_boundary` was confused with a generated name. The build failed 6 of 12 times with `conflicting type qualifiers for 'v__handled_boundary_'`, and PYTHONHASHSEED=3 reproduced it. Never rewrite user `v_*` names.
3. The test covered one simple function only. Cover try/finally in several functions and methods, classes, clones, and locals with reserved-looking names.

Do this on the current tree:
- With `AIL_FE_JOBS` unset, use min(4, cpu count) on POSIX. That is serial for programs with fewer than 8 functions and for --debug or a native build report. `AIL_FE_JOBS=1` forces serial. Windows stays serial.
- Acceptance:
  - The generated C is byte-identical between jobs=1 and jobs=4 for the 10 lab/compare tasks, the first 200 lab/corpus programs and the 40 docs/design/alias_study/trans programs, each under PYTHONHASHSEED=0, 3, 5 and random.
  - jobs=1 C is byte-identical to the base commit.
  - Report the build wall of the 10 tasks, median of 3, for jobs=1 and jobs=4, and peak RSS of the whole build for both (it must fit a 6 GB machine).
  - Run test_ail_fe_jobs (extended), test_ail_build_cache, test_ail_server (the server must still work with workers) and test_ail_safetynet.
- Run `python3 tools/update_manifest.py`, then commit.

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
