**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40782584863 (seed `2075423520`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 9: cpython='154' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075423520 -o prog.py`, if that tree has it).

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
    v1: int = 0
    try:
        v1 = ord(f'{'x'}{' pad ':<6}'[0])
    except IndexError:
        print(-15)
    finally:
        print(154)
    v2: str = str(78).lower()
    v3: list[int] = [1, 2, 3]
    v3.sort(key=lambda q: (-q, q))
    try:
        print((7.0 / min(66, 89)), 'a,b,c', 0.3)
    except ZeroDivisionError:
        print(-63)
    finally:
        print(108)
    if (('café' in b"a,b".decode()) and ('日本' in v2)):
        try:
            v3.remove((v1 & v1))
        except ValueError:
            print(-5)
    else:
        try:
            print((50 ** 3))
        except KeyError:
            p4: Pt = Pt(45, 3, 7.0, v2, [])
    if (a <= (v1 * a)):
        return (a % (abs(v1) + 1))
    return ((6 + a) * (5 ** 3))


def main() -> int:
    pt0: Pt = Pt(8, 4, 1.25, '12', [])
    v5: bool = False
    try:
        v5 = (int(b"hello".decode()) > (20 + 1))
    except ValueError:
        print(-47)
    for i6 in range(2, 9, 1):
        p7: Pt = Pt(i6, -3, 7.0, 'café', [])
    print(f'{34:^7}-')
    try:
        v5 = ((3 + 40) > (27 % -7))
    except ZeroDivisionError:
        print(-45)
    v8: int = 29
    print(((7.0 + 3.0) + (0.3 * 123456.789)))
    v9: set[int] = set()
    v10: float = 0.0
    try:
        v10 = (100.75 * (1e10 / abs(v8)))
    except ZeroDivisionError:
        print(-1)
    w11: int = 0
    while w11 < 1:
        w11 += 1
        for i12 in range(-2, 4):
            for i13 in range(6, 2, -1):
                if ((i13 % 4) > int(str(len(v9)))):
                    break
                try:
                    print(((73 + 67) // 3))
                except ZeroDivisionError:
                    print(-75)
            try:
                if (((v10 <= float(39)) or ((~v8) < (v8 + v8))) and (((i12 >> 3) == (v8 - w11)) and ('日本'[0:2].endswith('a')))):
                    print(((v10 * v10) % 7.0))
                    if ((f'{(w11 // (abs(62) + 1)):d}' == '-7'[-2:-1]) and ((23 - 55) < (-7 // 5))):
                        break
                elif ((str(h0((20 % v8), (v8 - w11))).startswith(' ')) and ((-65) > -3)):
                    print(pt0.name, sum(pt0.items))
                    try:
                        v8 = ((2 - 88) // w11)
                    except ZeroDivisionError:
                        print(-39)
            except ZeroDivisionError:
                print(-72)
            finally:
                print(110)
            if (abs(2.5e-3) == (v10 - v10)):
                v14: float = abs((1e-7 - 0.1))
            elif (not ((2 & v8) >= w11)):
                try:
                    v9.discard(h0(round((v10 * v10)), -6))
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-26)
            else:
                v15: list[int] = []
                try:
                    if (('x' + '12') == '-7'):
                        assert (str((v8 & -9223372036854775807)).startswith(' ')), "boom"
                except AssertionError:
                    print(-39)
        if ((73 | 9223372036854775807) <= (6 + 47)):
            w16: int = 0
            while w16 < 3:
                w16 += 1
                if (((v8 << 9) != max(w11, 16)) or ('日本' >= 'ab'[-2:2])):
                    break
                v9 |= set()
            v17: float = float(len(v9))
            for i18 in range(-1, 6):
                print(((34 * 17) << 2))
                print('Zed'[0:])
        elif ('abc' in str(min(v8, -7))):
            print((str(v8) + 'a,b,c'))
            v9.update({10, 4, 4, -5, 8, 2})
        else:
            print(pt0.name, sum(pt0.items))
            try:
                if (float((v8 >> 2)) <= abs(v10)):
                    break
                if (not (str((w11 // (abs(v8) + 1))).startswith('he'))):
                    continue
                if ('12' >= '-'.join('12'.split(' '))):
                    break
            except ValueError:
                v19: str = 'ab'.rstrip().lstrip()
            except ZeroDivisionError:
                v20: int = (v8 - w11)
            finally:
                print(219)
        v21: list[int] = []
        try:
            v21 = [(w11 + w11), (v8 % 20), len(v9), 25]
        except ZeroDivisionError:
            print(-83)
    try:
        v8 = (v8 + v8)
        v9.update({12, 9, 2, 6, -3, 2})
    except ZeroDivisionError:
        v22: float = max((v10 / (abs(v10) + 1.0)), (v10 * v10))
    finally:
        print(280)
    p23: Pt = Pt(v8, v8, 100.75, '日本', [])
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v5)
    print(v8)
    print(len(v9), sum(v9), max(v9) if len(v9) > 0 else 0)
    print(v10)
    print(p23.a, p23.b, p23.c, p23.name, len(p23.items))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-47
  34   -
37047.0367
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
154
0.10606060606060606 a,b,c 0.3
108
125000
110
154
0.10606060606060606 a,b,c 0.3
108
125000
12 0
219
280
8 4 1.25 12 0
True
58
5 26 12
34741379310.344826
58 58 100.75 日本 0
```

AIL stdout, exit code 1:

```
-47
  34   -
37047.0367
154
0.10606060606060606 a,b,c 0.3
108
125000
110
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz199.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz199.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz199.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='<end>'`.

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
