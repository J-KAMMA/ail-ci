**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40298776404 (seed `2075200891`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 45: cpython='-1.9999506175892305e+20' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075200891 -o prog.py`, if that tree has it).

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


def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 5) % 23003
    return (h0(n - 1, (a * 6 + n) % 23003) + 4) % 23003


def main() -> int:
    pt0: Pt = Pt(3, 7, 3.0, ' pad ', [])
    print(((1.25 - 1e-7) % 7.0))
    v1: list[int] = [1, 2, 3]
    v2: float = abs((1e10 - 123456.789))
    try:
        print(min((len(v1) / 8), (1.25 / -1)))
    except ZeroDivisionError:
        print(-40)
    v3: list[int] = []
    try:
        v3 = [(77 ** 3), max(27, 83), (0 // 2), 30, (58 ** 3)]
    except ZeroDivisionError:
        print(-89)
    finally:
        print(131)
    try:
        if ('Zed' in f'{h0(0, (-1 // -1)):3d}'):
            print(sum(v3))
        print(((100.75 - v2) % 0.75))
        for i4 in range(6, -1, -1):
            pt0.c += v2
            print(abs(v2), (v2 * v2), 7.0)
    except IndexError:
        p5: Pt = pt0
        p5.b = sum(v1)
        print(pt0.a, pt0.b, p5.b, 9)
    else:
        for i6 in range(8, 2, -1):
            v7: str = (b"hello".decode() + f'{max(i6, 76):05d}{i6:3d}')
            try:
                print((((37 % i6) != (98 // (abs(98) + 1))) or (i6 == i6)))
            except ZeroDivisionError:
                print(-56)
            finally:
                print(117)
            v8: str = ("%d" % int(v2)).replace('l', 'XY')
        print((v2 / (abs(min(0.3, v2)) + 1.0)))
    try:
        if ((13 >> 12) > max(-1, 38)):
            raise AssertionError('m0')
    except (AssertionError, ValueError):
        print(-48)
    else:
        print(40)
    v1.insert(-1, -3)
    for i9 in v1:
        try:
            v2 *= (v2 + v2)
            v10: str = ""
            try:
                v10 = str((i9 // 1))
            except ZeroDivisionError:
                print(-85)
        except ZeroDivisionError:
            v11: int = ((i9 * 84) | (99 - i9))
        w12: int = 0
        while w12 < 5:
            w12 += 1
            print((123456.789 - v2))
            for i13 in range(1, 7):
                print(((abs(7.0) ** 0.5) + v2))
                try:
                    print(((i9 % 3) << 12))
                except ZeroDivisionError:
                    print(-11)
                finally:
                    print(182)
            if ((i9 < round(v2)) and (((v2 - v2) <= ((i9 ** 2) / 4)) or ('abc' == '3.5'))):
                v14: bytes = b"a,b"
                if (-9223372036854775807 >= (w12 * -2)):
                    continue
            elif ((w12 + 42) > (74 * 2)):
                if (('q q' in 'a,b,c') and ((1e-7 * v2) <= float((w12 % 5)))):
                    break
                v15: bool = (('a,b,c' in 'AbCd') and (round(v2) < i9))
    for i16 in range(6):
        for i17 in range(4):
            if (i16 > 3):
                break
            v18: float = 0.0
            try:
                v18 = float((i16 % i16))
            except ZeroDivisionError:
                print(-16)
        print('12')
        if (not (v2 == 0.1)):
            break
    v19: int = 0
    try:
        v19 = ((52 - -6) - h0(10, 40))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-63)
    print(b"hello"[:-1].decode())
    print(float((-6 + v19)))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v1), sum(v1))
    print(v2)
    print(len(v3), sum(v3))
    print(v19)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
1.2499999
-1.25
131
0.03899955749511719
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
True
117
True
117
True
117
True
117
True
117
True
117
7692212725.546923
40
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
-7.999604945591099e+40
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
-7.999604945591099e+40
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
-7.999604945591099e+40
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
-7.999604945591099e+40
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
-7.999604945591099e+40
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.999604945591099e+40
8192
182
7.99
... [cut, 4647 bytes in all]
```

AIL stdout, exit code 1:

```
1.2499999
-1.25
131
0.03899955749511719
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
9999876543.211 9.999753087946159e+19 7.0
True
117
True
117
True
117
True
117
True
117
True
117
7692212725.546923
40
-1.9999506175892305e+20
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
1.9999506175892318e+20
4096
182
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz2.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz2.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz2.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='-N.Ne+N' ail='<end>'`.

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
