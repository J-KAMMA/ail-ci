**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/41325393110 (seed `2075816576`, CPython 3.12, modes default+ir) found a DIFF: `line 14: cpython='113' ail='-2'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2075816576 -o prog.py`, if that tree has it).

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


def h0(a: int, b: int) -> int:
    v1: int = ((99 & 23) - (b - a))
    v2: str = f'{33:d}'
    v3: list[int] = []
    for i4 in v3:
        if (-1 > 3):
            break
        b = v1
    print(('Zed'.replace(' ', 'XY') * 3))
    v3.append(v3.count(sum(v3)))
    if ((a % (abs(b) + 1)) > round((0.3 // 2.5))):
        return (21 & v1)
    return (round((0.5 - 1.25)) & (38 // -7))


def h1(a: int, b: int) -> int:
    v5: int = 3
    v6: str = ' pad '.replace('a', '-').upper()
    v7: list[int] = []
    v8: str = ""
    try:
        v8 = str((a // a))
    except ZeroDivisionError:
        print(-49)
    print(((abs(0.5) ** 0.5) - (100.75 * 0.5)))
    if ('a,b,c'.replace(' ', '-') < b"hello".decode()):
        for i9 in v7:
            try:
                print((b % len(v8)))
            except ZeroDivisionError:
                print(-7)
            if ((i9 + a) <= 72):
                break
            p10: Pt = Pt(37, 77, 0.1, v8, [])
        try:
            v7.append(h0((43 - a), v7.count(a)))
        except (IndexError, KeyError, ValueError, ZeroDivisionError):
            print(-47)
    else:
        try:
            if ((v5 > 3) or ((v5 * 76) != (b + 67))):
                raise ZeroDivisionError('m2')
        except ZeroDivisionError:
            print(-17)
        finally:
            print(177)
    if '3.5'.isupper():
        return (83 + 42)
    return ((a | 40) % a)


def h2(n: int, a: int) -> int:
    if n <= 0:
        return (a * 6 + 0) % 15003
    return (h2(n - 1, (a * 1 + n) % 15003) + 8) % 15003


def main() -> int:
    pt0: Pt = Pt(9, 6, 3.0, 'ab', [])
    v11: set[int] = {-5, 0}
    v13: list[int] = [(c12 ^ c12) for c12 in range(3) if c12 % 2 == 0]
    try:
        if ('q q'.strip() >= 'a,b,c'.replace(' ', '-')):
            assert ('café' in '-7'), "boom"
    except AssertionError:
        print(-19)
    finally:
        print(148)
    v13.sort(reverse=True)
    p14: Pt = Pt(77, 16, 0.3, '-7', [])
    print((15 * 65), 35, (44 // (abs(52) + 1)))
    print((abs(0.5) < (abs(7.0) ** 0.5)))
    print(0.1)
    al15: list[int] = v13
    al15.append(3)
    print(len(v13), len(al15), sum(v13) - sum(al15))
    try:
        w16: int = 0
        while w16 < 1:
            w16 += 1
            al17: list[int] = al15
            al15.append(5)
            print(len(al15), len(al17), sum(al15) - sum(al17))
            al18: list[int] = al17
            al17.sort()
            print(len(al17), len(al18), sum(al17) - sum(al18))
        if (('日本' + 'Zed') != str((1e-7 / (abs(3.0) + 1.0)))):
            print(((82 + 255) == (22 << 7)), (75 & 47))
            v19: str = ""
            try:
                v19 = (f'{min(80, -7)}{al15.pop():<4}' + 'ab')
            except IndexError:
                print(-52)
        elif (round(max(2.5e-3, 1e-7)) > (34 + 85)):
            try:
                v11.update({-5, -5, -5})
                try:
                    v11.remove(1)
                except KeyError:
                    print(-62)
            except ValueError:
                al15 += [1, (50 + 37)]
            finally:
                print(217)
        for i20 in range(3, 5, 1):
            if ('abc'.startswith(' ')):
                v11.add(round((abs(1e-7) ** 0.5)))
                print(min(123456.789, 123456.789), (i20 - i20), ('a,b,c' in ('café' + 'q q')))
            elif (('3.5' * 2) < ('AbCd' + 'AbCd')):
                if ('hello' in ('abc' + ' pad ')):
                    continue
                print(((i20 & i20) / 4), -6)
            else:
                print(12)
    except KeyError:
        if (44 > 3):
            v21: str = b"x".decode()[0:]
            for i22 in v21:
                print(pt0.name, sum(pt0.items))
                if (not (v21.count('b') > 11)):
                    continue
    except ValueError:
        v23: str = ""
        try:
            v23 = (f'{'abc':>8}{(3 + 49):>6}{ord(b"12".decode()[0]):>6}' + '-'.join('a,b,c'.split(' ')))
        except IndexError:
            print(-23)
        if ((91 + -1) > 3):
            if (0.5 <= max(0.3, 100.75)):
                print(p14.name, sum(p14.items))
                al24: list[int] = al15
                al24.reverse()
                print(len(al15), len(al24), sum(al15) - sum(al24))
            v13.reverse()
        else:
            for i25 in range(0, 4):
                if ('abc'[-2:-1].startswith('d')):
                    break
                try:
                    if '3.5'.islower():
                        assert (not ((19 ^ 1) == 82)), "boom"
                except (AssertionError, KeyError):
                    print(-40)
    for i26 in al15:
        try:
            if 'AbCd'.islower():
                assert (i26 >= (i26 * 96)), "boom"
        except (AssertionError, IndexError):
            print(-87)
        finally:
            print(113)
        if ((i26 // 3) >= len(v11)):
            break
    v13.sort(reverse=True)
    try:
        if ((31 << 0) < (13 - 12)):
            try:
                print((int('-'.join(' pad '.split(','))) - len(v13)))
            except ValueError:
                print(-78)
        elif ((f'{(0.5 / (70 ** 2)):.2f}'.startswith(' ')) or ('3.5' in f'#{'abc':>8}')):
            v11.remove(-2)
    except KeyError:
        print(-48)
    v27: set[int] = set(al15)
    try:
        v11.discard((62 // 3))
    except ZeroDivisionError:
        print(-81)
    print(((89 // (abs(4611686018427387904) + 1)) - len(v11)))
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v11), sum(v11), max(v11) if len(v11) > 0 else 0)
    print(len(v13), sum(v13))
    print(p14.a, p14.b, p14.c, p14.name, len(p14.items))
    print(len(al15), sum(al15))
    print(len(v27), sum(v27), max(v27) if len(v27) > 0 else 0)
    return 0


main()
```

CPython 3.12 stdout (first 2500 bytes), exit code 0:

```
-19
148
975 35 0
True
0.1
3 3 0
4 4 0
4 4 0
False 11
0.75 -6
1.0 -6
113
113
113
-2
9 6 3.0 ab 0
2 -5 0
3 3
77 16 0.3 -7 0
3 3
2 3 3
```

AIL stdout, exit code 0:

```
-19
148
975 35 0
True
0.1
3 3 0
4 4 0
4 4 0
False 11
0.75 -6
1.0 -6
113
113
-2
9 6 3.0 ab 0
2 -5 0
2 0
77 16 0.3 -7 0
2 0
1 0 0
```

AIL stderr:

```

```

**What to do.**
1. Save the program as `/tmp/probes/fz211.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz211.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz211.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='N' ail='-N'`.

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
