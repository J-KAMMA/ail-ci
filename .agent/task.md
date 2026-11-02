**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
Change: `_ail_en_num` now passes only numbers plus `_ail_dec`/`_ail_fr` objects; new `_ail_en_mul` adds `str/bytes/bytearray/list/tuple` (not `range`) for `*` only; bytes/bytearray repetition accepts `__index__`; `dunderrt` inserts an instance `MUL/RMUL` guard before the big-int slow path.

Claims:
- `_ail_en_num`/`_ail_en_mul` change: verified in diff.
- `sequence_ops` test, DEVLOG, MANIFEST update: verified; `update_manifest.py --check` clean.
- `p_cmp`, `p_seq`, `p_pow` match CPython on both builds: verified.
- `p_dec` “member-on-left Decimal/Fraction matches”: **false** for `>`/`<=`/some `>=` (see defect 1).
- Reflected Decimal/Fraction differences unchanged from base: verified (`/tmp/base` = `45950d7`).
- Tests `test_ail_reintenum4`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: verified, 0 failed (215s + 288s).
- Commit `c983168`: verified.

Pre-existing (same on base and HEAD): reflected Decimal/Fraction (`Decimal * C.B`, `+`, `-`, `/`); `Decimal("3") == C.B` false; `"ab" * P()` with only `__index__`; `StrEnum * IntEnum` and reverse.

Unverified: instruction-count/speed impact (the new guard is on the cold multiply path).

VERDICT: FIX
1. IntEnum/IntFlag ordering against Decimal/Fraction now crashes or silently changes instead of matching CPython. Probe `/tmp/rprobes/rev_gt.py` (and `/tmp/rprobes/rev_dec2.py`):
   - `C.B > Decimal("2.5")`: expected `True`; both builds give `AttributeError 'Decimal' object has no attribute 'value'`.
   - `C.B <= Decimal("3")`: expected `True`; both builds give the same `AttributeError`.
   - `C.B > Fraction(5,2)` / `C.B <= Fraction(3,1)`: expected `True`; both builds give `AttributeError 'Fraction' object has no attribute 'value'`.
   - `C.B.__gt__(Decimal("2.5"))`: expected `NotImplemented`; both builds give `True`.
   Not pre-existing: base gave `TypeError '>' not supported...` (and correct `NotImplemented` from the dunder), so this change caused the new crash (/tmp/rprobes/base_gt.log vs head_gt.log).
2. A program with a class but no enum now generates different C. Probe `/tmp/rprobes/rev_unrel.py`: HEAD adds `if (a.tag == AIL_T_INST || b.tag == AIL_T_INST) return ail_dun_binop(... AIL_D2_MUL ...)` immediately before `ail__mul_slow`, while base does not; behavior is still CPython-identical. Per the “programs not using the feature must have unchanged C” rule, the new guard needs to be gated to programs that need enum dispatch.
[cost $0.0438, opencode tokens {"total": 2919172, "input": 91327, "output": 10593, "reasoning": 25572, "cache.write": 0, "cache.read": 2791680}]
    tool time: bash 16.9 min, write 0.0 min
        290s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_fil
        217s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_rei
         90s bash   cd /tmp/rprobes && python3 - <<'EOF' p='rev_dec2.py' s=open(p).read() s=s.replace('t("pow3dec", lambda: pow(C.
         79s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/rev_gt.py $PWD > /tmp/rprobes/head_gt.l
         79s bash   cd /home/runner/work/ail-ci/ail-ci && (bash ~/tools/cmp.sh /tmp/rprobes/rev_plain_deccmp.py /tmp/base > /tmp/r
         77s bash   cd /tmp/base && bash ~/tools/cmp.sh /tmp/rprobes/rev_gt.py $PWD > /tmp/rprobes/base_gt.log 2>&1; date; cat /tm
         35s bash   cd /tmp/base && (bash ~/tools/cmp.sh /tmp/rprobes/p_dec.py $PWD > /tmp/rprobes/base_dec.log 2>&1 &); cd /home/
         32s bash   cd /home/runner/work/ail-ci/ail-ci && (bash ~/tools/cmp.sh /tmp/rprobes/rev_dec2.py $PWD > /tmp/rprobes/head_r


--- ORIGINAL TASK ---
**IntEnum / IntFlag leftovers: `**`, cross-kind equality, ordering and divmod dispatch.**

Background: an old job (`intenum4`, accepted but its diff no longer applies) fixed these silent differences. On integ, `_AilIntEnum` in `python/pkg-v12/prelude_enum.py` has no `__pow__`/`__rpow__`, and its `__eq__` accepts any `_AilEnum` operand, so an IntEnum member equals a plain Enum member with the same value. Re-check each on today's integ first and fix only what still differs.

Reproducers (both builds, compare with CPython 3.12):

```python
from enum import Enum, IntEnum
class C(IntEnum):
    A = 1
    B = 3
class E(Enum):
    A = 1
print(C.B ** 2)                 # CPython 9; was TypeError
print(pow(C.B, 2), pow(C.B, 2, 5), 2 ** C.B)
print(C.A == E.A, E.A == C.A)   # CPython False False; was True
print(divmod(C.B, 2), divmod(7, C.B))
try: print(E.A < 2)
except TypeError as e: print(e)  # '<' not supported between instances of 'E' and 'int'
class P:
    def __index__(self): return 3
try: print(divmod(P(), 2))
except TypeError as e: print(e)  # plain __index__ is not divmod
print(5 % 0)  # check the text for int % 0: "integer modulo by zero"; // and divmod keep "integer division or modulo by zero"
```

Details from the old job (verify, do not copy the diff): 3-argument `pow()` with a float anywhere keeps the int-only message; plain `Enum` equality across classes returns `NotImplemented` so the other operand's `__eq__` runs; plain enum ordering raises the operator-specific `TypeError` naming both classes; IntEnum/IntFlag members keep int-subclass `divmod`; StrEnum follows the same cross-kind equality rule. Pass the values through a parameter, a list item, an attribute and a dict value as well. Never leave a silent difference.

Start from today's integ (it has exact bigints by default), read `git log --oneline -40` first, and do not reuse the old diff (old branch: `out/ci/intenum4.branch`, patch `out/ci/intenum4.patch` in the agents folder, reference only).

Add a CPython-compared test module `AIL_CURRENT/test_ail_reintenum4.py` registered in `ail_check.py` MODULES, run `python3 tools/update_manifest.py`, then only that module, the modules of the files you touched, and `test_ail_safetynet`. Commit.

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
