**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41139193399 (seed `2075623813`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=3; line 10: cpython='<end>' ail='0 False <    0>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075623813 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 0) % 54003
    return (h0(n - 1, a + 1) * 3 + h0(n - 2, a - 2) + n) % 54003


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 2 == 0:
            continue
        t += x
    return t


def main() -> int:
    v1: float = 2.5e-3
    if ('12'.isdigit() or ('hello' in '-7')):
        try:
            if ('ab' in ("%-4d|" % (2 - 24))):
                raise AssertionError('m6')
        except AssertionError:
            print(-1)
        finally:
            print(187)
        try:
            print(0)
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-49)
        finally:
            print(187)
        v2: bytes = (b"a,b" + b"ab")
    elif ((41 - 4611686018427387904) < max(39, 35)):
        v1 = ((v1 + v1) // 2.5)
    v1 += (v1 * 1e-7)
    v3: str = '-'.join(("<%5d>" % 64).split('a'))
    v3 += 'abc'.upper()
    try:
        v4: bytes = b"ab"[:]
    except ZeroDivisionError:
        v5: int = ((~3037000499) ^ (30 + 3))
    except IndexError:
        print(b"12".decode())
    else:
        w6: int = 0
        while w6 < 6:
            w6 += 1
            print(62)
            if (7.0 < 1.25):
                print((v1 - v1), ((w6 ** 1) > (w6 - w6)))
                if v3.isalpha():
                    break
            elif (v3 in f'{'q q'}{(w6 + 92):3d}'):
                v3 = f'-{float(-8):>10.1f}'
        print((3.0 / (14 // (abs(3037000499) + 1))), (1e10 - v1), (min(-1, 14) <= 0))
    v7: list[int] = list(range(0, 7, 1))
    try:
        print((76 % -2), ((round((0.3 / (abs(123456.789) + 1.0))) <= 0) and v3.isspace()), ("<%5d>" % int((abs(v1) ** 0.5))))
    except ZeroDivisionError:
        print(-96)
    finally:
        print(108)
    if (83 > -9223372036854775807):
        w8: int = 0
        while w8 < 3:
            w8 += 1
            for i9 in range(0, 11, 1):
                v10: list[int] = [abs(93)]
                al11: list[int] = v7
                v7.append(4)
                print(len(v7), len(al11), sum(v7) - sum(al11))
                print(((79 << 6) * (4611686018427387904 ** 3)))
    print((len((v3 * 3)) >= 29))
    print((-(14 + -5)))
    al12: list[int] = v7
    al12.reverse()
    print(len(v7), len(al12), sum(v7) - sum(al12))
    al12.pop()
    v13: bool = ((v1 * 3.0) < (123456.789 - 1.25))
    print(v1)
    print(v3)
    print(len(v7), sum(v7))
    print(len(al12), sum(al12))
    print(v13)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
187
0
187
62
62
62
62
62
62
```

AIL stdout, exit code 3:

```
187
0
187
62
62
62
62
62
62
0 False <    0>
108
8 8 0
```

AIL stderr:

```
AIL limit: int_overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz207.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz207.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz207.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='N False <    N>'`.

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
