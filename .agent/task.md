**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41625900402 (seed `2076011679`, CPython 3.12, modes default+ir) found a DIFF: `line 11: cpython='55.0' ail='1.0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076011679 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = b
    v2: str = '日本'.replace(' ', '-').strip()
    v3: list[int] = [3] * 5
    v3.extend(v3)
    print(abs(float(a)))
    if (0.5 == float((43 * 73))):
        return int(0.1)
    return (255 % 3)


def h1(a: int, b: int) -> int:
    v4: int = len('hello'.replace(' ', '-'))
    v5: str = ""
    try:
        v5 = ('abc' + ("%03d" % h0(a, (v4 % (abs(80) + 1)))))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-73)
    v6: list[int] = [1, 2, 3]
    v7: int = ((a << 12) * (64 + b))
    w8: int = 0
    while w8 < 3:
        w8 += 1
        b <<= 4
        v9: list[int] = list(range(1, 9, 2))
    if (v5.startswith(' ')):
        return (28 ** 0)
    return (~ord(f'{(a * v7):05d}'[2]))


def h2(a: int, b: int) -> int:
    v10: int = 0
    try:
        v10 = ((b & 23) % (b % 7))
    except ZeroDivisionError:
        print(-4)
    finally:
        print(186)
    v11: str = ('hello'.strip() + 'Zed'.lstrip())
    v12: list[int] = []
    try:
        v12 = [77, (v10 // 3)]
    except ZeroDivisionError:
        print(-13)
    v13: list[int] = []
    if ((~b) > (96 << 9)):
        return (v10 + 76)
    return 1


def main() -> int:
    v14: int = 18
    try:
        v15: list[int] = [(v14 + v14), (v14 ** 1)]
        al16: list[int] = v15
        if len(v15) > 0:
            v15[0] = 7
        print(len(v15), len(al16), sum(v15) - sum(al16))
    except ValueError:
        print((('AbCd' + 'a,b,c') + 'café'[-2:-1]))
    finally:
        print(241)
    for i17 in range(1, 9, 2):
        v19: list[int] = [round((1.25 * 3.0)) for c18 in range(6) if c18 % 2 == 1]
        try:
            v20: list[str] = ['-7']
            al21: list[int] = v19
            al21.reverse()
            print(len(v19), len(al21), sum(v19) - sum(al21))
            v20.sort()
        except ValueError:
            v19.append(65)
        except ZeroDivisionError:
            v19.append((99 + i17))
            try:
                v14 %= (abs(max(v19)) + 1)
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-64)
    v22: str = str(v14)
    w23: int = 0
    while w23 < 3:
        w23 += 1
        for i24 in v22:
            v25: int = 0
            try:
                v25 = (w23 % 8)
            except ZeroDivisionError:
                print(-73)
        print(float((w23 - v14)))
        v26: list[int] = list(range(-2, 7, 1))
    try:
        v22 += v22
        w27: int = 0
        while w27 < 5:
            w27 += 1
            if ((w27 == (v14 - 70)) or ('hello'.endswith('d'))):
                v28: list[int] = [1, 2, 3]
                print((1e10 + (1e10 / (abs(1.25) + 1.0))))
                try:
                    if ('3.5' in (v22 * 0)):
                        assert ((v14 ** 1) > v14), "boom"
                except AssertionError:
                    print(-24)
            v29: str = v22.strip().upper()
            if (not (v22 in f'{(100.75 // 3.0):.2f}{(123456.789 * 100.75)}')):
                try:
                    print(((h1(h1(max(w27, w27), (w27 * w27)), (95 % -2)) / 3) / (abs((2.5e-3 * 0.1)) + 1.0)))
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-94)
                finally:
                    print(123)
                try:
                    if ((23 % 8) > 3):
                        assert ((v14 != (90 ** 3)) and ((v14 ** 1) == (4 - v14))), "boom"
                except (AssertionError, IndexError):
                    print(-74)
                if (v29.isspace() and ((w27 - w27) == abs(w27))):
                    break
        print((3.0 % 2.5))
    except KeyError:
        v22 = ("%d" % len(v22))[:2]
        for i30 in v22:
            v31: list[int] = list(range(-2, 6, 2))
            print(((v14 ^ v14) / 8))
            print(((7.0 + 100.75) - float((v14 * v14))))
    except ZeroDivisionError:
        for i32 in v22:
            for i33 in i32:
                if (h0((82 * v14), (v14 ** 0)) != (v14 + 16)):
                    continue
        v35: list[int] = [88 for c34 in range(7) if c34 % 2 == 0]
    print(v14)
    print(10)
    print(v14)
    print(v22)
    return 7


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
2 2 0
241
3 3 0
3 3 0
3 3 0
3 3 0
-17.0
-16.0
-15.0
1.0
55.0
-16.329251020578187
123
-74
2.0
50.0
-17.995501124718817
123
-74
3.0
58.0
-18.9952511872032
123
-74
4.0
53.0
-17.662251103890693
123
-74
5.0
50.0
-17.995501124718817
123
-74
0.5
18
10
18
1818
```

AIL stdout, exit code 0:

```
2 2 0
241
3 3 0
3 3 0
3 3 0
3 3 0
-17.0
-16.0
-15.0
1.0
1.0
55.0
55.0
-16.329251020578187
123
-74
2.0
2.0
50.0
50.0
-17.995501124718817
123
-74
3.0
3.0
58.0
58.0
-18.9952511872032
123
-74
4.0
4.0
53.0
53.0
-17.662251103890693
123
-74
5.0
5.0
50.0
50.0
-17.995501124718817
123
-74
0.5
18
10
18
1818
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz221.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz221.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz221.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N.N' ail='N.N'`.

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
