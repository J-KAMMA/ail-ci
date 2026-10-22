You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

1. **`math.floor`/`math.ceil` ignore `__floor__`/`__ceil__`** — `/tmp/rprobes/floorceil_dunder.py`:
```python
import math
class F:
    def __float__(self): return 2.5
    def __floor__(self): return 99
    def __ceil__(self): return 100
class G:
    def __floor__(self): return 41
    def __ceil__(self): return 42
```
Expected CPython: `floor F 99`, `ceil F 100`, `floor G 41`, `ceil G 42`.
Actual both builds: `floor F 2`, `ceil F 3`, `floor G TypeError must be real number, not G`, `ceil G TypeError must be real number, not G`. `G` has no `__float__`, so `checknum` runs before the `__floordiv__` branch; `F` converts through `float` and ignores its `__floor__`/`__ceil__`. This can return a silently wrong value.

2. **`checknum` leaks an internal `NotImplementedError` for class/function values** — `/tmp/rprobes/classtype.py`, `/tmp/rprobes/fn.ail`:
```python
import math
class P:
    def __init__(self): self.x = 1
def f(): return 1
math.sin(P); math.sin(f); math.floor(P); math.fsum([P])
```
Expected CPython: `TypeError must be real number, not type` / `... not function`.
Actual both builds: `NotImplementedError hasattr() on a 'type' value is not built on the general path ...` / `... on a 'function' value ...`. This is a runtime compiler limitation leaking out, not a named compile-time refusal.

Other unlisted pre-existing differences (not introduced here): `divmod(1.0, 0.0)` says `float floor division by zero` instead of `float divmod()`; `math.trunc` ignores `__trunc__` and returns a value for `__index__` objects where CPython raises.

Probe both builds with `bash ~/tools/cmp.sh`, add each fixed case to the tests, then commit. If a finding cannot be fixed safely, refuse the construct by name at compile time instead of leaving a silent wrong answer.

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

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
