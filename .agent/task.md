**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model opencode-go/deepseek-v4.1-flash]
**Diff.** `tuplib` now snapshots unstable module type constants (attribute values, later-rebound or forward names) into hidden `_ail_snap_*` names and adds `_ail_defined_*` forward markers; `pyboxed2` routes every module-bound class name through the module slot and registers those classes in `class_values` so the dynamic call path can construct them.

**Verified claims**
- Review probes `p11_attr_snapshot` (`True False`), `p8_rebind_class` (`False False`), `p4_forward_alias`/`p5_nested_forward` (exit 1, empty stdout) now match CPython on both builds. (NameError text names the hidden `_ail_defined_*` alias; stdout/exit match.)
- `p29`, `p30`, `p31`, `p32`, `p43_const_extra_read`, `p44_tuple_attr_mutation`, and worker probes `n1`–`n8` match CPython.
- Fresh `program.c` for all 10 `lab/compare` `main.ail` builds is byte-identical HEAD vs base `33ae61c`.
- `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` passes.
- Claim that module-bound class names "stay constructible" is **false in general**: keyword construction now refuses to build.

**Defect (change-caused regression)**
1. A module-bound class constructor with keyword arguments is now a compile-time refusal. The new dynamic path (`pyboxed2.py:2704`, `pyboxed2.py:7887`) sends all calls of a class in `module_names` through `call_value`, which refuses keywords at `boxclosure.py:372`.
```python
class A:
    def __init__(self, x, y=2):
        self.x = x; self.y = y
class B: pass
if False:
    A = B                      # only this dead binding makes A module-bound
a = A(x=3)
print(a.x + a.y)
```
CPython/base: `5`, exit 0. HEAD: both builds fail with `not in the subset: keyword arguments in a call through a function value`.
Same defect: `p46_rebound_ctor_kwargs` (CPython `7 4`; base wrong `5 6`), `p53_rebind_exc_kwargs` (CPython `7 f`; base wrong `7 x`), and `p45` (`5 6`) now all refuse instead of matching. `_call_class` already handles keyword arguments, so this can be exact.

**Pre-existing (identical on base, not blocking)**
- `p56`/`p57` unstable alias chains: CPython `True False`; both builds `False True` (snapshot re-expands an earlier unstable constant at the later assignment).
- `p50`/`p51` class rebound to a non-type used in `isinstance`: CPython TypeError exit 1; both builds print `False`, exit 0.
- `p49` module tuples naming `BaseException`/`LookupError`/`ArithmeticError`/`UserWarning` are refused identically on base (`_ISINSTANCE_EXC_NAMES` remains incomplete).

**Unverified.** Speed/icount on gdev, the 148-module census, `p37_attr_non_type`, and worker probes `p43`/`p53`–`p59` (not present in `/tmp/probes`).

VERDICT: FIX
1. `p54_kw_dead_if.py` (and `p45`/`p46`/`p53`): a module-bound class constructor with keyword arguments is refused (`keyword arguments in a call through a function value`) in both builds; expected CPython output `5` for p54, `7 4` for p46, `7 f` for p53.
[cost $0.0374, opencode tokens {"total": 2582726, "input": 84687, "output": 8423, "reasoning": 20368, "cache.write": 0, "cache.read": 2469248}]
    tool time: bash 8.8 min
        285s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_a
         79s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmpC_head /tmp/cmpC_base && mkdir -p /tmp/cmpC_head /tmp/cmp
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/n*.py; do b=$(basename $p); echo "===== $b"; timeou
         17s bash   cd /tmp/base && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p47_rebound_default p48_rebound_subcl
         17s bash   cd /tmp/base && for p in p40_kw_ctor p41_default_ctor p42_kw_exc p43_const_extra_read p44_tuple_attr_mutation;
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p40_kw_ctor p41_default_ctor p42_kw_exc p43_const_extra_read p4
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p29_rebind_conditional p30_rebind_constructor p31_rebind_static
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p47_rebound_def


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
