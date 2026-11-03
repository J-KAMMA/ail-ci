**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41706060840 (seed `2076020658`, CPython 3.12, modes default+ir) found a DIFF: `line 6: cpython='181' ail='False'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076020658 -o prog.py`, if that tree has it).

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


def h0(a: int, b: int) -> int:
    v1: int = ((255 % (abs(a) + 1)) - (a + b))
    v2: str = '12'
    v3: list[int] = [-3] * 5
    print(((sum(v3) > 3) or (len(v2) < (b // (abs(45) + 1)))))
    p4: Pt = Pt(98, b, 0.1, v2, [])
    try:
        print(v1)
        v3 += v3
    except IndexError:
        v5: list[int] = list(range(3, 11, 1))
    except KeyError:
        w6: int = 0
        while w6 < 3:
            w6 += 1
            if (((b + a) <= (a // (abs(55) + 1))) and ((a + w6) <= (96 - a))):
                break
            print(int((1e-7 // 3.0)))
            print(bump(p4, (92 * 51)))
        w7: int = 0
        while w7 < 4:
            w7 += 1
            v3 += [(6 - 95), len(v2)]
    else:
        v8: str = ""
        try:
            v8 = str((a // 6))
        except ZeroDivisionError:
            print(-57)
        if (b >= int((1e10 + 7.0))):
            try:
                print(((79 + b) - int(float((a % 3)))))
            except ZeroDivisionError:
                print(-81)
            finally:
                print(152)
            p9: Pt = Pt(b, v1, 0.5, '-7', [])
        else:
            v3.sort(key=lambda q: (-q, q))
            p4.name += 'q q'.lower()
    if ((a * b) == b):
        return v1
    return (a - (v1 // (abs(b) + 1)))


def main() -> int:
    pt0: Pt = Pt(1, 8, 1.25, '日本', [])
    print((-1 * (-1 // (abs(4611686018427387904) + 1))))
    for i10 in range(2):
        v11: str = 'café'
        pt0.name += str(0.5)
    print((47 // (abs(-1) + 1)))
    p12: Pt = pt0
    p12.b = (1 - 83)
    print(pt0.a, pt0.b, p12.b, 1)
    v13: str = ""
    try:
        v13 = (("%-4d|" % (69 ** 3)) + f'{h0((98 * 56), -2)}{('3.5' + '12').find('3.5'):<4}#')
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-53)
    finally:
        print(181)
    if (((123456.789 + 0.1) < 2.5e-3) or ((19 * 26) == (-1 ^ 76))):
        w14: int = 0
        while w14 < 3:
            w14 += 1
            try:
                v15: list[int] = [(0 * w14)]
            except KeyError:
                v16: list[int] = [0] * 4
            except IndexError:
                print(((w14 // (abs(54) + 1)) % -4))
            finally:
                print(292)
            v17: bytes = b"abc"
        v18: set[int] = set()
    v19: float = 0.0
    try:
        v19 = (((0 | 66) / 8) / (34 ** 0))
    except ZeroDivisionError:
        print(-61)
    v20: int = (-(49 // (abs(23) + 1)))
    v21: list[int] = [-1] * 5
    print(round((abs(2.5e-3) ** 0.5)))
    v21.extend([(-5 - 98)])
    print(('ab' + '日本').strip())
    al22: list[int] = v21
    if len(v21) > 0:
        v21[0] = 4
    print(len(v21), len(al22), sum(v21) - sum(al22))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(p12.a, p12.b, p12.c, p12.name, len(p12.items))
    print(v13)
    print(v19)
    print(v20)
    print(len(v21), sum(v21))
    print(len(al22), sum(al22))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
1
23
1 -82 -82 1
False
-5231
181
0
ab日本
6 6 0
1 -82 1.25 日本0.50.5 0
1 -82 1.25 日本0.50.5 0
328509|72320   #
8.25
-2
6 -103
6 -103
```

AIL stdout, exit code 0:

```
1
23
1 -82 -82 1
False
-5231
False
-5231
181
0
ab日本
6 6 0
1 -82 1.25 日本0.50.5 0
1 -82 1.25 日本0.50.5 0
328509|72320   #
8.25
-2
6 -103
6 -103
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz224.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz224.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz224.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='False'`.

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
