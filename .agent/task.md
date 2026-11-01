**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**Diff.** `tuplib._expand_isinstance_type_constants` rewrites module-level type constants into literal type specs at each `isinstance()` use before the tuple pass, with scope/order guards and assignment dropping; `pyboxed2`/`pyfunc`/`dunders` flatten nested tuples and add a dynamic `ail2_dyn_isinstance` fallback for non-name elements. Tests: `test_ail_covisin1` added via `tests.d`.

**Verified claims**
- `lab/compare` 10/10 `main.ail`: generated `program.c` byte-identical HEAD vs base `9afd6e4`.
- `test_ail_covisin1` + `test_ail_safetynet`: 2 modules, 0 failed.
- Review probes `p7_shadowclass`, `p9_localshadow`, `p10_order` on HEAD match CPython (exit 1 / empty stdout for p10).
- The new scope/order guard works for parameter/local/comprehension/class shadowing cases covered by the added tests.

**Defects (wrong answer / wrong exit, absent on base — base refuses by name)**
1. **Attribute value re-read at use instead of the value captured at assignment.** Probe `p11_attr_snapshot.py`:
```python
class A: pass
class B: pass
class Box: pass
b = Box(); b.t = A
T = b.t
b.t = B
print(isinstance(A(), T), isinstance(B(), T))
```
CPython: `True False`. HEAD default and general: `False True`. The assignment is dropped and `T` is replaced by `b.t` at the later use, after `b.t` changed.

2. **Names inside a constant are re-evaluated after rebinding.** Probe `p8_rebind_class.py`:
```python
class A: pass
class B: pass
T = (A,)
A = B
print(isinstance(A(), T), isinstance(B(), T))
```
CPython: `False False` (the tuple captured old `A`). HEAD both builds: `True False`.

3. **Forward references inside a constant are silently resolved.** `p4_forward_alias.py` (`K = C` before `class C: pass; print(isinstance(C(), K))`): CPython exits 1 with `NameError`; HEAD both builds exit 0 and print `True`. `p5_nested_forward.py` (`T = (K,); print(isinstance(1, T)); K = str`): CPython exits 1; HEAD exits 0 printing `False`. `is_type` checks only that `K`/`C` exists somewhere, not that it is bound at the assignment.

Root cause: `is_type`/`where[name] < index` validates only the outer assignment's position; `expand_value` then re-evaluates the element expressions at the use site, losing CPython's snapshot semantics.

**Pre-existing / other**
- `T = (ValueError, KeyError)` and a module constant used from a class body are still named refusals on both HEAD and base (`name 'int'/'ValueError' is not defined`, module tuple note); not caused by this change, but the "must never be refused" scope is not fully met.
- Module census (`148`, 0 refusals) and `p23_builtin_order` were not re-run; unverified.

VERDICT: FIX
1. `p11_attr_snapshot.py`: expected `True False`; actual `False True` (both builds) — attribute re-read after mutation.
2. `p8_rebind_class.py`: expected `False False`; actual `True False` (both builds) — element rebound before use.
3. `p4_forward_alias.py`: expected exit 1, empty stdout; actual exit 0, `True`. `p5_nested_forward.py`: expected exit 1, empty stdout; actual exit 0, `False` — unbound name inside a constant resolved.
[cost $0.0260, opencode tokens {"total": 1150177, "input": 54887, "output": 6076, "reasoning": 18238, "cache.write": 0, "cache.read": 1070976}]
    tool time: bash 5.6 min, write 0.0 min
        131s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_cov
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_covisin1 t
         44s bash   cd /tmp/ctmp && for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer scar_life tally_lang term_ra
         23s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; timeout 300
          5s bash   cd /tmp/base && for p in p4_forward_alias p5_nested_forward p8_rebind_class p3_class_body_order p1_exc_const p
          4s bash   cd /tmp/ctmp && rm -rf h/echo_pack b/echo_pack out/h_echo_pack out/b_echo_pack; src=/home/runner/work/ail-ci/a
          3s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p9_rebind_alias p10_lambda_isinstance; do echo "===== $p HEAD";
          2s bash   cd /home/runner/work/ail-ci/ail-ci && echo HEAD; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/p11_attr_snapsho


--- ORIGINAL TASK ---
**Coverage: `isinstance(x, T)` where T is not a plain name.** The module census of AIL's own compiler (after #307) shows 11 modules stopped by "isinstance with a non-name type". Examples: `isinstance(x, (int, str))`, `isinstance(x, ast.Name)`, `isinstance(x, mod.Class)`, `isinstance(x, TYPES)` with a module-level tuple constant.
- These must build. Use the typed path when the type set is known at compile time; otherwise use the general path. They must never be refused.
- Compare stdout and exit code with CPython on probes covering each form, including subclasses and `bool` against `int`.
- The generated C of the 10 lab/compare tasks must be byte-identical.
- Add tests, run them plus test_ail_safetynet, run `python3 tools/update_manifest.py`, and commit.

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
