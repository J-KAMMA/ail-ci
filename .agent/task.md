**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41234438491 (seed `2075719067`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=3; line 29: cpython='NAN    32' ail='-NAN    32'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075719067 -o prog.py`, if that tree has it).

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


def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 3 + 4) % 45003
    return (h0(n - 1, a + 0) * 3 + h0(n - 1, a - 0) + n) % 45003


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 4 == 0:
            continue
        t += x
    return t


def h2(a: int, b: int) -> int:
    v1: int = ((b // (abs(a) + 1)) - b)
    v2: str = '12'
    v3: list[int] = []
    try:
        v3 = [(a // (abs(v1) + 1)), (v1 // v1)]
    except ZeroDivisionError:
        print(-86)
    try:
        if (v2.endswith('he')):
            try:
                p4: Pt = Pt(v1, b, 100.75, 'café', [])
                print(p4.name, sum(p4.items))
                v5: bool = ((v1 > 3) or (f'{v2:<6}{v2:^9}{v2}'.startswith(' ')))
            except ValueError:
                print(b"abc"[-2:-1].decode())
            v6: dict[str, int] = {}
            v6['a'] = 98
            v6['c'] = 70
            v6['b'] = 13
        elif ((a % -5) != (v1 + 90)):
            b = (80 + (-1 - 97))
            w7: int = 0
            while w7 < 1:
                w7 += 1
                if (int(str(50)) < len(v2)):
                    break
                v8: list[str] = [v2, v2, v2]
        else:
            print((' pad '.upper() * 1))
            v9: float = 0.0
            try:
                v9 = float(max(v3))
            except ValueError:
                print(-76)
    except ValueError:
        print(-51)
    if ((1.25 * 123456.789) > (0.3 % 2.5)):
        return (a & a)
    return sum(v3)


def main() -> int:
    pt0: Pt = Pt(0, 8, 0.1, 'a,b,c', [])
    w10: int = 0
    while w10 < 6:
        w10 += 1
        print(max(w10, (~21)))
    v11: float = ((7.0 + 0.3) / (abs(3.0) + 1.0))
    v12: float = ((93 * 60) / 3)
    try:
        v13: list[int] = [f'{len('-7'.strip()):>6}{'3.5'}'.count('l'), int((1e10 + v11)), 38, 'ab'.upper().find('x')]
        try:
            v13.remove(-4)
        except ValueError:
            print(-2)
        finally:
            print(127)
        v13.reverse()
    except ValueError:
        print((abs((v12 / (abs(123456.789) + 1.0))) ** 0.5))
        w14: int = 0
        while w14 < 3:
            w14 += 1
            print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
            v11 *= 3.0
    finally:
        print(216)
    print(((56 ** 3) > 3))
    try:
        v15: list[int] = [87, int(v12)]
    except IndexError:
        v16: bool = ((v11 - v12) <= float((50 - 74)))
        try:
            if (('a,b,c' == str(len('x'.upper()))) and ((32 + 91) >= (45 + 46))):
                raise ZeroDivisionError('m0')
        except ZeroDivisionError:
            print(-57)
        finally:
            print(111)
    w17: int = 0
    while w17 < 6:
        w17 += 1
        v18: dict[str, int] = {}
        v18['c'] = 47
        try:
            if ((42 // (abs(w17) + 1)) > (w17 - w17)):
                raise ValueError('m4')
        except (IndexError, ValueError):
            print(-1)
        else:
            print(30)
    for i19 in range(3, 7, 1):
        try:
            print(f'{(v12 % 0.75):.0f}{ord(("%-4d|" % (i19 ^ 26))[3]):>6}'.upper())
        except IndexError:
            print(-1)
        w20: int = 0
        while w20 < 5:
            w20 += 1
            v12 *= (v12 + 100.75)
            if ((i19 - w20) != h0(9, h2((i19 // w20), (i19 - 2)))):
                v21: list[int] = []
                try:
                    v21 = [83, (65 % -2), (91 ** 3)]
                except ZeroDivisionError:
                    print(-7)
                if ((w20 // (abs(6) + 1)) < (w20 - i19)):
                    continue
            elif ('ab'.upper().endswith('a')):
                v22: int = ((56 - i19) + (14 * i19))
                v23: int = 3037000499
            print((6 % 7), '-'.join('a,b,c'.split(' ')), w20)
        v24: list[int] = [(i19 // (abs(i19) + 1)), (-7 + 18)]
    for i25 in range(5):
        for i26 in range(1, 11, 1):
            v11 *= 2.5e-3
            print(((-9223372036854775807 - i26) / 3))
        v27: str = str(i25)[-2:2]
        v28: list[int] = [-3] * 5
    if (31 > 3):
        for i29 in range(8, -2, -1):
            v30: list[int] = [0] * 0
            print(b"abc"[-2:2].decode())
            print((i29 - (75 * 5)))
    pt0.c += (7.0 / (abs(v12) + 1.0))
    p31: Pt = pt0
    pt0.b = int(str((57 + 67)))
    print(pt0.a, pt0.b, p31.b, 7)
    for i32 in range(2):
        v33: int = max((i32 + i32), 19)
    v34: list[int] = [1, 2, 3]
    print((8 ** 2), v12)
    for i35 in range(0, 7, 2):
        al36: list[int] = v34
        v34.reverse()
        print(len(v34), len(al36), sum(v34) - sum(al36))
        print(((abs(v12) ** 0.5) - (abs(0.1) ** 0.5)))
    print(3.0, 'hello'.upper(), (19 - 18))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v11)
    print(v12)
    print(p31.a, p31.b, p31.c, p31.name, len(p31.items))
    print(len(v34), sum(v34))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
1
2
3
4
5
6
-2
127
216
True
-1
-1
-1
-1
-1
-1
0    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
-86
-86
0    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
-86
NAN    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
6 a,b,c 5
NAN    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
6 a,b,c 5
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
-3.0744573456182584e+18
b
-367
b
-368
b
-369
b
-370
b
-371
b
-372
b
-373
b
-374
b
-375
b
-376
0 124 124 7
64 inf
3 3 0
inf
3 3 0
inf
3 3 0
inf
3 3 0
inf
3.0 HELLO 1
0 124 0.1 a,b,c 0
1.4396711520283483e-130
inf
0 124 0.1 a,b,c 0
3 6
```

AIL stdout, exit code 3:

```
1
2
3
4
5
6
-2
127
216
True
-1
-1
-1
-1
-1
-1
0    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
-86
-86
0    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
-86
-NAN    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
6 a,b,c 5
-NAN    32
6 a,b,c 1
6 a,b,c 2
6 a,b,c 3
6 a,b,c 4
6 a,b,c 5
-3.0744573456182584e+18
```

AIL stderr:

```
AIL limit: int_overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz208.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz208.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz208.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='NAN    N' ail='-NAN    N'`.

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
