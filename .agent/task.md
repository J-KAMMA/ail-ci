**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40745342315 (seed `2075419632`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=7 ail=1; line 4: cpython='True False' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075419632 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(a: int, b: int) -> int:
    v1: int = (18 | a)
    v2: str = f'/{'abc'}{'Zed'}'
    v3: list[int] = list(range(-1, 12, 3))
    v4: int = 0
    try:
        v4 = ((a // 35) + round((0.1 + 1e-7)))
    except ZeroDivisionError:
        print(-86)
    print(str((31 >> 0)))
    if ((abs(2.5e-3) ** 0.5) < float(v3[-1])):
        return (v1 - 18)
    return (v1 // 1)


def h1(a: int, b: int) -> int:
    v5: int = int((2.5e-3 - 2.5e-3))
    v6: str = 'Zed'
    v7: list[int] = [1, (49 ^ v5), v5, (b * -5)]
    for i8 in v6:
        v10: list[int] = [(a // (abs(51) + 1)) for c9 in range(8) if c9 % 2 == 0]
        v10 += v7
        for i11 in range(5):
            if ((0.5 + 123456.789) <= 1e10):
                continue
            print(len(v6), sum(v10))
            print((max(100.75, 123456.789) - (0.3 * 123456.789)))
    v6 += b"a,b".decode()
    if (v6 in 'hello'[-2:]):
        return (~14)
    return ((v5 % (abs(v5) + 1)) % -2)


def h2(a: int, b: int) -> int:
    v12: int = int(float((a ** 1)))
    v13: str = ('q q' * 1).lower()
    v14: list[int] = []
    try:
        v14 = [(b % -7), len(v13), 10, (a ** 2), 89]
    except ZeroDivisionError:
        print(-89)
    try:
        if (((len(v13) / 4) > (1.25 + 1e10)) and (max(99, 11) >= (a - b))):
            raise AssertionError('m5')
    except AssertionError:
        print(-35)
    finally:
        print(117)
    for i15 in range(3):
        v16: list[int] = []
        try:
            v16 = [int('Zed'), v14.index(v12), (~v12)]
        except ValueError:
            print(-12)
    try:
        print(((0.1 * 3.0) == (1e-7 / (b % -5))))
    except ZeroDivisionError:
        print(-74)
    if ((b - b) > 3):
        return len(v13)
    return (~(a % b))


def main() -> int:
    if ((0.5 - 7.0) <= (2.5e-3 / (abs(2.5e-3) + 1.0))):
        v17: bool = (' pad ' in ('AbCd' * 1))
    elif ((7.0 / 79) < (3.0 * 1.25)):
        if (((75 ** 0) > 3) and ('abc' in 'ab'[3])):
            try:
                v18: bytes = b"x"[-2:2]
                try:
                    if (round((0.1 + 1.25)) != 45):
                        assert ((61 // -7) > 3), "boom"
                except AssertionError:
                    print(-78)
            except IndexError:
                print(4)
                print((('hello' + 'hello') * 1))
            else:
                print((3.0 - 1e10))
                v19: int = 31
            finally:
                print(259)
        elif (b"12".decode() >= str((--7))):
            v20: dict[str, int] = {}
            if (not (str(34) != str((78 ** 2)))):
                print('hello'.rstrip(), (0.5 % 0.75), ((9223372036854775807 + 66) < len(v20)))
                v21: list[int] = []
                try:
                    v21 = [35, 14, (-2 + 58), (50 // (abs(15) + 1)), (37 % 1)]
                except ZeroDivisionError:
                    print(-66)
            else:
                print(((66 << 5) * min(86, 19)))
        v22: list[int] = list(range(0, 5, 1))
    v23: list[str] = ['café', 'ab', ' pad ']
    if (((44 + 8) <= (68 // -1)) or (95 < (68 ** 2))):
        print(len(v23))
        print((0.3 * (1e-7 * 7.0)))
        try:
            w24: int = 0
            while w24 < 5:
                w24 += 1
                v25: list[int] = [(60 ** 1)]
                if 'q q'.isalpha():
                    break
            v26: bytes = b"abc"
        except ValueError:
            if ((not (26 <= (70 >> 4))) or (('AbCd' in 'café'.strip()) and (9223372036854775807 > 3))):
                print(((123456.789 % 0.75) / (abs((1e10 - 3.0)) + 1.0)))
            elif (h0((-8 - 58), (-69)) < (255 // (abs(9) + 1))):
                print((' pad '[-2:4] * 2))
            else:
                try:
                    if ((18 % (abs(44) + 1)) > (66 - 25)):
                        raise ZeroDivisionError('m9')
                except (KeyError, ZeroDivisionError):
                    print(-70)
                else:
                    print(94)
                v27: set[int] = {4, 11, 4}
        except IndexError:
            print(' pad ')
        finally:
            print(228)
    else:
        print(b"Zed"[:].decode())
        v28: str = 'a,b,c'
    if ((-9) <= (84 * 24)):
        v29: str = b"a,b".decode()
    v30: float = float(round(float((-7 - -9223372036854775807))))
    print(('12' < 'café'), (('ab'[:-1].endswith('he')) and ((-7 | 41) < (39 >> 4))))
    try:
        print((v30 / (abs((v30 + 1e-7)) + 1.0)))
    except KeyError:
        w31: int = 0
        while w31 < 3:
            w31 += 1
            try:
                print(((abs(v30) ** 0.5) < (v30 / (35 + 97))))
            except ZeroDivisionError:
                print(-46)
            v32: bool = ((w31 < 97) or (45 == w31))
            if '3.5'.isdigit():
                print(v30)
                v33: str = 'Zed'.replace('a', 'XY')
            else:
                print(99)
                try:
                    if ((max(w31, w31) <= len(v23)) or ('ab' >= f'/- = ')):
                        assert ((62 + 73) > 3), "boom"
                except AssertionError:
                    print(-89)
        try:
            print(((69 % -7) % (abs(-1) + 1)))
        except ZeroDivisionError:
            print(-33)
        finally:
            print(167)
    except ValueError:
        v34: list[str] = 'abc'.split(' ')
    finally:
        print(243)
    v35: str = ('3.5' * 3)
    if (72 > 3):
        v23.append(','.join(v23))
    try:
        v23.append(v35)
        if ((len(v23) < len(v35)) and (len(v35) < 19)):
            try:
                if ((int((0.1 * v30)) == (-9 // 3)) or (((86 & 14) == 28) or ((9223372036854775807 % (abs(97) + 1)) >= (-4 + 58)))):
                    v36: bool = v35.islower()
                elif ((v30 / (abs(v30) + 1.0)) == (v30 - v30)):
                    try:
                        print((v35[:2] < ("<%5d>" % (88 % 4))))
                    except ZeroDivisionError:
                        print(-31)
                    try:
                        print((42 // -4))
                    except ZeroDivisionError:
                        print(-38)
            except ZeroDivisionError:
                print(-78)
            v23.reverse()
        else:
            for i37 in v35:
                if ((1.25 - v30) < float(len(v23))):
                    continue
                if ((91 % (abs(14) + 1)) <= (13 // 8)):
                    break
                print(((v30 * v30) - (0.1 - v30)))
            print(((93 + 53) < (91 >> 4)))
        for i38 in range(2):
            print((round((v30 // 2.5)) * 3))
            try:
                if ((i38 + i38) == i38):
                    raise KeyError('m6')
            except KeyError:
                print(-89)
            finally:
                print(192)
    except ValueError:
        v39: bool = ((max(83, 3) <= 3037000499) or (0 > 3))
        for i40 in v35:
            if ((v35 * 3) == 'AbCd'.upper()):
                try:
                    if (7.0 < (v30 + v30)):
                        raise IndexError('m8')
                except IndexError:
                    print(-16)
                finally:
                    print(159)
                v23.sort()
                v23.reverse()
            elif ((i40 < f'#{(2.5e-3 * v30):8.3f}{(71 % -3):<4}') or ((255 - 36) <= len(v23))):
                v41: float = 1e-7
                if ((''.join(v23) >= i40) or ((-8 * 8) == max(78, 55))):
                    break
            if (not ((71 // (abs(-9223372036854775807) + 1)) > h0((86 // (abs(4611686018427387904) + 1)), (12 << 10)))):
                break
            w42: int = 0
            while w42 < 5:
                w42 += 1
                v43: list[int] = [(w42 // (abs(28) + 1)), (w42 ^ w42)]
                try:
                    if 'x'.isdigit():
                        raise ZeroDivisionError
                except ZeroDivisionError:
                    print(-1)
    try:
        if (v35.endswith('a')):
            raise IndexError('m1')
    except (IndexError, ValueError):
        print(-27)
    try:
        print(((v30 % 2.5) / (abs((abs(v30) ** 0.5)) + 1.0)))
        v23.append(str(1e-7))
        print((11 - 82))
    except KeyError:
        try:
            if (7.0 > (0.5 * 0.1)):
                v44: list[int] = [(~24)]
            else:
                try:
                    print(round((v30 / (81 % (abs(1) + 1)))))
                except ZeroDivisionError:
                    print(-28)
                finally:
                    print(132)
        except ZeroDivisionError:
            print(-73)
    except IndexError:
        try:
            if (max(78, 22) > 3):
                assert (v35 in '-'.join(v23)), "boom"
        except (AssertionError, KeyError):
            print(-42)
        else:
            print(4)
    else:
        v45: bytes = (b"hello" + b"Zed")
    print(len(v23), ','.join(v23))
    print(v30)
    print(v35)
    return 7


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 7:

```
3
2.0999999999999997e-07
228
True False
1.0
243
11068046444225731584
-89
192
11068046444225731584
192
1.646361269414697e-10
-71
6 3.53.53.5,café,ab, pad , pad ,ab,café,1e-07
9.223372036854776e+18
3.53.53.5
```

AIL stdout, exit code 1:

```
3
2.0999999999999997e-07
228
```

AIL stderr:

```
round() result does not fit in this language's int64
```

**What to do.**
1. Save the program as `/tmp/probes/fz198.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz198.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz198.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='True False' ail='<end>'`.

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
