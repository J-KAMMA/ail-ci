# bigint-fix01: the SDK/wheel file lists miss python/pkg-v12/biggate.py (C, packaging)

Branch `bigint` (head b13dd0d) added `python/pkg-v12/biggate.py` and `cruntime.py` now does `import biggate as _biggate`
(cruntime.py:21907). Every place that copies or lists the compiler files was not told about the new module, so an
exported SDK / wheel / extracted package crashes at start: `ModuleNotFoundError: No module named 'biggate'`.

## Modules (about 25 failing tests, found by the triage)
test_ail_sdk (25), test_ail_packaging (1), test_ail_grid_return (2), test_ail_sdk_environment (1).

## What fails
- test_ail_packaging.WheelContents.test_every_compiler_file_is_selected:
  `Lists differ: ['python/pkg-v12/biggate.py'] != []` (the file is not selected for the wheel).
- test_ail_sdk: the exported SDK copy (`export-sdk`) runs `python/pkg-v12/pyc.py` and dies in `import cruntime` -> `import biggate`.
- test_ail_grid_return: same traceback from an exported copy.
- test_ail_sdk_environment: `export-sdk` / doctor in a fresh environment returns 2 (probably the same cause; confirm).

## Reproducer (CPython has no equivalent; this is a packaging failure)
```
cd the repository checkout/AIL_CURRENT
python3 -m unittest -q test_ail_packaging           # 1 failure, names biggate.py
python3 -m unittest -q test_ail_sdk 2>&1 | grep -m1 -B3 "No module named"
```
Likely places: MANIFEST.json (the file list near line 25203 names unified.py but not biggate.py; run the repo's
update_manifest tool, then `--check`), the wheel/SDK file selection in the packaging code (grep the code that
`test_ail_packaging.py` reads for "every compiler file"), and `export-sdk` in ail_chatgpt.py. Check bigint_obj.py and any
other file added by the bigint commits (`git diff --stat <merge-base>..HEAD -- python/pkg-v12`) the same way.

## Category
C (a real defect: a new compiler module is not shipped).

## Fixed means
All four modules pass; `export-sdk` output runs a compile; MANIFEST.json is regenerated and `--check` passes.

run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing.

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
