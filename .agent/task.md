**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42517310228 (seed `2076520850`, CPython 3.12, modes default+ir) found a DIFF: `line 30: cpython='True' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076520850 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = f'{(abs(123456.789) ** 0.5):.2f}{abs(0.3):>10.1f}'.find('x')
    v2: str = '3.5'[0:4].replace('l', '-')
    v3: list[int] = [min(v1, b), b]
    w4: int = 0
    while w4 < 5:
        w4 += 1
        w5: int = 0
        while w5 < 4:
            w5 += 1
            v3 += v3
            v6: dict[str, int] = {}
            v6['a'] = 13
            v6['dd'] = -7
            v6['b'] = 29
            print((max(a, w5) * (w4 ** 0)))
        v7: dict[str, int] = {}
        v7['dd'] = 19
        v7['a'] = 84
        v7['c'] = 73
        try:
            if (('ab' * 3).endswith(' ')):
                assert (((a - w4) <= b) or (a == 10)), "boom"
        except AssertionError:
            print(-5)
        else:
            print(7)
    v8: bytes = b"12"[-2:-1]
    v3.sort(key=lambda q: (-q, q))
    if (255 > (a * a)):
        return (a - 41)
    return ((b // a) + len(v3))


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 4 + 2) % 42003
    return (h1(n - 1, a + 1) * 5 + h1(n - 1, a - 1) + n) % 42003


def main() -> int:
    print((69 ^ 66))
    print(((abs(3.0) ** 0.5) * 1.25))
    try:
        v9: float = max(float(50), 1.25)
        if ((not (18 > (35 ** 2))) or ('abc'[1:2].endswith('he'))):
            v10: int = ((88 - 51) + 49)
        else:
            v11: int = ((58 ** 1) // (abs(91) + 1))
            print(64)
        v12: list[int] = [(9223372036854775807 % (abs(12) + 1)), 23]
    except ZeroDivisionError:
        v13: list[int] = [30, (-9223372036854775807 << 1), max(19, 81), 53]
    except ValueError:
        print('日本')
        v14: str = f'#{(77 / 8):>10.1f}'
    else:
        print((38 >> 11))
    finally:
        print(282)
    try:
        if ((((71 & 16) > 3) or ('ab'[:-1] >= 'a,b,c'[:2])) or ('AbCd' in 'café'[:])):
            for i15 in range(9, -2, -1):
                w16: int = 0
                while w16 < 5:
                    w16 += 1
                    print((abs((1e10 + 123456.789)) ** 0.5))
                    if ((-1 > 3) or 'x'.isupper()):
                        break
                    print(100.75)
                v17: bool = ((i15 > h0((i15 - i15), 9223372036854775807)) and (('café' * 0).endswith('a')))
            for i18 in range(5, 1, -1):
                print('AbCd'.lower()[-2:-1])
        elif ((' pad ' + ' pad ').endswith('he')):
            try:
                print(abs(61))
            except ValueError:
                print(-28)
        else:
            v19: str = ('q q' + 'x'.strip())
            try:
                print((h0((40 + 51), len(v19)) >= 255))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-34)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-43)
    try:
        print(int((100.75 * 0.3)), 100.75, (max(60, 3037000499) != int('hello')))
    except (ValueError, ZeroDivisionError):
        print(-89)
    for i20 in range(1, 5, 3):
        try:
            if (98 == int(("<%5d>" % (i20 // -5)))):
                raise KeyError
        except KeyError:
            print(-98)
        finally:
            print(193)
        v21: int = ((i20 + i20) >> 11)
        w22: int = 0
        while w22 < 6:
            w22 += 1
            print((int(1e-7) > len(("%-4d|" % 25))), ((97 + v21) > 3), ' pad '.upper())
    for i23 in range(0, 8):
        v24: int = 0
        try:
            v24 = (34 % -6)
        except ZeroDivisionError:
            print(-29)
        finally:
            print(198)
    v25: list[int] = [1, 2, 3]
    v26: float = min(0.5, 0.1)
    try:
        if (((-6 + 18) >= len(str(79))) or (('-7' + 'café') != 'a,b,c'.upper())):
            raise IndexError('m3')
    except (IndexError, ValueError):
        print(-33)
    else:
        print(54)
    v27: int = (2 + 71)
    al28: list[int] = v25
    al28.append(4)
    print(len(v25), len(al28), sum(v25) - sum(al28))
    for i29 in al28:
        if (v27 <= '3.5'[2].find('-7')):
            for i30 in range(2, 9, 1):
                print(v26, ((3.0 + 1e-7) <= (v26 + v26)), (' pad ' in 'AbCd'[0:-1]))
        elif (((v27 ** 0) <= (i29 * 60)) and (i29 == v27)):
            print((b"a,b" + b"Zed").decode())
        else:
            v31: str = 'abc'[-2:4][1:2]
            print(((69 << 6) == (48 ** 1)), f'{v26:>10.1f}/')
    for i32 in range(0, 10, 1):
        v27 = ((i32 - 14) - ('x' + 'abc').count('a'))
    print((-v27))
    print(len(v25), sum(v25))
    print(v26)
    print(v27)
    print(len(al28), sum(al28))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
7
2.1650635094610964
0
282
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
True
-89
193
```

AIL stdout, exit code 1:

```
7
2.1650635094610964
0
282
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
91
91
91
91
7
```

AIL stderr:

```
TypeError: '<' not supported between instances of 'object' and 'int'
```

**What to do.**
1. Save the program as `/tmp/probes/fz244.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz244.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz244.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='True' ail='<end>'`.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
