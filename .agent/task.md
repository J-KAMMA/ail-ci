**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40949475519 (seed `2075520147`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 39: cpython='<   91> café AbCd' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075520147 -o prog.py`, if that tree has it).

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


def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = (t * 5 + x) % 1000003
    return t


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 9) % 76003
    return (h1(n - 1, a + 2) * 1 + h1(n - 1, a - 0) + n) % 76003


def h2(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 25:
            break
        t += abs(x) + 1
    return t


def main() -> int:
    pt0: Pt = Pt(1, 6, 2.5e-3, '3.5', [])
    v1: str = (' pad ' * 3)
    print(str((abs(100.75) ** 0.5)))
    if (('café' + '3.5') == v1):
        try:
            print(0.3, (0.1 / -3))
        except ZeroDivisionError:
            print(-1)
        for i2 in v1:
            try:
                print((9 ** 2))
                try:
                    if ((123456.789 + 2.5e-3) > (0.3 % 0.75)):
                        raise RuntimeError
                except RuntimeError:
                    print(-95)
                else:
                    print(25)
                print(((2.5e-3 * 0.1) * (2.5e-3 * 3.0)))
            except KeyError:
                v1 = v1
            else:
                v3: int = 46
            v4: list[int] = []
            try:
                v4 = [(30 + 18), (-7 - 12), (28 + -1), max(-7, 48), (7 // 5)]
            except ZeroDivisionError:
                print(-37)
            try:
                if (i2.replace('a', '').count('l') > 3):
                    v4.extend(v4)
                elif (27 < max(v4)):
                    print((123456.789 * (abs(123456.789) ** 0.5)))
                    print(v1)
                else:
                    try:
                        v4.pop()
                    except IndexError:
                        print(-90)
            except IndexError:
                print(-69)
        print(bump(pt0, (-3 >> 9)))
    else:
        p5: Pt = Pt(22, 61, 7.0, v1, [])
        v6: int = (-min(18, 55))
    v7: float = abs((7.0 / (abs(100.75) + 1.0)))
    pt0.items.append(min(24, 28))
    v9: list[int] = [3 for c8 in range(8) if c8 % 2 == 1]
    for i10 in v1:
        print((v7 + v7))
        al11: list[int] = v9
        al11.sort()
        print(len(v9), len(al11), sum(v9) - sum(al11))
        al11.extend(v9)
    try:
        if (v1.replace('l', 'XY') == v1):
            raise ZeroDivisionError('m7')
    except ZeroDivisionError:
        print(-77)
    finally:
        print(116)
    al12: list[int] = v9
    v9 += [5]
    print(len(v9), len(al12), sum(v9) - sum(al12))
    for i13 in range(3):
        for i14 in range(1):
            al12.append((i13 - i14))
        w15: int = 0
        while w15 < 4:
            w15 += 1
            w16: int = 0
            while w16 < 3:
                w16 += 1
                if ((33 - 23) > (w15 + 4611686018427387904)):
                    continue
                v17: list[int] = []
                try:
                    v17 = [(w16 % -5)]
                except ZeroDivisionError:
                    print(-44)
                v18: str = '-'.join(f'{(0.3 * v7):.3f}{(i13 + 38)}'.split(' '))
            try:
                al12[-2] = len(al12)
            except IndexError:
                print(-34)
        print(v1.isalpha(), min(83, i13), ((-1 * i13) < (3037000499 + i13)))
    v9.extend(al12)
    print(89)
    v9.sort(key=lambda q: (-q, q))
    v19: dict[str, int] = {}
    v19['e'] = -6
    v19['b'] = 4
    v19['3.5'] = (3037000499 * 22)
    print(("<%5d>" % 91), 'café', ('AbCd' * 1))
    v20: bytes = (b"x" * 0)
    v21: bool = (((v1 + v1) < ('Zed' + v1)) or v1.isalpha())
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v1)
    print(v7)
    print(len(v9), sum(v9))
    print(len(al12), sum(al12))
    ks23: list[str] = []
    for k22 in sorted(v19):
        ks23.append(k22)
    print(len(v19), sum(v19.values()), ','.join(ks23))
    print(len(v20), v20.decode())
    print(v21)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
10.037429949942366
0.1375921375921376
4 4 0
0.1375921375921376
8 8 0
0.1375921375921376
16 16 0
0.1375921375921376
32 32 0
0.1375921375921376
64 64 0
0.1375921375921376
128 128 0
0.1375921375921376
256 256 0
0.1375921375921376
512 512 0
0.1375921375921376
1024 1024 0
0.1375921375921376
2048 2048 0
0.1375921375921376
4096 4096 0
0.1375921375921376
8192 8192 0
0.1375921375921376
16384 16384 0
0.1375921375921376
32768 32768 0
0.1375921375921376
65536 65536 0
-77
116
131073 131073 0
False 0 True
False 1 True
False 2 True
89
<   91> café AbCd
1 6 0.0025 3.5 1
 pad  pad  pad 
0.0687960687960688
262152 1572886
262152 1572886
3 66814010976 3.5,b,e
0 
True
```

AIL stdout, exit code 1:

```
10.037429949942366
0.1375921375921376
4 4 0
0.1375921375921376
8 8 0
0.1375921375921376
16 16 0
0.1375921375921376
32 32 0
0.1375921375921376
64 64 0
0.1375921375921376
128 128 0
0.1375921375921376
256 256 0
0.1375921375921376
512 512 0
0.1375921375921376
1024 1024 0
0.1375921375921376
2048 2048 0
0.1375921375921376
4096 4096 0
0.1375921375921376
8192 8192 0
0.1375921375921376
16384 16384 0
0.1375921375921376
32768 32768 0
0.1375921375921376
65536 65536 0
-77
116
131073 131073 0
False 0 True
False 1 True
False 2 True
89
```

AIL stderr:

```
TypeError: '<' not supported between instances of 'object' and 'int'
```

**What to do.**
1. Save the program as `/tmp/probes/fz204.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz204.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz204.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<   N> café AbCd' ail='<end>'`.

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
