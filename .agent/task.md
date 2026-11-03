Lane: packaging

**Fix the two wheel failures that the new platforms-wheel check found (PR #352, run 41532584596).** Both are bugs that users would hit.

1. **macOS: the wheel build fails.** The error is `ValueError: symlink or junction is not allowed: /var`, raised from `AIL_CURRENT/ail_sdk.py` `_no_links` (line ~653), called by `export_sdk` and then `packaging/ail_wheel_backend.py` `sdk_files`.
   - On macOS, `/var` is a system symlink to `/private/var`, and pip builds the wheel under `/var/folders/...`.
   - Fix: check for links only in the path components at or below the export root and source root that AIL itself creates or walks. Resolve the root first with `os.path.realpath`. Do not test the system prefix above it.
   - Links inside the tree must still be refused. Keep or add a test for both cases: a root reached through a symlinked parent must pass, and a symlink inside the tree must be refused. Linux can simulate the parent symlink in a tmp directory.
2. **Windows: 10 tutorial tests fail.** The error is `FileNotFoundError` from `AIL_CURRENT/test_ail_tutorial.py` line ~162, `subprocess.run(["./" + name + ".bin"] ...)`.
   - Find what file name the compiler actually writes on Windows (for example `name.bin.exe`, or `name.exe`). Read the build code; do not guess.
   - Make the test run that file: use an absolute path joined from `work`, and add the platform suffix the build uses.
   - If the CLI itself prints a wrong output path on Windows, fix the CLI instead.

Do not edit `.github/workflows`. Run the targeted tests on Linux (test_ail_tutorial plus the SDK/wheel tests that exist) and report them. After this job integrates, the wheel check on PR #352 will verify macOS and Windows.

Time budget: 60 minutes.

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
