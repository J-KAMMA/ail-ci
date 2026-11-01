**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41256273310 (seed `2075800891`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 21: cpython='2.4999999998e+19' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075800891 -o prog.py`, if that tree has it).

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
    v1: int = 0
    try:
        v1 = ord(('x' + 'AbCd')[1])
    except IndexError:
        print(-8)
    v2: str = f'{'3.5':>8}{(a ** 3)}{(70 + v1):^7}'.strip()
    v3: list[int] = [-3] * 5
    try:
        print(((v1 // -1) * (45 - 82)))
    except ZeroDivisionError:
        print(-12)
    if ('3.5'.upper().endswith('d')):
        return v1
    return (len(v2) ^ (2 - -4))


def h1(a: int, b: int) -> int:
    v4: int = min(a, (76 & b))
    v5: str = f' = '
    v6: list[int] = [(64 + -7), (a ** 1), abs(a)]
    try:
        a //= (abs(a) + 1)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-26)
    v7: bool = False
    try:
        v7 = (not (v5 in v5[3]))
    except IndexError:
        print(-52)
    if (b > (b + b)):
        return ord(v5.replace('a', '')[3])
    return (h0(b, (v4 - a)) | (a & 12))


def h2(a: int, b: int) -> int:
    v8: int = a
    v9: str = ("%d" % max(v8, 9))
    v10: list[int] = [1, 2, 3]
    v11: str = '日本'[:]
    try:
        v10.insert(0, v10.count((60 % a)))
    except ZeroDivisionError:
        print(-39)
    try:
        print('-7'[0])
    except IndexError:
        print(-90)
    if (len(v11) > 3):
        return 61
    return (v8 * (v8 * v8))


def main() -> int:
    pt0: Pt = Pt(5, 7, 100.75, 'x', [])
    print((31 + 40))
    print(bump(pt0, 23))
    if (69 > round((0.1 * 0.3))):
        print((2 / 8), 43)
        try:
            print(('Zed' * 1).lower())
            v12: list[int] = []
        except ZeroDivisionError:
            v13: list[int] = list(range(-2, 10, 1))
            try:
                print(((1e-7 / sum(v13)) * (2.5e-3 // 2.5)))
            except ZeroDivisionError:
                print(-11)
        except KeyError:
            print((float((9223372036854775807 - -9223372036854775807)) - (100.75 / (52 + 62))))
            print(1e10)
        else:
            v14: list[int] = []
            try:
                v14 = [(57 * 29), 7, h1(25, (-1 + 0))]
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-62)
            v14.sort()
    elif (str((3.0 % 0.75)) < f'-'):
        p15: Pt = Pt(23, 94, 7.0, 'hello', [])
    else:
        v16: list[int] = [5, (54 // (abs(37) + 1)), 27, (9223372036854775807 + 42), 97]
        pt0.a -= len(v16)
    p17: Pt = Pt(23, 16, 1e-7, '日本', [])
    v18: dict[str, int] = {}
    v18['dd'] = 31
    v18['c'] = 79
    v18['dd'] = 46
    v18['b'] = 83
    v18['日本'] = abs(0)
    v19: float = ((1e10 - 0.5) * (1e10 - 0.3))
    w20: int = 0
    while w20 < 6:
        w20 += 1
        p17.c += (v19 / (abs(v19) + 1.0))
        for i21 in range(3):
            try:
                if (str((i21 % (abs(-7) + 1))) != ('AbCd' + 'hello')):
                    assert (('AbCd' in 'ab'[0]) or (((18 * i21) / 8) <= v19)), "boom"
            except AssertionError:
                print(-41)
            try:
                if ('12' in '-7'):
                    continue
                p17.a -= (i21 % 9)
                v18.pop('a', 6)
            except ValueError:
                if (7.0 < (1e10 + 3.0)):
                    continue
                if ((3 ** 0) <= (21 + 74)):
                    continue
            except KeyError:
                v22: str = '-'.join(str((i21 + w20)).split('a'))
                try:
                    print(((7.0 / (w20 // -5)) / (abs((0.5 * v19)) + 1.0)))
                except ZeroDivisionError:
                    print(-79)
            else:
                try:
                    v18.pop('dd')
                except KeyError:
                    print(-95)
                finally:
                    print(145)
                try:
                    print(((v19 - 100.75) / (25 + i21)))
                except ZeroDivisionError:
                    print(-93)
                finally:
                    print(154)
            finally:
                print(207)
        print(((round(v19) / 4) + (v19 - v19)))
    for i23 in range(3, 14, 1):
        print(1.25)
        for i24 in range(5):
            try:
                if ('AbCd' in v18):
                    break
                if (((v19 + 0.3) == (v19 * v19)) and (i24 > (i24 % (abs(i24) + 1)))):
                    break
            except KeyError:
                print((b"a,b" + b"Zed").decode())
            finally:
                print(290)
            p17.items.append(round((v19 * v19)))
            v25: list[int] = []
        v26: str = f'{'ab':>8}'[-2:4]
    print((f'{(61 ** 0):>6}/ = ' < ('Zed' + 'AbCd')))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(p17.a, p17.b, p17.c, p17.name, len(p17.items))
    ks28: list[str] = []
    for k27 in sorted(v18):
        ks28.append(k27)
    print(len(v18), sum(v18.values()), ','.join(ks28))
    print(v19)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
71
29
0.25 43
zed
-52
-62
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
-95
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
-95
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
-95
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
-95
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
-95
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
2.4999999998e+19
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
1.25
290
290
290
290
290
True
28 7 100.75 x 1
5 16 6.0000001 日本 55
3 162 b,c,日本
9.9999999992e+19
```

AIL stdout, exit code 1:

```
71
29
0.25 43
zed
-52
-62
145
3.99999999968e+18
154
207
-95
145
3.846153845846154e+18
154
207
-95
145
3.7037037034074076e+18
154
207
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz209.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz209.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz209.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N.Ne+N' ail='<end>'`.

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
