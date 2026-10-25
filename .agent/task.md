# bigint-fix02: `int(<str or bytes>)` is refused on the typed IR path ("parses an int from text") (B, coverage)

`ir/driver.py` (apply(), about line 160) raises `Unsupported('%s() parses an int from text, which the tagged-int
lowering does not cover')` for every function that calls `int(s)`, `_ail_int2`, or a `*str_to_int` / `*bytes_to_int`
helper on a str/bytes operand. Before `bigint` these programs compiled on the typed path. Now the typed path refuses
them and the default build falls to the general path (about 20x slower, and with 16-bit strings, so e.g.
`chr(128512)` then dies with "AIL internal error: chr() non-BMP code point requires 32-bit strings").
This is the biggest single cause: about 25 modules.

## Modules
test_ail_re, test_ail_stdlib_batch4, test_ail_stdlib5, test_ail_stdlib_batch3, test_ail_stdlib_batch1,
test_ail_clock, test_ail_subprocess, test_ail_silent5, test_ail_exc_str, test_ail_tuples, test_ail_match,
test_ail_typed_blockers, test_ail_raise_from, test_ail_dunders, test_ail_crypto (about 60 of its 93 failures),
test_ail_json_fast, test_ail_python_syntax, test_ail_spec_fixes, test_ail_typed_tuples, test_ail_typed_parallel,
test_ail_ir_s4a (`int(sys.argv[1])` programs), test_ail_quirks; test_ail_zlib in the merge tree (its failures there are
this message; in the sandbox zlib fails only because zlib.h is missing, ignore that).
Fallout only (should pass once this is fixed): test_ail_ir_f1 and part of test_ail_spec_fixes (the chr() error above).

## Reproducers (typed path alone; the default build silently takes the general path)
`b3.py`:
```
def main() -> None:
    s = input().split()
    t = 0
    for w in s:
        t += int(w)
    print(t)

main()
```
stdin `1 2 3`. CPython: `6`. AIL (`AIL_NO_GENERAL=1`): `not in the subset: main() parses an int from text, which the tagged-int lowering does not cover`.

`ch.py` (shows the fallout; default build):
```
def main():
    n = int(input())
    print(ord(chr(n)))
main()
```
stdin `128512`. CPython `128512`. AIL: `AIL internal error: chr() non-BMP code point requires 32-bit strings`.

Also cover `int(bytes_value)`, `int(s, 16)`, `int(s)` of a value longer than 18 digits (CPython gives the exact big int; the
tagged int must hold it and `print` it), and the `ValueError` text for bad input (`invalid literal for int() with base 10: 'x'`).

## Category
B. Fix the compiler, keep the tests. Preferred: lower `int(text)` in the tagged-int lowering (small result stays a
tagged small int, a result beyond int64 becomes a big int; the runtime already has the exact parser the general path
uses, see bigint_obj.py / the `ail_tint` fragments). Acceptable only if lowering is not feasible in one session:
make the failure local (the function that parses text keeps the old int64-checked emitter with an overflow check that
falls back, instead of making the whole program general). Do not widen what silently wraps.

## Fixed means
The listed modules no longer show "parses an int from text"; `b3.py` compiles with `AIL_NO_GENERAL=1` and prints 6;
`int("123456789012345678901234567890")` prints the exact value; `ch.py` prints 128512. Report the modules that still
fail for a different reason (name the cause).

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
