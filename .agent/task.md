**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41401383270 (seed `2075907148`, CPython 3.12, modes default+ir) found a DIFF: `line 7: cpython='<end>' ail='0.17496355305594127'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075907148 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 6 + 7) % 24003
    return (h0(n - 1, (a * 5 + n) % 24003) + 7) % 24003


def main() -> int:
    try:
        print('-7'[:4].count('a'))
    except (IndexError, KeyError, ValueError, ZeroDivisionError):
        print(-85)
    try:
        print(float((80 % 96)))
    except ZeroDivisionError:
        print(-26)
    v1: list[int] = list(range(0, 11, 3))
    w2: int = 0
    while w2 < 1:
        w2 += 1
        try:
            if (97 < w2):
                raise RuntimeError('m9')
        except RuntimeError:
            print(-39)
        else:
            print(41)
        v1 += v1
        v3: str = 'ab'[0:2][:4]
    al4: list[int] = v1
    al4.reverse()
    print(len(v1), len(al4), sum(v1) - sum(al4))
    try:
        if (h0(9, int(float(int(2.5e-3)))) > 3):
            v5: list[int] = list(range(2, 11, 1))
        elif (str((85 | 80)) < ('café' + ' pad ')):
            try:
                v1.remove(len(('日本' + 'AbCd')))
            except ValueError:
                print(-33)
    except ValueError:
        print(-88)
    for i6 in range(7, 3, -1):
        v7: float = float(i6)
        try:
            print(((0.5 / (abs(v7) + 1.0)) * (abs(v7) ** 0.5)))
            try:
                al4.pop()
            except IndexError:
                print(-6)
        except IndexError:
            v8: set[int] = set(al4)
            if (i6 > 3):
                v9: str = ('Zed' + 'abc').rstrip()
            else:
                if (((i6 % (abs(i6) + 1)) <= len(al4)) or ((i6 ** 2) >= 21)):
                    break
        except ValueError:
            try:
                print((((3037000499 << 0) <= (i6 // i6)) or ((i6 % (abs(i6) + 1)) != 59)))
            except ZeroDivisionError:
                print(-96)
        else:
            try:
                print(f'{'a,b,c':<6}')
            except KeyError:
                print((i6 - (25 + i6)))
            except ValueError:
                if 'AbCd'.isupper():
                    break
            else:
                if ((i6 < int(' pad ')) or (((i6 + i6) / 3) < (v7 // 3.0))):
                    break
    v1.insert(0, sum(al4))
    if (27 > int('日本')):
        try:
            if (len(('AbCd' * 2)) <= (91 - 68)):
                w10: int = 0
                while w10 < 4:
                    w10 += 1
                    v11: set[int] = set(v1)
                    print(b"a,b"[1:-1].decode())
                    if (("<%5d>" % ('x' * 3).find('abc')).endswith('he')):
                        break
            elif ((-87) == (23 // (abs(53) + 1))):
                w12: int = 0
                while w12 < 5:
                    w12 += 1
                    v13: int = 0
                    try:
                        v13 = al4.count((36 % w12))
                    except ZeroDivisionError:
                        print(-67)
                    print(float((w12 * w12)))
                    print((b"ab" + b"ab").decode())
                try:
                    if ('abc'.rstrip() < b"a,b".decode()):
                        raise IndexError('m8')
                except IndexError:
                    print(-31)
            else:
                for i14 in range(1):
                    try:
                        al4.insert(3, (i14 // 6))
                    except ZeroDivisionError:
                        print(-41)
        except ZeroDivisionError:
            print(-41)
    elif (not (str((26 << 3)) != b"12".decode())):
        v15: dict[str, int] = {}
    else:
        try:
            if (str((47 ^ 93)) >= '-'.join('x'.split('a'))):
                assert ((87 + 34) != (-5 ** 0)), "boom"
        except AssertionError:
            print(-88)
        finally:
            print(148)
        print((' pad ' in str((32 << 7))))
    print(22)
    al16: list[int] = v1
    v1.sort()
    print(len(v1), len(al16), sum(v1) - sum(al16))
    if (not (53 != int(max(3.0, 7.0)))):
        v17: list[str] = '3.5'.replace('l', '-').split(',')
        try:
            print(((5 > 3) or ((31 - 97) >= (61 % 7))), 'q q'[1:2])
        except ZeroDivisionError:
            print(-72)
        print((123456.789 % 0.75), ('hello' + '日本'), max(3.0, 2.5e-3))
    v18: str = f'{'abc':>8}{100.75:>10.1f}'
    al19: list[int] = al16
    al19.reverse()
    print(len(al16), len(al19), sum(al16) - sum(al19))
    for i20 in v18:
        v21: str = 'x'
        if ('ab'.lower() == i20):
            break
        v22: str = str((255 & -7))
    v18 = '日本'
    try:
        v23: str = (('日本' + 'Zed') + str('x'[:].count('a')))
    except KeyError:
        for i24 in range(0, 5):
            al25: list[int] = al19
            if len(al25) > 0:
                al25[0] = 2
            print(len(al19), len(al25), sum(al19) - sum(al25))
        for i26 in range(3, 10, 3):
            w27: int = 0
            while w27 < 3:
                w27 += 1
                al28: list[int] = al4
                al4.sort()
                print(len(al4), len(al28), sum(al4) - sum(al28))
                if (v18 in v18[2]):
                    continue
    finally:
        print(246)
    print(len(v1), sum(v1))
    print(len(al4), sum(al4))
    print(len(al16), sum(al16))
    print(v18)
    print(len(al19), sum(al19))
    return 0


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
0
80.0
41
8 8 0
0.16535945694153692
a,b,c
```

AIL stdout, exit code 1:

```
0
80.0
41
8 8 0
0.16535945694153692
a,b,c 
0.17496355305594127
a,b,c 
0.18633899812498247
a,b,c 
0.2
a,b,c
```

AIL stderr:

```
ValueError: invalid literal for int() with base 10: '日本'
```

**What to do.**
1. Save the program as `/tmp/probes/fz215.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz215.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz215.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='<end>' ail='N.N'`.

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
