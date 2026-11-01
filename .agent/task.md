**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** The general path (`python/pkg-v12/pyboxed2.py`) now expands `**mapping` arguments into a runtime dict and binds parameters dynamically (new `_bind_args_dynamic`, `_expand_kwseq`, mapping-protocol expansion), and removes the refusal of required keyword-only parameters. Other files are a design note, one new test module, DEVLOG/DIFFERENCES and manifest updates. This matches the report's summary.

**Probes run** (`/tmp/rprobes`, `bash ~/tools/cmp.sh <p>.py $PWD`, both `g` and `d` builds):

| probe | result |
|---|---|
| `prec` (unexpected vs surplus precedence) | matches CPython |
| `defonce` (default expr/list evaluated once) | matches CPython |
| `orderdup` / `alias2` (evaluation order, no mutation of caller mapping) | matches CPython |
| `kwo` (keyword-only defaults, mutable default identity) | matches CPython |
| `methodq` (method + inherited method) | matches CPython |
| `plainkw` | no-`**` program: generated C byte-identical to base |
| `berth_sim/main.py`, `tree_fold/main.ail` | generated C byte-identical to base |
| `posdef`, `varprec`, `inherit`, `mapping2` | **differ from CPython** (below) |

`test_ail_kwargs_reach` and `test_ail_safetynet` pass (`-j 2`, 0 failures). `tools/update_manifest.py --check` is clean.

**Report claims:** 1 verified for normal mappings (positional-only names enter `**kwargs`); 2 verified (empty/non-empty exception calls); 3 **false at the boundaries** (missing `__getitem__` gives `AttributeError`; non-iterable `keys()` gives the wrong TypeError); 4 **false** for inherited `__init__` keyword/keyword duplicates. The base refuses `posdef`, `varprec`, `inherit` and `mapping2` by name, so none is pre-existing.

**Not checked:** the full 25-probe map was only inspected from `/tmp/kwmeasure/results_after.txt` (20 OK / 5 refused), not re-run; the worker's six probes were not re-run; the other eight `lab/compare` tasks were not rebuilt; no speed measurement was taken (the change is confined to the `**` call path).

---

VERDICT: FIX

1. **Positional-only defaults are replaced by `None` whenever any `**` argument is present**, even `**{}`. The binder emits `ail_box_none()` for an unsupplied positional-only parameter instead of its default.
   ```python
   def g(a, b=5, /, **kw):
       return (a, b, kw)
   print(g(1, **{}))
   print(g(1, **{"b": 9}))
   ```
   Expected `(1, 5, {})` / `(1, 5, {'b': 9})`; actual `(1, None, {})` / `(1, None, {'b': 9})` on both builds.

2. **`*args` and keyword-only parameters are swapped** in the dynamic binder: it appends the vararg tuple before the keyword-only values, while the callee's C signature expects keyword-only arguments first (the old path does this correctly).
   ```python
   def f(a, *args, b=2, **kw):
       return (a, args, b, kw)
   print(f(1, **{}))
   print(f(1, 2, 3, **{"b": 4, "c": 5}))
   ```
   Expected `(1, (), 2, {})` / `(1, (2, 3), 4, {'c': 5})`; actual `(1, 2, (), {})` / `(1, 4, (2, 3), {'c': 5})` on both builds.

3. **Wrong qualname for a keyword/keyword duplicate when a class inherits `__init__`.** `_bind_args_dynamic` uses the defining class (`B.__init__`) instead of the called class (`D`).
   ```python
   class B:
       def __init__(self, a, b=2):
           self.a = a
   class D(B):
       pass
   try:
       D(**{"a": 1}, **{"a": 2})
   except TypeError as e:
       print(e)
   ```
   Expected `__main__.D() got multiple values for keyword argument 'a'`; actual `__main__.B.__init__() got multiple values for keyword argument 'a'` on both builds.

4. **Mapping-protocol error boundaries do not follow CPython.**
   ```python
   class NI:
       def keys(self): return 5
   class NoItem:
       def keys(self): return ["a"]
   try: f(**NI())
   except Exception as e: print(type(e).__name__, e)
   try: f(**NoItem())
   except Exception as e: print(type(e).__name__, e)
   ```
   Expected `TypeError NI.keys() returned a non-iterable (type int)` and `TypeError 'NoItem' object is not subscriptable`; actual `TypeError 'int' object is not iterable` and `AttributeError 'NoItem' object has no attribute '__getitem__'` on both builds.
[cost $0.0323, opencode tokens {"total": 1383710, "input": 78079, "output": 8065, "reasoning": 19870, "cache.write": 0, "cache.read": 1277696}]
    tool time: bash 4.4 min
        169s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_kwargs_r
         23s bash   cd /tmp && rm -rf lch lcb && mkdir lch lcb && cp /home/runner/work/ail-ci/ail-ci/lab/compare/src/berth_sim/mai
         10s bash   cd /tmp && rm -rf lah lab && mkdir lah lab && cp /home/runner/work/ail-ci/ail-ci/lab/compare/src/tree_fold/mai
          9s bash   cd /tmp/rprobes && for p in inherit misc; do echo "=== $p HEAD ==="; timeout 400 bash ~/tools/cmp.sh $p.py /ho
          9s bash   cd /tmp/rprobes && for p in prec defonce; do echo "=== $p HEAD ==="; timeout 400 bash ~/tools/cmp.sh $p.py /ho
          9s bash   cd /tmp/rprobes && for p in kwo mapping2; do echo "=== $p HEAD ==="; timeout 400 bash ~/tools/cmp.sh $p.py /ho
          9s bash   cd /tmp/rprobes && for p in orderdup alias2; do echo "=== $p HEAD ==="; timeout 400 bash ~/tools/cmp.sh $p.py 
          6s bash   cd /tmp/rprobes && for p in nested methodq; do echo "=== $p HEAD ==="; timeout 400 bash ~/tools/cmp.sh $p.py /


--- ORIGINAL TASK ---
**Coverage: keyword arguments.** Keyword arguments, defaults, keyword-only parameters (*,), *args and **kwargs, calls passing **dict, defaults that are evaluated once. Measure 25 probe programs (refused / general / typed) in docs/design/KWARGS_REACH.md, then fix the top refusal. Acceptance: compare stdout and exit code with CPython on your own boundary probes; the generated C of the 10 lab/compare tasks must stay byte-identical unless the task is about them; add tests (register new modules in tests.d), run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, commit.

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
