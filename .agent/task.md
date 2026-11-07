**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42398208962 (seed `2076417375`, CPython 3.12, modes default+ir) found a DIFF: `line 38: cpython='0 nan' ail='0 inf'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076417375 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 3 == 0:
            continue
        t += x
    return t


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 4 + 5) % 76003
    return (h1(n - 1, (a * 1 + n) % 76003) + 6) % 76003


def h2(a: int, b: int) -> int:
    v1: int = (min(-4, a) + (b + 95))
    v2: str = b"ab".decode()
    v3: list[int] = [2] * 2
    try:
        print((24 % (abs(int((7.0 / (26 % (abs(a) + 1))))) + 1)))
    except ZeroDivisionError:
        print(-91)
    finally:
        print(126)
    for i4 in range(-1, 7):
        al5: list[int] = v3
        v3.sort()
        print(len(v3), len(al5), sum(v3) - sum(al5))
        print(3.0)
        try:
            print(((i4 // 4) - h0(al5)))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-59)
    if (sum(v3) != min(78, a)):
        return (b % (abs(v1) + 1))
    return (a + a)


def main() -> int:
    v6: str = ""
    try:
        v6 = f'{(49 // 33):d}{13:^7}'[0:-1]
    except ZeroDivisionError:
        print(-58)
    v7: float = ((0.3 // 2.5) + 1e10)
    v8: list[int] = [-4, 0, (89 * 2)]
    for i9 in v6:
        v10: str = str((86 + 79)).upper()
        for i11 in i9:
            al12: list[int] = v8
            if len(v8) > 0:
                v8[0] = 1
            print(len(v8), len(al12), sum(v8) - sum(al12))
            al13: list[int] = v8
            v8.sort()
            print(len(v8), len(al13), sum(v8) - sum(al13))
        print((75 + 39))
    v8.append((79 % (abs(83) + 1)))
    v8.extend([(54 * 93), (84 * 96), (65 ** 2)])
    for i14 in range(1, 8):
        print(v6)
        v15: float = v7
    v8.append(max(51, 0))
    v8.append((22 + 84))
    al16: list[int] = v8
    if len(v8) > 0:
        v8[0] = 0
    print(len(v8), len(al16), sum(v8) - sum(al16))
    for i17 in range(6):
        v18: dict[str, int] = {}
        for i19 in v6:
            v7 *= v7
            print((21 * i17), (v7 // 3.0))
            print('x')
    print(v7)
    v6 = v6
    v20: dict[str, int] = {}
    v20['c'] = 66
    v20[v6] = 29
    print(min(max(75, 76), (-14)))
    try:
        print(((51 + 66) // 9))
    except ZeroDivisionError:
        print(-91)
    finally:
        print(128)
    v21: str = (('café' * 3) + (v6 + 'hello'))
    print(v6)
    print(v7)
    print(len(v8), sum(v8))
    print(len(al16), sum(al16))
    ks23: list[str] = []
    for k22 in sorted(v20):
        ks23.append(k22)
    print(len(v20), sum(v20.values()), ','.join(ks23))
    print(v21)
    return 7


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
1  13  
1  13  
1  13  
1  13  
1  13  
1  13  
1  13  
9 9 0
0 3.333333333333333e+19
x
0 3.3333333333333336e+39
x
0 3.333333333333333e+79
x
0 3.3333333333333334e+159
x
0 nan
x
0 nan
x
0 nan
x
21 nan
x
21 nan
x
21 nan
x
21 nan
x
21 nan
x
21 nan
x
21 nan
x
42 nan
x
42 nan
x
42 nan
x
42 nan
x
42 nan
x
42 nan
x
42 nan
x
63 nan
x
63 nan
x
63 nan
x
63 nan
x
63 nan
x
63 nan
x
63 nan
x
84 nan
x
84 nan
x
84 nan
x
84 nan
x
84 nan
x
84 nan
x
84 nan
x
105 nan
x
105 nan
x
105 nan
x
105 nan
x
105 nan
x
105 nan
x
105 nan
x
inf
-14
13
128
1  13  
inf
9 17726
9 17726
2 95 1  13  ,c
cafécafécafé1  13  hello
```

AIL stdout, exit code 0:

```
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
3 3 0
3 3 0
114
1  13  
1  13  
1  13  
1  13  
1  13  
1  13  
1  13  
9 9 0
0 3.333333333333333e+19
x
0 3.3333333333333336e+39
x
0 3.333333333333333e+79
x
0 3.3333333333333334e+159
x
0 inf
x
0 inf
x
0 inf
x
21 inf
x
21 inf
x
21 inf
x
21 inf
x
21 inf
x
21 inf
x
21 inf
x
42 inf
x
42 inf
x
42 inf
x
42 inf
x
42 inf
x
42 inf
x
42 inf
x
63 inf
x
63 inf
x
63 inf
x
63 inf
x
63 inf
x
63 inf
x
63 inf
x
84 inf
x
84 inf
x
84 inf
x
84 inf
x
84 inf
x
84 inf
x
84 inf
x
105 inf
x
105 inf
x
105 inf
x
105 inf
x
105 inf
x
105 inf
x
105 inf
x
inf
-14
13
128
1  13  
inf
9 17726
9 17726
2 95 1  13  ,c
cafécafécafé1  13  hello
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz238.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz238.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz238.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N nan' ail='N inf'`.

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
