**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41512305944 (seed `2075919106`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 1: cpython='-13' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075919106 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(a: int, b: int) -> int:
    v1: int = 0
    try:
        v1 = (60 | (b % a))
    except ZeroDivisionError:
        print(-10)
    finally:
        print(148)
    v2: str = 'q q'.upper()
    v3: list[int] = [b, 3037000499]
    for i4 in v3:
        v5: int = 3037000499
    print(((a ** 2) ** 0))
    if (not ((b ** 2) == len(v3))):
        return (b % 3)
    return (52 % (abs(v1) + 1))


def h1(a: int, b: int) -> int:
    v6: int = 56
    v7: str = '日本'
    v8: list[int] = [(18 % (abs(a) + 1)), 67, a]
    try:
        v9: str = '12'
        v8.extend([(95 ** 3)])
        v8.extend([(21 - v6), min(v6, 16)])
    except KeyError:
        print(("%-4d|" % 40))
        print(abs((0.3 * 1e-7)))
    except ZeroDivisionError:
        print(min(v6, v6), (0.5 + 2.5e-3))
    else:
        w10: int = 0
        while w10 < 5:
            w10 += 1
            v8.append((w10 ^ w10))
            if ((v6 // 7) >= (-w10)):
                continue
            v11: bool = ((24 + 31) >= 40)
    if ((a % 7) > 3):
        return (v6 - b)
    return sum(v8)


def main() -> int:
    v12: int = (round(float(9223372036854775807)) + (-2 ^ 10))
    print((~12))
    v13: list[int] = list(range(0, 5, 2))
    v13.sort()
    w14: int = 0
    while w14 < 1:
        w14 += 1
        v13.sort(reverse=True)
        v13.insert(3, v12)
    for i15 in v13:
        v16: bytes = (b"ab" + b"abc")
    v13 += v13
    v13.append((23 ** 1))
    print(v12)
    print(len(v13), sum(v13))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-13
9223372036854775796
9 18446744073709551627
```

AIL stdout, exit code 1:

```

```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz218.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz218.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz218.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='-N' ail='<end>'`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
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
