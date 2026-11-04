**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41755164524 (seed `2076101071`, CPython 3.12, modes default+ir) found a DIFF: `line 34: cpython='-71' ail='0.5'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076101071 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = '-'.join('AbCd'.split('a')).count('ab')
    v2: str = ""
    try:
        v2 = '日本'[2]
    except IndexError:
        print(-92)
    finally:
        print(196)
    v3: list[int] = []
    try:
        v3 = [int(' pad '), abs(a)]
    except ValueError:
        print(-71)
    v4: int = len(v2)
    al5: list[int] = v3
    v3.append(0)
    print(len(v3), len(al5), sum(v3) - sum(al5))
    if ((v1 - 81) < max(v4, a)):
        return (~a)
    return ((b + b) << 1)


def h1(a: int, b: int) -> int:
    v6: int = (50 - 73)
    v7: str = str((v6 - 83))
    v8: list[int] = []
    try:
        v8 = [(b - 72), (0 - a), 74, a, ord(str((3.0 - 0.3))[3])]
    except IndexError:
        print(-75)
    finally:
        print(180)
    w9: int = 0
    while w9 < 2:
        w9 += 1
        v10: str = (str((2 * b)) + v7[0:4])
        v11: set[int] = set(v8)
    for i12 in range(3, 6, 1):
        w13: int = 0
        while w13 < 5:
            w13 += 1
            al14: list[int] = v8
            v8.reverse()
            print(len(v8), len(al14), sum(v8) - sum(al14))
            if ((len(al14) > 3) or ((0 % (abs(1) + 1)) >= (i12 ** 2))):
                continue
            try:
                if ((0.3 == 100.75) or ((39 + a) >= (12 % w13))):
                    assert ((v7 + 'AbCd').startswith('he')), "boom"
            except (AssertionError, ZeroDivisionError):
                print(-62)
            finally:
                print(164)
        v15: int = ((b // (abs(42) + 1)) * (i12 >> 0))
        print((abs(float((45 & b))) ** 0.5))
    if (str(51) >= (v7 + 'AbCd')):
        return (41 >> 0)
    return ((b | b) * (53 & v6))


def main() -> int:
    v16: float = 0.0
    try:
        v16 = float(85)
    except ZeroDivisionError:
        print(-51)
    v17: list[int] = []
    v18: dict[str, int] = {}
    v18['a'] = 33
    v18['a'] = 80
    v18['a'] = 60
    v18['a'] = 39
    v18['abc'] = (-18)
    v16 = 100.75
    v19: int = (72 + (18 ** 1))
    v16 += v16
    try:
        if ('Zed'.strip() < f'{'q q':<6}#{'x':>8}'):
            raise KeyError('m2')
    except KeyError:
        print(-47)
    v21: list[int] = [max(v19, 63) for c20 in range(7) if c20 % 2 == 1]
    for i22 in range(5, -2, -1):
        print(((abs(v16) ** 0.5) + float(i22)))
        print((abs(i22) - (v19 | -1)))
        print(' pad ')
    if ((3 - v19) < (v19 + 52)):
        print('-7')
    else:
        v23: int = (46 + v18.get(("%-4d|" % (v19 << 6)), 2))
        print((('AbCd' + ' pad ') + ('abc' + 'abc')))
    v18['abc'] = (v19 - v19)
    print(((v16 + v16) * (v16 / (abs(0.3) + 1.0))))
    v18['12'] = (3 ** 3)
    print(str((v19 - -1)))
    v24: int = 25
    try:
        if (('q q' in v18) or (not (v16 == (1.25 % 0.75)))):
            print(('q q'.upper() * 0))
            try:
                print((v16 - (3.0 * v16)))
                for i25 in v21:
                    try:
                        if ((len(v18) < (i25 * v24)) and ((i25 - v24) == v19)):
                            raise RuntimeError('m1')
                    except (RuntimeError, ZeroDivisionError):
                        print(-5)
                    finally:
                        print(117)
                print(((1e-7 / (abs(v16) + 1.0)) // 3.0))
            except ValueError:
                if (('hello' + 'abc').endswith('d')):
                    v26: str = (f'{(2.5e-3 - 7.0)}{float((v24 % (abs(65) + 1))):>10.1f}' + (' pad ' + '日本'))
                    print(v19, v18.get('-7', 3))
                    v27: str = ("%03d" % abs(99)).replace('l', '')
                else:
                    print(((-23) + v24))
            finally:
                print(210)
            try:
                v28: bytes = b"12"
                for i29 in range(4):
                    v18['q q'] = 87
                print(('café' + 'AbCd'), ('3.5' * 1))
            except ZeroDivisionError:
                print(f'{max(v19, v19):>6}')
            except IndexError:
                try:
                    print(abs(0.5))
                except IndexError:
                    print(-56)
                v16 = float((v19 - v19))
            else:
                v30: float = ((v16 * v16) // 3.0)
                print('3.5'[3][:])
        elif '3.5'.isupper():
            for i31 in v17:
                print(((v19 % v19) - h0(9223372036854775807, i31)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-71)
    print(((-6 // 3) - v19))
    print(v16)
    print(len(v17), sum(v17))
    ks33: list[str] = []
    for k32 in sorted(v18):
        ks33.append(k32)
    print(len(v18), sum(v18.values()), ','.join(ks33))
    print(v19)
    print(len(v21), sum(v21))
    print(v24)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-47
19.19506956657839
6
 pad 
18.19506956657839
5
 pad 
17.19506956657839
4
 pad 
16.19506956657839
3
 pad 
15.19506956657839
2
 pad 
14.19506956657839
1
 pad 
13.19506956657839
2
 pad 
-7
62465.0
91

-403.0
117
117
117
0.0
210
caféAbCd 3.5
-71
-92
201.5
0 0
4 153 12,a,abc,q q
90
3 270
25
```

AIL stdout, exit code 0:

```
-47
19.19506956657839
6
 pad 
18.19506956657839
5
 pad 
17.19506956657839
4
 pad 
16.19506956657839
3
 pad 
15.19506956657839
2
 pad 
14.19506956657839
1
 pad 
13.19506956657839
2
 pad 
-7
62465.0
91

-403.0
117
117
117
0.0
210
caféAbCd 3.5
0.5
-92
0.0
0 0
4 153 12,a,abc,q q
90
3 270
25
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz225.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz225.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz225.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='-N' ail='N.N'`.

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
