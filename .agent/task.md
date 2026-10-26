# bigint-fix09: `parallel for` bodies are refused because they reach the tint helpers (B, coverage)

Typed parallelism (typedpar.py: ThreadPoolExecutor.map, Pool.map, scoped Thread) checks that a parallel body only
calls thread-safe helpers. The IR now emits `ail_tint_from_int64` / `ail_tint_i64` (and `ail_list`) inside those
bodies, and the checker refuses: `parallel for (line 9): the body reaches ail_list, ail_tint_from_int64, ail_tint_i64,
which is not known to be thread-safe`. Before `bigint` these programs ran on the typed path without the GIL.

## Modules
test_ail_typed_parallel (7 failures), test_ail_typed_submit (4), test_ail_typed_tuples (1 `parallel for` failure; the rest
of that module is fix02).

## Reproducer (`AIL_NO_GENERAL=1`)
`par1.py`:
```
from concurrent.futures import ThreadPoolExecutor

def f(x: int) -> int:
    return x * x + 1

def main() -> None:
    xs = [1, 2, 3, 4]
    with ThreadPoolExecutor(max_workers=2) as ex:
        print(list(ex.map(f, xs)))

main()
```
CPython `[2, 5, 10, 17]`. AIL: `parallel for (line 9): the body reaches ail_list, ail_tint_from_int64, ail_tint_i64 ...`.

## Category
B. The tint helpers that only convert or test small values are pure; add them (and whatever the tagged-int arms call
for the small case) to the thread-safe list, and make sure a result that needs a big int in a worker is handled
thread-safely (stop with the exact error / allocate without shared state) rather than silently allowed. If a body
can allocate a big int, either refuse it by name with a `write instead:` line or give each worker its own state.
Do not weaken the race check for list/bytearray writes.

## Fixed means
par1.py compiles with `AIL_NO_GENERAL=1` and prints the CPython output at 1..8 workers; the three modules pass,
including their ThreadSanitizer cases; a worker that overflows int64 gives CPython's exact value or a named refusal.

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
