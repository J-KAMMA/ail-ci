Lane: modules

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
