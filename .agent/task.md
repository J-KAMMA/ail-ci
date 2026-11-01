**Re-apply PR #301 (no-implicit-decl) on the current tree and fix its CI failures.** Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git no-implicit-decl`. Its change is `git diff $(git merge-base FETCH_HEAD HEAD) FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`. Apply it here and resolve conflicts by keeping both sides' fixes. integ has since merged #284 (int64 default, intmode.py), which changed how cruntime.py's `/*B<*/…/*B|*/…/*B>*/` big/non-big blocks are chosen.

The PR has two parts:
1. Define `ail__math_double` on the non-big side.
2. Add `pipeline.STRICT_DECL_FLAGS` (`-Werror=implicit-function-declaration -Werror=implicit-int -Werror=incompatible-pointer-types`) to every compile of generated C.

On the current tree, its test_ail_no_implicit_decl fails with `error: redefinition of 'ail__math_double'` in general-path C. Make `ail__math_double` defined exactly once in every runtime world: typed and general, default int64 and --exact-int. Keep the strict flags.

Acceptance:
- test_ail_no_implicit_decl, test_ail_int64_default and test_ail_safetynet pass.
- The 10 lab/compare tasks build under both the default and --exact-int, with no compiler diagnostics.
- Run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, then commit. Change nothing else.

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
