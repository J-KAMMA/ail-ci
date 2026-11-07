**Fix one silent difference from CPython found by the daily fuzzer.** The fuzz-lab run https://github.com/J-KAMMA/ail-ci/actions/runs/42398208962 (seed `2076418519`, CPython 3.12, modes default+ir) found a DIFF: `line 1: cpython='False -7 -147573952589676412912' ail='158'`. The generated program below is the whole reproducer (generator: `python3 lab/fuzz/gen.py 2076418519 -o prog.py`, if that tree has it).

Program (`prog.py`; AIL compiles the same text as `prog.ail` with `--syntax python`):

```python
import sys

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
        return (a * 2 + 3) % 61003
    return (h0(n - 1, (a * 1 + n) % 61003) + 8) % 61003


def h1(xs: list[int]) -> int:
    t: int = 0
    for x in xs:
        t = (t * 6 + x) % 1000003
    return t


def h2(a: int, b: int) -> int:
    v1: int = 0
    v2: str = ""
    try:
        v2 = '3.5'[0]
    except IndexError:
        print(-56)
    v4: list[int] = []
    try:
        v4 = [int(str((a * v1))) for c3 in range(1) if c3 % 2 == 0]
    except ValueError:
        print(-43)
    if ((((a % 10) > (40 ** 0)) or ((0.3 / 2) < 3.0)) or ((a <= (60 - 46)) and ('3.5' in (v2 * 1)))):
        w5: int = 0
        while w5 < 2:
            w5 += 1
            p6: Pt = Pt(1, w5, 3.0, 'Zed', [])
        print((2.5e-3 + 0.3))
    else:
        a = len(v2)
    v7: int = 0
    try:
        v7 = ((87 + 18) % 2)
    except ZeroDivisionError:
        print(-76)
    print((11 % (abs(76) + 1)))
    if ((~a) > 3):
        return max(62, 82)
    return ((b // a) - int((len(v2) / 4)))


def main() -> int:
    pt0: Pt = Pt(4, 9, 0.5, 'Zed', [])
    w8: int = 0
    while w8 < 1:
        w8 += 1
        try:
            print((not (w8 != (38 % 9))), '-7'.replace('l', ''), str((-9223372036854775807 << 4)))
        except ZeroDivisionError:
            print(-95)
        finally:
            print(158)
        for i9 in range(2, 6):
            v10: list[int] = [3] * 5
            v10.insert(1, len(v10))
        print(((78 >> 1) - 3037000499))
    v12: list[int] = [c11 for c11 in range(3) if c11 % 2 == 1]
    try:
        print(v12.count(ord(f'#'[1])))
    except (IndexError, ZeroDivisionError):
        print(-5)
    print((' pad '.startswith('d')), 'abc'.replace('l', 'XY'))
    v13: list[int] = [(-0)]
    v14: int = 0
    try:
        v14 = round(float((74 - 79)))
    except ZeroDivisionError:
        print(-84)
    print(('café' + '3.5').upper())
    for i15 in range(4):
        if ('AbCd' in str(40)):
            continue
    print(((v14 & v14) - (v14 ** 0)))
    w16: int = 0
    while w16 < 4:
        w16 += 1
        v17: bool = (v14 < (98 ** 0))
        v14 <<= 1
        if (len(v12) >= ('café' * 0).count('b')):
            v13 += v12
    print(pt0.a, pt0.b, pt0.c, pt0.name, len(pt0.items))
    print(len(v12), sum(v12))
    print(len(v13), sum(v13))
    print(v14)
    return 1


sys.exit(main())
```

CPython 3.12 stdout (first 2500 bytes), exit code 1:

```
False -7 -147573952589676412912
158
-3037000460
-5
False abc
CAFÉ3.5
-6
4 9 0.5 Zed 0
1 1
5 4
-80
```

AIL stdout, exit code 1:

```
158
```

AIL stderr:

```
OverflowError
```

**What to do.**
1. Save the program as `/tmp/probes/fz239.py` and run `bash ~/tools/cmp.sh /tmp/probes/fz239.py $PWD` on both builds (default, and `AIL_IR=1`). Confirm the difference still shows on this tree; if it does not, change nothing and say so.
2. Minimize: delete statements until a few lines still show the difference (keep each step if the difference stays). Name the construct.
3. Fix that one cause, or refuse the construct by name at compile time. Do not special-case the fuzzer program.
4. Add the minimized case (plus one or two close variants: other types, a value from an argument / list item / attribute) to a new `test_ail_fz239.py` that compares AIL with CPython on both builds, and run only that module and `test_ail_safetynet`, then commit.
5. List other differences you saw in your report. Keep the job short.

Signature of this finding (for the report): `DIFF|cpython='False -N -N' ail='N'`.

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
