**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40883212738 (seed `2075514258`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 4: cpython='278' ail='café 2090'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075514258 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 58:
            break
        t += abs(x) + 1
    return t


def main() -> int:
    v1: float = 0.0
    try:
        v1 = ((100.75 + 0.3) / (7 + 8))
    except ZeroDivisionError:
        print(-67)
    v2: list[int] = ['q q'.replace('l', 'XY').find('café'), max(32, 98), 68, (70 * 41), (11 << 0)]
    if ('x'.startswith('d')):
        w3: int = 0
        while w3 < 6:
            w3 += 1
            v4: int = 0
            try:
                v4 = ((w3 - 67) ** 3)
            except ZeroDivisionError:
                print(-19)
            v5: list[str] = str(float(len('abc'))).split(',')
            print((-w3))
        if (' pad ' in '日本'.upper()):
            print(f'{'-7':^9} = ')
        else:
            for i6 in v2:
                print(((i6 // (abs(22) + 1)) | (i6 % (abs(i6) + 1))))
    elif (not ('日本' in f'{abs(18)}')):
        print((b"12" * 3).decode())
        v2 += [(32 | 0)]
    else:
        try:
            v2.pop()
        except IndexError:
            print(-14)
    try:
        v2.pop()
    except IndexError:
        print(-94)
    finally:
        print(186)
    try:
        v7: str = '3.5'[0:4].lower()
        v8: set[int] = set(v2)
    except IndexError:
        v9: set[int] = set(v2)
    else:
        try:
            w10: int = 0
            while w10 < 5:
                w10 += 1
                v11: int = w10
            print(("%d" % (-1 ^ -8)).replace('l', 'XY'))
        except IndexError:
            print((sum(v2) >= 81))
        except ZeroDivisionError:
            if ((-9223372036854775807 // -6) >= (44 ** 0)):
                v12: list[int] = [3] * 5
                print('café'.lower(), (38 * 55))
            elif (b"Zed".decode() >= '12'[0]):
                print(22)
            for i13 in range(0, 10, 1):
                print(((i13 - 84) >> 10))
        else:
            v14: str = f'{max(1e10, v1):.0f}'
            for i15 in v14:
                if ((v1 - 123456.789) > (2.5e-3 / (10 >> 12))):
                    continue
    finally:
        print(278)
    al16: list[int] = v2
    al16.append(7)
    print(len(v2), len(al16), sum(v2) - sum(al16))
    print(((v1 + v1) * abs(0.1)))
    print(((v1 // 3.0) + 1e-7))
    print((' pad '.upper().endswith('he')), v1)
    print(v1)
    print(len(v2), sum(v2))
    print(len(al16), sum(al16))
    return 7


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
121212
186
7
278
```

AIL stdout, exit code 0:

```
121212
186
7
café 2090
-1
-1
-1
-1
-1
-1
-1
-1
-1
-1
278
6 6 0
1.3473333333333333
2.0000001
False 6.736666666666666
6.736666666666666
6 3053
6 3053
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz202.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz202.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz202.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='café N'`.

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
