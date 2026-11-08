**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42455294323 (seed `2076507535`, CPython 3.12, modes default+ir) found a DIFF: `line 3: cpython='False' ail='275'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076507535 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if x % 4 == 0:
            continue
        t += x
    return t


def h1(a: int, b: int) -> int:
    v1: int = min(int((3.0 * 0.3)), (66 - a))
    v2: str = '-7'
    v3: list[int] = [(98 - 30), b, (40 + v1), (b * 66)]
    try:
        if ((v1 >> 0) > 3):
            v4: int = 0
            try:
                v4 = (v3[0] ** 2)
            except IndexError:
                print(-81)
            print((int(0.1) + (v4 - a)))
        else:
            try:
                print((h0(v3) / 8))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-53)
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-44)
    if ((a >= (v1 + a)) or ((v2 * 1).startswith('d'))):
        return int((0.3 + 123456.789))
    return max((v1 ** 1), (3037000499 % (abs(v1) + 1)))


def main() -> int:
    try:
        v5: float = 0.0
        try:
            v5 = ((0.1 % 0.75) % 7.0)
        except ZeroDivisionError:
            print(-98)
        finally:
            print(152)
        print(((46 ** 0) // (90 - 1)))
        print((2.5e-3 > float((4611686018427387904 * 53))))
    except ZeroDivisionError:
        v6: str = f'{0.5:>10.1f}{(2.5e-3 / (abs(2.5e-3) + 1.0)):.3f}'
        if (not (((33 - 63) == (92 // (abs(52) + 1))) and ('hello'.lower() >= b"abc".decode()))):
            v7: list[int] = []
            try:
                v7 = [(28 - 24), (17 // -6)]
            except ZeroDivisionError:
                print(-90)
            v7.insert(-2, len(v6))
            v8: str = (v6 * 1).upper()
        elif (('AbCd' in ('日本' + '12')) or ((~-4) < (-97))):
            v9: float = 1e-7
            print(float((96 ^ 71)))
    except KeyError:
        w10: int = 0
        while w10 < 1:
            w10 += 1
            print((w10 - w10), 'x')
            for i11 in range(6):
                v12: int = 0
                try:
                    v12 = min((w10 - 2), int(str(38)))
                except ValueError:
                    print(-32)
        v13: bytes = (b"Zed" + b"12")
    else:
        print(' pad '.isspace())
    finally:
        print(275)
    print(int('x'))
    try:
        print((h1((36 * 22), (36 % (abs(81) + 1))) + int((0.1 % 0.75))))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-60)
    v14: set[int] = {-5, 6, 2, 4, 7, -5}
    v15: bool = ((len(v14) == 84) or ' pad '.isdigit())
    print((abs(7.0) ** 0.5))
    v14.update({11, -1, -3, 6})
    w16: int = 0
    while w16 < 3:
        w16 += 1
        print(b"a,b".decode())
        v17: float = min(float(round((100.75 - 3.0))), 123456.789)
    print(len(v14), sum(v14), max(v14) if len(v14) > 0 else 0)
    print(v15)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
152
0
False
False
275
```

AIL stdout, exit code 1:

```
152
0
275
```

AIL stderr:

```
OverflowError
```

**What to do.**
1. Save the program as `/tmp/probes/fz240.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz240.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz240.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='False' ail='N'`.

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
