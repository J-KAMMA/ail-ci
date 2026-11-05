Lane: shdeps

# shdeps1: self-hosting prep, the import graph of the compiler's front-end modules (measurement only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** a dependency graph of the compiler modules that the `compile` command loads, with its layers
and its import cycles. A self-hosted compiler must be rewritten leaf first, and a cycle must be rewritten as one unit.
Today nobody knows how many modules the front end loads, how deep the graph is, or how many cycles it has. The target
is those three numbers, plus a leaf-first order. No compiler file is edited, and nothing is compiled.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `tools/selfhost_deps.py`
- `lab/selfhost/deps.json`, `lab/selfhost/DEPS.md`
- `lab/selfhost/deps_fixture/` (a tiny package of 6-8 files with a known graph and one cycle, for the test)
- `AIL_CURRENT/test_ail_selfhost_deps.py` and `AIL_CURRENT/tests.d/test_ail_selfhost_deps.txt` (one line:
  `test_ail_selfhost_deps`)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **The tool (25 min).** Write `tools/selfhost_deps.py`. It reads Python files with `ast` only (never imports
   them). It resolves `import x`, `from x import y`, `from . import y`, and imports inside functions (mark those
   `lazy`), against `AIL_CURRENT/` and `AIL_CURRENT/python/pkg-v12/` and their subpackages (`ir/`). It starts from
   `AIL_CURRENT/ail_chatgpt.py` and follows every edge it can resolve; standard-library imports are listed per module
   but not followed. Output per module: path, lines, top-level functions, classes, out-edges (eager and lazy),
   in-degree. Then compute strongly connected components (Tarjan), a layer number for each component (leaves are
   layer 0), and a leaf-first order. Write `lab/selfhost/deps.json` (`schema: ail.selfhost_deps/1`, with the base
   commit). Also accept `--root DIR --entry FILE` so the test can run it on the fixture. Commit, push, and open the PR
   against `integ`.
2. **Two graphs (15 min).** Run it twice: once with eager edges only (what loads at start), and once with lazy edges
   too. Record both in the JSON. Check by hand three modules picked at random: their edges match a `grep` of their
   import lines. Commit and push.
3. **Report and test (20 min).** Write `lab/selfhost/DEPS.md`: the module count and total lines reachable from
   `compile`, the number of layers, the number and size of the cycles (list each cycle with more than one module),
   the 15 modules with the highest in-degree, and the first 20 modules in the leaf-first order with their lines (the
   candidates for the first AIL rewrites). Mark which of those 20 the typed-path census in `lab/selfhost/census.json`
   accepts any function of. Write `AIL_CURRENT/test_ail_selfhost_deps.py`: it runs the tool on
   `lab/selfhost/deps_fixture/` and checks the exact edges, the one cycle and the layers. It does not check the real
   graph, which changes with every merge. Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- `deps.json` lists every module reachable from `ail_chatgpt.py`, in both graphs.
- `DEPS.md` gives module count, layer count and cycle count for both graphs.
- `python3 AIL_CURRENT/test_ail_selfhost_deps.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if more than 10% of import lines cannot be resolved (list them), or if a module builds its imports
dynamically (`importlib`, `__import__`) in a way that hides real edges: list each such place. Stop when 60 minutes
pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `packaging/ail_lang/cli.py`, or these files
   in `AIL_CURRENT/python/pkg-v12/`: `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
   `ir/*`, `parallel.py`, `typedpar.py`, `buildcache.py`, `stubcalls.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
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
