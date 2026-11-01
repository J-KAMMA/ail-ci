**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41281812892 (seed `2075807758`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 16: cpython='<end>' ail='a,b,c False'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075807758 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
def h0(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        if t > 8:
            break
        t += abs(x) + 1
    return t


def h1(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 8) % 49003
    return (h1(n - 1, a + 3) * 1 + h1(n - 1, a - 1) + n) % 49003


def main() -> int:
    v1: set[int] = {8}
    if ((88 - 26) != len(v1)):
        v2: str = '-'.join('-'.join('AbCd'.split(',')).split('a'))
        v3: str = f'{(26 + 57):>6}{(100.75 * 3.0):.3f}'.replace(' ', 'XY')
    elif (str(86) == 'abc'[-2:]):
        v4: str = ('a,b,c' + 'café'[:-1])
    v5: float = 7.0
    v6: list[int] = [3] * 2
    for i7 in range(6, 0, -1):
        try:
            print(((i7 // (abs(75) + 1)) % -7))
        except ZeroDivisionError:
            print(-40)
        v8: str = '12'.replace(' ', '-')[:]
    print((b"a,b" + b"a,b").decode())
    print(('日本'[1:-1] * 3))
    w9: int = 0
    while w9 < 2:
        w9 += 1
        for i10 in range(4):
            v5 -= (100.75 % 7.0)
        print('Zed'.strip(), (w9 >> 8), (20 * w9))
        for i11 in v6:
            try:
                if (((w9 << 0) <= w9) and (1e-7 < (max(w9, 17) / 4))):
                    try:
                        print(int((v5 % 2.5)))
                    except (IndexError, KeyError, ValueError, ZeroDivisionError):
                        print(-98)
                    v5 -= float(max(98, w9))
                    v5 = v5
                else:
                    v12: bool = ('café'.upper().endswith(' '))
                    try:
                        v1.discard((76 % -5))
                    except ZeroDivisionError:
                        print(-11)
            except ZeroDivisionError:
                print(-70)
            v13: bool = 'café'.isdigit()
            v13 = ('abc' in 'café')
    try:
        v1.remove(12)
    except KeyError:
        print(-59)
    try:
        v14: int = (66 - 34)
    except IndexError:
        w15: int = 0
        while w15 < 3:
            w15 += 1
            if (21 >= (3037000499 * 98)):
                break
            if ((w15 % (abs(24) + 1)) == (w15 - w15)):
                if (('a,b,c' + 'abc') < 'Zed'):
                    break
                v5 = (w15 / 3)
            elif ('AbCd'.startswith(' ')):
                if (round((1e-7 * v5)) == (w15 - 41)):
                    continue
        print('a,b,c', (2 >= h0(v6)))
    else:
        for i16 in range(4):
            if (('ab' * 0) != 'ab'[1:4]):
                v6.sort(reverse=True)
            if (i16 < v6[3]):
                v17: str = ("<%5d>" % len(v6))
                print(v5)
            elif ((i16 << 11) in v1):
                print(('12' * 1).replace('l', ''))
            print((v5 / (abs(v5) + 1.0)), ('q q'.isalpha() and ((44 * 255) <= i16)))
        try:
            for i18 in range(4):
                al19: list[int] = v6
                al19 += [0]
                print(len(v6), len(al19), sum(v6) - sum(al19))
                print(v6 == al19)
        except KeyError:
            v1.add(92)
    try:
        if ((len(v1) > 3) or ((2 % (abs(-3) + 1)) >= (3 - 58))):
            assert (('café'.lstrip() == 'café') and ((30 - 3037000499) > (48 ** 2))), "boom"
    except AssertionError:
        print(-80)
    finally:
        print(199)
    try:
        v6.pop()
    except IndexError:
        print(-80)
    w20: int = 0
    while w20 < 2:
        w20 += 1
        print((b"a,b" * 3).decode())
    v21: list[int] = [74]
    print((len(' pad ') + (-2 % (abs(-9) + 1))))
    print(len(v1), sum(v1), max(v1) if len(v1) > 0 else 0)
    print(v5)
    print(len(v6), sum(v6))
    print(len(v21), sum(v21))
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
0
0
0
0
0
0
a,ba,b

Zed 0 20
1
0
Zed 0 40
1
1
-59
```

AIL stdout, exit code 0:

```
0
0
0
0
0
0
a,ba,b

Zed 0 20
1
0
Zed 0 40
1
1
-59
a,b,c False
-80
199
a,ba,ba,b
a,ba,ba,b
13
1 8 8
-407.0
1 3
1 74
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz210.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz210.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz210.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='a,b,c False'`.

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
