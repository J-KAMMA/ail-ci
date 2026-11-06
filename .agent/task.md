**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42281367784 (seed `2076319083`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 4: cpython='286' ail='0.0'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076319083 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 1) % 47003
    return (h0(n - 1, (a * 2 + n) % 47003) + 1) % 47003


def h1(a: int, b: int) -> int:
    v1: int = a
    v2: str = f'{(a % (abs(a) + 1)):<4}{a:d}'
    v3: list[int] = [(b << 6), 47, (45 // (abs(a) + 1)), max(b, a), a]
    v4: list[int] = sorted(v3)
    if (((v1 + -9) != 29) or (f'{float(v1):>10.1f}{(0.1 + 0.1):8.3f} = ' != str((v1 - b)))):
        return (86 + 12)
    return (sum(v3) - (b ** 1))


def main() -> int:
    v5: int = 0
    try:
        v5 = (min(76, 46) // (21 * 2))
    except ZeroDivisionError:
        print(-88)
    v6: str = (f'{round(0.5):>6}{v5:<4} = ' + '-7'[:2])
    for i7 in v6:
        v6 += ('abc' + 'abc')
    try:
        try:
            print(f'{(v5 // -3):05d}', (v5 > 3))
        except ZeroDivisionError:
            print(-5)
        if ((-1 + 56) < int((1e10 % 0.75))):
            for i8 in range(-2, 5):
                print(float(round((0.3 / (abs(100.75) + 1.0)))))
                if ((92 - i8) <= (v5 - 26)):
                    break
            print(min((v5 + v5), v5))
    except ValueError:
        print(((2.5e-3 - 2.5e-3) / (abs(min(0.5, 0.5)) + 1.0)))
        for i9 in v6:
            try:
                v11: list[int] = [93 for c10 in range(0) if c10 % 2 == 1]
                if (round((3.0 // 3.0)) == (v5 // v5)):
                    break
            except ZeroDivisionError:
                v12: str = f'{(64 % (abs(71) + 1)):>6}{(123456.789 + 3.0):.3f}{(3.0 / (abs(1e10) + 1.0)):.3f}'
                v13: list[int] = list(range(2, 7, 1))
            else:
                v14: list[int] = [v5]
                al15: list[int] = v14
                v14.append(3)
                print(len(v14), len(al15), sum(v14) - sum(al15))
    except KeyError:
        try:
            print(((94 ** 1) ** 3))
        except ZeroDivisionError:
            print(-10)
    else:
        try:
            print((len(v6) - int((7.0 / (73 // (abs(v5) + 1))))))
        except ZeroDivisionError:
            print(-73)
        finally:
            print(179)
        if (int('café') >= (v5 // 5)):
            try:
                if ((v5 // (abs(v5) + 1)) > v5):
                    raise ValueError('m3')
            except ValueError:
                print(-17)
    finally:
        print(286)
    v16: list[int] = [v5, (28 + 20), min(v5, v5), (~v5), (v5 - 67)]
    for i17 in v16:
        if ((v5 % (abs(i17) + 1)) != ("%-4d|" % (i17 + v5)).count('ab')):
            continue
        try:
            if (not (str(min(v5, i17)) < '-'.join(v6.split(',')))):
                v18: list[str] = []
                try:
                    v18 = str(int(' pad ')).split(' ')
                except ValueError:
                    print(-10)
                v18.reverse()
                print(((0.3 * 1.25) * 1e10))
            elif (float(41) > 2.5e-3):
                print(b"hello"[:2].decode())
            else:
                try:
                    print((-ord(v6[0])))
                except (IndexError, ZeroDivisionError):
                    print(-11)
        except (IndexError, ZeroDivisionError):
            print(-43)
        for i19 in range(2, 5, 1):
            print(('-'.join(' pad '.split('a')) * 0))
            print(((1e-7 / (abs(0.1) + 1.0)) <= (abs(2.5e-3) ** 0.5)), v6.upper())
    v20: bytes = b"x"[1:]
    for i21 in v6:
        try:
            v16.pop()
        except IndexError:
            print(-3)
    try:
        if ('x'[0] >= 'ab'[1:-1]):
            assert ((v5 << 8) == min(v5, 32)), "boom"
    except (AssertionError, IndexError):
        print(-26)
    print(v16.count(-9))
    al22: list[int] = v16
    if len(al22) > 0:
        al22[0] = 3
    print(len(v16), len(al22), sum(v16) - sum(al22))
    w23: int = 0
    while w23 < 2:
        w23 += 1
        try:
            print(((~w23) < 93), ord(str(1.25)[1]))
        except IndexError:
            print(-17)
        try:
            print((100.75 / len(v6)))
        except ZeroDivisionError:
            print(-38)
    try:
        print(float((v5 + 22)))
    except ZeroDivisionError:
        print(-15)
    if (f'{(1.25 / (abs(2.5e-3) + 1.0)):>10.1f}{v6:<6}{28:>6}'.startswith('d')):
        print((2.5e-3 - (3.0 * 0.3)))
        al22.extend(al22)
        v24: float = 1e10
    elif (max(v5, v5) > 3):
        v25: float = ((v5 - 63) / 8)
        try:
            if ((('hello' in v6) and (v6.startswith(' '))) or (v6[3] != ("%03d" % (v5 + 93)))):
                print(float(v5))
            elif (((3037000499 // v5) != (v5 - v5)) and (len(v20) > 3)):
                v26: list[str] = 'x'[-2:4].split(' ')
            else:
                v27: float = ((v25 - v25) * (v25 - 1e10))
        except KeyError:
            try:
                del al22[3]
            except IndexError:
                print(-88)
        except ValueError:
            if ('-'.join(v6.split('a')) == ('x' + v6)):
                v28: float = v25
                v29: float = (abs((0.1 - v28)) ** 0.5)
                v30: float = ((v28 + 1e10) * (v28 + 0.3))
            v31: list[int] = list(range(-3, 7, 1))
        finally:
            print(254)
    print(v5)
    print(v6)
    print(len(v16), sum(v16))
    print(len(v20), v20.decode())
    print(len(al22), sum(al22))
    return 1


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
-0001 False
105
179
286
```

AIL stdout, exit code 0:

```
-0001 False
105
179
0.0
286
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-3
-26
0
0 0 0
True 46
0.9595238095238096
True 46
0.9595238095238096
23.0
1
     01    = -7abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabc
0 0
0 
0 0
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz237.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz237.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz237.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='N' ail='N.N'`.

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
