**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42486703487 (seed `2076514981`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 15: cpython='False' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076514981 -o prog.py`, if that tree has it).

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
        return (a * 2 + 3) % 33003
    return (h0(n - 1, (a * 5 + n) % 33003) + 0) % 33003


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 6 + 0) % 82003
    return (h1(n - 1, a + 1) * 5 + h1(n - 2, a - 3) + n) % 82003


def main() -> int:
    pt0: Pt = Pt(2, 5, 2.5e-3, 'a,b,c', [])
    v2: list[int] = [(c1 - c1) for c1 in range(4) if c1 % 2 == 0]
    w3: int = 0
    while w3 < 1:
        w3 += 1
        v4: float = ((2.5e-3 * 0.1) / (abs(0.5) + 1.0))
        print((~w3), 'a,b,c'[0:], 'AbCd')
    try:
        print(('日本'[2] * 1))
    except IndexError:
        print(-84)
    finally:
        print(192)
    for i5 in range(5):
        v2.append((25 + 98))
        v6: bool = ('abc'.lstrip() < '日本'[:-1])
    al7: list[int] = v2
    v2.sort()
    print(len(v2), len(al7), sum(v2) - sum(al7))
    print(v2 == al7)
    al8: list[int] = al7
    al8.append(0)
    print(len(al7), len(al8), sum(al7) - sum(al8))
    v9: dict[str, int] = {}
    w10: int = 0
    while w10 < 3:
        w10 += 1
        w11: int = 0
        while w11 < 1:
            w11 += 1
            print(b"hello".decode())
        print((b"ab" + b"ab").decode())
        for i12 in range(4):
            al7.extend(al8)
    print(b"hello".decode().replace(' ', 'XY'))
    try:
        print((7.0 / 18), 0.5)
    except ZeroDivisionError:
        print(-6)
    for i13 in range(-1, 3):
        for i14 in range(1):
            al8.sort(key=lambda q: (-q, q))
            try:
                print((len(al7) <= (i13 // -3)))
            except ZeroDivisionError:
                print(-58)
            al7 += [len(v9), round((7.0 % 2.5)), i13]
    p15: Pt = Pt(96, 89, 3.0, 'a,b,c', [])
    v16: str = '3.5'[:4]
    print(f'{v16:>8}')
    v17: list[int] = list(range(1, 9, 3))
    v17.extend([(23 * 0), (50 + 88), (52 - 40)])
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v2), sum(v2))
    print(len(al7), sum(al7))
    print(len(al8), sum(al8))
    ks19: list[str] = []
    for k18 in sorted(v9):
        ks19.append(k18)
    print(len(v9), sum(v9.values()), ','.join(ks19))
    print(p15.a, p15.b, p15.c, p15.name, len(p15.items))
    print(v16)
    print(len(v17), sum(v17))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-2 a,b,c AbCd
-84
192
7 7 0
True
8 8 0
hello
abab
hello
abab
hello
abab
hello
0.3888888888888889 0.5
False
False
False
False
     3.5
2 5 0.0025 a,b,c 0
32780 2519050
32780 2519050
32780 2519050
0 0 
96 89 3.0 a,b,c 0
3.5
6 162
```

AIL stdout, exit code 1:

```
-2 a,b,c AbCd
-84
192
7 7 0
True
8 8 0
hello
abab
hello
abab
hello
abab
hello
0.3888888888888889 0.5
```

AIL stderr:

```
TypeError: '<' not supported between instances of 'object' and 'object'
```

**What to do.**
1. Save the program as `/tmp/probes/fz241.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz241.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz241.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='False' ail='<end>'`.

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
