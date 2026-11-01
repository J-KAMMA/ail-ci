**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** Adds a dict-backed general-path `@lru_cache`/`@cache` wrapper (cache_info/clear/parameters, typed keys, run-time/negative maxsize, LRU eviction, unhashable-key TypeError), a prelude merge sort for `cmp_to_key` in `sorted`/`.sort`/`min`/`max`, keyword-bound `partialmethod` rewriting, `partial` defaults, and `reduce([])` → `TypeError`. Implementation matches the task description, but it adds a hidden extra `_lrkeyarg` parameter to every cached function, which not all adapter paths pass.

**Tests run (HEAD):** `test_ail_std_functools` + `test_ail_safetynet` — 2 modules, 0 failed. `update_manifest.py --check` rc 0.
**C check:** 7 lab/compare tasks build with `--debug-dir` C byte-identical (`berth_sim`, `chain_relax`*`, `echo_pack`, `ledger_bin`, `rail_transfer`*, `term_rank`, `ticket_audit`); `scar_life`/`tally_lang`/`tree_fold` refuse rc 3 on both. A non-functools program's C is identical; `@lru_cache` direct-call C differs.
*with `--exact-int`.

**Report claims:** 6 review fixes verified; tests/CI claims not all run; "15 probes all match" **false**; "programs that call none generate exactly the previous C" **false** (a direct-call `@lru_cache` program's C differs); lab/compare counts wrong (7 build, 3 refuse — requirement still met).

**Defects (blocking):**

1. A cached function used as `map()`/`sorted(key=)` no longer compiles (both builds); base builds and matches.
```python
from functools import lru_cache
@lru_cache(maxsize=8)
def sq(n): return n * n
print(sorted([3, 1, 2], key=sq))
```
Expected `[1, 2, 3]`; actual compile failure `error: too few arguments to function 'pf_sq'` — `pkf_sq` still calls the old 2-argument wrapper while `pf_sq` now takes `_lrkeyarg` (`pyboxed2.py:9521` adapter not updated).

2. `min`/`max(..., key=cmp_to_key(f))` over a dict or set crashes (new form; base refused by name).
```python
from functools import cmp_to_key
def cmp(a,b): return (a>b)-(a<b)
print(min({"a":5,"b":1,"c":8}, key=cmp_to_key(cmp)))
```
Expected `a`; actual `KeyError: 0`. With a set: expected `1`, actual `TypeError: 'set' object is not subscriptable`. `_ail_cmp_min/_max` (`prelude_genlib.py`) index `xs[0]` instead of materializing `list(xs)`.

3. `cache_info().maxsize` for `@lru_cache(maxsize=True)` prints `True`, CPython prints `1`.
```python
@lru_cache(maxsize=True)
def a(x): return x
a(1); a(1); print(a.cache_info())
```
Expected `CacheInfo(hits=1, misses=1, maxsize=1, currsize=1)`; actual `maxsize=True`.

**Pre-existing (identical on base, not blocking):** `@lru_cache` on `*args` fails to build; non-int `maxsize` (float/string) is accepted where CPython raises TypeError; `cmp_to_key` with constant/bool comparators sorts differently; keyword call through a `partial` value is refused (HEAD's refusal text differs from base's, both refuse).

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3` (outside review scope); instruction-count/speed before vs after.

VERDICT: FIX
1. Thread the extra cache-key argument through the `pkf_` map/key adapter (or stop adding it for functions never using cache_info/cache_clear); currently common `map`/`sorted(key=cached_fn)` programs stop compiling.
2. Materialize `list(xs)` in `_ail_cmp_min`/`_ail_cmp_max` so dict/set/generator inputs match CPython instead of crashing.
3. Coerce a `bool` `maxsize` to int in `CacheInfo.maxsize` (`True` → `1`).
[cost $0.0459, opencode tokens {"total": 2350345, "input": 94605, "output": 13457, "reasoning": 28267, "cache.write": 0, "cache.read": 2214016}]
    tool time: bash 11.1 min
        338s bash   cd /home/runner/work/_temp/w2 rm -rf /tmp/cmpc && mkdir -p /tmp/cmpc for t in berth_sim chain_relax echo_pack 
        155s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && AIL_NO_CACHE=1 timeout 1200 python3 ../tools/par_check.py -j 2 te
         35s bash   cd /home/runner/work/_temp/w2 for p in lru_lru1 lru_keys lru_hof lru_unhash cmp_iter cmp_places reduce_empty p
         24s bash   cat > /tmp/rprobes/lru_lru1.py <<'PY' from functools import lru_cache  @lru_cache(maxsize=2) def f(a, b=10):  
         19s bash   cat > /tmp/rprobes/cmp_minmax.py <<'PY' from functools import cmp_to_key  def cmp(a, b):     return (a > b) - 
         16s bash   cd /tmp/rprobes cat > hof_map.py <<'PY' from functools import lru_cache @lru_cache(maxsize=8) def sq(n):     r
         15s bash   cd /tmp/rprobes cat > pa1.py <<'PY' from functools import partial def f(a, b=2, c=3):     return (a, b, c) p =
         13s bash   cat > /tmp/rprobes/maxsize_float_noinfo.py <<'PY' from functools import lru_cache  @lru_cache(maxsize=2.0) def


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `functools` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `functools` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/functools/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/functools/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_functools.py registered in tests.d), and compare them with CPython in the test.
- Run that test plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
