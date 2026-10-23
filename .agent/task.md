**Fix one pre-existing difference from CPython.** A reviewer of job `fuzz82` recorded these as already present before that job:

- `q14` `del a[2**63]`: both default builds trap `integer overflow`, exit 1.
- `q26` delete from empty list: stdout matches, but stderr says `list index out of range` vs CPython `list assignment index out of range`.
- `q39` `global` in nested def: CPython prints `2`; AIL exits 1 with `UnboundLocalError` (loud, as reported).

**C unchanged / speed:** `program.c` hashes identical base vs HEAD for `n01`–`n03` and gdev `g07_024`, `g08_028` (the only gdev `del`s are on locals); no hot-code change.

**Tests:** `test_ail_fuzz82`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (258s). `test_ail_modconst` — 0 failed (173s). `update_manifest.py --check` rc 0.

**Report claims:** commit, cause, typed refusal message, fallback, tests, manifest — **verified**. “Before crashed” — **partially verified**: last/middle deletes were silent, crashes reproduced for index 0 and top-level. Exact p-number probe claims — **unverified** (their files not available), independent probes agree. Nested-global difference — **verified**.

Minor housekeeping: `python3 tools/ci_shards.py --check` reports `test_ail_fuzz82` unassigned (rc 1), but CI spreads unassigned modules and the test runs in exactly one shard; the task’s record rules did not require updating `ci_shards.json`.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre7.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
