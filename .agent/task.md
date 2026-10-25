# bigint-fix07: functions that write a module variable are refused ("writes a module variable, which the tagged-int lowering does not cover") (B, coverage)

`ir/driver.py` apply() raises this for any function with `global x` / module-variable assignment (and for methods that
do `Counter.n += 1` style class-level state). Before `bigint` such programs compiled on the typed path; now the typed
build refuses and the default build goes to the general path (about 20x slower).

## Modules
test_ail_globals (13 tests: bump, tick, start, shrink, state.bump, attribute writes, range bounds read once),
test_ail_dunders (Counter__bump), test_ail_nested_functions/test_ail_unbound (a few programs; check message).

## Reproducer (`AIL_NO_GENERAL=1`)
`mv1.py`:
```
counter = 0

def bump() -> int:
    global counter
    counter += 1
    return counter

def main() -> None:
    bump()
    print(bump())

main()
```
CPython `2`. AIL: `not in the subset: bump() writes a module variable, which the tagged-int lowering does not cover`.
Second shape: a module-level `limit = 10**20` read by one function and written by another; the value must be exact
(CPython has no overflow), so the module variable has to be able to hold a big int (or the IR path must keep the
variable int64-checked and stop at the first value that does not fit, then fall to the general path for that program).

## Category
B. Lower module-variable reads/writes with the tagged-int type (global storage as `ail_tint`), or at least keep
the old checked int64 emitter for these functions and fall back only when a value does not fit. The test files stay.

## Fixed means
mv1.py prints 2 on the typed path alone; the 13 test_ail_globals tests pass; no test_ail_globals test gets a
"general path" note where it did not before.

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
