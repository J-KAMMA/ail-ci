**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41755164524 (seed `2076102845`, CPython 3.12, modes default+ir) found a DIFF: `line 1: cpython='9223372036854775810' ail='287'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076102845 -o prog.py`, if that tree has it).

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
        if t > 22:
            break
        t += abs(x) + 1
    return t


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 49:
            break
        t += abs(x) + 1
    return t


def h2(a: int, b: int) -> int:
    v1: int = min(a, b)
    v2: str = 'AbCd'
    v3: list[int] = [v1, (v1 - v1), (10 - -8), v1, a]
    print((('abc' * 3) + (v2 + 'ab')))
    if (int((abs(0.5) ** 0.5)) < b):
        return (a & v1)
    return (v1 + (52 % 8))


def main() -> int:
    pt0: Pt = Pt(3, 5, 1e10, 'Zed', [])
    v4: float = ((123456.789 * 0.5) - (123456.789 / (abs(3.0) + 1.0)))
    pt0.a -= (97 - 91)
    v5: set[int] = {9, 11, 5, 8, 0, -5}
    try:
        print(((3 - -9223372036854775807) ** 1))
        print((~(8 + 9223372036854775807)))
    except ZeroDivisionError:
        v6: list[int] = [max(50, 3), 'a,b,c'[0:].count('b'), (9 * 40), (-4 - 72)]
        print('q q')
    except ValueError:
        try:
            print(('-7'[3] + 'a,b,c'[1:2]))
        except IndexError:
            print(-13)
        v7: int = (abs(42) + round((100.75 * v4)))
    finally:
        print(287)
    v5 -= {12, 7, 12, 0, 4}
    print('a,b,c'.upper(), (75 / 4), 'ab'.replace(' ', 'XY'))
    v4 -= (0.3 + v4)
    v8: dict[str, int] = {}
    v8['dd'] = 87
    for i9 in range(9, 0, -1):
        for i10 in range(1, 11, 3):
            print(b"12".decode())
            if ('ab'[2] >= 'a,b,c'.upper()):
                if 'hello'.isspace():
                    break
                v11: str = f'{(v4 % 2.5)}'
        print('ab'.lower(), ((i9 + i9) in v5), (abs(v4) ** 0.5))
        print(min(v4, (abs(v4) ** 0.5)))
    w12: int = 0
    while w12 < 3:
        w12 += 1
        v13: float = (max(1e-7, 100.75) * (v4 + v4))
        try:
            print((57 // 9))
        except ZeroDivisionError:
            print(-80)
        v8['hello'] = (w12 + -8)
    print(((v4 * 123456.789) + (v4 / (abs(v4) + 1.0))))
    pt0.items.append(72)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v4)
    print(len(v5), sum(v5), max(v5) if len(v5) > 0 else 0)
    ks15: list[str] = []
    for k14 in sorted(v8):
        ks15.append(k14)
    print(len(v8), sum(v8.values()), ','.join(ks15))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
9223372036854775810
-9223372036854775816
287
A,B,C 18.75 ab
12
```

AIL stdout, exit code 1:

```
287
```

AIL stderr:

```
OverflowError
```

**What to do.**
1. Save the program as `/tmp/probes/fz226.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz226.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz226.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='N'`.

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
