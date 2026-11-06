**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42101349152 (seed `2076220870`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 30: cpython='296' ail='True'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076220870 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
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
    v1: int = 0
    try:
        v1 = ((18 * -2) - int(str((0 - b))))
    except ValueError:
        print(-42)
    v2: str = '-'.join('-7'.split(',')).replace(' ', '')
    v3: list[int] = [(-v1), (50 + 48)]
    v3.extend([(a ** 0)])
    v3.extend([(b * b), (v1 << 2), 6])
    print(66)
    if (not ('12'.replace(' ', '') != f'{(4 // 2)}{'-7':<6}{(1e10 + 1e-7):.2f}')):
        return (-v1)
    return (int((123456.789 % 7.0)) | (b - v1))


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 3 == 0:
            continue
        t += x
    return t


def main() -> int:
    pt0: Pt = Pt(1, 5, 0.5, 'café', [])
    v4: dict[str, int] = {}
    v4['a'] = 14
    v4['b'] = 26
    v5: list[int] = []
    al6: list[int] = v5
    v5.append(0)
    print(len(v5), len(al6), sum(v5) - sum(al6))
    v4['ab'] = 25
    try:
        print(max(float(max(96, 50)), (100.75 + 0.3)))
        try:
            v5.remove((9223372036854775807 ** 1))
        except ValueError:
            print(-52)
    except KeyError:
        v7: bytes = (b"Zed" + b"ab")
        print((min(0, 38) - len(v4)))
    except ValueError:
        print('3.5'.replace(' ', '-'), (int((1e-7 - 100.75)) <= v4.get('Zed'.upper(), 4)), (3.0 / (abs(0.5) + 1.0)))
        print(b"12"[:-1].decode())
    finally:
        print(204)
    v5 += [(79 - 48)]
    try:
        v5.extend([(-1 & 1), (6 // 20), (93 // 4)])
    except ZeroDivisionError:
        print(-45)
    finally:
        print(185)
    print(f'{67:d}-')
    print((0.3 / (abs(0.5) + 1.0)))
    try:
        print(h0((78 - 97), 92))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-61)
    print(float(78))
    try:
        if ('a,b,c' in v4):
            v8: str = str((8 + 11))
            v8 += v8
            print('-'.join(v8[1:4].split('a')))
        elif (f'{(2.5e-3 / (50 // 24)):.0f}{((-5 // -6) / 8):.2f}'.startswith('d')):
            v4.pop('b', 5)
        try:
            if ('a,b,c' in v4):
                raise IndexError('m0')
        except IndexError:
            print(-76)
        finally:
            print(174)
        for i9 in range(8, 0, -1):
            try:
                v10: list[int] = sorted(v5)
                print(((i9 * i9) + (i9 - 82)))
            except IndexError:
                v11: bytes = (b"ab" + b"a,b")
                v11 = (v11 + v11)
            finally:
                print(266)
    except ZeroDivisionError:
        try:
            print(h1(v5))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-2)
        finally:
            print(169)
        for i12 in al6:
            print((1e10 - 0.3), ('ab' in 'ab'), str((81 + i12)))
    except ValueError:
        v13: int = 0
        try:
            v13 = (88 % (abs((86 // 65)) + 1))
        except ZeroDivisionError:
            print(-84)
    try:
        v4.pop('a')
    except KeyError:
        print(-37)
    try:
        print(((77 + 4) // -4))
    except ZeroDivisionError:
        print(-50)
    try:
        al14: list[int] = v5
        al14.reverse()
        print(len(v5), len(al14), sum(v5) - sum(al14))
    except ZeroDivisionError:
        v15: int = ((59 % (abs(85) + 1)) - (5 - 22))
        try:
            print((not (v5[3] != max(v5))))
        except (IndexError, ValueError):
            print(-3)
        finally:
            print(179)
    else:
        w16: int = 0
        while w16 < 5:
            w16 += 1
            v17: list[int] = list(range(-3, 10, 1))
            if (f'{(1e-7 / round((1e-7 / (abs(1.25) + 1.0))))}'.startswith(' ')):
                al18: list[int] = v5
                if len(v5) > 0:
                    v5[0] = 3
                print(len(v5), len(al18), sum(v5) - sum(al18))
            elif ((w16 % (abs(45) + 1)) > w16):
                if ('ab' in '-'.join('a,b,c'.split(' '))):
                    continue
            v19: float = min(1e-7, (1e-7 - 1e-7))
        try:
            print(((3037000499 - 15) % 7))
        except ZeroDivisionError:
            print(-82)
    finally:
        print(296)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    ks21: list[str] = []
    for k20 in sorted(v4):
        ks21.append(k20)
    print(len(v4), sum(v4.values()), ','.join(ks21))
    print(len(v5), sum(v5))
    print(len(al6), sum(al6))
    return 7


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
1 1 0
101.05
-52
204
185
67-
0.19999999999999998
66
36
78.0
174
-10
266
-26
266
-40
266
-52
266
-62
266
-70
266
-76
266
-80
266
-21
5 5 0
296
```

AIL stdout, exit code 0:

```
1 1 0
101.05
-52
204
185
67-
0.19999999999999998
66
36
78.0
174
-10
266
-26
266
-40
266
-52
266
-62
266
-70
266
-76
266
-80
266
-21
5 5 0
True
179
296
1 5 0.5 café 0
2 51 ab,b
5 55
5 55
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz232.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz232.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz232.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='True'`.

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
