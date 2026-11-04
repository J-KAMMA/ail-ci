Lane: getopt

# getopt1: `import getopt` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/getopt.py`)

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** programs in `lab/stdlib/getopt/` that build in the default mode and print what CPython prints,
with the same exit status. Today it is 0/12: `import getopt` is refused with
`not in the subset: getopt.getopt (not yet published in NAMES_library.json)`. The target is at least 10/12.
`getopt` is the option parser for small CLI tools, the roadmap's P4 niche. (`argparse` is not possible yet: it needs
`type=int` as a value, and the general path refuses `int` used as a value.)

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/getopt.py` (new)
- `lab/stdlib/getopt/*.py` (12 new programs) and `lab/stdlib/getopt/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_getopt.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_getopt.txt` (new, one line:
  `test_ail_std_getopt`)
- the manifest files that `tools/update_manifest.py` writes

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import getopt` (see Appendix B). A test on
2026-11-04 put a stub `getopt.py` there, and `import getopt` then built. Follow `AIL_CURRENT/stdlib/shlex.py` and
`AIL_CURRENT/test_ail_std_shlex.py` as models.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/getopt/`, each 15-40 lines of ordinary
   Python 3.12. Each one passes a fixed argument list to the parser, so no command-line arguments are needed at
   run time. Together they must cover:
   - short options with and without values: `"ab:c"`, `-b value`, `-bvalue`, grouped flags `-ac`;
   - long options: `["help", "out=", "verbose"]`, `--out=x`, `--out x`, a unique prefix (`--he` for `--help`);
   - `--` as the end of options, and stopping at the first non-option (`getopt`);
   - `gnu_getopt`, which mixes options and arguments, and a `+` at the start of its short-option string;
   - each error, caught as `except getopt.GetoptError as e:` and printed as `e.msg`, `e.opt` and `str(e)`:
     an unknown short option, an unknown long option, a missing value, a value given to a long option that takes
     none, and an ambiguous prefix;
   - `getopt.error` as another name for `GetoptError`;
   - a program that prints usage to stderr and calls `sys.exit(2)` on an error;
   - a program that turns an option value into an int with `int()`. Use the values `"42"`, `"-9223372036854775808"`
     and `"99999999999999999999"`, which is beyond int64. Print what CPython prints, or let the program stop.
   Do not catch `SystemExit`: the compiler does not support it yet.
   Build each program with the default command. Record typed, general or refused, with the first refusal line, in
   `RESULTS.md` under "Before". Commit, push, and open the PR against `integ`.
2. **The module (20 min).** Write `AIL_CURRENT/stdlib/getopt.py` from CPython 3.12's `Lib/getopt.py`. Print it with
   `python3 -c "import getopt, inspect; print(inspect.getsource(getopt))"`. Keep its logic: `getopt`, `gnu_getopt`,
   `do_longs`, `long_has_args`, `do_shorts`, `short_has_arg`, the `GetoptError(msg, opt='')` class with `.msg` and
   `.opt` attributes and a `str()` equal to `msg`, and `error = GetoptError`. Every error text must be exactly
   CPython's, for example `option -x not recognized` and `option --out requires argument`. CPython reads
   `os.environ.get("POSIXLY_CORRECT")` in `gnu_getopt`. Keep that if `os.environ` builds. Otherwise drop it and
   write down the difference in the module docstring. Rewrite only what the compiler refuses, and keep the
   behaviour. Add annotations where they help the typed path (`args: list[str]`, `shortopts: str`). Commit and push.
3. **Make the programs pass (20 min).** Build all 12 programs again. Fix the module, never the programs, until at
   least 10 build and match. A refusal that needs a compiler file goes into `RESULTS.md` as a follow-up, with the
   exact refusal text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_getopt.py`, copying the structure of
   `test_ail_std_shlex.py`. It builds every passing program and compares stdout and the exit status with
   `python3`. It does this in the default build and again with `AIL_UNIFIED_FORCE=1`. It skips when there is no C
   compiler. Register the test (Appendix A rule 6) and run it. Fill `RESULTS.md` under "After": one row per program
   with typed, general or refused. Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_getopt.py` passes.
- At least 10 of the 12 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `getopt.py` is not picked up by `import getopt`; give the exact message. Also stop if
fewer than 6 programs can pass without editing a compiler file; name each blocking refusal. Stop when 80 minutes
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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
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
