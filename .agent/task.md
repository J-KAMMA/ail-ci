Lane: reprlib

# reprlib1: `import reprlib` as a bundled AIL module (`AIL_CURRENT/stdlib/reprlib.py`)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/reprlib/` that build in the default mode and print what CPython
prints, with the same exit status. On `integ` today it is 0/12: `reprlib.repr(...)` is refused with
`not in the subset: reprlib.repr (not yet published in NAMES_library.json)`. The target is at least 10/12.
`reprlib` is what logging and debugging helpers use to print big values in short form.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/reprlib.py` (new)
- `lab/stdlib/reprlib/*.py` (12 programs) and `lab/stdlib/reprlib/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_reprlib.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_reprlib.txt` (new, one line:
  `test_ail_std_reprlib`)
- the manifest files that `tools/update_manifest.py` writes

**Known risk (probe on 2026-11-04).** CPython's `Repr.repr1` dispatches with
`getattr(self, 'repr_' + typename)`. On the general path a program that does this on a class with no `__init__`
raised `AttributeError: 'R' object has no attribute 'repr_int'` although `hasattr` had returned True. Test this
first (sub-step 2). If the dynamic dispatch fails, dispatch with an explicit chain on `type(x).__name__` for the
built-in types, then fall back to `getattr` only for names a subclass defines. Record the probe program and its
output in `RESULTS.md` as a finding (it is a compiler bug: file, the two lines of output, and CPython's output).

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/reprlib/`, each 15-40 lines of ordinary
   Python 3.12. Together they cover: `reprlib.repr` of long lists, tuples, dicts, sets, frozensets, strings
   and nested containers (the `...` cut-offs and `maxlevel`); a `reprlib.Repr()` instance with changed limits
   (`maxlist`, `maxstring`, `maxdict`, `maxlevel`, `maxother`, `fillvalue`) set as attributes and as 3.12 keyword
   arguments; `Repr(indent=4)` and `indent='--'`; `reprlib.aRepr`; a subclass that adds `repr_MyClass` and one that
   overrides `repr_str`; `@reprlib.recursive_repr()` on a class whose `__repr__` would recurse, with the default and a
   custom fill value; big ints: `reprlib.repr(10**50)` and `reprlib.repr(2**70)` (in the default int64 build these
   stop loudly at the arithmetic; record that, it is allowed), and an int64 value with more digits than `maxlong`
   would cut, using `Repr(maxlong=10)`; a dict with keys of mixed types (CPython falls back from sorted order).
   Build each with the default command; record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before (integ <short sha>)". Commit, push, and open the PR against `integ`.
2. **Dispatch probe (5 min).** Build the risk probe above (a class with `__init__`, and one without) on today's
   integ in both builds. Record the results. Commit.
3. **The module (25 min).** Write `AIL_CURRENT/stdlib/reprlib.py` from CPython 3.12's `Lib/reprlib.py` (print it with
   `python3 -c "import reprlib, inspect; print(inspect.getsource(reprlib))"`). Keep `Repr` with all its limits and
   `repr_*` methods, `_possibly_sorted`, `aRepr`, `repr`, and `recursive_repr`. `recursive_repr` keys on
   `(id(self), get_ident())`: use `id(self)` with a constant thread key if `_thread` does not build, and write that
   difference in the module docstring. Rewrite only what the compiler refuses; keep the output. Commit and push.
4. **Make the programs pass, then test (20 min).** Build all 12 again in the default build and with
   `AIL_UNIFIED_FORCE=1`. Fix the module, never the programs, until at least 10 build and match. A refusal that needs
   a compiler file goes into `RESULTS.md` as a follow-up with the exact text. Write
   `AIL_CURRENT/test_ail_std_reprlib.py`, copying the structure of `AIL_CURRENT/test_ail_std_shlex.py`: it builds every
   passing program and compares stdout and the exit status with `python3`, in both builds, and skips when there is no
   C compiler. Register it (Appendix A rule 6), run `python3 tools/par_check.py -j 2 test_ail_std_reprlib`, fill
   `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_reprlib.py` passes.
- At least 10 of the 12 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table and the dispatch-probe finding.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `reprlib.py` is not picked up by `import reprlib`; give the exact message. Also stop if
fewer than 6 programs can pass without editing a compiler file; name each blocking refusal. Stop when 80 minutes
pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
