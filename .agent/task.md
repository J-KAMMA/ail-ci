# bigint-fix10: no typed clone is made for mixed (typed + general) programs ("no typed clone") (B, coverage)

In a default build, a program that the typed path cannot take whole is compiled on the general path, and each function
that is typed-eligible is also emitted as a typed "mix" clone (`<exe>_mix*.c`, see AIL_NO_MIX). With `bigint` the
clones of int functions with unbounded values are no longer made, so the program runs fully general.

## Modules
test_ail_mixed_bounds (10 failures: list_len_boundary, str_slice, ... each for ir=0 and ir=1; `[] is not true : no typed clone`),
test_ail_flush_exit (3: mixed_int_value_error_in_clone, mixed_output_beyond_one_buffer, mixed_zero_division_in_clone; ir1: no typed clone).

## Reproducer
`x1.py`:
```
def risky(xs: list[int], i: int) -> int:
    return xs[i] + xs[i - 1]

def main():
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([5, 6, 7], 2))
    print(risky([5, 6, 7], 3))
main()
```
```
cd the repository checkout/AIL_CURRENT
AIL_SURFACE=python python3 -B python/pkg-v12/pyc.py x1.exe --file x1.py   # the test's command
ls x1*     # expected: x1.c and a mixed clone file (the test globs exe_<name>_<ir>_mix*.c next to the exe); there is none
```
CPython: `start {'k': [1, 2, 3]}`, `13`, then `IndexError: list index out of range` (exit 1). The output is right today;
what is lost is the typed clone of `risky` (`AIL_NO_GENERAL=1` compiles `risky` alone fine, so the clone builder
rejects it: probably the same driver check as fix03/fix06, an int `+` of two list elements needs a tagged local).

## Category
B. Let the clone builder use the tagged-int lowering (or the checked int64 arm with fallback) so these functions get a
clone again; the clone must still stop correctly: an int64-overflowing sum goes to the exact path, never wraps.

## Fixed means
x1 produces a mix clone; both modules pass for ir=0 and ir=1 (including the ASan/UBSan runs in test_ail_mixed_bounds).

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
