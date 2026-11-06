**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42101349152 (seed `2076220186`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 64: cpython='<end>' ail='-13'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076220186 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = (round((0.5 / (abs(1e10) + 1.0))) + min(3037000499, b))
    v2: str = ""
    try:
        v2 = '12'.replace(' ', 'XY')[2]
    except IndexError:
        print(-72)
    v3: list[int] = [(v1 | b)]
    for i4 in v3:
        w5: int = 0
        while w5 < 5:
            w5 += 1
            if ((123456.789 * 0.1) <= 7.0):
                continue
            if (((6 + b) == v1) or ('AbCd'[0:].endswith('a'))):
                break
            if ((w5 // a) != (b - w5)):
                continue
    if (sum(v3) > v1):
        return 2
    return int('-7')


def main() -> int:
    v6: list[str] = ['q q']
    print((','.join(v6) >= 'abc'))
    print(255)
    try:
        print(f'{'hello'}{ord('-'.join(v6)[0]):^7}{h0((1 + 55), (60 % (abs(31) + 1))):<4}')
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-95)
    finally:
        print(183)
    v7: list[int] = []
    try:
        v7 = [h0((-27), 9), 8]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-48)
    for i8 in range(1, 6):
        v9: int = 0
        try:
            v9 = ((1 + 27) + v7[0])
        except IndexError:
            print(-95)
        print(f' = ')
        w10: int = 0
        while w10 < 5:
            w10 += 1
            print(min((v9 * -9), v9))
            try:
                if (('-7'.upper() >= 'q q') and (v9 != (i8 // (abs(i8) + 1)))):
                    assert ('ab'.find('x') == min(39, w10)), "boom"
            except (AssertionError, KeyError):
                print(-18)
            finally:
                print(105)
            for i11 in range(4):
                v12: bytes = (b"abc" + b"a,b")
    v13: list[int] = []
    try:
        v13 = [(-9 ** 0), (61 % 8), 30, len(v6)]
    except ZeroDivisionError:
        print(-32)
    al14: list[int] = v13
    al14.sort()
    print(len(v13), len(al14), sum(v13) - sum(al14))
    v15: dict[str, int] = {}
    v15['a'] = 6
    try:
        al16: list[int] = al14
        al16.reverse()
        print(len(al14), len(al16), sum(al14) - sum(al16))
        v17: str = '-7'
        try:
            if (v17.replace('l', '-').endswith(' ')):
                raise ValueError
        except (KeyError, ValueError):
            print(-40)
    except IndexError:
        v18: list[int] = [(97 // (abs(28) + 1)), 0]
        try:
            try:
                print((-(79 // 6)))
            except ZeroDivisionError:
                print(-98)
            w19: int = 0
            while w19 < 2:
                w19 += 1
                if (' pad '.endswith(' ')):
                    break
                print((v13.count((w19 >> 1)) * len(v6)))
                v20: int = w19
        except IndexError:
            v21: set[int] = {4, 8, 7, 11, 7, 10}
            v22: str = (f'{max(0.5, 100.75):.3f}{' pad ':<6}{max(-1, 3)}' + ('-7' + 'hello'))
        except ZeroDivisionError:
            try:
                if ('AbCd' in ','.join(v6)):
                    raise AssertionError('m0')
            except (AssertionError, KeyError):
                print(-72)
    except ZeroDivisionError:
        print(((0.5 + 0.1) - float((57 - 95))))
    else:
        for i23 in range(2):
            v24: float = ((7.0 / (abs(0.1) + 1.0)) - (1.25 * 1e10))
            del v7[2]
        try:
            v25: float = ((1e10 * 100.75) - max(123456.789, 0.3))
            try:
                v7[-2] = max(97, 1)
            except IndexError:
                print(-98)
            print(v25)
        except IndexError:
            try:
                al26: list[int] = v13
                v13.reverse()
                print(len(v13), len(al26), sum(v13) - sum(al26))
                v7.sort()
            except IndexError:
                print((int(abs(1e10)) + (45 >> 6)))
                v27: float = ((1e10 + 100.75) + float(f'{(7.0 * 100.75):8.3f}'.count('l')))
            else:
                print(('q q'.replace('l', '') + 'café'))
                print((100.75 / (abs(0.5) + 1.0)), (0 - 67))
            finally:
                print(247)
            try:
                if ((('日本' + ' pad ').startswith(' ')) and ((7.0 * 1e10) == (0.3 * 7.0))):
                    print(('café' in ','.join(v6)), ''.join(v6), 'AbCd')
                    print((14 - 9223372036854775807), (123456.789 / (abs(1e-7) + 1.0)))
                elif ((0 ^ 32) != (3 % 8)):
                    print((max(1e-7, 1e-7) / (abs((2.5e-3 + 1.25)) + 1.0)))
                else:
                    print(min((31 - 40), round(0.5)))
                    v28: int = 0
                    try:
                        v28 = ((29 % 94) >> 12)
                    except ZeroDivisionError:
                        print(-39)
            except ZeroDivisionError:
                print(-23)
    print(len(v6), ','.join(v6))
    print(len(v7), sum(v7))
    print(len(v13), sum(v13))
    print(len(al14), sum(al14))
    ks30: list[str] = []
    for k29 in sorted(v15):
        ks30.append(k29)
    print(len(v15), sum(v15.values()), ','.join(ks30))
    return 7


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
True
255
-72
hello  113  -7  
183
-72
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
4 4 0
4 4 0
```

AIL stdout, exit code 0:

```
True
255
-72
hello  113  -7  
183
-72
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
 = 
-189
105
-189
105
-189
105
-189
105
-189
105
4 4 0
4 4 0
-13
1 q q
2 1
4 35
4 35
1 6 a
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz231.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz231.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz231.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='-N'`.

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
