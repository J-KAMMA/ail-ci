Lane: stdfall

# stdfall1: `fnmatch`, `reprlib` and `sched` in compiled programs, shipped as AIL source from CPython's pure-Python code

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on relnotice1 (lane `notice`) merged into `integ`: it adds `THIRD_PARTY_NOTICES.md`,
`AIL_CURRENT/stdlib/LICENSE-PSF.txt` and `test_ail_third_party_notices`, which fails when a derived file has no entry.
If it is not merged, stack on its branch `job-relnotice1-*` (your one stacked base) and say so in the PR.

**Number this moves:** programs in `lab/stdlib/{fnmatch,reprlib,sched}/` that build in the default mode and print
what CPython prints, with the same exit status. Today 0/18. Probe on integ 18703a92 (2026-11-05), default build:
- `fnmatch.fnmatch` -> `not in the subset: fnmatch.fnmatch (not yet published in NAMES_library.json)`;
- `reprlib.repr` -> `not in the subset: reprlib.repr (not yet published in NAMES_library.json)`;
- `sched.scheduler` -> `not in the subset: sched.scheduler (not yet published in NAMES_library.json)`.
The target is at least 15/18, with at least 4/6 per module. These three were picked from the stdlib census
(`lab/stdcensus/RESULTS.md`) because AIL has no model of them, their CPython source is pure Python and short, and
their first census blockers are small: `fnmatch` needs `os.path.normcase` (identity on POSIX), `reprlib` needs
`id()`, `sched` trips on a call with a missing argument.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/fnmatch.py`, `AIL_CURRENT/stdlib/reprlib.py`, `AIL_CURRENT/stdlib/sched.py` (new)
- `lab/stdlib/{fnmatch,reprlib,sched}/*.py` (6 new programs each) and `lab/stdlib/stdfall1/RESULTS.md` (new)
- `THIRD_PARTY_NOTICES.md`: one entry per new file (origin CPython 3.12 `Lib/<name>.py`, PSF License)
- `AIL_CURRENT/test_ail_std_stdfall1.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_stdfall1.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

## Sub-steps

1. **Programs and baseline (15 min).** Write 6 programs per module, 10-30 lines each, ordinary Python 3.12:
   - `fnmatch`: `fnmatch`, `fnmatchcase`, `filter`, `translate` output text; patterns with `*`, `?`, `[a-c]`,
     `[!x]`, `[]]`, an unclosed `[`; mixed case names;
   - `reprlib`: `reprlib.repr` of long lists, dicts, nested lists, strings and big ints (`10**30`); a `Repr()` with
     `maxlist`/`maxstring` changed; `@reprlib.recursive_repr()` on a class whose list contains itself;
   - `sched`: a scheduler with a fake clock (`timefunc` and `delayfunc` are program functions, so no real sleep):
     `enter`, `enterabs`, priorities at equal time, `cancel`, `empty()`, `queue`, `run(blocking=False)`.
   Build each with the default command and record typed, general or refused, with the first refusal line, under
   "Before" in `RESULTS.md`. Commit, push, open the PR against `integ`.
2. **The modules (30 min).** Write each module from CPython 3.12's source (print it with
   `python3 -c "import X, inspect; print(inspect.getsource(X))"`). First docstring line:
   `Derived from CPython 3.12 Lib/<name>.py; PSF License, see stdlib/LICENSE-PSF.txt.` Keep the logic and every message
   text. Rewrite only what the compiler refuses, keeping the behaviour: `os.path.normcase` is the identity on POSIX
   (write that in the docstring); the `functools.lru_cache` on `fnmatch._compile_pattern` may be dropped if refused
   (no visible effect). If `sched` needs `threading.RLock` and it is refused, drop the lock and write in the
   docstring that the scheduler is not thread-safe; if any other visible behaviour differs, the module refuses that
   use instead. Add the three entries to `THIRD_PARTY_NOTICES.md`. Commit and push.
3. **Make the programs pass (20 min).** Build all 18 again. Fix the modules, never the programs. A refusal that needs
   a compiler file goes into `RESULTS.md` as a follow-up with the exact refusal text. Commit and push.
4. **Test (15 min).** `test_ail_std_stdfall1.py`, copying `test_ail_std_shlex.py`: builds every passing program and
   compares stdout and exit status with `python3`, in the default build and with `AIL_UNIFIED_FORCE=1`; skips when
   there is no C compiler. Register it (Appendix A rule 6). Run it, `test_ail_third_party_notices` and
   `test_ail_std_shlex`. Fill "After" in `RESULTS.md`. Commit, push, wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_stdfall1.py` and `test_ail_third_party_notices` pass.
- At least 15 of the 18 programs (at least 4 per module) build and match CPython in both builds.
- `RESULTS.md` has the before/after table; `THIRD_PARTY_NOTICES.md` lists the 3 new files.
- The 20 shards pass; `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop on any wrong output against CPython (stdout, exit status) in either build: record the program and both outputs
in `RESULTS.md` first, then fix the module or make it refuse that use. Stop if fewer than 9 programs can pass without
editing a compiler file; name each blocking refusal. Stop when 80 minutes pass. Push what is done first.

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
   `pyc.py`, `optlib.py`, `buildcache.py`, `pyboxed2.py`, `unified.py`, `stubcalls.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md`. Edit only the files this task names,
   plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. A fallback to the
  general path prints `note: ... built on the general path ...` on stderr.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. A bundled file shadows
  AIL's own model of a module of the same name, so bundle only modules that have no model (all three here).
  Examples: `AIL_CURRENT/stdlib/getopt.py`, `shlex.py` and `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status.

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
