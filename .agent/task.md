**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41950413669 (seed `2076201466`, CPython 3.12, modes default+ir) found a DIFF: `line 34: cpython='130' ail='6-6-6'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076201466 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = ((90 + 67) - a)
    v2: str = str(a)[:]
    v3: list[int] = [15, v1, (-1 | 5), 50, (b + 14)]
    v4: list[str] = [v2, v2, v2]
    print('-'.join(v4))
    if (v2 in v2[:4]):
        return int((3.0 * 0.1))
    return v3[-3]


def main() -> int:
    print(b"a,b".decode(), 38, (2.5e-3 - 100.75))
    print((b"Zed" + b"12").decode())
    v6: list[int] = [(c5 - c5) for c5 in range(0) if c5 % 2 == 1]
    w7: int = 0
    while w7 < 2:
        w7 += 1
        print((73 % (abs(39) + 1)), abs(2.5e-3), ('Zed' in '3.5'[0:-1]))
        try:
            v8: list[str] = []
            try:
                v8 = f'{int(str(w7)):05d}{(0.1 // 3.0):8.3f}{(0.3 / (abs(100.75) + 1.0)):>10.1f}'.split(' ')
            except (IndexError, ValueError):
                print(-62)
            try:
                if ('q q'.startswith('a')):
                    assert (w7 == 22), "boom"
            except (AssertionError, IndexError):
                print(-13)
            else:
                print(79)
            finally:
                print(194)
            w9: int = 0
            while w9 < 2:
                w9 += 1
                if ('Zed' in f'{'ab':>8}'):
                    break
                v10: int = (int(float(int((1e-7 * 1e10)))) + (w7 * w9))
                al11: list[int] = v6
                v6 += [6]
                print(len(v6), len(al11), sum(v6) - sum(al11))
                print(v6 == al11)
        except IndexError:
            print(('-7' + '12'))
            print(((22 - w7) - round(0.1)))
        except ZeroDivisionError:
            print(b"x"[-2:-1].decode())
            v12: float = ((2.5e-3 + 2.5e-3) + (0.1 * 0.3))
        else:
            v6.reverse()
            if (not (max(w7, w7) > (w7 // -5))):
                break
    w13: int = 0
    while w13 < 5:
        w13 += 1
        v14: str = str(len(v6))
    v15: set[int] = {0, 10, -5, 6, 11, -3}
    v6 += v6
    w16: int = 0
    while w16 < 3:
        w16 += 1
        for i17 in v6:
            if ((i17 % (abs(w16) + 1)) == (i17 << 5)):
                if (not ((i17 % (abs(63) + 1)) >= (i17 + i17))):
                    break
                v18: bool = (((w16 & i17) != (w16 + w16)) and ((0.3 * 1e10) < 0.1))
            elif (((w16 * w16) >= 31) or ((i17 // 7) >= i17)):
                v19: str = ("<%5d>" % (w16 * 7))
                v20: int = 0
                try:
                    v20 = ord((v19 * 3)[1])
                except IndexError:
                    print(-2)
            print((i17 + i17), 'ab'.lower(), ('12' * 0))
            print(f'{(0.1 * 0.5):.2f}{'abc':<6}'.count('a'))
        for i21 in v6:
            v22: str = 'hello'
            v23: str = ""
            try:
                v23 = (("%-4d|" % h0(i21, (w16 * w16))) + f'-{(0.1 / (abs(1.25) + 1.0)):>10.1f}{1.25:8.3f}')
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-48)
            finally:
                print(130)
        v24: dict[str, int] = {}
        v24['b'] = 13
        v24['a'] = 66
        v24['a'] = 21
    v15.add((43 << 5))
    w25: int = 0
    while w25 < 6:
        w25 += 1
        w26: int = 0
        while w26 < 1:
            w26 += 1
            w27: int = 0
            while w27 < 5:
                w27 += 1
                al28: list[int] = v6
                al28.sort()
                print(len(v6), len(al28), sum(v6) - sum(al28))
                v29: dict[str, int] = {}
                v29['a'] = 34
                v29['e'] = 15
                v29['b'] = 1
                v29['e'] = 35
                if (float(max(-6, w25)) > float((w27 % w26))):
                    break
        print(max((0.1 % 7.0), (2.5e-3 / (abs(1e-7) + 1.0))))
        v30: list[int] = [-2] * 0
    v31: list[int] = sorted(v6)
    try:
        v6.pop()
    except IndexError:
        try:
            try:
                v6[-2] = '日本'[0:-1].find('-'.join(' pad '.split(',')))
            except IndexError:
                print(-88)
            v15.add((1 % (abs(20) + 1)))
            print(('q q' in 'café'), (abs(1e10) ** 0.5))
        except IndexError:
            if ('abc' in ' pad '[1:4]):
                v32: str = f'{(45 ** 1):05d}'
                v33: dict[str, int] = {}
                v33['e'] = 71
                v33['e'] = 19
                try:
                    print((float((3 // 29)) / (90 + 4611686018427387904)))
                except ZeroDivisionError:
                    print(-56)
                finally:
                    print(197)
            else:
                print(max(0.3, (100.75 - 1e-7)))
        except KeyError:
            print((('Zed' * 3) + '-'.join(' pad '.split(' '))))
        finally:
            print(269)
    print(len(v6), sum(v6))
    print(len(v15), sum(v15), max(v15) if len(v15) > 0 else 0)
    print(len(v31), sum(v31))
    return 1


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
a,b 38 -100.7475
Zed12
33 0.0025 False
79
194
1 1 0
True
2 2 0
True
33 0.0025 False
79
194
3 3 0
True
4 4 0
True
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
6-6-6
130
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
7 42
7 1395 1376
8 48
```

AIL stdout, exit code 0:

```
a,b 38 -100.7475
Zed12
33 0.0025 False
79
194
1 1 0
True
2 2 0
True
33 0.0025 False
79
194
3 3 0
True
4 4 0
True
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
12 ab 
1
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
6-6-6
6-6-6
130
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
8 8 0
0.1
7 42
7 1395 1376
8 48
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz230.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz230.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz230.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='N-N-N'`.

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
