**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40782584863 (seed `2075500845`, CPython 3.12, modes default+ir) found a DIFF: `line 11: cpython='0.0' ail='-0.0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075500845 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 8 + 6) % 24003
    return (h0(n - 1, (a * 5 + n) % 24003) + 7) % 24003


def h1(a: int, b: int) -> int:
    v1: int = a
    v2: str = 'a,b,c'
    v3: list[int] = list(range(-3, 9, 1))
    v4: list[int] = [90, (b & 9223372036854775807)]
    try:
        print(f'{v2:^9}{len(v2):>6}{abs(0.3):.2f}'.rstrip())
        b *= 97
        print((max(a, a) * (~b)))
    except ZeroDivisionError:
        for i5 in v4:
            try:
                a = len(v2)
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-71)
            if (float(int(str(abs(a)))) == ((51 // 83) / 8)):
                continue
            print(v2, 2.5e-3)
    v4.extend(v3)
    if ('ab'.replace(' ', 'XY') != (v2 + ' pad ')):
        return int((1e10 % 7.0))
    return 0


def main() -> int:
    v7: list[int] = [7 for c6 in range(0) if c6 % 2 == 1]
    if (h1(len(v7), (80 % -9)) == (9 % (abs(49) + 1))):
        try:
            print(b"abc".decode(), (81 // 97), (90 - 90))
        except ZeroDivisionError:
            print(-74)
    elif ((6 - 43) >= max(53, 1)):
        print((~(1 + 56)))
        print('3.5'.lstrip().upper())
    else:
        print((float(round(1.25)) % 0.75))
    print((b"a,b" * 2).decode())
    v8: list[int] = [(50 - 92), (87 - 12), (77 + 94), 0]
    v8 += v8
    try:
        v7.pop()
    except IndexError:
        print(-57)
    try:
        if ('12' in 'AbCd'[-2:4]):
            v8.append((74 * 255))
            for i9 in v8:
                try:
                    print('AbCd'[0][-2:2])
                except IndexError:
                    print(-19)
    except IndexError:
        print(-87)
    w10: int = 0
    while w10 < 4:
        w10 += 1
        if (float((w10 % w10)) < (123456.789 + 7.0)):
            try:
                v7.remove(('a,b,c' + 'AbCd').count(' '))
            except ValueError:
                print(-43)
            if (max(63, w10) < 90):
                print((float((w10 - 60)) % 0.75))
        else:
            w11: int = 0
            while w11 < 6:
                w11 += 1
                al12: list[int] = v8
                if len(v8) > 0:
                    v8[0] = 6
                print(len(v8), len(al12), sum(v8) - sum(al12))
                v13: str = '-'.join('abc'.split(',')).replace('l', '')
                v13 += ('x' + ' pad ')
    v14: int = (85 // (abs(76) + 1))
    v15: list[int] = []
    v7.append((20 | v14))
    w16: int = 0
    while w16 < 3:
        w16 += 1
        if ('ab'.isspace() and 'abc'.isalpha()):
            try:
                v7.sort(key=lambda q: (-q, q))
                print((len(v7) > 3))
                v17: dict[str, int] = {}
            except ZeroDivisionError:
                al18: list[int] = v7
                v7.sort()
                print(len(v7), len(al18), sum(v7) - sum(al18))
            else:
                print(len(v15))
                if (w16 >= 84):
                    continue
        else:
            if (b"a,b".decode() < 'a,b,c'.strip()):
                if (((-2 - w16) > 54) or (66 > 3)):
                    continue
            else:
                if ((f'{(v14 - v14):3d}{'café'}{'ab'}' == 'x'.replace('a', 'XY')) or ((w16 + w16) > 3)):
                    break
    al19: list[int] = v7
    if len(v7) > 0:
        v7[0] = 0
    print(len(v7), len(al19), sum(v7) - sum(al19))
    try:
        print(float(round(float((2 ** 2)))))
        print('12', (65 - 30), ' pad '.replace(' ', 'XY'))
        try:
            if ((v14 | 3037000499) >= (19 + v14)):
                print((20 // (abs((74 - v14)) + 1)))
                al19.insert(0, (v14 + 29))
            elif ('Zed'.startswith('he')):
                try:
                    al19.remove((92 - 18))
                except ValueError:
                    print(-54)
                finally:
                    print(193)
                print(("%d" % (v14 % (abs(v14) + 1))).upper())
            else:
                try:
                    v7.pop()
                except IndexError:
                    print(-17)
        except IndexError:
            print(-83)
    except ValueError:
        v20: float = 1.25
        try:
            try:
                print(('x' + '-7')[2])
            except IndexError:
                print(-40)
        except ValueError:
            print(v20)
    except ZeroDivisionError:
        try:
            del v15[1]
        except IndexError:
            print(-89)
    print(' pad ')
    print(len(v7), sum(v7))
    print(len(v8), sum(v8))
    print(v14)
    print(len(v15), sum(v15))
    print(len(al19), sum(al19))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
  a,b,c       50.30
0
0.25
a,ba,b
-57
-43
0.25
-43
0.5
-43
0.0
-43
0.25
1 1 0
4.0
12 35 XYpadXY
0
 pad 
2 30
8 408
1
0 0
2 30
```

AIL stdout, exit code 0:

```
  a,b,c       50.30
0
0.25
a,ba,b
-57
-43
0.25
-43
0.5
-43
-0.0
-43
0.25
1 1 0
4.0
12 35 XYpadXY
0
 pad 
2 30
8 408
1
0 0
2 30
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz200.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz200.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz200.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N.N' ail='-N.N'`.

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
