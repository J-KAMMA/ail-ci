**Fix one pre-existing difference from CPython.** A reviewer of job `pre278` recorded these as already present before that job:

- `v1_return_route` (`make(4).f()` where `make` returns the colliding `C`): both base and HEAD print `-1` where CPython prints `40`; the refusal does not resolve a function-return receiver.
- `r6_setattr`: `setattr(self,'f',lambda:101)` still yields `102` vs CPython `101` on base and HEAD.
- `r8_nested_class`: refused for the nested class definition on base and HEAD.
- Typed-only (`AIL_NO_GENERAL=1`) also refuses `r1` for its lambda-as-value rule; not part of the two cmp builds.

**Report claims:** direct collision fixed (verified); r1/r2/r3 now match (verified); r4/self-subclass/inherited/list/dict/attr/alias/non-callable refused (verified via tests and probes); r7 match (verified); r6/r8 pre-existing (verified); field collection stays inside its class (verified by code inspection); `test_ail_pre278`+`test_ail_safetynet` pass on HEAD (verified, 0 failed); manifest `--check` clean (verified); 4-module test run and typed-only build not rerun by me (out of reviewer scope / acknowledged).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not rerun here, per scope); typed-only build not separately validated.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre289.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
