**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41706060840 (seed `2076019435`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 14: cpython='<end>' ail='3.50.000café  0.003'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076019435 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 4 + 8) % 41003
    return (h0(n - 1, a + 3) * 1 + h0(n - 2, a - 2) + n) % 41003


def h1(a: int, b: int) -> int:
    v1: int = ((17 - b) & a)
    v2: str = b"abc".decode()
    v3: list[int] = [1, 2, 3]
    v4: list[int] = [(72 * b)]
    if (not ((a - b) == (a * v1))):
        try:
            print(len(v3))
            print(((1e-7 % 7.0) - (100.75 + 2.5e-3)))
            print((b"x" + b"x").decode())
        except KeyError:
            v5: int = 31
            print((abs(0.3) ** 0.5))
        except IndexError:
            try:
                if ((-a) >= h0(6, (a + v1))):
                    raise KeyError('m2')
            except KeyError:
                print(-40)
            finally:
                print(148)
            try:
                v3 += [(b % 6), (-7 % 3)]
            except ZeroDivisionError:
                print(-16)
        else:
            v6: bytes = (b"x" * 2)
            print(a)
        w7: int = 0
        while w7 < 2:
            w7 += 1
            try:
                print(((a + a) // -8))
            except ZeroDivisionError:
                print(-15)
            v4.insert(-1, 31)
    elif ('AbCd' in v2.strip()):
        v4 += [(a - v1), (b * 21)]
        v8: int = 0
        try:
            v8 = ((v1 << 8) - (v1 // 9))
        except ZeroDivisionError:
            print(-55)
    else:
        print('日本')
    if (abs(b) >= (10 - a)):
        return v1
    return ((b - 37) - (a % 80))


def main() -> int:
    for i9 in range(-2, 5):
        print(('-7'.lstrip() * 1))
    try:
        try:
            print(f'#{33:>6}{(123456.789 // 2.5):.0f}', (99 % -2))
        except ZeroDivisionError:
            print(-24)
        finally:
            print(119)
        v10: float = 1e-7
    except ZeroDivisionError:
        v11: int = (41 + max(69, 23))
        print((('-7' * 0) + 'café'[:4]))
    finally:
        print(276)
    v12: str = (' pad ' + 'abc')[0:-1]
    v13: list[int] = [1, 2, 3]
    try:
        print(((28 // -4) / 4))
    except ZeroDivisionError:
        print(-51)
    v14: int = len(v13)
    v15: list[str] = '-'.join('3.5'.split(',')).split(',')
    w16: int = 0
    while w16 < 6:
        w16 += 1
        v17: int = ((23 - v14) + (-w16))
    print(0.3)
    v13 += v13
    try:
        v15.append(f'{(1e-7 + 1e-7):.3f}{'café':<6}{(0.3 / (abs(100.75) + 1.0)):.3f}')
        for i18 in range(3, 11, 2):
            w19: int = 0
            while w19 < 1:
                w19 += 1
                v12 = str((0.1 - 7.0))
                if ((35 >> 4) <= (-19)):
                    break
                if ((v13[-2] >= (v14 - 76)) or ((1.25 + 123456.789) > (1.25 * 3.0))):
                    continue
    except ValueError:
        v12 = ''.join(v15)
    except IndexError:
        al20: list[int] = v13
        v13.append(6)
        print(len(v13), len(al20), sum(v13) - sum(al20))
        v14 //= (abs((v14 - 80)) + 1)
    else:
        try:
            w21: int = 0
            while w21 < 2:
                w21 += 1
                v22: list[str] = []
                v23: set[int] = set(v13)
                if (int(str(1e-7)) > v12.strip().count('b')):
                    continue
            v24: dict[str, int] = {}
            v24['a'] = 10
            v24.pop('b')
        except KeyError:
            try:
                print(0.5)
            except ValueError:
                try:
                    print(('abc'[0].startswith('a')))
                except IndexError:
                    print(-13)
                print(abs(1e10))
        else:
            for i25 in v12:
                print(((v14 % (abs(v14) + 1)) + (v14 ** 3)))
                v14 = ((v14 - v14) >> 2)
            if ((v14 ** 3) == int(float((18 ** 2)))):
                try:
                    v14 = (v14 - h1(h0(3, len(v12)), (18 + 4611686018427387904)))
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-58)
            elif ((0.1 / 78) == (1e-7 - 1e-7)):
                v12 += v12.upper()
            else:
                v26: str = str((98 - v14)).upper()
    finally:
        print(217)
    print(v12)
    print(len(v13), sum(v13))
    print(v14)
    print(len(v15), ','.join(v15))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
-7
-7
-7
-7
-7
-7
-7
#    3349382 -1
119
276
-1.75
0.3
217
```

AIL stdout, exit code 0:

```
-7
-7
-7
-7
-7
-7
-7
#    3349382 -1
119
276
-1.75
0.3
217
3.50.000café  0.003
6 12
3
2 3.5,0.000café  0.003
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz222.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz222.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz222.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='N.N.Ncafé  N.N'`.

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
