Lane: tcc

# tcc1: quick-run probe: compile AIL's generated C with TinyCC instead of gcc -O2

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Measurement only: do not change the compiler (a throwaway local patch to pick the C compiler is fine; do not commit it
outside `lab/tcc`).

**Why (owner, 2026-11-07):** AIL is for vibe coding; the write-run-fix loop is slowed by gcc. A fast "quick-run" mode
(fast compile, slower program) for the loop and gcc -O2 for the final build may fit. Measure before designing.

**Number this moves:** `lab/tcc/RESULTS.md`: for the 10 `lab/compare/src/*/main.py` programs and 50 corpus programs:
1. does the generated C compile with `tcc` (install `tcc` via apt on the runner; record the version)? For each failure,
   the first error and which construct of the generated C or runtime causes it (GCC vector extensions, `__builtin_*`,
   statement expressions, `__int128`, attributes, inline asm, ...), grouped and counted: this list is the blocker list.
2. for those that compile: compile wall (cold, and with the runtime part cached if the build already caches it),
   tcc vs `gcc -O0` vs `gcc -O2`, median of 3; program wall on the public case for each; output byte-identical to the
   gcc -O2 build (any difference is a bug: list it).
3. the edit-run loop number: compile + run on a small input, tcc vs gcc -O2. This is the headline.
4. one paragraph: would a `--quick` mode be worth it, and what the blockers would cost to remove (a `#if` fallback per
   construct vs a different backend).

Run on GitHub (proposed workflow `lab/tcc/tcc.yml` if needed; workers cannot push `.github/`, I install it).
Files you may create: `lab/tcc/*` only.

## Sub-steps
1. (40 min) Script `lab/tcc/run.sh`, compile census, blocker list. Commit, push.
2. (50 min) Timing table and output comparison. Commit, push.
3. (30 min) RESULTS.md with headline and the paragraph. Commit, push.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
