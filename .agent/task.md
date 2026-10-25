# bigint-fix18: typed-only (`AIL_NO_GENERAL=1`) builds now refuse programs whose ints can exceed int64 (A, update the tests)

The typed path has int64 only; the compiler now proves a program cannot need a big int, otherwise the typed-only
build is refused with `the module code can need an int beyond int64 (it calls main(), which can need a big int
(<reason>)); the typed path has int64 only and the general path has exact big ints`, and the default build runs it on the
general path with exact results. That is intended. These tests build programs of that kind with the typed path alone and
expect success.

## Cases (reason in brackets)
- test_ail_crypto: ~30 failures, `typed build of ints/interrors: ... int.from_bytes` [a call of int.from_bytes can be any size]
  (the others in that module are fix02).
- test_ail_stdlib_batch1: `math.factorial` [a call of math.factorial]; `pow(x, y, m)`/int-with-base programs [an int
  operation beyond int64].
- test_ail_spec_fixes: `f()` with `**` and a non-constant exponent [`**` with an exponent that is not a constant].
- test_ail_dunders: `function __pow__() can need an int beyond int64 (** with an exponent that is not a constant)` (AIL_IR=0 run).
- test_ail_globals / test_ail_crypto "ints": module code that calls main() which can need a big int.

## What to do
For each failing subtest: the program is fine on the default build. Change the test to build it in the default mode
(general path allowed) and require CPython's output, and, where the test wanted the typed path (speed or a typed-only
feature), shrink the program so a proof bounds it (constant small exponent, `int.from_bytes` of at most 7 bytes) or assert
that the refusal text is the new named reason. Verify every output with `python3`. Do not remove coverage of the typed
path for programs that are bounded.

## Category
A. Fixed means: each listed subtest passes; `git diff` touches only tests; add one new assertion per module that the
refusal names the big-int reason, so the intended behaviour is pinned.

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
