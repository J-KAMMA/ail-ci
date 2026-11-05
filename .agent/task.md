Lane: fc-os

# fcos1: `os.stat`, `os.lstat`, `os.fspath`, `os.scandir` and the missing `os.path` functions, the largest stdlib-census blocker

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Numbers this move:**
- stdlib census (`lab/stdcensus/RESULTS.md`, integ 0bb1bf7b): the bucket **"os.X is not built" is the only reason of
  23 modules**, the largest bucket. Among them: `filecmp`, `genericpath`, `linecache`, `pstats`, `uu` (`os.stat`);
  `fnmatch`, `bdb`, `tabnanny`, `trace`, `tracemalloc` (`os.path.normcase`); `posixpath`, `configparser`
  (`os.fspath`); `tempfile` (`os.lstat`); `netrc` (`os.path.expanduser`). Target: at least 10 of the 23 modules get
  past their `os` reason (their first reason changes or they build).
- `lab/stdlib/os_stat/`: 12 new programs; target at least 10/12 build and match CPython in the default build.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/filelower.py` (raises `%s is not built. Built: os.getcwd ...`, lines ~909-984)
- the one runtime source that already implements `os.listdir` for compiled programs (find it with
  `git grep -n listdir -- AIL_CURRENT ':!*test_*'`; name it in the PR)
- `lab/stdlib/os_stat/*.py` (12 new), `lab/stdlib/os_stat/data/*` (new), `lab/stdlib/os_stat/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_os_stat.py` (new) and `AIL_CURRENT/tests.d/test_ail_os_stat.txt` (new, one line)
- the manifest files that `tools/update_manifest.py` writes

## What to build

- `os.stat(path)`, `os.lstat(path)`, `os.fstat(fd)` if fds exist: a `stat_result` with `st_mode`, `st_ino`, `st_dev`,
  `st_nlink`, `st_uid`, `st_gid`, `st_size`, `st_mtime`, `st_atime`, `st_ctime` (floats) and the `_ns` ints; a missing
  file raises `FileNotFoundError: [Errno 2] No such file or directory: 'x'` as CPython prints it.
- `os.fspath(p)` for str and bytes; `os.path.normcase` (identity on POSIX), `expanduser`, `expandvars`, `getmtime`,
  `getatime`, `getctime`, `samefile`, `samestat`.
- `os.scandir(path)` with `DirEntry.name`, `.path`, `.is_dir()`, `.is_file()`, `.is_symlink()`, `.stat()`, used in a
  `for` loop and in `with os.scandir(p) as it:`; entry order as the OS returns it (programs sort before printing).
- Both the typed path and the general path, if `filelower.py` serves both. If the general path needs
  `pyboxed2.py` (another lane's file), build the typed path only, list the general-path gaps in RESULTS.md, and say so.
Times differ between runs: programs print only differences, comparisons and sorted names, never raw times.

## Sub-steps

1. **Programs and baseline (15 min).** Write 12 programs in `lab/stdlib/os_stat/` over a fixed tree in `data/`
   (files, a subdirectory, a symlink created by the program in a temp directory under `/tmp`, removed at the end):
   sizes, `stat.S_ISDIR(st.st_mode)`, `st_mtime_ns` comparisons, `lstat` vs `stat` on the symlink, a missing path
   (the exception text), `expanduser("~")` against `os.environ["HOME"]`, `scandir` sorted listing, `samefile`, sizes
   of a file larger than 2**31 bytes are not needed. Record "Before" per program. Rebuild the 23 census modules
   (`lab/stdcensus/README.md` gives the command) and record their first reasons. Commit, push, open the PR.
2. **Build it (30 min).** Implement in `filelower.py` and the runtime source. Run the 12 programs in the default
   build and with `AIL_UNIFIED_FORCE=1` after each change. Commit and push.
3. **Test and numbers (15 min).** `AIL_CURRENT/test_ail_os_stat.py` builds every passing program and compares stdout
   and exit status with `python3` in both builds; skip with no C compiler. Register it. Rebuild the 23 modules again;
   record "After" (first reason before and after) in RESULTS.md. Commit, push, wait for CI.

## Done-check

- At least 10/12 programs build and match; at least 10 of the 23 census modules get past their `os` reason.
- `python3 AIL_CURRENT/test_ail_os_stat.py` passes; the 20 shards pass; only the files above changed.

## Stop rule

Stop at once, push, and report on any wrong output in either build. Stop if the change needs `pyboxed2.py` for
both paths or any file not listed; name it. Stop when 60 minutes pass. Push what is done first.

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
- Stdlib census: `lab/stdcensus/run.py` and `report.py`, 197 modules in `modules.txt`; a module counts as built only
  when `program.c` carries code from it.
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
