**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/40668578955 (seed `2075400536`, CPython 3.12, modes default+ir) found a DIFF: `exit code cpython=1 ail=0; line 8: cpython='<end>' ail='73'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075400536 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
from dataclasses import dataclass


@dataclass
class Pt:
    a: int
    b: int
    c: float
    name: str
    items: list[int]


def bump(p: Pt, k: int) -> int:
    p.a += k
    p.items.append(k)
    return p.a + len(p.items)


def h0(n: int, a: int) -> int:
    if n <= 0:
        return (a * 7 + 2) % 84003
    return (h0(n - 1, (a * 7 + n) % 84003) + 2) % 84003


def main() -> int:
    pt0: Pt = Pt(0, 0, 1e-7, 'hello', [])
    try:
        if ((100.75 - 3.0) <= (1.25 * 123456.789)):
            raise RuntimeError
    except RuntimeError:
        print(-87)
    finally:
        print(139)
    try:
        print(('hello' + '-7'), ('x'[1] >= 'café'))
    except IndexError:
        print(-12)
    finally:
        print(100)
    v1: list[int] = []
    try:
        v1 = [(3037000499 // 92), (31 >> 6)]
    except ZeroDivisionError:
        print(-26)
    v1.append(v1.count(9))
    try:
        v1.pop()
    except IndexError:
        print(-26)
    print(76)
    print(("%-4d|" % 72))
    try:
        v1.sort(reverse=True)
    except ValueError:
        if ((36 - 28) != 53):
            if ('ab'[0:].endswith('d')):
                print((min(81, 88) < 56))
        else:
            print(max(52, 6), (abs(1.25) ** 0.5))
    else:
        try:
            print((round((123456.789 // 3.0)) != min(52, 76)), 'a,b,c'[:2], (1e-7 - 123456.789))
            v2: int = 84
            v2 >>= 6
        except KeyError:
            if ((68 + 6) == (51 << 12)):
                pt0.a = (29 // -1)
                v3: int = 0
                try:
                    v3 = v1[2]
                except IndexError:
                    print(-39)
            else:
                v1.reverse()
            v4: int = max(max(28, 30), (49 & 75))
        else:
            if (((v1.index((67 + -9223372036854775807)) < (50 - 63)) or (41 <= (90 + -2))) and (round((0.3 + 123456.789)) >= (91 - 0))):
                pt0.items.append(255)
            else:
                try:
                    if ('ab'[1:2] != 'a,b,c'):
                        assert (24 < (28 & 58)), "boom"
                except (AssertionError, KeyError):
                    print(-1)
            al5: list[int] = v1
            v1 += [2]
            print(len(v1), len(al5), sum(v1) - sum(al5))
        try:
            print(sum(v1))
            try:
                try:
                    if ((95 + 24) <= 43):
                        raise IndexError('m8')
                except IndexError:
                    print(-60)
                else:
                    print(91)
            except ZeroDivisionError:
                v1.sort()
            finally:
                print(250)
            al6: list[int] = v1
            al6.sort()
            print(len(v1), len(al6), sum(v1) - sum(al6))
        except KeyError:
            for i7 in range(1, 5, 1):
                print(((0.1 + 0.1) * float((78 + i7))))
                if ((0.5 + 123456.789) > abs(0.5)):
                    break
        except ZeroDivisionError:
            pt0.c += (0.3 / (abs(1.25) + 1.0))
            v8: bytes = (b"x" * 1)
    if ((27 + 23) < (52 * 1)):
        try:
            if (87 > 3):
                assert (not ((78 - 67) <= int((0.5 // 2.5)))), "boom"
        except (AssertionError, IndexError):
            print(-18)
        else:
            print(73)
        v9: dict[str, int] = {}
        v9['dd'] = 71
        v9['e'] = 76
        v9['c'] = 8
        v9['b'] = 77
    elif ((67 ** 2) != (92 % -8)):
        v10: bytes = b"abc"
        v1.sort(key=lambda q: (-q, q))
    else:
        try:
            v1.pop()
        except IndexError:
            print(-88)
        p11: Pt = Pt(89, 92, 3.0, 'café', [])
    v12: str = f'{abs(100.75):.0f}{round(float(len(v1))):05d}'[:]
    print((v12 + v12))
    v13: str = ('hello' + v12).replace(' ', 'XY')
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v1), sum(v1))
    print(v12)
    print(v13)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
-87
139
-12
100
76
72  |
True a, -123456.7889999
```

AIL stdout, exit code 0:

```
-87
139
-12
100
76
72  |
True a, -123456.7889999
73
1010000210100002
0 0 1e-07 hello 0
2 33010874
10100002
hello10100002
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz4.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz4.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz4.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|exit code cpython=N ail=N; cpython='<end>' ail='N'`.

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
