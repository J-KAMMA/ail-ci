**Fix one pre-existing difference from CPython.** A reviewer of job `pre279` recorded these as already present before that job:

**Defects (not identical on base; caused by the new field-call path)**
1. A field holding a callable instance is not called. Probe:
```python
class F:
    def __call__(self, x): return x + 10
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
print(C().f(1))
```
CPython `11`; HEAD both builds exit 1, `TypeError: 'instance' object is not callable`; base `101`. The new branch routes through `call_value`, which only accepts `AIL_T_FUNC`; it should call the instance's `__call__` or refuse by name.
2. Type name in the new TypeError is wrong for instance/bytes fields. Probe:
```python
class F: pass
class C:
    def __init__(self): self.f = F()
    def f(self, x): return x + 100
try: C().f(1)
except TypeError as e: print('TypeError', e)
```
CPython `TypeError 'F' object is not callable`; HEAD `TypeError 'instance' object is not callable` (base prints the method result). Likewise `self.f = b'x'`: CPython names `'bytes'`, HEAD names `'instance'`. This contradicts the report's "non-callable fields raise CPython's TypeError" (its test only used `5`).

**Unverified:** `test_ail_quirks` (not re-run), instruction counts (non-feature C identical, so no hot-path change; not measured).

Reproduce the first one that still differs on this tree (`bash ~/tools/cmp.sh` on both builds). Fix that one cause, or refuse the construct by name at compile time. Add the case to a new `test_ail_pre293.py` and run only that module and `test_ail_safetynet`, then commit. If none of them still differs, change nothing and say so.

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
