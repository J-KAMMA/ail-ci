# bigint-fix14: general path: `list.count / index / remove` of a NaN lose identity semantics (C)

CPython compares list items by identity first, then `==`, so `[m, 1.0].index(m)` finds the same NaN object. The general
path (with the bigint changes) raises `ValueError: nan is not in list`.

## Modules
test_ail_silent2 (NanIdentity.test_general_path_with_a_float_list; the other silent2 failure is fix05).

## Reproducer (general path; use `--general-only` or the default build)
`nan.py`:
```
def main():
    big = 1e308 * 10
    m = big - big
    xs = [m, 1.0]
    print(xs.count(m), xs.index(m), xs.count(1.0))
    ys = [1.0, m, 2.0]
    ys.remove(m)
    print(len(ys), ys.index(2.0))

main()
```
CPython: `1 0 1` then `2 1`. AIL: no stdout, exit 1, `ValueError: nan is not in list`.
Check whether the new object-equality helper compares by value only (the same float boxed twice is two objects) and
fix the identity shortcut (`a is b or a == b`) in count/index/remove/`in`/list equality, also for ints (a big int is
an object: `x in [x]` with a NaN-free value must still work, and a NaN stored in a tuple/dict key keeps CPython's rule).

## Category
C. Fixed means: the reproducer matches CPython; `m in [m]` is True, `[m] == [m]` is True, `m == m` is False.

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
