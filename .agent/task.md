**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41902054682 (seed `2076120347`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 15: cpython='6 63 10000000000.0 12 1' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076120347 -o prog.py`, if that tree has it).

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
        if t > 36:
            break
        t += abs(x) + 1
    return t


def main() -> int:
    pt0: Pt = Pt(6, 7, 1e10, '12', [])
    print(pt0.name, sum(pt0.items))
    print(((42 * 38) * round(((~36) / 3))))
    w1: int = 0
    while w1 < 6:
        w1 += 1
        for i2 in range(0):
            try:
                if ((0.1 / (abs(7.0) + 1.0)) > (3.0 / (abs(2.5e-3) + 1.0))):
                    raise IndexError('m0')
            except IndexError:
                print(-13)
            v3: bytes = b"12"[:]
    if ((((25 * 65) > int(0.5)) and (1 >= 44)) or (not (float(abs(255)) == (0.5 * 3.0)))):
        w4: int = 0
        while w4 < 3:
            w4 += 1
            try:
                print(((str(1) != 'AbCd') and ((92 >= 67) or ((w4 // -9) >= w4))))
            except ZeroDivisionError:
                print(-68)
            v5: float = (float(w4) % 7.0)
        print(0.1, ('日本' * 1))
        w6: int = 0
        while w6 < 5:
            w6 += 1
            v7: int = max(w6, w6)
            v8: str = ""
            try:
                v8 = ('12' + ("%03d" % (w6 % -6)))
            except ZeroDivisionError:
                print(-35)
            v10: list[int] = [12 for c9 in range(5) if c9 % 2 == 1]
    try:
        print(max((-1 - 91), (28 % 8)))
    except ZeroDivisionError:
        print(-26)
    p11: Pt = pt0
    pt0.b = (20 + 43)
    print(pt0.a, pt0.b, p11.b, 2)
    v12: list[int] = []
    try:
        v12 = [abs(96), 27, (62 % 4611686018427387904), 0]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-62)
    if (round(abs(0.3)) > (-1 // -9)):
        print(b"12"[:2].decode())
        v13: float = 0.3
        v14: float = v13
    v15: str = f'{(32 % (abs(5) + 1)):3d}{min(7.0, 0.1)}{int(abs(0.5)):>6}'
    pt0.items.append(-3)
    print(max(abs(43), (56 // (abs(255) + 1))))
    v16: int = ((10 * 40) - (98 + 8))
    for i17 in range(4):
        w18: int = 0
        while w18 < 4:
            w18 += 1
            v12 += v12
        w19: int = 0
        while w19 < 4:
            w19 += 1
            if ((' pad ' in ('x' * 0)) or ('café' != f'{'Zed':^9}')):
                if ((w19 & 78) > 3):
                    continue
                v20: dict[str, int] = {}
                v20['b'] = 37
                v20['c'] = 88
            else:
                print(float(len(v15)))
                try:
                    if (v15 in 'ab'):
                        assert (not ((i17 - w19) >= (i17 ^ v16))), "boom"
                except (AssertionError, KeyError):
                    print(-32)
            try:
                v12[2] = i17
            except IndexError:
                print(-69)
    v16 %= (abs((67 * v16)) + 1)
    print(((1.25 + 100.75) * (0.5 + 0.5)))
    try:
        print(((0.5 * 100.75) % 0.75))
        try:
            print(v12.pop())
        except IndexError:
            print(-3)
        print(((len('AbCd'[:-1]) > v16) and (f'{(0 + v16)}' != '-'.join(v15.split(',')))))
    except KeyError:
        try:
            for i21 in v15:
                print(v16)
                print((37 - 5))
                v12 += v12
        except IndexError:
            v15 += v15
        except ValueError:
            try:
                if (str(abs(92)).startswith('a')):
                    v22: set[int] = set(v12)
                elif ((v16 | 5) != int((v15 * 2))):
                    al23: list[int] = v12
                    if len(v12) > 0:
                        v12[0] = 4
                    print(len(v12), len(al23), sum(v12) - sum(al23))
                    try:
                        if (v15[2] != f'{(123456.789 + 123456.789):8.3f}{(3.0 + 1e-7):8.3f}{(54 + v16)}'):
                            assert ((v16 % -6) > 3), "boom"
                    except (AssertionError, ValueError):
                        print(-82)
                    else:
                        print(67)
            except (IndexError, ZeroDivisionError):
                print(-95)
        finally:
            print(291)
        v24: list[int] = sorted(v12)
    finally:
        print(251)
    try:
        v16 = ((91 // (abs(12) + 1)) // (abs(h0(v12)) + 1))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-30)
    w25: int = 0
    while w25 < 6:
        w25 += 1
        for i26 in range(6):
            v12.sort(key=lambda q: (-q, q))
            try:
                if (len(v12) == (i26 * i26)):
                    raise RuntimeError('m0')
            except (RuntimeError, ValueError):
                print(-95)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(p11.a, p11.b, p11.c, p11.name, len(p11.items))
    print(len(v12), sum(v12))
    print(v15)
    print(v16)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
12 0
-19152
True
True
True
0.1 日本
4
6 63 63 2
43
102.0
0.125
0
False
251
6 63 10000000000.0 12 1
6 63 10000000000.0 12 1
262143 11870481
  20.1     0
0
```

AIL stdout, exit code 1:

```
12 0
-19152
True
True
True
0.1 日本
4
6 63 63 2
43
102.0
0.125
0
False
251
```

AIL stderr:

```
TypeError: '<' not supported between instances of 'object' and 'int'
```

**What to do.**
1. Save the program as `/tmp/probes/fz228.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz228.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz228.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N N N.N N N' ail='<end>'`.

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
