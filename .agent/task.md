# bigint-fix11: bit operations on unproven ints leave the IR ("a bit operation on an unproven int") (B, coverage)

The IR lowering now declines functions that use `& | ^ << >> ~` on ints it cannot bound: the function is recorded
`path: legacy, reason: a bit operation on an unproven int` and compiled by the old int64 emitter (so the typed result
stays int64-checked; speed and exactness for values beyond 2**63 are the open points). The tests require these
functions to be on the IR path.

## Modules
test_ail_ir_s0 (test_generated_numeric_programs_match_cpython seed=23: `Items in the first set but not the second: 'f6'`
with reason 'a bit operation on an unproven int'), test_ail_ir_s3 (`put`, `w2`, `h1`: generated list-programs whose
functions use bit operations). Other failures of those two modules are A (fix17).

## Reproducer
`bit1.py`:
```
def mix(a: int, b: int) -> int:
    return ((a & b) ^ (a << 3)) | (b >> 1)

def main() -> None:
    t = 0
    for i in range(1000):
        t += mix(i, i + 3)
    print(t)

main()
```
`AIL_IR_STATS=/tmp/s.jsonl python3 -B ail_chatgpt.py compile bit1.py --syntax python -o bit1.exe` then `cat /tmp/s.jsonl`:
`mix` is `"path": "legacy", "reason": "a bit operation on an unproven int"`. Output `4142726` matches CPython.
`<<` with a large shift must give CPython's exact big value (e.g. `1 << 100`, `(a << 70) >> 68` for a > 2**20); `>>` of a
negative, `~x`, `&`/`|`/`^` of negative ints must follow two's-complement semantics at any size (CPython).

## Category
B. Lower the bit operations in the tagged-int lowering (small case inline, big case through the bigint routines),
so `mix` is `path: ir`. Check against CPython with negative operands and shifts of 0, 63, 64, 65, 200.

## Fixed means
`mix` is on the IR; a differential test of the operators over negative and large operands equals CPython; test_ail_ir_s0
and test_ail_ir_s3 lose the 'bit operation' items.

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
