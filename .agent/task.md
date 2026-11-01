**Measure first: where can AIL run faster than C written with the same effort? (owner request 2026-11-01).** This task measures and prices only. Do not change the compiler's default output.

Four candidate mechanisms:
- **A. Automatic parallelism.** Typed loops with no side effects are split over cores automatically.
- **B. `restrict`.** AIL knows when arrays do not overlap, and emits `restrict` / no-alias facts in the C.
- **C. Specialization and inlining.** Callbacks are fixed and inlined (for example a sort comparator, instead of `qsort` calling through a function pointer). Dict and str operations get specialized versions.
- **D. Allocation.** Objects whose lifetimes group together are allocated from arenas or regions.

**Step 1, baseline.** For each of the 10 lab/compare tasks, build AIL (default mode) and the C version. Record:
- wall time, median of 5 runs, with `taskset` on one core and again on all cores;
- instruction count (tools/icount.c);
- peak RSS.

Put the table in docs/design/BEAT_C.md. Mark each task as an AIL win, a tie (within ±3%), or a C win.

**Step 2, profile.** For every task that is not a clear AIL win, profile the AIL binary with `perf record` (or gprof if perf is unavailable). Name the top 3 hot functions or loops and their share of wall time.

**Step 3, price each mechanism per task.** Use the speed-claims rule. For each of A–D, state:
- the measured share of wall time it could touch;
- the Amdahl bound that follows;
- the fraction of that bound you assume can be reached, and why.

Use `tools/roofcheck_v1.py` where it applies. Where a mechanism matches no known roof, say so rather than assume.

**Step 4, cheap evidence.** Use the two most promising mechanism/task pairs. Test each by hand-editing the generated C: add `restrict`, add an OpenMP `parallel for`, inline the comparator, or use an arena. Record:
- whether the output is byte-identical to the unedited build;
- the speed and RSS, measured as in Step 1.

This is evidence only. Do not implement the mechanism in the compiler.

**Step 5, the report.** BEAT_C.md ends with a ranked list:
- mechanism;
- the tasks it wins;
- the measured gain from Step 4, or the priced bound from Step 3;
- the estimated implementation size;
- the semantic risk, such as float sum order under parallelism.

Rules:
- Note the GitHub runner noise: give medians and spreads, and treat a difference under 3% as a tie.
- Do not change default compiler behaviour or any test expectation.
- Commit the doc and any measurement scripts, kept under lab/beatc/.

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
