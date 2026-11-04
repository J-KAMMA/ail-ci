Lane: stdstat

# stdstat1: `import stat` on the typed path, shipped as AIL source (`AIL_CURRENT/stdlib/stat.py`)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/stat/` that build in the default mode, print what CPython prints, and
take the typed path. The stdlib census (`lab/stdcensus/RESULTS.md`) has `stat` built-general ("about 20x slower")
because `'stat._filemode_table' is a module-level list of non-numbers`. Target: at least 10/12 programs build and
match, and at least 8/12 are typed. `stat` is what file tools use to print `-rw-r--r--` and test file kinds.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/stat.py` (new)
- `lab/stdlib/stat/*.py` (12 new programs) and `lab/stdlib/stat/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_std_stat.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_stat.txt` (new, one line:
  `test_ail_std_stat`)
- the manifest files that `tools/update_manifest.py` writes

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import stat` (Appendix B). Models:
`AIL_CURRENT/stdlib/getopt.py`, `AIL_CURRENT/stdlib/shlex.py` and `AIL_CURRENT/test_ail_std_shlex.py`.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs, each 15-40 lines of ordinary Python 3.12. `os.stat` is not
   built, so every program uses fixed mode ints (`0o100644`, `0o40755`, `0o120777`, `0o20666`, `0o60660`, `0o10644`,
   `0o140755`, `0o104755`, `0o102755`, `0o41777`, `0`). Together they cover: `S_ISDIR`, `S_ISREG`, `S_ISLNK`,
   `S_ISCHR`, `S_ISBLK`, `S_ISFIFO`, `S_ISSOCK`, `S_IMODE`, `S_IFMT`, `filemode(m)` on every mode above including
   setuid, setgid and sticky bits, the `S_I*` permission constants combined with `|` and tested with `&`, the
   `ST_MODE`..`ST_CTIME` index constants, `UF_*`/`SF_*` flags printed, a mode loop over 4096 permission values that
   prints a checksum of `filemode` strings (a speed probe), and a mode beyond int64 (`filemode(2**70)` in a
   `try`, print the exception name) so the program stops loudly or matches. Build each with the default command and
   record typed, general or refused, with the first refusal or fallback line, in `RESULTS.md` under "Before". Commit,
   push, and open the PR against `integ`.
2. **The module (20 min).** Write `stat.py` from CPython 3.12's `Lib/stat.py` (`python3 -c "import stat, inspect;
   print(inspect.getsource(stat))"`). Keep every public name and value. Rewrite `_filemode_table` and `filemode` into
   a form the typed path takes (for example parallel tuples of ints and one-char strings, or explicit `if` chains),
   with the same output for every mode. Drop the trailing `from _stat import *` (there is no C `_stat`); write that
   down in the module docstring. Add annotations (`mode: int`). Commit and push.
3. **Make the programs pass (20 min).** Build all 12 again. Fix the module, never the programs, until the targets are
   met. Measure the speed probe with `tools/icount.c` against CPython and the census's general-path build (put the old
   module text in a temp dir to build it); record both counts. A refusal that needs a compiler file goes into
   `RESULTS.md` as a follow-up with the exact text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_stat.py`, copying the structure of `test_ail_std_shlex.py`. It
   builds every passing program and compares stdout and exit status with `python3`, in the default build and with
   `AIL_UNIFIED_FORCE=1`, and checks that the typed programs build with `--strict`. It also checks under `python3`
   that the bundled `filemode(m)` equals CPython's for every m in `range(0, 0o200000)` (a pure-Python check, fast).
   It skips the builds when there is no C compiler. Register the test (Appendix A rule 6) and run it. Fill
   `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_stat.py` passes.
- At least 10 of the 12 programs build and match CPython in both builds, and at least 8 are typed.
- `RESULTS.md` has the before/after table and the icount numbers.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `stat.py` is not picked up by `import stat`; give the exact message. Also stop if no
spelling of `filemode` reaches the typed path without a compiler edit; give the refusal text. Stop when 80 minutes
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
