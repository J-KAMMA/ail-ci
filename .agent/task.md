**Finish this job.** Your earlier commits are on this branch, but the last review ran out of time before giving a verdict. Check that the work meets the original task below, measure as it asks, and fix anything missing. If the change does not reach the keep threshold, revert it and say so. Commit.

--- ORIGINAL TASK ---
**Speed: csv_table is 2.5x slower than C.** It builds fields with repeated `field += ch` and does a `dict.get` plus list updates per row. Make `s += x` on a str that nothing else references append in place (amortized growth) instead of copying. Then measure again and pick the next biggest cost.

**How to work (speed rules).**
1. Before building anything, measure. Profile the app with `tools/icount.c`, or perf if available, and state the share of run time spent in the part you will change. Give the best possible gain that follows (Amdahl).
2. Change the compiler or runtime, not the app source in `bench/apps`. The point is that idiomatic AIL code gets fast.
3. Output must stay identical. `compare.py` checks it against the Python oracle, and the full suite must keep passing, which the integration gate checks.
4. Report `python3 bench/compare.py --app csv_table` before and after (time ratio vs C, RSS, binary size). If the gain is under 3%, or its range overlaps the range before the change, revert and report what you measured. Commit.


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
