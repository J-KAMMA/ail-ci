**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40479948304 (seed `2075300933`, CPython 3.12, modes default+ir) found a DIFF: `line 8: cpython='160' ail='False 1.2525'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075300933 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = 14
    v2: str = ' pad '.replace('a', 'XY').replace('a', '-')
    v3: list[int] = []
    for i4 in range(5):
        v1 = ((13 + b) + (b // (abs(b) + 1)))
        print(((b"12".decode() < '12'.replace('l', '-')) and v2.isdigit()), (2.5e-3 + 1.25))
    print((1e10 + 1e-7), (v2 + v2), (2 - a))
    print((v2 * 0))
    if ((b | a) <= (53 % (abs(b) + 1))):
        return (97 - a)
    return len(v2)


def h1(a: int, b: int) -> int:
    v5: int = 0
    try:
        v5 = ((-4 % 9) ^ b)
    except ZeroDivisionError:
        print(-24)
    v6: str = ""
    try:
        v6 = (f'{h0((91 + a), 33):>6}' + '3.5'.lstrip())
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-62)
    finally:
        print(160)
    v8: list[int] = [len(v6) for c7 in range(8) if c7 % 2 == 0]
    w9: int = 0
    while w9 < 4:
        w9 += 1
        v10: float = 1e10
    v11: list[str] = b"x".decode().split(' ')
    if (v5 > 3):
        return (48 ^ v5)
    return (len(v6[1:]) - 35)


def h2(a: int, b: int) -> int:
    v12: int = ((~-3) ^ (b - 64))
    v13: str = ""
    try:
        v13 = '-'.join('AbCd'[2].split('a'))
    except IndexError:
        print(-72)
    finally:
        print(180)
    v14: list[int] = [(a % (abs(a) + 1)), max(b, v12), abs(v12), b, 60]
    v15: list[str] = str(b).split('a')
    try:
        v16: float = ((2.5e-3 - 1.25) - 3.0)
    except IndexError:
        print((b * a), (b << 5), v13[:])
        print(7.0)
    except ValueError:
        v14 += [(78 - v12), a]
        v17: list[int] = []
    else:
        print(min((1.25 * 2.5e-3), (1e10 * 1e10)))
        if ((v12 % 9) == (13 - a)):
            v15.sort()
        elif ((a + b) == b):
            v18: bytes = b"x"
    finally:
        print(256)
    if (not v13.isdigit()):
        return b
    return (h0((83 // (abs(57) + 1)), (v12 - 52)) + (b - v12))


def main() -> int:
    v19: list[int] = []
    try:
        v19 = [(-9223372036854775807 + 255), (67 + 12), h1((71 - 76), (45 - 18))]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-52)
    if ('x' in ('q q' + 'q q')):
        print('AbCd'.replace('a', ''), 'AbCd'[-2:-1], '日本'.replace('l', 'XY'))
    elif ((0.3 == max(1.25, 2.5e-3)) and (max(30, 6) > (67 // -4))):
        v20: str = (f' = {(9223372036854775807 ** 0):3d}{2.5e-3:8.3f}' + ('q q' + 'café'))
        try:
            v20 = v20
            for i21 in v19:
                if ((i21 | 23) != i21):
                    continue
        except IndexError:
            try:
                print((7.0 % 0.75), (abs(100.75) ** 0.5), int('-'.join('hello'.split(','))))
            except ValueError:
                print(-26)
            try:
                v19[2] = max(12, 79)
            except IndexError:
                print(-56)
        except KeyError:
            w22: int = 0
            while w22 < 1:
                w22 += 1
                try:
                    print((h1(59, (w22 // (abs(w22) + 1))) > 3))
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-68)
                print(((1.25 / (abs(0.1) + 1.0)) - (2.5e-3 / (abs(0.1) + 1.0))))
    al23: list[int] = v19
    v19.append(6)
    print(len(v19), len(al23), sum(v19) - sum(al23))
    v24: int = 0
    try:
        v24 = (v19.index((-7 + 52)) + (18 + 6))
    except ValueError:
        print(-23)
    try:
        v19.pop()
    except IndexError:
        print(-54)
    print(v24)
    print((('日本' == 'x'.strip()) or ((v24 - v24) > 3)), len(v19))
    print(round(float((v24 - 95))))
    print((int((0.5 / (abs(0.5) + 1.0))) - (v24 - v24)))
    try:
        try:
            if (b"abc".decode() >= '12'[-2:-1]):
                raise ValueError
        except ValueError:
            print(-15)
        else:
            print(92)
        v24 ^= (41 & v24)
        print((float(4611686018427387904) + (0.5 / (abs(1e10) + 1.0))))
    except KeyError:
        v25: float = 3.0
        print(sum(al23))
    except ZeroDivisionError:
        w26: int = 0
        while w26 < 3:
            w26 += 1
            v27: bytes = b"hello"
        v28: bytes = b"ab"[1:-1]
    finally:
        print(253)
    print((((2.5e-3 < min(2.5e-3, 1e10)) and (max(v24, 1) != max(v24, 81))) and (v24 == 99)))
    print(len(v19), sum(v19))
    print(len(al23), sum(al23))
    print(v24)
    return 1


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
False 1.2525
False 1.2525
False 1.2525
False 1.2525
False 1.2525
10000000000.0  pXYd  pXYd  -84

160
4 4 0
-23
0
False 3
-95
0
-15
4.611686018427388e+18
253
False
3 -9223372036854775427
3 -9223372036854775427
0
```

AIL stdout, exit code 0:

```
False 1.2525
False 1.2525
False 1.2525
False 1.2525
False 1.2525
10000000000.0  pXYd  pXYd  -84

False 1.2525
False 1.2525
False 1.2525
False 1.2525
False 1.2525
10000000000.0  pXYd  pXYd  -84

160
4 4 0
-23
0
False 3
-95
0
-15
4.611686018427388e+18
253
False
3 -9223372036854775427
3 -9223372036854775427
0
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz3.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz3.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz3.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='False N.N'`.

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
