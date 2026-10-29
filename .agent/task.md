**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40828421046 (seed `2075507942`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 38: cpython='-60' ail='106'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075507942 -o prog.py`, if that tree has it).

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
    v1: int = min(3037000499, (72 - a))
    v2: str = str(float((v1 * 9223372036854775807)))
    v3: list[int] = [-2] * 3
    p4: Pt = Pt(50, v1, 7.0, v2, [])
    try:
        if ((b // (abs(a) + 1)) >= (9223372036854775807 + 38)):
            raise ValueError('m7')
    except ValueError:
        print(-30)
    else:
        print(61)
    if (v2 < ("%-4d|" % (a | 53))):
        return (v1 ** 3)
    return ((b >> 7) ^ len(v2))


def h1(a: int, b: int) -> int:
    v5: int = ((96 + a) * b)
    v6: str = (f'{'abc':^9}{(1.25 * 1.25)}' + 'hello')
    v7: list[int] = [(19 + a), (a ^ 1), (v5 >> 2), 2]
    v5 -= (90 // (abs(b) + 1))
    try:
        v7.pop()
    except IndexError:
        print(-76)
    if (((a - 35) != (v5 * 56)) or ((59 % (abs(b) + 1)) == b)):
        return int(abs(2.5e-3))
    return (93 ** 2)


def main() -> int:
    pt0: Pt = Pt(1, 8, 3.0, 'abc', [])
    v8: float = (123456.789 * 1e10)
    v9: str = 'café'
    v10: int = ((10 * 28) * (3037000499 ^ 50))
    try:
        v9 = f'{(v10 % 8):05d}{v9:^9}{(abs(1e-7) ** 0.5)}'
    except ZeroDivisionError:
        print(-31)
    v11: float = ((0.1 / (abs(3.0) + 1.0)) - (0.5 + v8))
    for i12 in v9:
        v13: dict[str, int] = {}
        v13['dd'] = 48
        print(((v10 + 2) << 5))
    print(((v10 - v10) ^ (-v10)))
    v14: str = (v9 + 'hello').upper()
    try:
        if (v9 >= '-7'.lower()):
            assert (((v10 ** 3) == v10) and (51 > 3)), "boom"
    except AssertionError:
        print(-60)
    finally:
        print(106)
    v15: list[int] = [1, 2, 3]
    v16: str = str(float(len(v9)))
    print((v10 & abs(-5)))
    pt0.c += v11
    v15.sort(reverse=True)
    print(int((123456.789 / (abs(v8) + 1.0))))
    v17: int = ((95 >> 1) << 7)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v8)
    print(v9)
    print(v10)
    print(v11)
    print(v14)
    print(len(v15), sum(v15))
    print(v16)
    print(v17)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
-850360125720
-60
106
0
0
1 8 -1234567889999997.5 abc 0
1234567890000000.0
00000  café   0.00031622776601683794
850360125720
-1234567890000000.5
00000  CAFÉ   0.00031622776601683794HELLO
3 6
36.0
6016
```

AIL stdout, exit code 1:

```
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
27211524023104
-850360125720
106
```

AIL stderr:

```
OverflowError
```

**What to do.**
1. Save the program as `/tmp/probes/fz201.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz201.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz201.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='-N' ail='N'`.

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
