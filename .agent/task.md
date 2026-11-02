**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41356299474 (seed `2075822001`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 146: cpython='0.548' ail='242'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075822001 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 2 + 7) % 21003
    return (h0(n - 1, (a * 1 + n) % 21003) + 0) % 21003


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 2 + 8) % 11003
    return (h1(n - 1, (a * 6 + n) % 11003) + 9) % 11003


def h2(a: int, b: int) -> int:
    v1: int = 40
    v2: str = str(len('abc'))
    v3: list[int] = []
    try:
        v3 = [(-1 // a), round(float((59 ** 1))), (b - b), (43 ** 3)]
    except ZeroDivisionError:
        print(-48)
    print(str(abs(85)))
    for i4 in v3:
        v5: list[int] = []
    print(((abs(b) == (b - v1)) and ((95 // v1) < (a + 45))))
    if (len(v2) > 3):
        return (b * 95)
    return ((-1 // 3) // (abs(b) + 1))


def main() -> int:
    v6: list[int] = [(0 // (abs(3037000499) + 1))]
    if (not ((-1 | 56) > (42 // -3))):
        print((0.3 + (0.1 * 0.1)))
        v7: list[str] = ['abc', '日本', 'café', 'AbCd']
        v8: int = len(v7)
    v9: str = (str((-2 + 30)) + ('q q' + 'abc'))
    try:
        print((len(v6) % (61 % 5)))
    except ZeroDivisionError:
        print(-66)
    if ((3037000499 - 27) == 52):
        try:
            print(v9)
        except ZeroDivisionError:
            v10: float = abs(abs(0.1))
            v6.append(len(v9))
        except ValueError:
            print((1.25 % 2.5), (1e-7 / (-6 + -1)), (int((0.1 - 0.3)) == (33 % 2)))
            for i11 in v9:
                print((b"hello" * 3).decode())
        try:
            print((-2 <= max(23, 3037000499)), ((f'{v9:^9}{'a,b,c':^9}' != v9.lower()) and ((19 // 21) == (1 % (abs(4) + 1)))), (12 // (abs(72) + 1)))
        except ZeroDivisionError:
            print(-51)
        finally:
            print(150)
    elif (str((40 - 81)) != str(13)):
        print((b"hello" + b"a,b").decode())
        if v9.islower():
            v6 += v6
            v12: list[str] = [v9]
        else:
            try:
                v6.remove((0 + 23))
            except ValueError:
                print(-69)
            finally:
                print(125)
            print('a,b,c')
    else:
        print(7.0)
    v13: bool = ((~60) > 3)
    try:
        v6.pop()
    except IndexError:
        print(-88)
    try:
        try:
            v6.pop()
        except IndexError:
            print(-66)
        v14: int = -6
        try:
            v6[-3] = (v14 * 8)
        except IndexError:
            print(-9)
    except IndexError:
        if (ord((v9 * 3)[2]) > 20):
            v15: int = 5
            if (v15 <= (32 ** 1)):
                print((v9 + 'café'), f'{5:05d}', (v15 - v15))
                v16: int = (f' = {min(v15, v15):>6}{'3.5'}'.count('a') + v15)
            elif v9.isspace():
                print(v15)
                v17: int = v15
            al18: list[int] = v6
            v6.append(7)
            print(len(v6), len(al18), sum(v6) - sum(al18))
        elif (max(55, 76) > 3):
            try:
                v6[1] = (86 // (abs(95) + 1))
            except IndexError:
                print(-7)
        else:
            v19: str = str((65 * 54))
            v6.sort()
    v20: set[int] = {-3, 2, 2, 2}
    al21: list[int] = v6
    v6.sort()
    print(len(v6), len(al21), sum(v6) - sum(al21))
    for i22 in v9:
        v6.insert(0, len(v20))
        for i23 in range(0, 3):
            try:
                print((58 | round((0.1 * 2.5e-3))))
                v24: dict[str, int] = {}
                v24['e'] = 7
                v24['c'] = 6
                v24['e'] = 80
                print(str((123456.789 + 7.0)))
            except ZeroDivisionError:
                print((1e10 * (7.0 + 1.25)))
            except IndexError:
                print((not (not ((-1 + i23) > (0 - 77)))))
                print(f'{i23}{(0.1 * 2.5e-3):.2f}')
            try:
                print(max(h0(9, (i23 + 79)), i23))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-95)
            finally:
                print(122)
    if ((~95) <= round((3.0 / (abs(0.3) + 1.0)))):
        print((((v9 * 1).endswith('d')) or (v9.replace(' ', 'XY') >= ('abc' * 2))))
        v25: float = 0.0
        try:
            v25 = (123456.789 / (abs((100.75 / (44 - 9223372036854775807))) + 1.0))
        except ZeroDivisionError:
            print(-32)
        finally:
            print(195)
    elif ((74 + 3037000499) <= (2 ** 1)):
        print((((30 + -9) / 8) / (abs(min(100.75, 0.5)) + 1.0)))
        print(((abs(0.3) ** 0.5) // 2.5))
    al26: list[int] = v6
    if len(al26) > 0:
        al26[0] = 0
    print(len(v6), len(al26), sum(v6) - sum(al26))
    v9 = v9.strip()[0:-1]
    v13 = (len(v6) in v20)
    w27: int = 0
    while w27 < 6:
        w27 += 1
        al28: list[int] = v6
        al28 += [1]
        print(len(v6), len(al28), sum(v6) - sum(al28))
        v29: int = ((87 // -5) * 88)
        w30: int = 0
        while w30 < 3:
            w30 += 1
            print((-(w27 * 12)))
            try:
                al28.sort(key=lambda q: (-q, q))
                v31: int = ((v29 - w27) << 10)
                v31 = (v31 - len(v20))
            except ValueError:
                v32: str = 'ab'
                print(f'#{(82 ^ 7):<4}#')
            except KeyError:
                try:
                    print((float(len(v9)) + (0.5 / (21 ** 0))))
                except ZeroDivisionError:
                    print(-52)
                al33: list[int] = al26
                al26.reverse()
                print(len(al26), len(al33), sum(al26) - sum(al33))
            else:
                print(f'{(abs(0.3) ** 0.5):.3f}')
                al26 += al26
            finally:
                print(242)
            v34: set[int] = {6, 0}
    al35: list[int] = al26
    al35.sort()
    print(len(al26), len(al35), sum(al26) - sum(al35))
    print(len(v6), sum(v6))
    print(v9)
    print(v13)
    print(len(v20), sum(v20), max(v20) if len(v20) > 0 else 0)
    print(len(al21), sum(al21))
    print(len(al26), sum(al26))
    print(len(al35), sum(al35))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
0
helloa,b
-9
0 0 0
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
False
195
8 8 0
9 9 0
-12
0.548
242
-12
0.548
242
-12
0.548
242
73 73 0
-24
0.548
242
-24
0.548
242
-24
0.548
242
585 585 0
-36
0.548
242
-36
0.548
242
-36
0.548
242
4681 4681 0
-48
0.548
242
-48
0.548
242
-48
0.548
242
37449 37449 0
-60
0.548
242
-60
0.548
242
-60
0.548
242
299593 299593 0
-72
0.548
242
-72
0.548
242
-72
0.548
242
2396744 2396744 0
2396744 3969608
28q qab
False
2 -1 2
2396744 3969608
2396744 3969608
2396744 3969608
```

AIL stdout, exit code 1:

```
0
helloa,b
-9
0 0 0
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
58
123463.789
255
122
58
123463.789
257
122
58
123463.789
259
122
False
195
8 8 0
9 9 0
-12
0.548
242
-12
0.548
242
-12
0.548
242
73 73 0
-24
0.548
242
-24
0.548
242
-24
0.548
242
585 585 0
-36
0.548
242
-36
0.548
242
-36
0.548
242
4681 4681 0
-48
0.548
242
-48
0.548
242
-48
0.548
242
37449 37449 0
-60
242
```

AIL stderr:

```
TypeError: '<' not supported between instances of 'range' and 'object'
```

**What to do.**
1. Save the program as `/tmp/probes/fz213.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz213.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz213.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N.N' ail='N'`.

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
