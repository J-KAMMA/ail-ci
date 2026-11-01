**Tooling fix: a new compiler module must land in sdk_files automatically.** Jobs keep failing the integration gate the same way. `test_ail_packaging.test_every_compiler_file_is_selected` and `test_ail_sdk.test_sdk_files_cover_every_compiler_module_import` fail because a job added a new file under `AIL_CURRENT/python/pkg-v12/`. `tools/update_manifest.py` pinned the file with flags `-`, not `s`. Two jobs hit this on 2026-11-01: rbccsplit2 added `ccsplit.py`, and rbfailfast added another new file.

1. In `tools/update_manifest.py`, every `.py`, `.h` or `.c` file under `python/pkg-v12/` and under `stdlib/` must get the `s` flag when the manifest is updated. That is the set `test_every_compiler_file_is_selected` checks. Keep its other flags. Do not add `s` to anything else.
2. Make `update_manifest.py --check` report a compiler file without `s`, so the job's own pipeline sees the problem before the gate does.
3. Add a test, registered in tests.d. It adds a new dummy module under `python/pkg-v12/` in a temporary copy of the tree, runs `update_manifest.py`, and asserts the module's flags contain `s`. It also runs the packaging selection check on that copy.
4. Run that test plus `test_ail_packaging`, `test_ail_sdk` and `test_ail_safetynet`, run `python3 tools/update_manifest.py`, and commit.

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
