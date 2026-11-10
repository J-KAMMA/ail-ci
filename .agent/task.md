**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42713674894 (seed `2076623644`, CPython 3.12, modes default+ir) found a DIFF: `line 23: cpython='inf       nan-' ail='inf      -nan-'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076623644 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 1 + 3) % 71003
    return (h0(n - 1, (a * 3 + n) % 71003) + 9) % 71003


def main() -> int:
    v1: float = ((3.0 / (abs(0.5) + 1.0)) - 1e10)
    try:
        print((not ((-9 >= (99 % (abs(255) + 1))) or ((v1 * v1) <= (v1 / (74 * 37))))))
    except ZeroDivisionError:
        print(-23)
    print(f'{'3.5':^9} = ')
    v2: set[int] = {3}
    print(str('a,b,c'.replace('l', '').count('ab')))
    if ((not (v1 > (1e-7 / (abs(v1) + 1.0)))) or (((71 - 78) <= (86 - 23)) and ((88 ** 2) != (79 + 80)))):
        try:
            v2.add(h0(9, (28 - 64)))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-85)
        finally:
            print(182)
        for i3 in range(8, -2, -1):
            v1 *= (2.5e-3 + v1)
            if (i3 >= (84 % (abs(i3) + 1))):
                try:
                    print((-9223372036854775807 & i3), '3.5'[2], abs(2.5e-3))
                except IndexError:
                    print(-31)
                print((i3 > (-9 * i3)))
            else:
                print((str(abs(v1)) + f'{(v1 / (abs(v1) + 1.0)):>10.1f}-'))
                print(('hello' in 'ab'))
            for i4 in range(5):
                v5: int = (~abs(i4))
                if ('-7'[0:4] != '3.5'[2]):
                    continue
    for i6 in range(9, 3, -1):
        try:
            v2.remove(3)
        except KeyError:
            print(-79)
        try:
            if (((i6 // 5) >= (i6 - i6)) and ((~i6) >= (i6 + 71))):
                raise ValueError('m0')
        except (KeyError, ValueError):
            print(-96)
        try:
            if (not ((i6 - i6) < (4611686018427387904 - -6))):
                try:
                    print((2.5e-3 * v1), (v1 / ("%d" % (255 + i6)).count('l')), ' pad '[-2:-1])
                except ZeroDivisionError:
                    print(-65)
                v1 = ((v1 / (abs(v1) + 1.0)) * (v1 / (abs(v1) + 1.0)))
            else:
                if (not ((84 | 65) > (i6 % i6))):
                    break
                try:
                    print((55 // 4), (v1 / (abs(0.5) + 1.0)))
                except ZeroDivisionError:
                    print(-9)
        except ZeroDivisionError:
            print(-82)
        finally:
            print(162)
    try:
        print(f'{(83 % 5):05d}')
    except ZeroDivisionError:
        print(-22)
    v7: float = ((v1 - v1) % 2.5)
    try:
        for i8 in range(7, 0, -1):
            v9: float = v1
            v10: bytes = (b"a,b" * 1)
    except IndexError:
        w11: int = 0
        while w11 < 1:
            w11 += 1
            try:
                if ((12 % w11) < (w11 // -6)):
                    assert ((3 << 1) >= 87), "boom"
            except AssertionError:
                print(-81)
        v2 &= set()
    except KeyError:
        print((' pad '[-2:2] * 1))
        v12: float = 1e10
    print(b"Zed".decode())
    print(((v7 - 123456.789) + (abs(1e10) ** 0.5)))
    try:
        print(float((11 + 87)))
        print(1e-7)
        v13: float = (abs(0.1) * ((66 ^ 81) / 3))
    except ValueError:
        print((v1 > v1))
    except ZeroDivisionError:
        v14: int = 'abc'.find(('ab' + 'x'))
        for i15 in range(-2, 5):
            try:
                print(((98 - 9223372036854775807) + (i15 % -7)))
            except ZeroDivisionError:
                print(-67)
            finally:
                print(143)
            v7 *= (v1 / (abs(v7) + 1.0))
    else:
        v16: float = ((v7 + 123456.789) - (123456.789 * 1e-7))
    try:
        print(((82 >> 10) % 8))
    except ZeroDivisionError:
        print(-73)
    print((b"x" * 3).decode())
    w17: int = 0
    while w17 < 6:
        w17 += 1
        if (57 == w17):
            try:
                print(((v7 % 2.5) / (w17 * w17)))
            except ZeroDivisionError:
                print(-52)
            finally:
                print(120)
            v18: str = 'hello'
            v2.add(w17)
        elif (len(v2) > 3):
            try:
                print((w17 // (abs((9223372036854775807 * w17)) + 1)))
                print((80 + max(w17, 11)))
                v20: list[int] = [len(v2) for c19 in range(2) if c19 % 2 == 1]
            except ZeroDivisionError:
                print((((w17 % (abs(w17) + 1)) in v2) and ('日本' in ('a,b,c' * 0))))
                try:
                    v7 *= (v7 / (-7 ^ w17))
                except ZeroDivisionError:
                    print(-70)
            except ValueError:
                if ('Zed'.strip().find('日本') < h0(1, (65 + w17))):
                    break
                v7 -= (7.0 + v1)
            print(abs((61 + w17)))
        else:
            v21: set[int] = set()
            v22: bool = (w17 >= len(v2))
        if ('3.5'.startswith('a')):
            v23: int = 0
            try:
                v23 = len(v2)
            except ZeroDivisionError:
                print(-78)
            v1 *= v1
        elif ((w17 - 16) >= (~w17)):
            try:
                v7 = ((v7 - v1) - (1e10 / w17))
            except ZeroDivisionError:
                print(-96)
            w24: int = 0
            while w24 < 5:
                w24 += 1
                print(0.1)
    v25: int = 0
    try:
        v25 = (66 // 9)
    except ZeroDivisionError:
        print(-93)
    print((49 ** 2))
    print(v1)
    print(len(v2), sum(v2), max(v2) if len(v2) > 0 else 0)
    print(v7)
    print(v25)
    return 7


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 7:

```
True
   3.5    = 
0
182
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
False
inf       nan-
False
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
00003
Zed
nan
98.0
1e-07
0
xxx
2401
inf
1 14176 14176
nan
7
```

AIL stdout, exit code 7:

```
True
   3.5    = 
0
182
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
True
1 5 0.0025
True
0 5 0.0025
False
inf      -nan-
False
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
-79
13 inf
162
00003
Zed
nan
98.0
1e-07
0
xxx
2401
inf
1 14176 14176
nan
7
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz246.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz246.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz246.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='inf       nan-' ail='inf      -nan-'`.

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
