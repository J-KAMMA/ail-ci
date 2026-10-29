**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40949475519 (seed `2075521727`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=3; line 4: cpython='110' ail='159'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075521727 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(a: int, b: int) -> int:
    v1: int = 0
    try:
        v1 = ((b % 3) % -3)
    except ZeroDivisionError:
        print(-35)
    finally:
        print(159)
    v2: str = 'Zed'.lstrip().strip()
    v3: list[int] = [3] * 3
    try:
        print(float((a // 2)))
    except ZeroDivisionError:
        print(-31)
    v3.insert(3, 61)
    try:
        print(((abs(123456.789) ** 0.5) / 13))
    except ZeroDivisionError:
        print(-98)
    if ('AbCd' in 'hello'.lstrip()):
        return (a // -5)
    return (-1)


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 1 + 0) % 90003
    return (h1(n - 1, (a * 6 + n) % 90003) + 1) % 90003


def main() -> int:
    v4: str = ""
    try:
        v4 = (str(h0((53 >> 4), 92)) + '日本')
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-12)
    finally:
        print(110)
    for i5 in v4:
        print((f'{(6 - 51)}' + 'abc'))
        v6: list[int] = [1, 2, 3]
        try:
            v6[-3] = len(v6)
        except IndexError:
            print(-45)
    v4 = v4
    v7: list[int] = [(98 - 29), -7, (-9223372036854775807 ** 1)]
    v4 = (str((53 + 9223372036854775807)) + str((12 + 55)))
    try:
        if ((30 ** 3) <= int(str('a,b,c'.count('a')))):
            raise ZeroDivisionError('m0')
    except ZeroDivisionError:
        print(-11)
    try:
        print((41 * (92 % 7)))
    except ZeroDivisionError:
        print(-35)
    finally:
        print(143)
    v7 += v7
    print(((0.3 - 123456.789) + (123456.789 + 2.5e-3)))
    v7.append(len(v4))
    al8: list[int] = v7
    v7.append(6)
    print(len(v7), len(al8), sum(v7) - sum(al8))
    v9: dict[str, int] = {}
    v9['e'] = 29
    v9['b'] = 24
    v9['dd'] = 53
    v9['c'] = 30
    try:
        al8.insert(2, 85)
        v9[v4] = (-53)
    except ValueError:
        print(100.75)
    except KeyError:
        al10: list[int] = al8
        if len(al8) > 0:
            al8[0] = 7
        print(len(al8), len(al10), sum(al8) - sum(al10))
        v9.pop('b', 7)
    else:
        try:
            print(ord('café'.upper()[0]), v4)
        except IndexError:
            print(-19)
    finally:
        print(227)
    v11: int = (int(1e-7) - (55 | 7))
    print(v4)
    print(len(v7), sum(v7))
    print(len(al8), sum(al8))
    ks13: list[str] = []
    for k12 in sorted(v9):
        ks13.append(k12)
    print(len(v9), sum(v9.values()), ','.join(ks13))
    print(v11)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
159
1.0
27.028014066495864
110
-45abc
-45abc
-45abc
-45abc
41
143
0.3025000000052387
8 8 0
67 922337203685477586067
227
922337203685477586067
9 -18446744073709551378
9 -18446744073709551378
5 83 922337203685477586067,b,c,dd,e
-55
```

AIL stdout, exit code 3:

```
159
1.0
27.028014066495864
159
1.0
27.028014066495864
110
-45abc
-45abc
-45abc
-45abc
```

AIL stderr:

```
AIL limit: int_overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz206.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz206.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz206.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='N'`.

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
