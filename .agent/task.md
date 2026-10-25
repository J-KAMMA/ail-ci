# bigint-fix05: tint runtime helpers missing from the C ("undefined reference to ail_tint_from_int64 / ail_tint_i64") (C)

Some typed+IR programs call `ail_tint_from_int64` / `ail_tint_i64` (and the callee prototype) but the tagged-int
runtime fragment is not emitted, or the call is emitted before its prototype. gcc warns `implicit declaration of function
'ail_tint_from_int64'` and the link fails with `undefined reference`. (Distinct from fix04, where the types disagree.)

## Modules
test_ail_modconst (2 tests: recursive entry reading a module table; str-set methods recursion), test_ail_silent2
(test_singleton_identity_typed_path_builds), test_ail_typed_inherit (test_ir_leaves_hierarchies_to_the_legacy_emitter),
test_ail_nested_functions (grid: undefined reference in `grid`/`dfs` programs; may be fix04 as well), test_ail_typed_blockers (1).

## Reproducers (typed path, `AIL_NO_GENERAL=1 AIL_IR=1`)
`m1.py`:
```
STOP = {"a", "the"}

def solve(n: int) -> int:
    if n <= 0:
        return 0
    return (1 if "a" in STOP else 0) + solve(n - 1)

def main() -> None:
    print(solve(4))
    print(solve(0))

main()
```
CPython `4` `0`. AIL: `undefined reference to 'ail_tint_from_int64'` / `'ail_tint_i64'` in `solve`. With `AIL_IR=0` it works.

`is1.py`:
```
def p(v: int) -> int:
    return v

def q(x: int) -> int:
    return 1 if p(1) is None else 2

def main() -> None:
    print(q(3))
main()
```
CPython `2`. AIL: `implicit declaration of function 'p'` and `'ail_tint_from_int64'` at the `p(...)` call (the call sits in a
statement context emitted before the prototype, and the helper fragment is not included).

## Category
C. Fix the fragment selection (the tint helpers must be included whenever any emitted code references them, including
discarded-result calls, `is` comparisons, recursive functions and module-table readers) and the prototype order.

## Fixed means
m1.py and is1.py build and print the CPython output on the typed path alone, with `AIL_IR=1` and `AIL_IR=verify`.
test_ail_silent2.NumberIs and test_ail_modconst pass. (test_ail_silent2.NanIdentity is a different cause, fix14.)

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
