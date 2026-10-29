**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40949475519 (seed `2075520206`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 19: cpython='<end>' ail='2 2 0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075520206 -o prog.py`, if that tree has it).

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
    v1: int = ('Zed' + '12').find('ab'.strip())
    v2: str = '日本'.lower()[:-1]
    v3: list[int] = [1, 2, 3]
    print(26)
    if 'q q'.isdigit():
        v3.insert(-2, (b % (abs(a) + 1)))
    if ((123456.789 + 0.1) > (1.25 / (abs(3.0) + 1.0))):
        return (v1 // 6)
    return max(v3)


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 4 == 0:
            continue
        t += x
    return t


def main() -> int:
    pt0: Pt = Pt(0, 3, 3.0, '12', [])
    print(' pad ')
    v4: list[int] = list(range(3, 5, 2))
    v5: bytes = b"Zed"
    if ((not ((100.75 % 7.0) <= 3.0)) or (((11 + 14) <= (29 | 55)) or (98 <= 80))):
        v6: int = 3
        if ('Zed' in 'café'[1]):
            for i7 in range(0, 8, 2):
                print((((3.0 / (abs(0.5) + 1.0)) > max(0.3, 1e10)) and (not ((i7 + 14) > 3))))
                if (not ((i7 % (abs(-4) + 1)) < (82 // (abs(94) + 1)))):
                    break
                if (not ((99 - i7) == (v6 ** 0))):
                    continue
            if ((v6 + v6) == (v6 << 3)):
                v6 >>= 1
                print('hello')
            elif ('日本'.replace('l', '-').startswith('a')):
                print(('日本' + 'hello'), 0.3, ("%-4d|" % (v6 * 61)))
            p8: Pt = pt0
            p8.b = (11 + 61)
            print(pt0.a, pt0.b, p8.b, 4)
        elif (((-v6) < len(v5)) and (1.25 > (0.1 / (abs(123456.789) + 1.0)))):
            for i9 in range(3, 8, 1):
                try:
                    del v4[-2]
                except IndexError:
                    print(-34)
                print(('a,b,c'.replace(' ', '').endswith(' ')))
            for i10 in v4:
                print((round((0.5 + 7.0)) - v6))
                try:
                    if ((38 + i10) > 3):
                        raise AssertionError
                except AssertionError:
                    print(-70)
                finally:
                    print(192)
        pt0.a += (v6 % (abs(23) + 1))
    pt0.c += min(123456.789, 1e10)
    print((len(v4) // (abs((89 % (abs(40) + 1))) + 1)))
    if ((3 // 4) >= (95 - 21)):
        for i11 in v4:
            v5 = v5
            print((v5 + v5).decode())
            try:
                print(0)
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-87)
        try:
            v12: int = 0
            try:
                v12 = v4.index((66 ^ 9223372036854775807))
            except ValueError:
                print(-29)
        except ZeroDivisionError:
            v13: int = len(v5)
        except IndexError:
            try:
                if (('café' * 1) != ('Zed' * 0)):
                    pt0.a += (36 // 44)
            except ZeroDivisionError:
                print(-72)
        else:
            print(str((100.75 * 3.0)))
        al14: list[int] = v4
        al14.append(5)
        print(len(v4), len(al14), sum(v4) - sum(al14))
    print(('-7' in v5.decode()))
    v15: float = ((1e10 - 7.0) * (1e-7 - 123456.789))
    for i16 in range(4):
        for i17 in range(4):
            print(('日本' in str((-5 % (abs(-8) + 1)))))
            try:
                try:
                    v4.remove(len(v4))
                except ValueError:
                    print(-77)
            except ZeroDivisionError:
                al18: list[int] = v4
                v4.append(4)
                print(len(v4), len(al18), sum(v4) - sum(al18))
            else:
                if (int((1e-7 / i17)) < i16):
                    break
            v5 = v5
        try:
            for i19 in range(5, 1, -1):
                v20: int = 0
                try:
                    v20 = int('日本'.upper())
                except ValueError:
                    print(-94)
                if ((84 * 53) == (67 - 47)):
                    continue
                if (h0((11 % i16), max(i16, v20)) < max(i16, i16)):
                    continue
            try:
                print((h0(sum(v4), (i16 ** 2)) != 69), (v4.count((i16 - i16)) > 3))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-4)
        except ZeroDivisionError:
            w21: int = 0
            while w21 < 6:
                w21 += 1
                if (('x' + 'Zed') >= 'q q'):
                    continue
                print(v5.decode())
            for i22 in v4:
                if ((i16 * 66) > (i16 + 97)):
                    continue
        else:
            print(((76 & i16) > 3))
        print(min(47, 3037000499), 'café')
    try:
        print((((52 // (abs(61) + 1)) > 3) or ((15 // 7) <= (2 // 5))), ('AbCd' >= str(min(40, 9))))
    except ZeroDivisionError:
        print(-18)
    v4.insert(-2, 52)
    v23: list[int] = [(22 + 68), (71 * 0)]
    v24: set[int] = {3, 0, -4}
    al25: list[int] = v23
    v23.reverse()
    print(len(v23), len(al25), sum(v23) - sum(al25))
    if ('abc'.upper() >= str(min(11, 23))):
        v26: int = 0
        try:
            v26 = ((-7 // (abs(39) + 1)) % -9)
        except ZeroDivisionError:
            print(-55)
        try:
            if ((round((v15 / (abs(v15) + 1.0))) > (17 % (abs(v26) + 1))) or ((v26 >> 12) == min(70, 99))):
                raise IndexError('m1')
        except IndexError:
            print(-96)
        else:
            print(12)
        v24.update({-4})
    elif (((v15 / (abs(100.75) + 1.0)) < float(len(al25))) or (61 != (90 ** 3))):
        for i27 in v4:
            w28: int = 0
            while w28 < 1:
                w28 += 1
                v29: list[int] = [(i27 - w28), i27]
                v24.add((11 % (abs(6) + 1)))
            if (((95 * i27) == i27) or ((95 % (abs(12) + 1)) in v24)):
                continue
            if ((i27 << 6) == (90 % i27)):
                continue
    else:
        v30: int = (82 + (-8 - 63))
    try:
        if (((--1) == (80 - 53)) and (min(3037000499, 62) == (48 // 9223372036854775807))):
            assert ('AbCd'.upper() == f'{(32 + -9223372036854775807)}{(v15 + v15):.3f}'), "boom"
    except AssertionError:
        print(-84)
    else:
        print(36)
    finally:
        print(154)
    pt0.a += round(v15)
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v4), sum(v4))
    print(len(v5), v5.decode())
    print(v15)
    print(len(v23), sum(v23))
    print(len(v24), sum(v24), max(v24) if len(v24) > 0 else 0)
    print(len(al25), sum(al25))
    return 1


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
 pad 
-34
False
-34
False
-34
False
-34
False
-34
False
5
-70
192
0
False
False
-77
```

AIL stdout, exit code 0:

```
 pad 
-34
False
-34
False
-34
False
-34
False
-34
False
5
-70
192
0
False
False
-77
2 2 0
False
-77
False
-77
False
-77
-94
47 café
False
-77
3 3 0
False
-94
26
-94
26
-94
26
-94
26
26
True False
False
47 café
False
-77
3 3 0
False
-77
-94
26
-94
26
-94
26
-94
26
26
True False
False
47 café
False
-77
4 4 0
False
-94
26
-94
26
-94
26
-94
26
26
True False
False
47 café
False True
2 2 0
12
36
154
-1234567889134799 3 123459.789 12 0
4 64
3 Zed
-1234567889134802.5
2 90
3 -1 3
2 90
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz205.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz205.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz205.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='N N N'`.

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
