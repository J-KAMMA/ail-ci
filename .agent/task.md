# bigint-fix16: `'%d' % obj` (and `%x`) with a class that defines only `__int__` / `__index__` raises TypeError (C, merge-tree test)

The main line fixed `%d` formatting of objects that define `__int__` or `__index__` (test_ail_pre128, which exists only in
the merge tree /home/bluec/code/ail-wt/bigint-merge). `bigint`'s format path replaced that code, so the fix is lost: the
merged compiler raises TypeError where CPython formats the number. (On plain `bigint` the same program also fails,
with `unsupported format string passed to non-int`.)

## Modules
test_ail_pre128 (test_trunc_only_percent).

## Reproducer (default build)
`pc.py`:
```
class IntOnly:
    def __int__(self):
        return 6

class IndexOnly:
    def __index__(self):
        return 7

def main():
    print('%d' % IntOnly())
    print('%d' % IndexOnly())
    print('%x' % IndexOnly())
    print(int(IntOnly()), int(IndexOnly()))

main()
```
CPython 3.12: `6`, `7`, `7`, `6 7`. AIL (merge tree): `TypeError: %d format: a real number is required, not IntOnly`
(bigint tree: `TypeError: unsupported format string passed to non-int`).
The full program is `test_ail_pre128.TRUNC_PERCENT` (a `__trunc__`-only class must give TypeError for `%d`; classes with
`__int__` give '6', `__index__` gives '7' for d/i/u/x/X/o/c/f-style codes exactly as CPython: see the expected
lines in the test's output with `python3`).

## Category
C. Fix in the bigint format routine (it must accept `__index__` for `%d %i %u %x %X %o %c`, `__int__` for `%d %i %u`,
and `__float__`/int for `%f %e %g`), keeping big ints exact (`'%d' % 10**30`, `'%x' % -2**70`).

## Fixed means
pc.py matches CPython; test_ail_pre128 passes in the merge tree; test_ail_bigint still passes.

Work on branch `bigint` in the repository checkout (reproduce there); run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing. test_ail_pre128 exists only in the merge tree: copy it from /home/bluec/code/ail-wt/bigint-merge/AIL_CURRENT/ to run it, without committing the copy.

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
