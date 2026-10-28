**Fix the CSV reader difference that fails `test_ail_cov2` on CI.**

On GitHub CI, `AIL_CURRENT/test_ail_cov2.py` `PreludeCsv.test_reader` fails: the AIL build's `csv.reader` output differs from CPython's. The same test passes on the maintainer's laptop, so the cause probably depends on the environment: locale, `LANG`/`LC_ALL`, the Python minor version, line endings, or the file-reading path. Earlier CI runs on `integ` failed 4 methods of this module; now only `test_reader` fails.

1. Reproduce it the way CI runs it: read `.github/workflows/` to see the CI environment, then run the test under that environment (for example with `LC_ALL=C` and `LANG` unset).
2. Find the cause in the CSV prelude or the runtime, and fix it so the output matches CPython in every locale. If something cannot match, refuse it by name at compile time; never leave a silent difference.
3. Add a regression case to `test_ail_cov2`, or to a new `test_ail_csv1.py` registered in `ail_check.py` MODULES, that pins the environment that failed.

Run `python3 tools/update_manifest.py`, then only `test_ail_cov2`, the new module and `test_ail_safetynet`, then commit.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
