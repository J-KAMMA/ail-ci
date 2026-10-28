**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40687999220 (seed `2075412095`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 10: cpython='<end>' ail='abca,b'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075412095 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 9 + 4) % 74003
    return (h0(n - 1, a + 3) * 4 + h0(n - 1, a - 0) + n) % 74003


def h1(a: int, b: int) -> int:
    v1: int = (a - 42)
    v2: str = 'abc'[0:-1]
    v3: list[int] = list(range(-3, 9, 3))
    al4: list[int] = v3
    al4.reverse()
    print(len(v3), len(al4), sum(v3) - sum(al4))
    w5: int = 0
    while w5 < 3:
        w5 += 1
        try:
            v3.extend([(a // a)])
        except ZeroDivisionError:
            print(-84)
        for i6 in v2:
            if ((a - w5) >= int((100.75 / (79 // 99)))):
                break
    for i7 in v2:
        print(i7)
        for i8 in v3:
            v9: bytes = b"hello"[1:2]
            if ((39 > 3) and (82 < 8)):
                break
        v10: list[int] = list(range(3, 4, 1))
    if v2.isupper():
        return len(v2)
    return ((a + a) // (abs((64 * 97)) + 1))


def main() -> int:
    if (((80 << 5) <= 89) and (58 == (69 // (abs(0) + 1)))):
        print(('x' + 'Zed'), (abs(100.75) ** 0.5))
        print(((4611686018427387904 >> 1) < (~255)))
        print((47 | 5), (78 * 36))
    elif ('AbCd'.endswith('d')):
        print(((74 | 94) > -5))
        print((' pad ' * 1))
    try:
        if ((77 - 6) > 3):
            raise RuntimeError('m1')
    except RuntimeError:
        print(-2)
    v11: list[int] = [80, (82 + 41), (85 * 28)]
    v12: float = ((abs(100.75) ** 0.5) / (abs(abs(100.75)) + 1.0))
    try:
        v11.insert(0, max(v11))
    except ValueError:
        print(-45)
    try:
        try:
            al13: list[int] = v11
            v11.append(4)
            print(len(v11), len(al13), sum(v11) - sum(al13))
            print(f'{(v12 * v12):.3f}{(7.0 * 7.0)}{float((59 << 8)):.3f}')
        except ZeroDivisionError:
            for i14 in v11:
                v16: list[int] = [(40 % (abs(c15) + 1)) for c15 in range(0) if c15 % 2 == 1]
                if ((len(v16) <= (i14 ** 2)) or 'x'.isalpha()):
                    break
            v12 = 123456.789
        except ValueError:
            v17: list[int] = list(range(1, 11, 1))
        else:
            print(max(float((-7 + 35)), abs(v12)))
        finally:
            print(221)
    except IndexError:
        v11.sort(key=lambda q: (-q, q))
        print((b"abc" + b"a,b").decode())
    except ValueError:
        for i18 in range(4):
            v11 += v11
            if (min(9, i18) < max(i18, i18)):
                try:
                    if ((i18 >> 7) == v11.pop()):
                        raise RuntimeError
                except RuntimeError:
                    print(-43)
                else:
                    print(69)
                v19: float = ((v12 + 1e-7) / (abs((v12 % 2.5)) + 1.0))
                v20: set[int] = {11, 7, -4, 12}
            elif ((v12 / (abs(v12) + 1.0)) < (v12 + v12)):
                v21: int = 25
            else:
                if (not ('3.5' in '3.5')):
                    continue
            v22: set[int] = set(v11)
    else:
        try:
            print(len(v11))
        except IndexError:
            print(-91)
        finally:
            print(125)
        if ('x'[3] < '3.5'[0]):
            try:
                print(sum(v11))
            except IndexError:
                print(-33)
            try:
                v11.append((3037000499 + 4611686018427387904))
                v23: str = str(92)
            except ZeroDivisionError:
                print('-7')
                v24: float = ((abs(0.3) ** 0.5) / (abs((abs(1.25) ** 0.5)) + 1.0))
        elif (('abc' != f'{'日本':>8}{(9223372036854775807 - 27):<4}') or ((38 // (abs(11) + 1)) <= (88 << 7))):
            w25: int = 0
            while w25 < 3:
                w25 += 1
                try:
                    print(("<%5d>" % (17 // 1)))
                except ZeroDivisionError:
                    print(-33)
    try:
        try:
            print(((58 + 2) - v11.pop()))
        except IndexError:
            print(-82)
        v26: list[str] = ['3.5', 'ab', 'café', 'AbCd']
        try:
            if (38 > 3):
                raise AssertionError('m5')
        except AssertionError:
            print(-70)
        else:
            print(71)
    except ZeroDivisionError:
        try:
            v11.pop()
        except IndexError:
            print(-26)
        finally:
            print(167)
    finally:
        print(297)
    for i27 in v11:
        v28: list[int] = []
        try:
            v28 = [i27, (i27 - i27), (51 % i27), i27, round((v12 / (abs(1e10) + 1.0)))]
        except ZeroDivisionError:
            print(-3)
        w29: int = 0
        while w29 < 5:
            w29 += 1
            if ('q q' in ('abc' + 'abc')):
                if ('x' in b"Zed".decode()):
                    continue
                al30: list[int] = v28
                if len(al30) > 0:
                    al30[0] = 4
                print(len(v28), len(al30), sum(v28) - sum(al30))
                v31: bool = (' pad '.replace(' ', '-') != ('Zed' + '3.5'))
            else:
                if (('Zed' >= ('x' + 'café')) and ((94 << 2) < round((v12 - 100.75)))):
                    continue
    print(len(v11), sum(v11))
    print(v12)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
True
 pad 
-2
5 5 0
0.01049.015104.000
28.0
221
5
125
```

AIL stdout, exit code 0:

```
True
 pad 
-2
5 5 0
0.01049.015104.000
28.0
221
5
125
abca,b
56
-70
297
4 4963
0.09864796019599377
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz197.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz197.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz197.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='abca,b'`.

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
