**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41706060840 (seed `2076019464`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 11: cpython='<end>' ail='6 7 7.0 x 0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076019464 -o prog.py`, if that tree has it).

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


def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 22:
            break
        t += abs(x) + 1
    return t


def main() -> int:
    pt0: Pt = Pt(6, 7, 7.0, 'x', [])
    v1: list[int] = [(27 + 1)]
    v2: bool = False
    try:
        v2 = ((68 % 1) >= (24 ** 0))
    except ZeroDivisionError:
        print(-28)
    try:
        try:
            print(min(v1))
        except ValueError:
            print(-4)
    except KeyError:
        try:
            v1.insert(0, (57 // -6))
        except ZeroDivisionError:
            print(-86)
        for i3 in range(4):
            pt0.items.append((i3 + i3))
            v4: float = (3.0 + (1e-7 / (abs(3.0) + 1.0)))
    for i5 in range(0, 5):
        print(str(3.0))
    print((b"x" + b"a,b").decode())
    v6: bool = ('ab' in '12')
    print('Zed')
    try:
        print(((42 | 58) // 1))
    except ZeroDivisionError:
        print(-67)
    try:
        al7: list[int] = v1
        v1.append(9)
        print(len(v1), len(al7), sum(v1) - sum(al7))
        v2 = ((67 + 32) == (20 >> 5))
    except ZeroDivisionError:
        v8: str = f'{'-7'}'
    except IndexError:
        v9: str = '-'.join('12'.split('a'))
    else:
        for i10 in range(2):
            if ('x' == ('-7' * 0)):
                if (((i10 // (abs(i10) + 1)) >= 28) or ((74 + i10) <= (i10 | i10))):
                    break
                v11: str = ('Zed' + ' pad ').lstrip()
            elif (((i10 // i10) <= (i10 % -5)) and ((i10 // 5) > (75 // (abs(i10) + 1)))):
                v12: int = ((64 ** 0) ** 0)
            try:
                if (h0(v1) <= (37 - i10)):
                    raise KeyError
            except KeyError:
                print(-55)
            finally:
                print(103)
    v6 = (max(9, 47) < v1.count((40 % (abs(51) + 1))))
    v13: list[int] = [(85 // (abs(83) + 1)), (44 // (abs(0) + 1)), (7 + 81)]
    v13 += v1
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v1), sum(v1))
    print(v2)
    print(v6)
    print(len(v13), sum(v13))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
28
3.0
3.0
3.0
3.0
3.0
xa,b
Zed
58
2 2 0
```

AIL stdout, exit code 0:

```
28
3.0
3.0
3.0
3.0
3.0
xa,b
Zed
58
2 2 0
6 7 7.0 x 0
2 37
False
False
5 170
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz223.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz223.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz223.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='N N N.N x N'`.

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
