# bigint-fix08: "no implicit conversion from tint to i1" for a maybe-unassigned int local (B, coverage)

The UnboundLocalError support (unbound.py) gives a maybe-unassigned local a flag. When that local is an int that now
needs the tagged-int lowering, the C emitter raises `no implicit conversion from tint to i1`, the function leaves
the typed path, and the default build prints `note: built on the general path (about 20x slower) because f1() needs the
tagged-int lowering, which does not cover it: no implicit conversion from tint to i1`. test_ail_unbound requires that the
fixed programs stay on the typed path (no "general path" note).

## Modules
test_ail_unbound (8 failures: branch, definite, classes, kinds, loops, script, try, random; all with ir=1 default build).

## Reproducer (default build, look at the note)
`u1.py`:
```
def f1(a: int) -> int:
    if a > 0:
        z = a
    return z + 1

def main() -> None:
    print(f1(3))
    try:
        print(f1(-1))
    except UnboundLocalError as e:
        print("unbound", e)

main()
```
```
cd the repository checkout/AIL_CURRENT
python3 -B ail_chatgpt.py compile u1.py --syntax python -o u1.exe 2>&1 | grep general
```
CPython: `4` then `unbound cannot access local variable 'z' where it is not associated with a value`. AIL output is right
(it runs on the general path) but the note shows the typed path was lost. Expected: no note, same output.

## Category
B. Make the flag test in the tagged-int lowering compare the flag (an `i1`), not the tint value (probably a
conversion inserted where the unbound check reads the variable, or a `bool` of a tint used as the flag).

## Fixed means
u1.py compiles with no "general path" note and prints the CPython output; all of test_ail_unbound passes.

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
