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
