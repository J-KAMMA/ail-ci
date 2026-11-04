**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41902054682 (seed `2076120023`, CPython 3.12, modes default+ir) found a DIFF: `line 1: cpython='False 3746 2.9562089861714024e+16' ail='False 3746 2.9562089861714028e+16'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076120023 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 8 + 6) % 8003
    return (h0(n - 1, a + 0) * 4 + h0(n - 1, a - 0) + n) % 8003


def h1(a: int, b: int) -> int:
    v1: int = '-7'.find('-7')
    v2: str = ("%03d" % a)
    v3: list[int] = []
    try:
        v3 = [h0(7, min(b, v1)), (49 % (abs(a) + 1)), (b - a), (a // 4), (28 - a)]
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-76)
    finally:
        print(174)
    print((v1 << 1))
    v4: str = 'ab'
    if ((a ** 1) >= len(v3)):
        return v1
    return v3.index(len(v3))


def h2(n: int, a: int) -> int:
    if n <= 0:
        return (a * 6 + 0) % 89003
    return (h2(n - 1, (a * 3 + n) % 89003) + 7) % 89003


def main() -> int:
    w5: int = 0
    while w5 < 6:
        w5 += 1
        v6: bytes = b"a,b"
    try:
        print((f' = /{(86 // 9):<4}' >= ('café' + 'café')), ("%03d" % h0(3, (20 + 95))), ((4611686018427387904 // 52) / 3))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-31)
    print(((~3) * f'{abs(1.25):.2f}{abs(0.5):.0f}{(1e-7 - 123456.789):.0f}'.find(('Zed' * 2))))
    try:
        print(h1((74 ** 1), (54 - 42)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-11)
    v7: str = ""
    try:
        v7 = 'ab'[0][-2:4]
    except IndexError:
        print(-77)
    try:
        if ((8 + -1) > 3):
            raise ZeroDivisionError('m6')
    except ZeroDivisionError:
        print(-63)
    else:
        print(57)
    finally:
        print(110)
    for i8 in v7:
        v9: float = 100.75
        print((max(7.0, 3.0) - (2.5e-3 - v9)))
    v10: list[int] = []
    try:
        try:
            if (not (v7 in str(0.1))):
                assert (v7.startswith('he')), "boom"
        except (AssertionError, ZeroDivisionError):
            print(-85)
        finally:
            print(166)
        print((3 ** 2))
        v10.append(93)
    except IndexError:
        v11: str = (f'{29}' + ' pad ')
        v12: bytes = b"Zed"[:]
    except KeyError:
        w13: int = 0
        while w13 < 4:
            w13 += 1
            try:
                v10.extend([abs(w13), int('12')])
            except ValueError:
                print(-27)
            print((v7 in v7), (2.5e-3 % 7.0), (v7 + 'a,b,c'))
            try:
                v10 += [(w13 // 2), ord(v7[3][2]), (12 ** 3)]
            except (IndexError, ZeroDivisionError):
                print(-7)
            finally:
                print(165)
    try:
        print(((1.25 % 2.5) * min(1e-7, 3.0)))
        print(f'{'hello':>8}')
        for i14 in range(0):
            v15: set[int] = set(v10)
            v16: dict[str, int] = {}
            for i17 in range(4):
                print(((i14 * i17) + max(i17, 255)))
                if ('ab' in f'{min(0.1, 7.0):.0f}{(84 % i14):3d}'):
                    continue
    except KeyError:
        if ((1.25 / (abs(0.3) + 1.0)) == 0.5):
            v10.reverse()
    except ValueError:
        try:
            v10[0] = 19
        except IndexError:
            print(-26)
    else:
        print((3 + (57 & 36)))
    try:
        v10 += [25, v10[abs(75)]]
    except IndexError:
        print(-39)
    finally:
        print(168)
    al18: list[int] = v10
    v10.sort()
    print(len(v10), len(al18), sum(v10) - sum(al18))
    try:
        print(h0(2, sum(v10)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-14)
    v19: list[int] = [(93 % (abs(46) + 1))]
    print(v7)
    print(len(v10), sum(v10))
    print(len(al18), sum(al18))
    print(len(v19), sum(v19))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
False 3746 2.9562089861714024e+16
4
174
0
0
-63
110
107.7475
-85
166
9
1.25e-07
   hello
35
-39
168
1 1 0
2751
a
1 93
1 93
1 46
```

AIL stdout, exit code 0:

```
False 3746 2.9562089861714028e+16
4
174
0
0
-63
110
107.7475
-85
166
9
1.25e-07
   hello
35
-39
168
1 1 0
2751
a
1 93
1 93
1 46
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz227.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz227.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz227.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='False N N.Ne+N' ail='False N N.Ne+N'`.

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
