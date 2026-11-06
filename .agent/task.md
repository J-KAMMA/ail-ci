**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42209881722 (seed `2076311363`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=3; line 15: cpython='235' ail='100.7525 False'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076311363 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 3) % 8003
    return (h0(n - 1, (a * 5 + n) % 8003) + 4) % 8003


def main() -> int:
    v1: float = (((67 - 21) / 4) / (abs(1e10) + 1.0))
    for i2 in range(1, 5):
        if ('q q'[1:2].startswith('a')):
            break
        v1 -= (1.25 + 7.0)
    v3: bool = '12'.isdigit()
    print(float(max(42, 30)))
    w4: int = 0
    while w4 < 5:
        w4 += 1
        for i5 in range(3):
            v3 = (((98 - w4) == (w4 + w4)) and ((15 & i5) <= (34 * 54)))
    v6: list[int] = []
    try:
        v6 = [22, 'q q'.find(' pad '), 9223372036854775807, h0(10, (21 + 3037000499))]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-2)
    v7: list[int] = [0] * 0
    al8: list[int] = v7
    v7.sort()
    print(len(v7), len(al8), sum(v7) - sum(al8))
    print(51)
    v7.append((59 + 5))
    v9: dict[str, int] = {}
    v9['dd'] = 90
    v9['c'] = -8
    v9['c'] = 92
    v9['a'] = 62
    try:
        print(('日本'.startswith('a')))
        try:
            if (not (68 != len(v9))):
                raise ZeroDivisionError('m3')
        except ZeroDivisionError:
            print(-72)
        else:
            print(33)
        finally:
            print(192)
    except ZeroDivisionError:
        for i10 in range(4):
            print(47)
        try:
            try:
                if (str((v1 - v1)) == ('x' + '12')):
                    assert ('café' == '3.5'[-2:]), "boom"
            except (AssertionError, IndexError):
                print(-59)
            else:
                print(1)
            print((0.5 + 1.25), '日本'.replace('l', ''), (v1 / (abs(v1) + 1.0)))
        except IndexError:
            print((abs(float((-1 - 28))) ** 0.5))
            if ('12' in v9):
                v11: list[int] = [(6 * 3), 14]
        else:
            al12: list[int] = al8
            al8.append(8)
            print(len(al8), len(al12), sum(al8) - sum(al12))
            print((7 - 32))
        finally:
            print(295)
    except KeyError:
        try:
            if (str(92).startswith('a')):
                raise KeyError
        except KeyError:
            print(-18)
    else:
        print('café')
    print((((87 - 4611686018427387904) / 8) < (v1 * v1)), (3037000499 == (40 * 66)))
    print((not ((52 + 80) >= (-9223372036854775807 + 42))))
    try:
        al13: list[int] = v7
        al13 += [3]
        print(len(v7), len(al13), sum(v7) - sum(al13))
        try:
            del v9['c']
        except KeyError:
            print(-73)
    except IndexError:
        print((100.75 + 2.5e-3), ((abs(82) == (69 * 92)) and ((len(v6) / 4) <= ((95 * 89) / 4))))
    else:
        try:
            if ((((89 ** 2) > v6[0]) or (("%d" % (72 % -1)) < ' pad ')) and (34 < (89 * 38))):
                print(str(round(v1)).replace('a', ''))
                try:
                    v9.pop('c')
                except KeyError:
                    print(-55)
                try:
                    print(((57 + 42) // 3))
                except ZeroDivisionError:
                    print(-85)
        except ZeroDivisionError:
            print(-66)
        finally:
            print(175)
        if (39 == (0 & -6)):
            w14: int = 0
            while w14 < 6:
                w14 += 1
                v15: float = 0.0
                try:
                    v15 = float((w14 - w14))
                except ZeroDivisionError:
                    print(-9)
                v6.extend([(w14 // (abs(85) + 1)), (w14 * 18), (w14 - w14)])
                v15 += (0.3 - v1)
            v9['abc'] = (~-4)
            v16: dict[str, int] = {}
            v16['dd'] = 52
        elif ((round((v1 * v1)) > al8[3]) or ('hello'.startswith(' '))):
            v3 = ('q q' in '3.5'[1:-1])
            print(al8.count((10 + 77)))
    finally:
        print(235)
    try:
        print((v1 * (v1 / 86)))
    except ZeroDivisionError:
        print(-90)
    print(v1)
    print(v3)
    print(len(v6), sum(v6))
    print(len(v7), sum(v7))
    print(len(al8), sum(al8))
    ks18: list[str] = []
    for k17 in sorted(v9):
        ks18.append(k17)
    print(len(v9), sum(v9.values()), ','.join(ks18))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
42.0
0 0 0
51
False
33
192
café
True False
False
2 2 0
-33
-55
33
175
235
```

AIL stdout, exit code 3:

```
42.0
0 0 0
51
False
33
192
café
True False
False
2 2 0
-33
-55
33
175
100.7525 False
235
12.66279069679186
-32.99999999885
False
```

AIL stderr:

```
AIL limit: int_overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz236.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz236.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz236.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='N.N False'`.

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
