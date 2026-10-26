**Fix one pre-existing difference from CPython.** A reviewer of job `pre288` recorded these as already present before that job:

**Defects (new vs base, all named refusals of code that base compiles correctly):**

1. Parameter resolution still matches calls by bare function name across scopes (`calls_by_name`), the same root cause fixed for returns:
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
class F:
    def g(self, x): return x.f()
def g(a, x): return 0
def run(): return F().g(D())
print(run()); print(g(D(), C()))
```
Expected `3\n0`; actual compile refusal “the method .f() … also stores an instance field named f” on both builds.

2. A nested function inside a method treats its first parameter as `self` of that method’s class (`func_class` is propagated into nested defs):
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
class F:
    def __init__(self): self.f = lambda: 4
    def f(self): return 5
    def run(self):
        def inner(x): return x.f()
        return inner(D())
print(F().run())
```
Expected `3`; actual refusal both builds, although `x` is a `D`.

3. An annotation-only statement is treated as a binding even when a later assignment fixes the value; all bindings in the scope are unioned rather than stopping at the effective one:
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
def run():
    x: C
    x = D()
    return x.f()
print(run())
```
Expected `3`; actual refusal both builds.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3`; typed-only build in isolation; full suite. No icount run: the pass is compile-time only and non-feature C is byte-identical.

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre301.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
