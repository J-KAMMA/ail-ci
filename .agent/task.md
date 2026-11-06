**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42145827731 (seed `2076302692`, CPython 3.12, modes default+ir) found a DIFF: `line 8: cpython='258' ail='日本'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076302692 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(a: int, b: int) -> int:
    v1: int = (int((0.1 + 1e10)) - b)
    v2: str = 'x'
    v3: list[int] = [b, max(v1, b)]
    v4: int = ((b << 4) - (v1 - v1))
    if ((b - a) <= (v4 - b)):
        return v4
    return (90 >> 6)


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 8 + 5) % 64003
    return (h1(n - 1, a + 2) * 2 + h1(n - 1, a - 1) + n) % 64003


def h2(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 7) % 15003
    return (h2(n - 1, (a * 1 + n) % 15003) + 0) % 15003


def main() -> int:
    v5: int = ((0 ** 3) | (80 + 1))
    v5 = (82 ** 3)
    for i6 in range(4):
        v7: int = v5
        try:
            print((v5 % 9))
        except ZeroDivisionError:
            print(-12)
    try:
        v8: dict[str, int] = {}
        v8['e'] = 34
        v8['dd'] = 81
        try:
            v8['AbCd'] = (v5 ^ v5)
        except ZeroDivisionError:
            v9: bool = (('hello' in str((v5 << 6))) or ((2 - 53) <= (56 + 89)))
            v10: int = ((v5 ^ v5) + (v5 + v5))
        print(round((1e10 * 1e-7)), f'{(v5 - v5):^7}/')
    except KeyError:
        print(((v5 - 78) % (abs((v5 - v5)) + 1)))
    except ZeroDivisionError:
        if (b"abc".decode().startswith('a')):
            print('日本')
            v11: int = (v5 - 'ab'.replace('l', 'XY').count('l'))
        v12: str = 'café'
    else:
        try:
            if (('hello' + '3.5') >= ("%-4d|" % ' pad '.find('日本'.upper()))):
                assert ((86 < h1(8, (v5 - 49))) or (42 < (47 ** 2))), "boom"
        except (AssertionError, IndexError):
            print(-37)
        finally:
            print(187)
        for i13 in range(-1, 3):
            if (70 > (v5 % i13)):
                v14: bytes = (b"x" * 0)
                print((str(7.0) + 'x'[0:-1]))
                v15: list[int] = []
            else:
                v16: list[int] = [(v5 + v5), 91, (i13 ** 1)]
    finally:
        print(258)
    v17: list[int] = []
    al18: list[int] = v17
    al18.sort()
    print(len(v17), len(al18), sum(v17) - sum(al18))
    print(('AbCd' * 3), (~v5))
    al19: list[int] = al18
    al18.reverse()
    print(len(al18), len(al19), sum(al18) - sum(al19))
    al20: list[int] = al19
    al19.sort()
    print(len(al19), len(al20), sum(al19) - sum(al20))
    v21: str = 'x'
    print(((2.5e-3 * 0.1) + (2.5e-3 % 0.75)))
    print('-'.join(v21.rstrip().split(' ')))
    v22: bool = False
    try:
        v22 = (((v5 // 6) > 3) and ((v5 << 10) > 3))
    except ZeroDivisionError:
        print(-71)
    finally:
        print(140)
    v23: float = 0.5
    print(v5)
    print(len(v17), sum(v17))
    print(len(al18), sum(al18))
    print(len(al19), sum(al19))
    print(len(al20), sum(al20))
    print(v21)
    print(v22)
    print(v23)
    return 1


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
1
1
1
1
1000    0   /
187
7.0
258
```

AIL stdout, exit code 1:

```
1
1
1
1
1000    0   /
187
7.0
日本
258
0 0 0
AbCdAbCdAbCd -551369
0 0 0
0 0 0
0.00275
x
140
551368
0 0
0 0
0 0
0 0
x
True
0.5
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz233.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz233.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz233.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='日本'`.

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
