**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40883212738 (seed `2075517896`, CPython 3.12, modes default+ir) found a DIFF: `line 19: cpython='3.5' ail='-29'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075517896 -o prog.py`, if that tree has it).

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
    v1: int = ((36 - 81) - b)
    v2: str = 'AbCd'
    v3: list[int] = [round((123456.789 / (abs(0.1) + 1.0))), (-a)]
    try:
        v3[2] = (b + b)
    except IndexError:
        print(-29)
    v4: set[int] = set(v3)
    if (v2[-2:] < v2[1:4]):
        return v1
    return ord((v2 * 2)[0])


def main() -> int:
    pt0: Pt = Pt(6, 9, 1.25, 'a,b,c', [])
    v5: list[int] = []
    try:
        try:
            v6: int = ((-8 + -1) ^ abs(98))
        except ZeroDivisionError:
            try:
                v7: list[int] = []
                try:
                    v7 = [abs(19), (80 % -5), (47 + 58)]
                except ZeroDivisionError:
                    print(-41)
            except IndexError:
                pt0.items.append(61)
            finally:
                print(244)
            w8: int = 0
            while w8 < 5:
                w8 += 1
                v9: int = ('q q'.replace(' ', 'XY').find('abc') - 31)
        except KeyError:
            if '3.5'.isalpha():
                pt0.a = (91 - 74)
                v10: list[int] = list(range(-2, 9, 2))
            elif (not ((89 * 32) != (53 ** 2))):
                p11: Pt = Pt(0, 34, 1e10, '-7', [])
                al12: list[int] = v5
                if len(v5) > 0:
                    v5[0] = 4
                print(len(v5), len(al12), sum(v5) - sum(al12))
            else:
                pt0.items.append((4 // (abs(2) + 1)))
                try:
                    if (((55 << 2) > 3) or ((' pad ' * 2) < str(max(3037000499, 57)))):
                        raise AssertionError
                except AssertionError:
                    print(-2)
                else:
                    print(58)
                finally:
                    print(103)
            v5.append((97 >> 3))
    except KeyError:
        print('AbCd'.replace('l', ''), (1.25 * 1e10))
        p13: Pt = Pt(73, 59, 1e-7, 'AbCd', [])
    al14: list[int] = v5
    if len(al14) > 0:
        al14[0] = 3
    print(len(v5), len(al14), sum(v5) - sum(al14))
    print(89)
    for i15 in range(4):
        v16: list[int] = []
        for i17 in range(4):
            v18: str = 'AbCd'.rstrip()
            v19: str = ""
            try:
                v19 = (("<%5d>" % h0(round(abs(123456.789)), (~-1))) + '-'.join('q q'.split(',')))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-56)
            v16.append(44)
    try:
        if '日本'.isdigit():
            raise IndexError('m6')
    except IndexError:
        print(-30)
    print('3.5')
    al20: list[int] = al14
    al14.append(9)
    print(len(al14), len(al20), sum(al14) - sum(al20))
    al21: list[int] = al14
    if len(al21) > 0:
        al21[0] = 0
    print(len(al14), len(al21), sum(al14) - sum(al21))
    try:
        print(((17 % -6) - (69 ** 2)))
    except ZeroDivisionError:
        print(-31)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v5), sum(v5))
    print(len(al14), sum(al14))
    print(len(al20), sum(al20))
    print(len(al21), sum(al21))
    return 7


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 7:

```
0 0 0
89
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
3.5
1 1 0
1 1 0
-4762
6 9 1.25 a,b,c 0
1 0
1 0
1 0
1 0
```

AIL stdout, exit code 7:

```
0 0 0
89
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
-29
3.5
1 1 0
1 1 0
-4762
6 9 1.25 a,b,c 0
1 0
1 0
1 0
1 0
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz203.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz203.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz203.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N.N' ail='-N'`.

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
