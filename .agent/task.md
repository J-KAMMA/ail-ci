**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40298776404 (seed `2075200054`, CPython 3.12, modes default+ir) found a DIFF: `line 2: cpython='<end>' ail='-11'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075200054 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = ((a * b) | (65 // a))
    v2: str = '-7'.upper().upper()
    v3: list[int] = [(99 - 4), round(abs(3.0)), (b + v1), (a * a), (v1 ** 1)]
    for i4 in v3:
        b = len(v2)
        a //= (abs((-5 + a)) + 1)
    al5: list[int] = v3
    v3.sort()
    print(len(v3), len(al5), sum(v3) - sum(al5))
    print(v2)
    if (int(1.25) <= v1):
        return (v1 - v1)
    return sum(v3)


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 2 == 0:
            continue
        t += x
    return t


def main() -> int:
    if (54 == (90 + 6)):
        v6: list[int] = list(range(0, 12, 2))
        print(((7 >> 3) % (abs((23 - 9223372036854775807)) + 1)))
        print(f'{'café'}{31:3d}')
    else:
        if ('q q'[1:4] != 'ab'):
            v7: int = 0
            try:
                v7 = max(0, 11)
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-86)
            try:
                v8: bool = (0.3 == 0.5)
            except ValueError:
                v9: list[int] = list(range(-1, 5, 2))
            else:
                try:
                    if (str((v7 & 9223372036854775807)).startswith(' ')):
                        assert ((int((100.75 / (abs(1e-7) + 1.0))) != (56 % -7)) and (('abc' * 3).endswith('he'))), "boom"
                except AssertionError:
                    print(-22)
                else:
                    print(78)
                v10: list[int] = [(19 % 82), int('AbCd'[-2:4])]
            try:
                if ((--1) != (v7 % 8)):
                    raise AssertionError('m9')
            except AssertionError:
                print(-11)
        elif ('Zed'.startswith('he')):
            v12: list[int] = [c11 for c11 in range(4) if c11 % 2 == 1]
            v13: int = (7 - max(0, 23))
        else:
            print(('3.5' * 1).replace('l', 'XY'))
            v14: list[int] = list(range(0, 4, 2))
    for i15 in range(1, 7):
        try:
            try:
                if ((i15 // (abs(14) + 1)) < i15):
                    raise ZeroDivisionError('m8')
            except ZeroDivisionError:
                print(-26)
            finally:
                print(130)
            v16: bool = ((1e10 + 1e10) > abs(0.3))
        except KeyError:
            v17: list[int] = []
            try:
                v17 = [(59 % -9), ord('Zed'[1]), (i15 - i15), i15, 77]
            except (IndexError, ZeroDivisionError):
                print(-23)
            v17.sort()
        finally:
            print(283)
        v18: list[int] = [1, 2, 3]
    if ((51 + 80) != 37):
        try:
            print((0 % -8))
        except ZeroDivisionError:
            print(-76)
    v19: list[str] = ['-7']
    v20: int = 0
    try:
        v20 = ((55 // -4) - 23)
    except ZeroDivisionError:
        print(-50)
    print((min(v20, -7) - v20))
    v21: list[int] = list(range(3, 7, 3))
    try:
        v22: float = (1.25 * (abs(2.5e-3) ** 0.5))
        try:
            if 'q q'.isdigit():
                raise IndexError
        except IndexError:
            print(-49)
    except ZeroDivisionError:
        print(('日本' + 'q q'), abs(7.0))
        v23: list[int] = []
        try:
            v23 = [(v20 % 5), (v20 * -1), (12 // (abs(v20) + 1)), 'x'.count('a')]
        except ZeroDivisionError:
            print(-95)
    except IndexError:
        try:
            if (b"ab".decode() == ' pad '.lower()):
                print(('q q' in 'AbCd'[0:4]), 2.5e-3, sum(v21))
            elif (f'{'-7'}' < ' pad '.upper()):
                v20 <<= 9
                print(((0.3 / (abs(100.75) + 1.0)) / (abs((100.75 * 123456.789)) + 1.0)))
            else:
                al24: list[int] = v21
                if len(v21) > 0:
                    v21[0] = 2
                print(len(v21), len(al24), sum(v21) - sum(al24))
                v25: int = (35 - (v20 // (abs(v20) + 1)))
            v20 = 64
            try:
                if ((f'{'hello':^9}{int((1e-7 * 1.25)):>6}' < 'Zed') and ((123456.789 / (abs(1.25) + 1.0)) <= (123456.789 // 3.0))):
                    raise RuntimeError('m0')
            except RuntimeError:
                print(-52)
            finally:
                print(118)
        except ValueError:
            v26: int = v20
        try:
            v21.extend([(v20 ^ v20), (v20 // (abs(v20) + 1)), (v20 // -6)])
        except ZeroDivisionError:
            print(-56)
    finally:
        print(268)
    v27: float = 0.0
    try:
        v27 = (((v20 % -4) / 8) - min(1e-7, 0.1))
    except ZeroDivisionError:
        print(-6)
    finally:
        print(141)
    if ('ab'.upper() >= 'ab'[3]):
        print(str((v20 >> 12)))
        try:
            al28: list[int] = v21
            if len(v21) > 0:
                v21[0] = 8
            print(len(v21), len(al28), sum(v21) - sum(al28))
        except ZeroDivisionError:
            try:
                v21 += [h1(v21)]
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-54)
            w29: int = 0
            while w29 < 4:
                w29 += 1
                v30: list[int] = sorted(v21)
                if ((3.0 > v27) and ((w29 + 76) > 3)):
                    continue
                print(('-7' * 1).replace('l', ''))
        finally:
            print(224)
    print((7.0 + ((v20 * v20) / 4)))
    print(len(v19), ','.join(v19))
    print(v20)
    print(len(v21), sum(v21))
    print(v27)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
78
```

AIL stdout, exit code 1:

```
78
-11
-26
130
283
-26
130
283
-26
130
283
-26
130
283
-26
130
283
-26
130
283
0
0
268
141
```

AIL stderr:

```
IndexError: string index out of range
```

**What to do.**
1. Save the program as `/tmp/probes/fz1.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz1.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz1.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='<end>' ail='-N'`.

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
