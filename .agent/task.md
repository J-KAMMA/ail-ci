**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41569692800 (seed `2076003115`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=3; line 6: cpython='-67' ail='-31'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076003115 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 5 + 1) % 6003
    return (h0(n - 1, (a * 7 + n) % 6003) + 3) % 6003


def h1(a: int, b: int) -> int:
    v1: int = b
    v2: str = ""
    try:
        v2 = f'{round((1e10 / (abs(123456.789) + 1.0))):3d}{(a // 8):05d}{(1.25 % 7.0):8.3f}'
    except ZeroDivisionError:
        print(-89)
    v3: list[int] = []
    try:
        v3 = [(v1 % 1), 3037000499]
    except ZeroDivisionError:
        print(-46)
    print(len(v2))
    print((not (v1 < (b // 4))))
    if ('café'.rstrip() >= 'ab'[:2]):
        return v3.index(len(v3))
    return ((v1 | v1) + abs(89))


def main() -> int:
    v4: list[int] = [(18 - 49)]
    try:
        print(((55 % 98) - (98 + 33)))
    except ZeroDivisionError:
        print(-47)
    v5: int = int(1e-7)
    if ((68 + v5) >= 2):
        v6: int = max((v5 + v5), 10)
        print(len(v4))
        print((b"hello" * 2).decode())
    try:
        print(((100.75 - 1.25) / len(v4)))
    except ZeroDivisionError:
        print(-60)
    try:
        al7: list[int] = v4
        al7.reverse()
        print(len(v4), len(al7), sum(v4) - sum(al7))
        v8: set[int] = set(v4)
        for i9 in range(4):
            v10: str = str((7.0 - 1e-7))
            try:
                try:
                    if ('hello'.endswith(' ')):
                        raise ZeroDivisionError('m2')
                except ZeroDivisionError:
                    print(-10)
                if ((i9 * v5) > round(float((-i9)))):
                    continue
                v8.add(i9)
            except ZeroDivisionError:
                print(sum(al7))
            else:
                if (0.3 > (1e10 / (v5 + i9))):
                    break
            for i11 in al7:
                v12: dict[str, int] = {}
                try:
                    print(((i11 ** 2) + (3 // i11)))
                except ZeroDivisionError:
                    print(-60)
    except KeyError:
        v13: list[int] = list(range(2, 5, 3))
    except ZeroDivisionError:
        try:
            v5 = v5
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-92)
        try:
            if (((-3 | 93) / 4) > float((~v5))):
                assert ((49 - v5) == (v5 << 10)), "boom"
        except AssertionError:
            print(-67)
        finally:
            print(118)
    try:
        v5 = ((v5 ** 1) - max(v4))
    except ValueError:
        print(-85)
    try:
        if ((v5 >= v5) and (' pad ' != 'abc')):
            raise IndexError
    except (IndexError, ValueError):
        print(-6)
    else:
        print(66)
    for i14 in v4:
        v15: list[int] = []
        print((123456.789 - 1e10), str(min(56, i14)))
        for i16 in range(1, 13, 1):
            v5 = ((9223372036854775807 & i14) + i14)
            v5 <<= 9
    print(0.5)
    if (('abc' == '-'.join('q q'.split('a'))) and (not ((v5 ^ v5) <= v5))):
        try:
            v17: dict[str, int] = {}
        except IndexError:
            v18: float = 1e10
            print(-9)
        finally:
            print(292)
    elif ((2 + 70) <= (v5 + 13)):
        v19: dict[str, int] = {}
        v19['a'] = 62
        v19['a'] = 84
        v19['c'] = 83
        try:
            print(str((79 % 3)).replace('a', 'XY'))
        except ZeroDivisionError:
            print(-73)
    else:
        v4.sort(key=lambda q: (-q, q))
    try:
        if (('x'[2] >= ("%03d" % (-9223372036854775807 ** 2))) or ('日本' in ' pad '.strip())):
            assert (62 > (v5 + v5)), "boom"
    except (AssertionError, KeyError):
        print(-88)
    else:
        print(66)
    print(len(v4))
    v4.append(v5)
    print(((v5 + 64) >> 5))
    print(len(v4), sum(v4))
    print(v5)
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
-76
1
hellohello
99.5
1 1 0
-67
118
-6
-9999876543.211 -31
0.5
1
```

AIL stdout, exit code 3:

```
-76
1
hellohello
99.5
1 1 0
-31
960
-6
-9999876543.211 -31
```

AIL stderr:

```
AIL limit: int_overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz219.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz219.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz219.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='-N' ail='-N'`.

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
