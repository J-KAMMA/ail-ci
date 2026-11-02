**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41401383270 (seed `2075907166`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=0 ail=1; line 5: cpython='-34' ail='False'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075907166 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = (t * 7 + x) % 1000003
    return t


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 2 + 0) % 31003
    return (h1(n - 1, a + 3) * 4 + h1(n - 1, a - 2) + n) % 31003


def h2(a: int, b: int) -> int:
    v1: int = (b % (abs(b) + 1))
    v2: str = f'{max(0.3, 1e-7):>10.1f} = '.replace('a', 'XY')
    v4: list[int] = [(-1 - v1) for c3 in range(0) if c3 % 2 == 1]
    if ((f'{(1e-7 / (abs(0.3) + 1.0)):8.3f}{a:^7}{v2:>8}' != (v2 + v2)) and ((27 - b) > 3)):
        print(((0.5 + 0.1) == (2.5e-3 - 3.0)))
        print(b"Zed".decode())
    elif (not (str(min(v1, v1)).find(('abc' * 0)) >= (b - b))):
        print((v2 != f'{1.25:>10.1f}'), (123456.789 % 7.0))
        try:
            v4[0] = 92
        except IndexError:
            print(-66)
    v4.extend(v4)
    if ((72 * a) == b):
        return (a // -2)
    return h0(v4)


def main() -> int:
    v5: list[int] = [1, 2, 3]
    try:
        print(float((73 ** 1)))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-71)
    finally:
        print(129)
    v5.append(int(100.75))
    print(87)
    v6: int = ((97 ^ -5) - 15)
    w7: int = 0
    while w7 < 4:
        w7 += 1
        try:
            v6 *= v5[max(42, v6)]
        except IndexError:
            print(-82)
        w8: int = 0
        while w8 < 2:
            w8 += 1
            w9: int = 0
            while w9 < 5:
                w9 += 1
                v6 *= len(v5)
                try:
                    print((62 + v6), ((v5[(4611686018427387904 * w9)] > (89 * w9)) or ((w9 & 81) >= 9223372036854775807)), v5.count(h2(abs(w9), 20)))
                except (IndexError, KeyError, ValueError, ZeroDivisionError):
                    print(-34)
                finally:
                    print(166)
                if ('日本' != b"12".decode()):
                    continue
        v10: int = 0
        try:
            v10 = int(str(h0(v5)))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-3)
        finally:
            print(177)
    w11: int = 0
    while w11 < 4:
        w11 += 1
        print((not ((47 << 11) > 3)))
    try:
        del v5[1]
    except IndexError:
        print(-9)
    if (str((v6 + v6)).startswith('d')):
        print(("%-4d|" % (0 ^ v6)))
    elif (f'{(2 + 44):>6}' != f'{1e10:.0f}'):
        try:
            del v5[3]
        except IndexError:
            print(-92)
    else:
        try:
            print((int(str((v6 - v6))) - (48 // (abs(v6) + 1))))
        except ValueError:
            print(-24)
        finally:
            print(166)
        v12: int = 58
    print(len(v5), sum(v5))
    print(v6)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
73.0
129
87
-82
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
177
-82
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
177
-82
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
177
-82
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
-34
166
177
False
False
False
False
-92
3 104
-141444320894911613440622592
```

AIL stdout, exit code 1:

```
73.0
129
87
-82
False
Zed
-34
166
False
Zed
```

AIL stderr:

```
integer overflow
```

**What to do.**
1. Save the program as `/tmp/probes/fz216.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz216.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz216.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='-N' ail='False'`.

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
