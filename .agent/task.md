# bigint-fix13: check-stage diagnostic for an out-of-range literal lost its precise location kind (C, small)

`ail check` on the native `.ail` surface reports an int literal above int64 as a type error. The test pins the location
kind `source` (exact column) and now gets `source_statement`. The line/column assertions before it pass, so only the
kind label changed (or the diagnostic is now made at a later stage with statement-level provenance).

## Modules
test_ail_source_check (3 subtests of test_int64_literal_limits_and_original_positions: values 9223372036854775808,
-9223372036854775809, +9223372036854775808). The other 3 failures of this module are fix03 (`ail check --syntax python
--interface` on `def read(box:Box)->int: return box.get()` returns "has an int operation the local proof cannot bound").

## Reproducer
`s1.ail` (note the non-ASCII comment in the real test; keep it):
```
# x
fn main()->int {let label="a"; return 9223372036854775808;}
```
`python3 -B ail_chatgpt.py check s1.ail` ->  `... "line": 2, "column": 32, "function": "main", "location_kind": "source_statement"`;
the test expects `"source"`. The message text also still says "a 64-bit signed integer ... CPython computes it exactly ...
this compiler would have to wrap it": decide with the SEMANTICS owner text whether the native `.ail` surface keeps int64
literals (then keep the error, fix the location kind) or the message needs the new wording; do not change semantics,
only restore the location kind and keep the message accurate for this surface.

## Category
C (diagnostic regression). If the new `source_statement` is deliberate, it is A: update the test and say why.

## Fixed means
test_int64_literal_limits_and_original_positions passes with the exact column; the `.ail` surface still rejects the literal.

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
