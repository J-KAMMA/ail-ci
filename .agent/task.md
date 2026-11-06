**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42145827731 (seed `2076302877`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 28: cpython='abc3.5abc3.5' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076302877 -o prog.py`, if that tree has it).

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
    v1: int = 95
    v2: str = '日本'
    v3: list[int] = [(a + 57), (69 % (abs(44) + 1))]
    try:
        v3.remove((v1 >> 3))
    except ValueError:
        print(-78)
    w4: int = 0
    while w4 < 6:
        w4 += 1
        print((b"hello" + b"abc").decode())
        if ('-'.join(v2.split('a')).startswith('a')):
            v2 = ("%-4d|" % 86)[-2:-1]
        if (v2.lstrip().endswith('d')):
            break
    try:
        if (b < (57 * a)):
            raise RuntimeError
    except (KeyError, RuntimeError):
        print(-92)
    finally:
        print(138)
    if (v2.replace('a', '-') >= '12'[0:2]):
        return 58
    return ((a // -6) >> 0)


def main() -> int:
    pt0: Pt = Pt(8, 0, 0.3, 'ab', [])
    print((-63), 1e10, (1e10 / (abs(0.5) + 1.0)))
    try:
        v6: list[int] = [67 for c5 in range(7) if c5 % 2 == 1]
        v6.append(len(v6))
    except ZeroDivisionError:
        w7: int = 0
        while w7 < 4:
            w7 += 1
            v8: int = w7
        print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    except IndexError:
        for i9 in range(5, 2, -1):
            try:
                pt0.a = (82 ** 0)
                v10: list[int] = [i9, (i9 << 6)]
            except ValueError:
                v11: list[int] = [1] * 1
            finally:
                print(208)
            print(((-8 + i9) > 3), 3.0)
            v12: int = -3
        v13: list[int] = []
        try:
            v13 = [(58 - 38), int((1e10 / (60 - 66))), (87 ** 1)]
        except ZeroDivisionError:
            print(-62)
    else:
        try:
            if ('AbCd' in 'abc'.upper()):
                v14: list[str] = []
            else:
                v15: str = (("%03d" % 84) * 1)
                v16: int = 0
                try:
                    v16 = (h0((88 // 28), (6 & 64)) // 3)
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-3)
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-89)
        try:
            v17: str = ("<%5d>" % int(2.5e-3))
        except ZeroDivisionError:
            v18: float = (float(20) * float((1 // (abs(-1) + 1))))
        else:
            print(10)
            try:
                v19: list[int] = list(range(1, 10, 2))
            except ZeroDivisionError:
                print(str(30))
                v20: list[str] = f'{(23 - 48):<4}/{2:^7}'.split(' ')
        finally:
            print(201)
    finally:
        print(278)
    print((96 + (-9 - 52)))
    v21: set[int] = {-1, 9, 9}
    w22: int = 0
    while w22 < 5:
        w22 += 1
        v24: list[int] = [len(v21) for c23 in range(8) if c23 % 2 == 1]
        if ((w22 + 84) > sum(v24)):
            try:
                print(((w22 * w22) & (w22 % 8)))
            except ZeroDivisionError:
                print(-85)
            finally:
                print(185)
            for i25 in range(2):
                print((('abc' + '3.5') * 2))
                try:
                    if ((h0((w22 - 91), abs(99)) < (i25 - 64)) or (b"Zed".decode() < 'q q')):
                        raise ValueError
                except (ValueError, ZeroDivisionError):
                    print(-37)
                finally:
                    print(114)
                if (round((1e10 * 1e10)) > (36 - 3)):
                    continue
            if ('a,b,c'.isalpha() or ('AbCd' in ('x' + 'AbCd'))):
                if ((w22 * 75) != (w22 << 4)):
                    continue
        elif (('12'.strip() != 'abc') and (w22 == (88 - w22))):
            if ((-3 ** 3) == (34 * w22)):
                print('日本')
    if ('日本'.endswith('d')):
        v26: int = ((37 - 94) - 64)
        v21 ^= {-1, 12, 12, -5, -4}
        try:
            print(((0.5 / (v26 % (abs(v26) + 1))) - (0.5 + 0.1)))
        except ZeroDivisionError:
            print(-68)
        finally:
            print(183)
    elif 'q q'.islower():
        if ('-7' in '日本'):
            try:
                v21.remove(12)
            except KeyError:
                print(-6)
            print('abc')
            try:
                v21.remove(0)
            except KeyError:
                print(-13)
        elif (not ('ab'.startswith('a'))):
            v27: float = ((123456.789 / (abs(0.1) + 1.0)) * (7.0 / (abs(0.3) + 1.0)))
    try:
        v21.add((96 // -4))
    except ZeroDivisionError:
        print(-67)
    try:
        try:
            print(((98 * 49) != (6 - 32)))
        except ZeroDivisionError:
            v28: int = ((11 >> 1) * (-39))
            for i29 in range(3):
                if (len(v21) >= (i29 // (abs(59) + 1))):
                    break
                if ((1e10 / (abs(0.5) + 1.0)) <= 7.0):
                    break
                try:
                    if ((abs(1e-7) ** 0.5) <= float((70 + -2))):
                        raise ValueError('m4')
                except ValueError:
                    print(-18)
        except ValueError:
            print((not (max(1, 91) in v21)))
        else:
            p30: Pt = Pt(-3, 99, 1e10, 'a,b,c', [])
            print(54)
        finally:
            print(205)
        v31: list[int] = []
        try:
            v31 = [(6 - 2), (-6 % -5)]
        except ZeroDivisionError:
            print(-33)
    except KeyError:
        v32: str = f'{(1.25 / (abs(1e10) + 1.0)):.2f}{max(123456.789, 0.1):.3f}{(1e-7 / (abs(0.1) + 1.0)):.3f}'
        try:
            print(v32)
        except IndexError:
            print((not (255 < (4611686018427387904 & 45))), (0.5 - 0.1), (76 * -2))
            w33: int = 0
            while w33 < 6:
                w33 += 1
                v34: float = abs(min(123456.789, 1e10))
    except ValueError:
        v21.remove(-1)
        for i35 in range(6, 2, -1):
            print(2.5e-3)
    else:
        print(87)
    try:
        if (52 != len('café'.lower())):
            for i36 in range(2, 13, 1):
                v37: bytes = (b"a,b" + b"a,b")
                try:
                    if (h0((73 ^ i36), (i36 % (abs(42) + 1))) == i36):
                        raise IndexError('m1')
                except IndexError:
                    print(-87)
                try:
                    if (len(v37) != round((123456.789 / (abs(100.75) + 1.0)))):
                        assert ('café' != 'q q'), "boom"
                except (AssertionError, ValueError):
                    print(-36)
            v38: float = 0.5
            print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
        elif ((5 % 3) < len(v21)):
            v21.add((-34))
        else:
            try:
                v21.remove(4)
            except KeyError:
                print(-45)
    except KeyError:
        print(-59)
    v39: int = 0
    try:
        v39 = min(min(40, 49), (-9 // 4))
    except ZeroDivisionError:
        print(-65)
    finally:
        print(177)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v21), sum(v21), max(v21) if len(v21) > 0 else 0)
    print(v39)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-63 10000000000.0 6666666666.666667
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
10
201
278
35
1
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
0
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
1
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
0
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
1
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
True
54
205
87
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
8 0 0.3 ab 0
177
8 0 0.3 ab 0
3 -16 9
-3
```

AIL stdout, exit code 1:

```
-63 10000000000.0 6666666666.666667
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
-92
138
10
201
278
35
1
185
abc3.5abc3.5
-78
helloabc
helloabc
helloabc
helloabc
helloabc
helloabc
138
-37
114
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz234.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz234.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz234.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='abcN.NabcN.N' ail='<end>'`.

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
