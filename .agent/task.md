**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41625900402 (seed `2076011178`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 3: cpython='2 7 123456.789 x 0' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076011178 -o prog.py`, if that tree has it).

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
        t = (t * 7 + x) % 1000003
    return t


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 57:
            break
        t += abs(x) + 1
    return t


def h2(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 3 == 0:
            continue
        t += x
    return t


def main() -> int:
    pt0: Pt = Pt(2, 7, 123456.789, 'x', [])
    w1: int = 0
    while w1 < 2:
        w1 += 1
        v2: int = (w1 - round((1e10 % 0.75)))
    try:
        print(abs((0.3 / (74 << 4))))
    except ZeroDivisionError:
        print(-48)
    for i3 in range(1, 5, 3):
        v4: list[int] = [96]
        v5: int = len(v4)
    v6: str = ('a,b,c' + 'a,b,c').lstrip()
    try:
        print(((96 // (abs(-4) + 1)) % 3))
    except ZeroDivisionError:
        print(-80)
    v7: list[int] = []
    v8: str = ("%d" % (67 + 24))
    v9: list[str] = str(round((1e10 * 1e10))).split('a')
    v7.sort(key=lambda q: (-q, q))
    for i10 in v8:
        if ('abc' in '3.5'):
            v6 = ('x'.strip() + ("%03d" % (42 ** 1)))
            v11: float = ((abs(7.0) ** 0.5) * (1e10 - 1.25))
            v12: int = ((96 // (abs(85) + 1)) + int((7.0 % 0.75)))
        elif ((i10 in v8[:4]) and ((0.5 / (abs(2.5e-3) + 1.0)) == (0.5 / (abs(0.3) + 1.0)))):
            try:
                try:
                    print(i10[1], b"x".decode())
                except IndexError:
                    print(-80)
            except IndexError:
                v13: set[int] = set(v7)
            except ZeroDivisionError:
                print((b"ab" + b"ab").decode())
            if (i10[0:-1] == i10):
                if (((abs(3.0) ** 0.5) > float((66 + -1))) or (79 > (48 ** 1))):
                    break
                v14: dict[str, int] = {}
                v14['dd'] = 88
        else:
            p15: Pt = Pt(39, 92, 100.75, '日本', [])
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v6)
    print(len(v7), sum(v7))
    print(v8)
    print(len(v9), ','.join(v9))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
0.0002533783783783784
1
2 7 123456.789 x 0
a,b,ca,b,c
0 0
91
1 100000000000000000000
```

AIL stdout, exit code 1:

```
0.0002533783783783784
1
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz220.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz220.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz220.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N N N.N x N' ail='<end>'`.

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
