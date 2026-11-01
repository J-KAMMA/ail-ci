**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** extends the `abc` source pass (`smalllib5.py`) to compute per-class abstract-method sets, strip `ABC`/decorators, inject an `_ail_abc_guard__` method plus a generated `_ail_abc_check_name`, and calls that guard from class construction in `pyboxed2.py` / `boxclosure.py`; it also maps `get_cache_token()` to a constant `0`. It is not just the three stated review fixes: it changes class-call ordering and error handling for every class with a guard.

**Checks run**
- `test_ail_std_abc`, `test_ail_safetynet`: 2/2 pass (179 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- `lab/compare` rebuilt against `work` (`/tmp/base`): 5 build with byte-identical `program.c`; 5 fail identically on both. The report's "six build / four fail" is false (it is 5/5), though the C-equality conclusion holds.
- Probes (`bash ~/tools/cmp.sh`, both builds) found the defects below; all were compile-time refusals on `work`, so they are caused by this change.

**Defects**
1. **Constructor binding errors are silently swallowed for any concrete subclass that inherits an ABC guard** (`pyboxed2.py:7677-7686`; same via `boxclosure.py`). The comment "the guard always raises for this class" is false for concrete subclasses: the inherited guard checks `type(obj).__name__`, which is not in the abstract set, so it does not raise, and the caught arity/keyword `Unsupported` is converted to `return t`.
   - Probe `/tmp/rprobes2/arity_concrete.py`: expected `none TypeError A.__init__() missing 2 ...`, `many TypeError A.__init__() takes 3 positional arguments but 4 were given`; actual `none ok B NOX`, `many ok B NOX`.
   - Probe `/tmp/rprobes2/arity_custom_own_init.py`: expected three `TypeError`s; actual prints `valid 9` then crashes `AttributeError: 'B' object has no attribute 'x'` (exit 1).
   - Probe `/tmp/rprobes2/routes_arity.py`: same wrong `ok B NOX` through list item, dict value, function argument and alias.
2. **`abc.get_cache_token()` returns a fake `0`** (`smalllib5.py:342`). Probe `/tmp/rprobes2/cache_value.py`: expected `token 24` / `positive True`; actual `token 0` / `positive False`. Base refused this by name, so a refusal would be acceptable; silently returning a wrong token is not.
3. **A metaclass subclassing `ABCMeta` is not recognised as an ABC metaclass** (`smalllib5.py` only compares `keyword.value` to the name `ABCMeta`). Probe `/tmp/rprobes2/meta_sub.py` (`class Meta(ABCMeta)`, `class Shape(metaclass=Meta)`): expected `blocked Can't instantiate abstract class Shape ...`; actual `built`. Base refused the program; this change made it silently wrong.

**Claims in the report**
- Defects 1-3 in the report: plain-hierarchy fix verified (test/regression); assignment/lambda override verified (`override_chain.py`); guard ordering verified for abstract classes (`abstract_arity.py`, `incomplete_sub_arity.py`, `noinit_concrete.py`) but the shared implementation broke concrete subclasses as above. "MRO concrete mixins clear them" is unverified because multiple inheritance is still refused.
- "29 probes match CPython": unverified and contradicted by the probes above; the suite misses arity errors on concrete subclasses, custom `ABCMeta` subclasses and the token value.
- Test/manifest claims verified for the modules I ran; `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3` not re-run (not edited by this change per instruction).
- `lab/compare` count is false (5/5, not 6/4); generated C is identical for the 5 that build.

**Pre-existing (identical on `work`)**
- `m: int` annotation-only override wrongly clears an abstract method (`ann_only.py`: base and HEAD both print `B built`).
- Abstract property overridden by plain class attributes reads `None None` (`prop_abs.py`).
- Nested/conditional class definitions and the general-path object/bound-method display limitations remain refusals/differences on both.

**Non-blocking note:** `Plain(1)` for a non-ABC class with no `__init__` changed from a named compile refusal on `work` to a runtime `TypeError` matching CPython (`noinit_plain2.py`), so the shared `_call_class` change alters non-`abc` C behaviour; output is correct, but it is outside the feature's provenance.

VERDICT: FIX
[cost $0.0307, opencode tokens {"total": 1307172, "input": 65331, "output": 8249, "reasoning": 20536, "cache.write": 0, "cache.read": 1213056}]
    tool time: bash 9.3 min
        317s bash   sed 's#BASE=/tmp/base_abc#BASE=/tmp/base#; s#OUT=/tmp/compare_c#OUT=/tmp/compare_c2#' /tmp/compare_c.sh > /tmp
        180s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_
         19s bash   cd /tmp/rprobes2 && for p in *.py; do echo "===== $p ====="; timeout 180 bash ~/tools/cmp.sh "$p" /home/runner
         17s bash   cd /tmp/rprobes2 && for p in routes2.py meta_sub.py prop_abs.py incomplete_sub_arity.py noinit_concrete.py; do
          4s bash   cd /tmp/rprobes2 && cat > routes_arity.py <<'EOF' from abc import ABC, abstractmethod  class A(ABC):     def _
          4s bash   cd /tmp/rprobes2 && timeout 200 bash ~/tools/cmp.sh prop_abs.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -4
          3s bash   cd /tmp/rprobes2 && for p in arity_concrete.py arity_custom_own_init.py cache_value.py class_in_if.py; do echo
          3s bash   cd /tmp/rprobes2 && cat > ann_only.py <<'EOF' from abc import ABC, abstractmethod  class A(ABC):     @abstract


--- ORIGINAL TASK ---
**Coverage: make real programs that use the CPython stdlib module `abc` build and print exactly what CPython prints.**

1. Write 12 small realistic programs, each 15–60 lines, that use `abc` the way typical code does: its most common functions and classes, the common argument forms and keyword arguments, and its edge cases (empty inputs, errors that the program catches). Put them in lab/stdlib/abc/.
2. Build each one in the default mode (`ail_chatgpt.py compile X.py --syntax python`). Record the result for each: typed / general / refused, with the first refusal message, in lab/stdlib/abc/RESULTS.md.
3. Fix the reasons, starting with the one that blocks the most programs, until at least 9 of the 12 build. Each built program must match CPython's stdout and exit code. Fix the compiler, runtime or prelude, never the programs.
4. A reason that needs a big new feature is out of scope for this task: leave it, and write it in RESULTS.md as a follow-up with the exact refusal text.

Rules:
- Never wrap ints silently. Default ints are int64, and overflow stops loudly.
- The generated C of the 10 lab/compare tasks must stay byte-identical.
- Add the passing programs as a test (a new test_ail_std_abc.py registered in tests.d), and compare them with CPython in the test.
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
