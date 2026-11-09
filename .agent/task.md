**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42544036372 (seed `2076601581`, CPython 3.12, modes default+ir) found a DIFF: `line 9: cpython='14551915228366852444681616108227133440' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076601581 -o prog.py`, if that tree has it).

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
    v1: int = len('hello'.upper())
    v2: str = b"12".decode()[0:]
    v3: list[int] = []
    try:
        v3 = [int('hello')]
    except ValueError:
        print(-65)
    finally:
        print(198)
    p4: Pt = Pt(2, a, 123456.789, v2, [])
    if ((ord(('x' + v2)[0]) >= len(v3)) and ((b + 4611686018427387904) <= (a >> 7))):
        return -1
    return ((1 & 12) + (99 & b))


def h1(a: int, b: int) -> int:
    v5: int = round((1.25 * 0.3))
    v6: str = '日本'[1:2].upper()
    v7: list[int] = list(range(1, 9, 2))
    v8: list[int] = [(b * 95), int((100.75 + 1e10)), v7[h0(v6.find('café'), len(v7))], (72 << 11), -4]
    v9: str = ""
    try:
        v9 = (("%-4d|" % (1 // b)) * 1)
    except ZeroDivisionError:
        print(-96)
    v10: int = 12
    if ('-'.join(v9.split('a')) != v6.replace('l', 'XY')):
        return (v5 % (abs(a) + 1))
    return (str((v5 + a)).find('ab') // -7)


def h2(a: int, b: int) -> int:
    v11: int = (-9223372036854775807 + b)
    v12: str = f'{(b - b):d}{(1e-7 % 0.75):.0f}'
    v13: list[int] = [1, 2, 3]
    for i14 in range(3, 9, 1):
        for i15 in range(9, -2, -1):
            print(int((7.0 * 2.5e-3)))
            if (a != i15):
                break
        for i16 in v13:
            if (i14 >= max(45, i16)):
                break
            if (((i14 << 10) <= (a + v11)) or (b <= min(35, b))):
                break
            if (str((-6 - 64)) >= b"ab".decode()):
                break
    v17: list[int] = list(range(2, 12, 1))
    if (b"Zed".decode() < v12[0]):
        v18: list[int] = []
        try:
            v18 = [v11, (v11 - b), (a // -8)]
        except ZeroDivisionError:
            print(-33)
        v19: set[int] = set(v18)
    else:
        try:
            print(round(float((v11 % 86))))
        except (IndexError, ZeroDivisionError):
            print(-73)
        v13.append((b + v11))
    if (f'{(0.5 + 2.5e-3):>10.1f}{v12:<6}{'a,b,c':<6}' < b"x".decode()):
        return min(43, a)
    return int((abs(100.75) ** 0.5))


def main() -> int:
    pt0: Pt = Pt(8, 8, 0.3, 'abc', [])
    v20: dict[str, int] = {}
    v20['dd'] = 22
    v21: list[str] = 'ab'.rstrip().split(' ')
    v22: str = f'#'
    v21.append((v22 * 0))
    print(('日本' + '-7'), (('3.5'.upper() >= v22.replace(' ', '')) or ('日本' in v20)))
    v23: float = 0.0
    try:
        v23 = ((1.25 * 1.25) * (1e10 / (39 % -5)))
    except ZeroDivisionError:
        print(-79)
    finally:
        print(198)
    w24: int = 0
    while w24 < 4:
        w24 += 1
        try:
            print(len(v21))
        except ZeroDivisionError:
            print(-62)
        pt0.name += (v22 + '-7')
        if ((w24 << 4) > (~w24)):
            break
    try:
        if ('x' in v22[0:4]):
            raise AssertionError
    except AssertionError:
        print(-2)
    finally:
        print(141)
    w25: int = 0
    while w25 < 2:
        w25 += 1
        w26: int = 0
        while w26 < 1:
            w26 += 1
            w27: int = 0
            while w27 < 1:
                w27 += 1
                p28: Pt = Pt(50, w26, 3.0, v22, [])
            v23 *= (v22.find(('ab' + '日本')) / 4)
        try:
            if (not (v22 in f'{(abs(v23) ** 0.5)}')):
                v23 *= v23
                v20.pop('b', 6)
            else:
                v20[v22] = (w25 + 52)
        except IndexError:
            try:
                print((w25 & (74 // 1)))
            except ZeroDivisionError:
                print(-7)
        except ZeroDivisionError:
            v29: list[int] = [1, 2, 3]
            try:
                print(((33 ** 2) ** 2))
            except ZeroDivisionError:
                print(-25)
        finally:
            print(258)
        print((~w25))
    print(round(v23))
    for i30 in range(2):
        v31: set[int] = {-1, 3, 0, 0}
        if (((i30 + i30) > (i30 - i30)) and ((v23 * 0.3) == max(v23, v23))):
            v32: int = 'a,b,c'.count('b')
            v33: str = (f'{i30}' + (v22 * 2))
        else:
            v34: float = abs((0.5 + 7.0))
        v21.reverse()
    print(1e10)
    del v20['b']
    for i35 in range(2, 9, 3):
        try:
            v21.reverse()
        except IndexError:
            print(-46)
        try:
            v36: set[int] = set()
            w37: int = 0
            while w37 < 6:
                w37 += 1
                if (((56 - i35) <= i35) or ('-7'.startswith('he'))):
                    break
            if (i35 < (i35 // (abs(96) + 1))):
                break
        except ValueError:
            v20[v22] = 75
        except ZeroDivisionError:
            v38: list[str] = v22.split('a')
            v39: list[str] = []
        w40: int = 0
        while w40 < 2:
            w40 += 1
            try:
                print(float(int(str(94))))
            except ValueError:
                print(-96)
            v41: str = b"Zed".decode()
    v22 = f'{float(int(max(2.5e-3, v23)))}{'AbCd':<6}{(86 ** 0):05d}'
    try:
        print(h1(h2((92 % (abs(95) + 1)), len(v20)), (-1 - -6)), 1.25)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-37)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    ks43: list[str] = []
    for k42 in sorted(v20):
        ks43.append(k42)
    print(len(v20), sum(v20.values()), ','.join(ks43))
    print(len(v21), ','.join(v21))
    print(v22)
    print(v23)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
日本-7 True
198
2
141
258
-2
258
-3
14551915228366852444681616108227133440
10000000000.0
```

AIL stdout, exit code 1:

```
日本-7 True
198
2
141
258
-2
258
-3
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz245.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz245.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz245.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='<end>'`.

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
