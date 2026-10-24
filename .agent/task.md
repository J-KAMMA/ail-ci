**Fix one pre-existing difference from CPython.** A reviewer of job `pre68` recorded these as already present before that job:

1. Large finite float `%d` (`1e20`, `9.3e18`): CPython prints the big integer; HEAD exits 3 `AIL limit: integer overflow`; base exits 1 `TypeError`. The same int64 limit hits `print(10**20)` on both trees, so this is the language's int64 width, not this change.
2. Augmented float assignment (`y += 0.5`, `w -= 0.25`) leaves `infer_kind` as int: CPython prints `1`/`0`; base and HEAD both exit 1 with the same `TypeError` (identical).
3. `"%.3d" % 7`: build fails with a compiler `TypeError` on both base and HEAD (message-construction bug in the precision refusal); `"%.3d" % 3.7` now works on HEAD.
4. `"%lld"`: AIL prints on both trees, CPython raises `ValueError` (identical).

**Tests / records.** `test_ail_pre68 test_ail_safetynet test_ail_files test_ail_corpus_findings3` -> 27 tests, 1 skipped, OK. Manifest `--check` rc 0. Commit `1e66e46` has the required `Co-Authored-By`.

**Report claims.** Fixed on both builds: verified. Test/DEVLOG/DIFFERENCES/manifest: verified. 27 passed/1 skipped: verified. 17-probe claim: verified from the worker log plus reruns of key cases. The `d`/`i`/`u` wording is inaccurate (only `d` changed; `i`/`u` already used the runtime), but behaviour is correct. No regression found in int formatting, flags, widths, int64 edges or mutation.

**Unverified.** Speed (no `~/corpus/gdev` program uses literal `%d` formatting); full 17-probe rerun (log inspected, key cases rerun).

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre100.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
