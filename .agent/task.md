**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42517310228 (seed `2076519017`, CPython 3.12, modes default+ir) found a DIFF: `line 1: cpython='-72' ail='<end>'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076519017 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(a: int, b: int) -> int:
    v1: int = (60 - b)
    v2: str = 'abc'.upper()[-2:2]
    v3: list[int] = [max(v1, 1), (b - b), b]
    try:
        if (v2 != ('-7' + v2)):
            raise AssertionError
    except AssertionError:
        print(-72)
    else:
        print(57)
    finally:
        print(155)
    if ((1 + b) > 3):
        return (39 % -1)
    return ((v1 ** 2) ** 3)


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 47:
            break
        t += abs(x) + 1
    return t


def h2(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 0) % 50003
    return (h2(n - 1, (a * 6 + n) % 50003) + 3) % 50003


def main() -> int:
    for i4 in range(3):
        v5: list[int] = []
        try:
            v5 = [h2(5, (16 % (abs(i4) + 1))), (5 - i4)]
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-88)
        v6: bool = ((i4 * 95) != 23)
        if ((h0((i4 + 27), max(62, 72)) >= v5.count((i4 % i4))) or ((3.0 + 7.0) == (7.0 / (~90)))):
            break
    w7: int = 0
    while w7 < 3:
        w7 += 1
        if (26 > (12 - 99)):
            w8: int = 0
            while w8 < 3:
                w8 += 1
                print((f'{(1.25 - 1.25):.2f}{(25 // 27):3d}' * 2))
                print(72)
                print(w8)
            v9: dict[str, int] = {}
            v9['c'] = 30
            v9['c'] = 40
            v9['e'] = 46
            v9['e'] = 41
            print((abs(abs(100.75)) ** 0.5))
        elif (not (' pad ' in ('a,b,c' + 'Zed'))):
            for i10 in range(2, 4):
                v11: list[int] = []
                try:
                    v11 = [(i10 // -6), (84 * 62)]
                except ZeroDivisionError:
                    print(-40)
            try:
                print((h0((-7 * w7), abs(w7)) % 6))
            except (IndexError, KeyError, ValueError, ZeroDivisionError):
                print(-93)
        else:
            try:
                v12: str = 'café'
                if v12.islower():
                    break
            except ValueError:
                v13: float = (2.5e-3 - min(0.1, 7.0))
                if ('café' in '-7'):
                    break
            except ZeroDivisionError:
                v14: list[int] = [1, 2, 3]
            finally:
                print(294)
        try:
            if ('x' < str(max(70, w7))):
                assert (not (w7 > 3)), "boom"
        except AssertionError:
            print(-16)
        finally:
            print(130)
    print(str((10 ^ 255)))
    v15: float = (abs(123456.789) * 0.1)
    v16: set[int] = set()
    print((len(v16) + (76 - 66)))
    print(b"Zed".decode())
    v15 = (v15 + v15)
    print(v15)
    print(len(v16), sum(v16), max(v16) if len(v16) > 0 else 0)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
-72
155
```

AIL stdout, exit code 1:

```

```

AIL stderr:

```
integer modulo by zero
```

**What to do.**
1. Save the program as `/tmp/probes/fz242.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz242.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz242.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='-N' ail='<end>'`.

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
