# bigint-fix17: tests that still expect the old int64 overflow stop or old messages (A, update the test expectations)

The compiler is now right (it matches CPython); the tests pin the old wrong behaviour. Update each expectation to
CPython's real output (verify every program with `python3`), keep the test's purpose, do not touch the compiler.

## Cases
1. test_ail_fuzz_findings.test_int_overflow_stop_runs_no_finally_block (4 subtests: LIMIT_IN_TRY / LIMIT_IN_HANDLER x default/ir).
   `x = 9223372036854775807 - len(v) * -1` is 9223372036854775810 in CPython: no stop. CPython output for the try program is
   `3` (len(a)... print it yourself) `9223372036854775810`, `2`, `70`, `4`, `5`, exit 0. Rewrite the test to check the
   finally/handler ordering with a stop that still exists (e.g. a ZeroDivisionError or `[]` IndexError at the same place), or
   assert CPython's output.
2. test_ail_ir_s0.test_overflow_and_zero_division_keep_their_messages: `grow(5)` = 5 * 3**80 is
   739044147071729616580416051031916488005 in CPython; the test expects exit 1 `integer overflow`. Keep the ZeroDivision
   half; make the overflow half a big-int result.
3. test_ail_ir_s3 test_sanitizers_report_nothing_on_the_ir_builds (program 'uncaught', args 5): IR output
   `start 5` + `27670116110564327421` (exit 0) equals CPython; the legacy build stops with exit 1. Compare with CPython
   instead of with the legacy build, or drop the legacy comparison for programs whose values pass 2**63.
4. test_ail_ir_s3b test_sanitizers_report_nothing_on_the_sharing_builds (program 'refused'): the IR/general build prints
   exactly CPython's `1 2210 / 1002331 2041259 / 41 / 12 / 79 / 8 / 4 725884 / 6 34`; the `AIL_IR=0` legacy build prints
   different numbers (`1089559 ...`) because the program has aliased lists that the legacy emitter refuses/mishandles.
   Compare the IR run to CPython, not to legacy.
5. test_ail_ir_gridbounds (6 tests) and test_ail_ir_s3 (1): stderr is now `IndexError: bytearray index out of range` /
   `IndexError: list index out of range`, which is CPython's last traceback line; the tests expect `IndexError` alone or the bare message. Update.
   (The `stats.jsonl` FileNotFoundError errors in gridbounds are not this; they are fix12.)
6. test_ail_ir_specsel (3 tests): `0 not greater than or equal to 1` and a pin `'__builtin_expect((uint64_t)('` missing from
   the C: the checked-add arm text changed with the tagged ints. Decide with the test text whether the pin is still the
   point of the test (re-pin to the new arm) and make sure overflow now means "go to the exact path", not "stop".
7. Merge-tree-only: test_ail_debug_flush.test_overflow_stop_keeps_what_was_printed (expects exit 1 at the int64 limit; CPython goes on; compare
   the printed prefix + CPython), test_ail_pre160.test_out_of_int64_index_is_refused (round(2.5, <obj with __index__ returning
   10**30-(10**30+5)>) : CPython prints `0.0` and `2.0`, no overflow error), test_ail_pre97.test_maxsplit_literal_above_int64_refused
   (the refusal wording changed to "... fit in a 64-bit signed integer ..."; expect the new text, or CPython's behaviour if
   the compiler now accepts it). These three exist only in /home/bluec/code/ail-wt/bigint-merge; make the edits there on
   a scratch copy and send the patch, or leave them as a list for the integrator if you cannot run them.

## Category
A. Fixed means: each listed test passes with the corrected expectation; `git diff` touches only tests.

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
