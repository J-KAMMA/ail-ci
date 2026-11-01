**Re-apply PR #305 (cc-split) on the current tree and fix its three CI failures.** Fetch it anonymously: `git fetch https://github.com/J-KAMMA/ail-ci.git cc-split`. Its change is `git diff $(git merge-base FETCH_HEAD HEAD) FETCH_HEAD -- . ':!.agent' ':!corpus' ':!AIL_CURRENT/MANIFEST.json'`; apply the same change here, resolving conflicts by keeping both sides' fixes (integ has since merged #284 int64-default and #307 module-system).

Defaults must stay as in the PR: clone dedupe on; split only with AIL_CC_SPLIT=N / AIL_CC_JOBS=N; exit merge only with AIL_EXIT_MERGE=1.

Fix these CI failures of the PR:
1. test_ail_server `test_import_time_environment_reads_are_all_keyed`: `AIL_EXIT_MERGE_MIN` is read at import time in pyfunc.py; add it to the keyed environment list the test expects (or read it lazily), whichever matches how the other AIL_* knobs are handled.
2. test_ail_packaging `test_every_compiler_file_is_selected`: add `python/pkg-v12/ccsplit.py` to the wheel file selection.
3. test_ail_sdk `test_sdk_files_cover_every_compiler_module_import`: register ccsplit.py in the SDK manifest like other modules (pyc.py imports it).

Then run `python3 tools/diff_ids.py` and `python3 tools/update_manifest.py`, run test_ail_cc_split, test_ail_server, test_ail_packaging, test_ail_sdk, test_ail_safetynet, and commit. Check that the generated C of the 10 lab/compare tasks is byte-identical to the base except chain_relax's deduped fmt clones. Change nothing else.

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
