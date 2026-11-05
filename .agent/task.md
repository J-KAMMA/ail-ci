**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41950413669 (seed `2076201221`, CPython 3.12, modes default+ir) found a DIFF: `line 12: cpython='<end>' ail='10'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076201221 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = max((~b), b)
    v2: str = f'{'12':^9}{4611686018427387904:<4}'
    v3: list[int] = [3] * 3
    v3.append(len(v3))
    if (('AbCd' + v2) < v2.upper()):
        v4: list[str] = '-7'.upper().split(' ')
        try:
            print(v2)
            al5: list[int] = v3
            al5 += [3]
            print(len(v3), len(al5), sum(v3) - sum(al5))
            print(v3 == al5)
            print(v2)
        except ValueError:
            al6: list[int] = v3
            v3.append(8)
            print(len(v3), len(al6), sum(v3) - sum(al6))
        finally:
            print(249)
    elif ((39 - a) == (~4611686018427387904)):
        print(1e10)
    else:
        print((1e10 + (0.1 + 1e-7)))
    if ((80 ** 3) == (98 * 20)):
        return (v1 - a)
    return (min(v3) - v3[(96 - b)])


def h1(a: int, b: int) -> int:
    v7: int = a
    v8: str = ' pad '.upper().lstrip()
    v9: list[int] = [1, 2, 3]
    print('-'.join(v8.split('a')))
    print('3.5'.isalpha(), str(0.1), (v7 // (abs(20) + 1)))
    print(max(1e10, (123456.789 % 2.5)))
    if (not v8.islower()):
        return h0(int('-7'), len(v8))
    return v7


def h2(a: int, b: int) -> int:
    v10: int = (~(40 * b))
    v11: str = ("%d" % a)
    v12: list[int] = [2] * 4
    w13: int = 0
    while w13 < 4:
        w13 += 1
        print((b // (abs(b) + 1)), sum(v12))
        try:
            print(v11.rstrip(), 0.1, str(int(str(v12[(35 + w13)]))))
        except (IndexError, ValueError):
            print(-28)
        for i14 in range(6, 2, -1):
            if ('Zed' < (v11 + v11)):
                break
            v15: dict[str, int] = {}
            v15['c'] = 60
            v15['a'] = 39
            v15['a'] = 37
            v15['dd'] = 46
    v16: str = ""
    try:
        v16 = (str((93 // 3)) + 'Zed')
    except ZeroDivisionError:
        print(-20)
    finally:
        print(160)
    if ((26 << 4) != len(v11)):
        return a
    return ((89 // -9) << 0)


def main() -> int:
    v17: int = ((51 + 28) * (38 << 8))
    print(((v17 - 34) / 8))
    try:
        try:
            v17 %= (abs(h2((v17 // 2), (v17 % (abs(v17) + 1)))) + 1)
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-74)
    except IndexError:
        try:
            print((31 // 3))
        except ZeroDivisionError:
            print(-19)
    else:
        w18: int = 0
        while w18 < 5:
            w18 += 1
            print((int(str(len('hello'))) + h0(v17, (w18 + 56))))
            if (f'{max(w18, v17):3d}{'12':>8}' < ('abc' + 'café')):
                break
            v19: bool = ('ab' in (' pad ' + 'ab'))
    print((abs(1e-7) // 2.5))
    v17 = (v17 - (29 ^ v17))
    try:
        print((int((0.5 / 82)) - min(95, 63)))
    except ZeroDivisionError:
        print(-41)
    v17 = ((35 + v17) >> 4)
    try:
        if ((v17 * 44) > 3):
            assert (' pad ' == ' pad '), "boom"
    except AssertionError:
        print(-41)
    print(((0.1 * 123456.789) * abs(0.3)))
    v20: bool = ((47 ** 0) <= (v17 // (abs(v17) + 1)))
    print(((abs(123456.789) ** 0.5) % 7.0))
    v21: str = 'ab'
    if (((v17 + v17) > round((3.0 / h1(v17, (3 | v17))))) or ((72 != len(v21)) and (v17 < v17))):
        v22: list[int] = list(range(1, 11, 1))
        for i23 in range(1, 10, 2):
            try:
                print(((f'{(1e-7 / (abs(1e10) + 1.0)):.3f}{(-2 ** 3):d}{'-7':<6}' == (v21 + v21)) or (f'{v21:>8}{max(1e-7, 0.1):>10.1f}' == v21[0])))
            except IndexError:
                print(-30)
            print(((0.5 * 2.5e-3) + (2.5e-3 / (abs(3.0) + 1.0))))
    elif v21.isupper():
        if (v17 >= (v17 - v17)):
            print(b"ab"[-2:2].decode())
            v24: list[int] = []
            try:
                v24 = [(v17 ** 0), v17, 29, (v17 % -1), (v17 // (abs(44) + 1))]
            except ZeroDivisionError:
                print(-56)
            w25: int = 0
            while w25 < 4:
                w25 += 1
                print(((1e10 / (abs(3.0) + 1.0)) + (2.5e-3 - 7.0)))
                if (v24.index(round((1e-7 / (abs(1e10) + 1.0)))) != int((123456.789 / max(w25, 21)))):
                    break
        else:
            try:
                v26: list[int] = [(v17 ^ 255), int((0.3 - 1e-7)), (68 % (abs(v17) + 1)), (-v17)]
                al27: list[int] = v26
                if len(al27) > 0:
                    al27[0] = 7
                print(len(v26), len(al27), sum(v26) - sum(al27))
                print(v26 == al27)
                al27.reverse()
            except KeyError:
                print((max(24, v17) / 3))
            except IndexError:
                try:
                    print(ord(f'{(1e-7 / (abs(1e-7) + 1.0))}#{v21:>8}'[3]))
                except IndexError:
                    print(-69)
                print(max((42 & v17), (v17 ** 0)))
    else:
        v17 = 10
    print(v17)
    print(v20)
    print(v21)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
96059.75
0 8
-28
0 8
-28
0 8
-28
0 8
-28
160
10000000000.1
```

AIL stdout, exit code 1:

```
96059.75
0 8
-28
0 8
-28
0 8
-28
0 8
-28
160
10000000000.1
10
0.0
-63
3703.70367
1.3641828644462066
PAD 
False 0.1 0
10000000000.0
10000000000.1
```

AIL stderr:

```
IndexError: list index out of range
```

**What to do.**
1. Save the program as `/tmp/probes/fz229.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz229.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz229.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='<end>' ail='N'`.

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
