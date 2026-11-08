**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42517310228 (seed `2076519205`, CPython 3.12, modes default+ir) found a DIFF: `line 11: cpython='-18' ail='12abc'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076519205 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

from dataclasses import dataclass


@dataclass
class Pt:
    a: int
    b: int
    c: float
    name: str
    items: list[int]


def bump(p: Pt, k: int) -> int:
    p.a += k
    p.items.append(k)
    return p.a + len(p.items)


def h0(a: int, b: int) -> int:
    v1: int = 54
    v2: str = ('Zed' + '12'.lstrip())
    v3: list[int] = [2] * 3
    w4: int = 0
    while w4 < 4:
        w4 += 1
        for i5 in v2:
            v6: bytes = (b"x" + b"a,b")
            v7: int = 0
            try:
                v7 = (w4 - 44)
            except ZeroDivisionError:
                print(-95)
        for i8 in range(2, 11, 3):
            if (((-9223372036854775807 | 84) <= sum(v3)) or ((b // 75) > 3)):
                break
            try:
                v3[2] = (9 ** 2)
            except IndexError:
                print(-73)
            if ((35 + w4) == (a - 63)):
                continue
        print((b"12" + b"abc").decode())
    try:
        b //= (abs((1 ^ v1)) + 1)
    except ZeroDivisionError:
        print(-79)
    v9: set[int] = {-2}
    if (len(v3) > 3):
        return (v1 // -4)
    return len(v9)


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 6 + 2) % 17003
    return (h1(n - 1, a + 0) * 1 + h1(n - 2, a - 1) + n) % 17003


def main() -> int:
    pt0: Pt = Pt(5, 9, 3.0, '3.5', [])
    try:
        print(27)
        if ('AbCd' in str((97 - 72))):
            v10: list[str] = ('ab' * 0).split(',')
        elif ((27 ** 2) > int(1e-7)):
            v11: list[int] = [(25 + 82)]
            if (123456.789 == float(int(str(len('ab'[1]))))):
                v11.reverse()
                p12: Pt = Pt(50, 4, 100.75, '日本', [])
            else:
                print(((58 * -7) - (60 // (abs(-5) + 1))))
                print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
        else:
            try:
                print(max(h0((24 << 12), ('hello' + 'café').count('b')), (-6 - 9)))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-85)
            if ((0.3 * 123456.789) < float(26)):
                v13: list[int] = [-2] * 5
                pt0.name += ' pad '
            elif (((~15) > 57) or (-9223372036854775807 == (-3 + 3))):
                pt0.c += (1e10 + 123456.789)
                pt0.a += -5
        try:
            try:
                print(4611686018427387904)
            except ZeroDivisionError:
                print(-70)
            try:
                v14: int = ((43 ** 3) - (16 // (abs(46) + 1)))
                print((b"abc" * 1).decode())
            except ZeroDivisionError:
                p15: Pt = Pt(56, 5, 2.5e-3, 'Zed', [])
            else:
                print(max((0.5 * 3.0), (1e-7 % 2.5)))
                pt0.items.append(255)
            v16: str = ""
            try:
                v16 = ('q q' + str(h0(str((2.5e-3 - 1e10)).count('a'), (90 // 9))))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-52)
        except ValueError:
            w17: int = 0
            while w17 < 4:
                w17 += 1
                print('AbCd')
                v18: str = ('x'[:] + 'abc')
                if ((2.5e-3 + 3.0) <= (abs(0.3) ** 0.5)):
                    break
        else:
            v19: float = (abs((100.75 * 1e10)) ** 0.5)
            for i20 in range(5):
                try:
                    if (str((v19 * 100.75)) < str(v19)):
                        assert (not (i20 < 40)), "boom"
                except AssertionError:
                    print(-53)
                try:
                    print(('3.5' * 0), (88 - 72), (v19 / (-i20)))
                except ZeroDivisionError:
                    print(-18)
                if (((i20 << 10) <= (44 + i20)) and ((0.5 // 2.5) <= min(1e10, v19))):
                    break
    except KeyError:
        print('12'[:2])
        try:
            try:
                if (f'{(22 % 6)}{min(-8, -9223372036854775807)}{(3 // (abs(29) + 1))}' >= ('日本' + 'hello')):
                    raise IndexError('m9')
            except IndexError:
                print(-53)
            else:
                print(83)
            finally:
                print(147)
            for i21 in range(1):
                v22: int = (max(i21, i21) | (68 + 50))
                if (((29 - i21) <= v22) and ((79 - i21) < (i21 + 73))):
                    break
        except ZeroDivisionError:
            try:
                print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
            except KeyError:
                v23: list[int] = [1, 2, 3]
                try:
                    v23.remove((-7 + 22))
                except ValueError:
                    print(-56)
            except IndexError:
                try:
                    if ((('ab' + 'Zed').endswith('he')) or ('café'.replace(' ', 'XY') < 'café'.replace(' ', ''))):
                        raise KeyError('m5')
                except KeyError:
                    print(-70)
                finally:
                    print(184)
            else:
                v24: bytes = (b"a,b" + b"a,b")
            w25: int = 0
            while w25 < 3:
                w25 += 1
                print(('q q' + '-'.join('a,b,c'.split('a'))))
                print((b"ab" * 2).decode())
                print((2.5e-3 + (3.0 * 2.5e-3)))
    except ZeroDivisionError:
        v26: list[int] = [-1] * 1
    finally:
        print(247)
    print(((68 - 74) + 60))
    v27: list[int] = [(2 - 49), round(2.5e-3), 75]
    try:
        if ((float((35 ** 3)) == 0.5) or (2 <= (3037000499 // 41))):
            raise ValueError('m7')
    except ValueError:
        print(-36)
    v28: int = 0
    try:
        v28 = (-7 % (abs(h1(3, (91 // -6))) + 1))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-85)
    finally:
        print(180)
    try:
        v29: str = 'q q'[-2:4]
        w30: int = 0
        while w30 < 3:
            w30 += 1
            print('abc'.upper())
            for i31 in range(2, 6):
                print((v29.replace('a', 'XY') >= 'AbCd'.rstrip()))
        v32: str = ('3.5'.lstrip() + ('3.5' + 'Zed'))
    except ZeroDivisionError:
        v27.extend([v28, (42 + v28)])
    except IndexError:
        print('-'.join(('日本' * 0).split(' ')))
    try:
        v27.remove((46 + v28))
    except ValueError:
        print(-74)
    al33: list[int] = v27
    al33.sort()
    print(len(v27), len(al33), sum(v27) - sum(al33))
    try:
        v27.remove((v28 + 77))
    except ValueError:
        print(-20)
    al34: list[int] = al33
    al33.sort()
    print(len(al33), len(al34), sum(al33) - sum(al34))
    try:
        pt0.items.append(39)
    except ValueError:
        v35: bool = ((54 << 0) <= (v28 * v28))
    finally:
        print(265)
    for i36 in range(6, 2, -1):
        if ((len(al33) <= (v28 ** 0)) and ('ab' < ('abc' + '12'))):
            continue
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v27), sum(v27))
    print(v28)
    print(len(al33), sum(al33))
    print(len(al34), sum(al34))
    return 1


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
27
-416
5 9 3.0 3.5 0
4611686018427387904
abc
1.5
12abc
12abc
12abc
12abc
-18
247
54
-36
180
ABC
False
False
False
False
ABC
False
False
False
False
ABC
False
False
False
False
-74
3 3 0
-20
3 3 0
265
5 9 3.0 3.5 2
3 28
16504
3 28
3 28
```

AIL stdout, exit code 1:

```
27
-416
5 9 3.0 3.5 0
4611686018427387904
abc
1.5
12abc
12abc
12abc
12abc
12abc
12abc
12abc
12abc
-18
247
54
-36
180
ABC
False
False
False
False
ABC
False
False
False
False
ABC
False
False
False
False
-74
3 3 0
-20
3 3 0
265
5 9 3.0 3.5 2
3 28
16504
3 28
3 28
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz243.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz243.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz243.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='-N' ail='Nabc'`.

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
