**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does.** In `ail_modules.py` the merge step now, for each local module used as a value, emits a generated class plus one instance (`_AilMod_pkg__util` / `_ail_modval_pkg__util`) with a `*a` method per function, a property per global, properties for module aliases and for `__name__/__file__/__package__/__path__/__loader__/__spec__/__cached__`, and rewrites module occurrences to that instance. It also adds a name-tracking map (`modvars`/`visit_Assign`/`visit_AnnAssign`) that folds `m.attr` wherever `m` was assigned a module value, and adds refusals (unknown store, `setattr`/`delattr`, dynamic `getattr`, keyword call through a runtime-held value). The report itself is empty; the DEVLOG claims were checked.

**Claims checked.** 8 probes + 2 named refusals match CPython in both builds (test_ail_modules_values passed; probes re-run directly). 10/10 `lab/compare/src/*` C files byte-identical to base (verified: all ten). `test_ail_modules, modules3, lib_modules, safetynet, modules_values` pass. `manifest --check` clean. The `m.NEW = 5` KeyError is now a named refusal. Dunder reads through a value work for the tested paths (direct `pkg.__spec__` stays a named refusal).

**Defects (all are programs the base refused by name, so the change caused them):**

1. **Last module assignment wins, ignoring the branch condition.** `main.py`:
```python
import pkg.a
import pkg.b
if input() == "a":
    m = pkg.a
else:
    m = pkg.b
m.run()
```
stdin `a`: CPython prints `a.run`; HEAD (both builds) prints `b.run`. Same with `if 1: m = pkg.a else: m = pkg.b` (`a.run` vs `b.run`). `visit_Assign` records both assignments in AST order and `m.run()` is folded to the last one.

2. **A local module assignment inside a nested function leaks to the enclosing scope.** `main.py`:
```python
import pkg.a
import pkg.b
m = pkg.a
def outer():
    def inner():
        m = pkg.b
        return m.run()
    print(m.run())
    inner()
outer()
```
CPython `a.run` / `None` / `b.run`; HEAD (both builds) `b.run` / `None` / `b.run`. The one flat `modvars` dict is not scope-aware.

3. **Reading a name re-exported into a module through a module value crashes.** `pkg/base.py: X = 7`, `pkg/util.py: from pkg.base import X` + `def getx(): return X`; `main.py`:
```python
import pkg.util
mods = [pkg.util]
m = mods[0]
print(m.X)
print(m.getx())
```
CPython `7` / `7`; HEAD (both builds) `AttributeError: '_AilMod_pkg__util' object has no attribute 'X'`, exit 1. `_modval_nodes` skips alias entries whose kind is not `mod`, so the generated class has no property. A named refusal would be acceptable; a crash is not.

4. **A function read as a value through a module value crashes.** `def f(mod): return (mod is pkg.util, mod.double is pkg.util.double)` — CPython `(True, True)`; HEAD `AttributeError: '_AilMod_pkg__util' object has no attribute 'double'`, exit 1. (Reading a bound method as a value also fails for a plain hand-written class on the base, so the underlying gap is pre-existing, but this feature compiles it instead of refusing by name.)

Named refusals observed for keyword calls via a parameter/list item/dict/getattr (`double() called with an unknown keyword argument x`), `mod.Thing(...)`, dynamic getattr, `setattr`, `delattr`, unknown-name store, `__doc__`, and `__spec__.has_location` are acceptable.

**Pre-existing / not defects.** int64 width limits (`r06_widths`), `p15`'s refusal, and the plain-class method-value crash (`p19`) are identical on base.

**Unverified.** Speed: not applicable, the change is merge-time only (no runtime/hot-path code). Namespace-package value probes not run; two module-value shapes with `global` inside a function not run.

VERDICT: FIX
[commandcode stop=end_turn turns=45 out_tokens=35304]


--- ORIGINAL TASK ---
Lane: modules

**Finish modval2 from its existing work; do not redo it.** The run on branch `job-modval2-11040508` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-modval2-11040508` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-modval2-11040508
git log --oneline origin/job-modval2-11040508
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

**Modules and packages (roadmap P4): a module used as a value.** Today the multi-file front end refuses it.
This program prints `6 9` on CPython:

```python
import pkg.util
import pkg.sub.m
def run(mod, x: int) -> int:
    return mod.double(x) if hasattr(mod, "double") else mod.tri(x)
print(run(pkg.util, 3), run(pkg.sub.m, 3))
```

AIL refuses it: `c3.py:5:11: pkg.util is a module, used as a value; this compiler needs a module to be named in the
source.` Small CLI tools do this: plug-in tables, `handlers = {"csv": csv_mod, "json": json_mod}`, passing a backend
module to a function. Plain imports, packages, relative imports, `TYPE_CHECKING` and version-conditional imports
already work. This job only adds module values.

# modval2: modules as values, resolved at build time

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** 8 probe programs where a module is used as a value (listed below). Today 0/8 build. The goal is
8/8 matching CPython (stdout and exit status) in the default build and with `AIL_UNIFIED_FORCE=1`. A ninth, truly
dynamic probe must stay refused by name.

Base: `origin/integ`.

## Design (follow it literally)

All edits go in `AIL_CURRENT/ail_modules.py`, in the merge step, where the program is still Python text.

For each local module M that is used as a value, emit in the merged text, right after M's body is spliced in, a class
and one instance:

```python
class _AilMod_pkg__util:                       # one class per module M (here M = pkg.util)
    def double(self, *a, **k):                 # one method per top-level function f of M
        return pkg__util__double(*a, **k)
    @property
    def COUNT(self):                           # one property per module global x of M
        return pkg__util__COUNT
    @COUNT.setter
    def COUNT(self, value):
        global pkg__util__COUNT
        pkg__util__COUNT = value
    @property
    def __name__(self):                        # also __file__ and __package__, with M's values
        return "pkg.util"
    def __repr__(self):                        # CPython's text
        return "<module 'pkg.util' from '/abs/path/pkg/util.py'>"
_ail_modval_pkg__util = _AilMod_pkg__util()    # the one instance: `m is pkg.util` stays true
```

Then rewrite each place where M appears as a value (not in the `M.attr` form, which keeps its current rewrite) to
`_ail_modval_<mangled>`. Do it only for local modules. Keep every current refusal for the cases the class cannot
model, for example `getattr(m, NAME)` where NAME is not a constant string, or `setattr` with a non-constant name.
A program without module values must produce the same merged text as before, so its C does not change.

If the compiler refuses the generated class (a property or a `*a` method is outside its subset), do not change the
compiler. Narrow the generated class (for example, emit only the attributes the program reads), or refuse by name.

## Probes (put them under `AIL_CURRENT/tests/modval/`, each with a small `pkg/` package)

1. Pass a module to a function: the example above.
2. `m = pkg.util; print(m.double(2))`.
3. A list of modules: `for m in [pkg.a, pkg.b]: print(m.NAME)`.
4. A dict of modules picked by a key read from `input()`.
5. `m = pkg.a if len(sys.argv) > 5 else pkg.b`, then `m.run()`.
6. `getattr(m, "double")(3)` and `hasattr(m, "nope")`.
7. `m.COUNT = 5` through a module value, then `print(pkg.util.COUNT)`.
8. `print(m.__name__)` and `print(m is pkg.util)`.
9. (stays refused) `getattr(m, input())`: refused by name, and the message names the module and says what to write
   instead.

## Sub-steps

1. **Probes and test (15 min).** Write the 9 probes and their expected CPython outputs. Write
   `AIL_CURRENT/test_ail_modules_values.py`, which runs them; mark 1-8 as expected failures for now. Register it in
   `tests.d`, update the manifest, run `--check`. Commit, push, open the PR.
2. **Single-module values (25 min).** Make probes 2, 6, 7 and 8 pass using the class described above. The refusal
   sites are `ail_modules.py` lines 2315, 2589, 2620 and 2701. Remove the expected-failure marks for the probes that
   pass. Commit, push.
3. **Several modules (20 min).** Make probes 1, 3, 4 and 5 pass with the same class. These need no new mechanism: the
   value is one of the instances. Check that probe 9 is still refused. Commit, push.
4. **No-change check (15 min).** Byte-compare `--debug-dir DIR/program.c` against `origin/integ` on the 10 compare
   tasks and on the module tests' programs (`test_ail_modules`, `test_ail_modules3`, `test_ail_lib_modules`). Run
   those three modules, the new test and `test_ail_safetynet`. Add one row to `docs/spec/DIFFERENCES.md` if any
   behaviour still differs, using a placeholder id `C?-modval2-1`. Commit, push.

## Done-check

- 8/8 probes match CPython in both builds, and probe 9 is refused by name.
- 10/10 compare `program.c` files are byte-identical to integ.
- The listed tests pass.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- A probe needs a change outside `ail_modules.py` and the new test files.
- Any program without module values changes its C.
- 80 minutes pass.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- `AIL_CURRENT/ail_modules.py`, 3,124 lines:
  - `merge_program(entry_path, entry_text, read=None)` is at line 2844. It returns ONE Python text and renames
    `p.m.name` to `p__m__name`.
  - `class Program` is at line 277. Search-path setup (the entry directory, then `AIL_PATH`) is at line 283.
  - `class Rewriter(ast.NodeTransformer)` is at line 2491. It rewrites `m.attr`.
  - The module docstring (lines 1-55) lists what is modelled and what is refused.
- Module state is shared the CPython way: there is one variable per module global, and `m.x = v` writes it.
- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile entry.py -o OUT [--debug-dir DIR]`. The search path starts at
  the entry file's directory.
- Probe: `bash ~/tools/cmp.sh entry.py $PWD`. Run it from the probe directory so `pkg/` is found.

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
