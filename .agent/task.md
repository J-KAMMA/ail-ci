**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41325393110 (seed `2075816770`, CPython 3.12, modes default+ir) found a DIFF: `line 18: cpython='2 2 0' ail='1 1 0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075816770 -o prog.py`, if that tree has it).

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
    v1: int = (b - (a << 8))
    v2: str = '12'
    v3: list[int] = [-2] * 4
    w4: int = 0
    while w4 < 5:
        w4 += 1
        print(((1.25 * 3.0) <= ((89 + v1) / 3)))
        try:
            print((float((4 | b)) / min(92, 0)))
        except ZeroDivisionError:
            print(-40)
    v6: list[int] = []
    try:
        v6 = [min(v3) for c5 in range(3) if c5 % 2 == 0]
    except ValueError:
        print(-39)
    if (("%d" % -8).endswith('a')):
        return v3[1]
    return ((a - 36) % 8)


def main() -> int:
    pt0: Pt = Pt(2, 2, 0.1, 'café', [])
    v7: list[int] = [1, 2, 3]
    print('3.5')
    if ('AbCd'[1:-1].startswith('he')):
        print('12', (2.5e-3 < min(2.5e-3, 1.25)))
        v8: int = (0 + 42)
        v9: int = ((-9223372036854775807 << 12) // (abs((v8 + 15)) + 1))
    if ((0.5 > (0.5 + 0.3)) and ((1e10 > (100.75 / (abs(0.5) + 1.0))) and (round((123456.789 + 1.25)) < 15))):
        pt0.a -= (67 % 90)
    elif ((123456.789 - 2.5e-3) < float(72)):
        try:
            v7.append(v7.index(52))
        except ValueError:
            print(-64)
        v10: list[int] = [(84 % (abs(55) + 1))]
    w11: int = 0
    while w11 < 4:
        w11 += 1
        al12: list[int] = v7
        v7.sort()
        print(len(v7), len(al12), sum(v7) - sum(al12))
    v13: float = 0.0
    try:
        v13 = (0.5 * (0.1 / len(v7)))
    except ZeroDivisionError:
        print(-41)
    v14: str = ""
    try:
        v14 = (str(v7.pop()) + 'café'.upper())
    except IndexError:
        print(-24)
    try:
        print(min(h0(len(v7), (37 >> 11)), len(v14)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-19)
    v7.sort(key=lambda q: (-q, q))
    pt0.name += 'hello'.replace(' ', '-')
    w15: int = 0
    while w15 < 2:
        w15 += 1
        v7.sort(key=lambda q: (-q, q))
        v16: dict[str, int] = {}
        v16['c'] = 93
        v16['b'] = 71
    for i17 in range(3):
        try:
            v18: list[int] = []
            try:
                v18 = [v7.index((12 - 18)), max(28, i17), (i17 >> 2)]
            except ValueError:
                print(-46)
            p19: Pt = Pt(21, 93, 0.1, v14, [])
        except IndexError:
            print(b"abc".decode())
            v14 = ("%-4d|" % (i17 & 0)).lower()
        except ZeroDivisionError:
            v20: str = b"x".decode()
            v14 += '12'[1:]
        if (((15 % -9) <= (85 % (abs(i17) + 1))) or ((v14 >= ("<%5d>" % max(i17, i17))) and (v13 <= min(v13, v13)))):
            v7.sort(reverse=True)
            for i21 in range(2, 4):
                v22: dict[str, int] = {}
                v22['a'] = 33
                v22['c'] = 60
                v22['c'] = 6
                if ((abs(v13) ** 0.5) < v13):
                    continue
        elif (((v14 + v14) == b"12".decode()) and (f'/{(i17 - 42):>6}{(v13 + 2.5e-3):.0f}' >= v14[1:4])):
            v13 += (abs(0.3) ** 0.5)
            al23: list[int] = v7
            if len(al23) > 0:
                al23[0] = 4
            print(len(v7), len(al23), sum(v7) - sum(al23))
            print(v7 == al23)
        else:
            print((25 >= (79 + 48)), (i17 - i17))
            print(v14.replace('a', '-').find('x'), int((v13 / (abs(100.75) + 1.0))), (abs(v13) ** 0.5))
        for i24 in v14:
            v25: str = i24
            al26: list[int] = v7
            if len(al26) > 0:
                al26[0] = 1
            print(len(v7), len(al26), sum(v7) - sum(al26))
            try:
                try:
                    if (f'{v7.index(v7.index(i17)):05d}' == ("<%5d>" % (i17 - -1))):
                        assert ((i17 - 60) >= (~i17)), "boom"
                except (AssertionError, KeyError):
                    print(-45)
                finally:
                    print(115)
                if ' pad '.isalpha():
                    break
                try:
                    if ((19 + i17) >= al26.pop()):
                        raise KeyError
                except (KeyError, ZeroDivisionError):
                    print(-77)
                finally:
                    print(138)
            except IndexError:
                v7.append(8)
            except KeyError:
                if ((v13 <= (v13 / int((v13 + 0.1)))) and (min(i17, i17) >= (i17 - -7))):
                    break
                v27: str = ""
                try:
                    v27 = f'/{(92 - i17):05d}{(v13 / 79)}'.replace(' ', '')
                except ZeroDivisionError:
                    print(-27)
                finally:
                    print(192)
            else:
                try:
                    print((v13 / (abs(123456.789) + 1.0)), (v13 / (i17 - 45)))
                except ZeroDivisionError:
                    print(-22)
                v28: list[str] = (v25 + i24).split('a')
    for i29 in range(-2, 8):
        v14 = f'/'
        for i30 in v14:
            pt0.name += '3.5'.rstrip()
            print(min((i29 << 3), min(i29, 96)))
            if (('3.5' + i30) < str(abs(v13))):
                break
    print(((66 - 57) % (abs(len(v7)) + 1)))
    try:
        print((ord(v14[0][1]) % (abs(len(v14)) + 1)))
    except IndexError:
        print(-61)
    print(bump(pt0, v7[(56 + 8)]))
    w31: int = 0
    while w31 < 5:
        w31 += 1
        v32: set[int] = set(v7)
        try:
            v14 = f'{'-7':<6}{(h0(v7.pop(), int((7.0 + v13))) / 8):8.3f}'.replace('l', '-')
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-36)
        finally:
            print(172)
        v14 = '-'.join('-'.join('ab'.split(',')).split('a'))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v7), sum(v7))
    print(v13)
    print(v14)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
3.5
3 3 0
3 3 0
3 3 0
3 3 0
False
-40
False
-40
False
-40
False
-40
False
-40
5
-46
2 2 0
115
```

AIL stdout, exit code 1:

```
3.5
3 3 0
3 3 0
3 3 0
3 3 0
False
-40
False
-40
False
-40
False
-40
False
-40
5
-46
1 1 0
115
```

AIL stderr:

```
ValueError: 0 is not in list
```

**What to do.**
1. Save the program as `/tmp/probes/fz212.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz212.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz212.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N N N' ail='N N N'`.

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
