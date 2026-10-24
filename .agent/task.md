**Fix one pre-existing difference from CPython.** A reviewer of job `pre26` recorded these as already present before that job:

- `p21`/`p22`: `s = e.args[0]; repr(s)` still textual (`'3.0'`), and list/attribute/dict aliases likewise; direct `repr(e.args[i])` is fixed.
- `p9`: general path `repr(e.args[-1])` on an `OSError` prints the filename instead of strerror.
- `p34`: general-path `repr(e)` of a numeric exception still `ValueError('3.0')`; `args_mutate` and `args_getattr` unchanged (eager text, unsupported `getattr`).

**Tests/records:** `test_ail_pre26`, `test_ail_safetynet` (86 s), `test_ail_exc_str` (94 s), `test_ail_files`, `test_ail_corpus_findings3` all pass, 0 failed; `update_manifest.py --check` passes. Records/DIFFERENCES/DEVLOG present; commit message and `Co-Authored-By` correct.

**Claim check:** fix and probe claims verified; “general path unchanged” is true behaviourally, though C for programs that read exception text (but not `repr(args)`) gains one unused static helper; non-exception gdev C is byte-identical (`g00_000`, `g05_010`, `g20_000`). The DIFFERENCES “both builds match CPython” wording is slightly overbroad because the general path refuses multi-arg raises by name (acceptable). Test timings not exactly reproduced but all five modules pass.

**Speed:** not measured; change is off the hot path (only `repr` of an exception argument). `tools/icount.c` is in fact present.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre48.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
