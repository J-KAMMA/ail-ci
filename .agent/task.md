**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41356299474 (seed `2075823824`, CPython 3.12, modes default+ir) found a DIFF: `line 1: cpython='-81' ail='182'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075823824 -o prog.py`, if that tree has it).

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
    v1: int = (85 // (abs(b) + 1))
    v2: str = f'{'Zed':^9}'
    v4: list[int] = [(49 << 6) for c3 in range(6) if c3 % 2 == 0]
    try:
        p5: Pt = Pt(a, 36, 123456.789, v2, [])
    except ZeroDivisionError:
        for i6 in v2:
            a = int(abs(123456.789))
    except ValueError:
        v4.reverse()
    else:
        v4.remove(b)
    if (b > 3):
        try:
            v4[2] = (89 % -7)
        except (IndexError, ZeroDivisionError):
            print(-50)
    elif (v2 in ('café' + v2)):
        p7: Pt = Pt(a, 88, 1e-7, v2, [])
    else:
        v4.append((v1 * 76))
    if (f'-'.endswith(' ')):
        return (b + a)
    return b


def h1(a: int, b: int) -> int:
    v8: int = (b - (59 >> 11))
    v9: str = ""
    try:
        v9 = b"abc".decode()
    except IndexError:
        print(-67)
    finally:
        print(182)
    v10: list[int] = []
    v10.extend([(~a), (b ** 1), v8])
    if 'Zed'.islower():
        return (~-3)
    return 54


def h2(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 5) % 9003
    return (h2(n - 1, (a * 4 + n) % 9003) + 9) % 9003


def main() -> int:
    pt0: Pt = Pt(3, 4, 2.5e-3, 'café', [])
    v11: int = 0
    try:
        v11 = (h1(h0((44 + 78), (56 - -1)), (85 % 7)) + abs(88))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-81)
    try:
        v11 += (v11 + 81)
    except IndexError:
        print(('café' + '日本').lstrip())
        try:
            v11 %= (abs((56 % -6)) + 1)
        except ZeroDivisionError:
            print(-9)
    finally:
        print(252)
    try:
        print(('a,b,c'[0:] + '-7'))
        pt0.items.append(3)
        v13: list[int] = [min(v11, 255) for c12 in range(5) if c12 % 2 == 0]
    except KeyError:
        v11 = ((84 % (abs(v11) + 1)) + (v11 ^ 90))
    else:
        v14: float = ((0.3 + 123456.789) / (abs(0.3) + 1.0))
    finally:
        print(215)
    v15: str = (b"x".decode() + 'Zed'[:-1])
    try:
        print(((0.5 % 7.0) / 30))
    except ZeroDivisionError:
        print(-63)
    finally:
        print(118)
    v16: list[int] = [(v11 << 8), (v11 - v11), (v11 - v11)]
    print((v15 + v15))
    al17: list[int] = v16
    if len(al17) > 0:
        al17[0] = 5
    print(len(v16), len(al17), sum(v16) - sum(al17))
    if (v11 <= (v11 ** 1)):
        for i18 in al17:
            for i19 in range(0, 3):
                if (((i18 % (abs(v11) + 1)) == (54 // (abs(i18) + 1))) or ((-1 % 7) > (i19 - v11))):
                    continue
                if ((v11 + i18) > 3):
                    continue
                print(len(v15))
            if (not (max(1e-7, 123456.789) < 1.25)):
                break
    elif (v15.upper().endswith('a')):
        v16.append((84 + v11))
        try:
            print((7.0 / len(v16)))
        except ZeroDivisionError:
            print(-31)
    else:
        v20: str = f'{100.75} = {(-4 * v11)}'
        print(f'{float(round((abs(0.3) ** 0.5))):.2f}')
    al17.insert(1, len(al17))
    al21: list[int] = al17
    al21 += [4]
    print(len(al17), len(al21), sum(al17) - sum(al21))
    w22: int = 0
    while w22 < 6:
        w22 += 1
        al17.reverse()
        if ((55 // 7) > (v11 % 5)):
            print(len(al17))
        elif (("%-4d|" % 77) < '3.5'.upper()):
            print((v15 in v15[0:2]))
    print('3.5')
    v23: int = 0
    try:
        v23 = ((v11 // 2) | abs(30))
    except ZeroDivisionError:
        print(-80)
    try:
        v23 = sum(v16)
    except ZeroDivisionError:
        print(-61)
    print(((3.0 / (abs(1.25) + 1.0)) / (abs((123456.789 % 2.5)) + 1.0)))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(v11)
    print(v15)
    print(len(v16), sum(v16))
    print(len(al17), sum(al17))
    print(len(al21), sum(al21))
    print(v23)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-81
252
a,b,c-7
215
0.016666666666666666
118
xZexZe
3 3 0
5 5 0
5
5
5
5
5
5
3.5
0.47806860284376984
3 4 0.0025 café 1
81
xZe
5 12
5 12
5 12
12
```

AIL stdout, exit code 0:

```
182
252
a,b,c-7
215
0.016666666666666666
118
xZexZe
3 3 0
5 5 0
5
5
5
5
5
5
3.5
0.47806860284376984
3 4 0.0025 café 1
365
xZe
5 12
5 12
5 12
12
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz214.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz214.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz214.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='-N' ail='N'`.

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
