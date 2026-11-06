**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42209881722 (seed `2076311105`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 16: cpython='242' ail='4 4 0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076311105 -o prog.py`, if that tree has it).

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
    v1: int = a
    v2: str = ""
    try:
        v2 = 'café'[3]
    except IndexError:
        print(-8)
    v3: list[int] = [a, v1, (2 ** 2)]
    print(3.0)
    for i4 in range(2, 11, 2):
        try:
            if ' pad '.isspace():
                raise ValueError('m1')
        except ValueError:
            print(-90)
        else:
            print(78)
        print(v2[-2:].lower())
    if (not (b > 3)):
        return (-1 >> 1)
    return len(v3)


def h1(a: int, b: int) -> int:
    v5: int = b
    v6: str = 'Zed'
    v7: list[int] = []
    try:
        v7 = [len(v6), int('12')]
    except ValueError:
        print(-70)
    w8: int = 0
    while w8 < 1:
        w8 += 1
        p9: Pt = Pt(36, b, 3.0, v6, [])
    p10: Pt = Pt(-3, 91, 0.1, v6, [])
    v11: dict[str, int] = {}
    v11['c'] = -2
    v11['a'] = 6
    if (v5 > (34 ** 0)):
        return (-8 >> 2)
    return (44 % 7)


def h2(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 2 == 0:
            continue
        t += x
    return t


def main() -> int:
    pt0: Pt = Pt(4, 2, 2.5e-3, ' pad ', [])
    print(str((1.25 * 7.0)))
    v12: list[int] = list(range(0, 9, 2))
    p13: Pt = Pt(12, 3, 0.3, 'AbCd', [])
    p13.c += (1e-7 % 2.5)
    try:
        v12.remove(h2(v12))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-69)
    print(((79 * -1) > 3), 'x')
    try:
        print(((123456.789 - 123456.789) / (abs((2.5e-3 / (90 - 58))) + 1.0)))
    except ZeroDivisionError:
        print(-91)
    try:
        v14: list[int] = [-2] * 5
    except IndexError:
        v15: list[int] = ['-7'.upper().count('a'), max(0, 3), (85 * 71)]
    except ValueError:
        if ((17 // (abs(98) + 1)) == h1((41 + 4611686018427387904), 14)):
            try:
                print((v12[(-8 * 4611686018427387904)] + (15 // (abs(59) + 1))))
            except IndexError:
                print(-1)
        elif (max(6, 4611686018427387904) >= (79 // (abs(55) + 1))):
            v16: list[int] = []
            try:
                v16 = [22, (-30), (5 // -8), (60 + 52), (73 | 1)]
            except ZeroDivisionError:
                print(-13)
            v17: list[int] = [1] * 1
        w18: int = 0
        while w18 < 4:
            w18 += 1
            try:
                v12[-3] = w18
            except IndexError:
                print(-74)
            print((b"Zed" + b"hello").decode())
            print(('q q' in ('q q' + '12')), (w18 | w18), 98)
    try:
        try:
            print((0.5 / v12.pop()))
        except (IndexError, ZeroDivisionError):
            print(-57)
        try:
            if ((76 ** 0) > min(15, 33)):
                raise KeyError('m1')
        except KeyError:
            print(-77)
        finally:
            print(147)
    except IndexError:
        v19: bytes = b"hello"[1:2]
    except ValueError:
        try:
            if (len(v12) > 3):
                assert ((89 - 45) > (9 + 49)), "boom"
        except AssertionError:
            print(-16)
        if ((h2(v12) > (~3037000499)) or (('3.5' in str((33 // 5))) or 'café'.isupper())):
            v12.append(3037000499)
            try:
                if ((70 & 27) >= (94 // (abs(40) + 1))):
                    raise AssertionError('m0')
            except AssertionError:
                print(-45)
            finally:
                print(171)
        elif ((81 // -8) >= (2 ^ 87)):
            try:
                print(('x' + '-7'[2]))
            except IndexError:
                print(-38)
        else:
            print(('café' + 'q q').lstrip())
    finally:
        print(261)
    try:
        if ('x' in str((-86))):
            if (85 > 3):
                p20: Pt = pt0
                pt0.b = (37 // 13)
                print(pt0.a, pt0.b, p20.b, 6)
                v12 += v12
                v21: list[str] = ['3.5', 'hello', 'a,b,c', '3.5']
            print((len(v12) - 39))
        v22: list[str] = ' pad '[0:4].split(',')
        print(int(100.75), (abs(0.3) ** 0.5))
    except ZeroDivisionError:
        try:
            try:
                print(h2(v12))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-41)
            v23: int = 0
            try:
                v23 = ((55 * 69) % -6)
            except ZeroDivisionError:
                print(-45)
        except IndexError:
            al24: list[int] = v12
            al24.append(4)
            print(len(v12), len(al24), sum(v12) - sum(al24))
        except KeyError:
            print(((41 + 61) & (-4 % (abs(4) + 1))))
        print((-9223372036854775807 - 82))
    except IndexError:
        al25: list[int] = v12
        v12.append(7)
        print(len(v12), len(al25), sum(v12) - sum(al25))
    else:
        print(('12' in str(0.1)))
        w26: int = 0
        while w26 < 6:
            w26 += 1
            print(sum(v12))
            w27: int = 0
            while w27 < 3:
                w27 += 1
                v28: set[int] = set(v12)
                print((b"Zed" + b"x").decode())
                try:
                    print((len(v12) % 4))
                except ZeroDivisionError:
                    print(-51)
            if (('hello' in 'q q'[3]) or (len(v12) < (38 << 12))):
                break
    finally:
        print(242)
    al29: list[int] = v12
    v12 += [7]
    print(len(v12), len(al29), sum(v12) - sum(al29))
    v30: bytes = b"Zed"[-2:]
    print(((16 >> 4) >= 87))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v12), sum(v12))
    print(p13.a, p13.b, p13.c, p13.name, len(p13.items))
    print(len(al29), sum(al29))
    print(len(v30), v30.decode())
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
8.75
False x
0.0
0.0625
147
261
100 0.5477225575051661
False
12
Zedx
3
Zedx
3
Zedx
3
242
```

AIL stdout, exit code 0:

```
8.75
False x
0.0
0.0625
147
261
100 0.5477225575051661
False
12
Zedx
3
Zedx
3
Zedx
3
4 4 0
242
5 5 0
False
4 2 0.0025  pad  0
5 26
12 3 0.3000001 AbCd 0
5 26
2 ed
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz235.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz235.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz235.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='N N N'`.

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
