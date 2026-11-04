Lane: sqlite

# std_sqlite3: twelve realistic sqlite3 programs, built and checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `lab/stdlib/sqlite3/` programs that build in the default mode and print exactly what CPython
prints: not measured today (the directory does not exist) -> at least 9/12, with the typed count stated.

Base: `origin/integ`. Files you may edit: `AIL_CURRENT/python/pkg-v12/sqllower.py` (the source-to-source pass for
`sqlite3`; read its docstring first: rows are typed by annotations such as `rows: list[tuple[int, str, float]] =
cur.fetchall()`), `AIL_CURRENT/python/pkg-v12/ailsql_core.h` (the C over libsqlite3), new `lab/stdlib/sqlite3/`, new
`AIL_CURRENT/test_ail_std_sqlite3.py`, new `AIL_CURRENT/tests.d/test_ail_std_sqlite3.txt`. Read
`AIL_CURRENT/test_ail_sqlite.py` for what is built today. Do not edit `filert.py`, `safetyrt.py`, `cruntime.py` or any file
in Appendix A rule 8 (the bind-type choice `bi / bf / bs / bb` lives in `pyfunc.py`: a fix there is a finding, not a change).
If `sqlite3.h` is missing on the runner: `sudo apt-get install -y libsqlite3-dev`.

## Sub-steps

1. **Programs (25 min).** Write 12 programs in `lab/stdlib/sqlite3/`, 20-60 lines each, as a user would write them,
   using `sqlite3.connect(":memory:")` (or a file under `tempfile.gettempdir()` that the program deletes), annotated rows
   as the sqllower docstring shows. Cover: create/insert/select with `?` params; named `:name` params from a dict;
   `executemany` of 1000 rows then aggregate `SUM/AVG/GROUP BY`; `fetchone` loop until `None`; `with conn:` commit and
   rollback on an exception; `IntegrityError` from a UNIQUE constraint (print the message); `rowcount` and `lastrowid`;
   NULL handling (`None` in and out, `tuple[int, str | None]`); text with non-ASCII UTF-8; REAL values printed with
   `repr`; ints beyond int32 and near int64 max (9223372036854775807); `executescript` with two statements; a JOIN of two
   tables ordered by two keys. Run each with `python3`. Commit, push, open the PR against `integ`.
2. **Census (10 min).** Build each with the default command and with `AIL_UNIFIED_FORCE=1`. Write
   `lab/stdlib/sqlite3/RESULTS.md`: a table of program, typed / general / refused, matches CPython (stdout + exit),
   first stderr line. Commit.
3. **Fixes (30 min).** Fix the most common refusal or difference first, in `sqllower.py` / `ailsql_core.h` only. Each fix:
   a refused program becomes built and equal to CPython, or a differing one becomes equal. Keep refusals loud and by name
   for what you do not build. After each fix rebuild all 12 and update the table; commit.
4. **Test (15 min).** `test_ail_std_sqlite3.py` (model: `test_ail_std_statistics.py`): `PASSING` programs build and match
   CPython; `REFUSED` programs stay refused with a named text. Register it (Appendix A rule 6). Run
   `python3 tools/par_check.py -j 2 test_ail_std_sqlite3 test_ail_sqlite`. Add a "Before / After" line to `RESULTS.md`.
   Push.

## Done-check

>= 9/12 equal to CPython in the default build; the typed count stated; `test_ail_sqlite` still passes; 20 shards pass.

## Stop rule

A fix that needs `pyfunc.py` or another file outside the list: write it as a finding with the refusal text and go on.
If fewer than 9 match at 70 minutes, stop fixing, finish the test with what passes, and report the number. Stop at
80 minutes; push what is done.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. Turning a
   correct program into a refusal or a stop is a regression. When a new fast path cannot handle a case, keep the old route.
2. Probe ints beyond int64 wherever ints come from text, fields or arithmetic. Run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, and compare both with `python3`.
3. Push early and open the PR against `integ`. Wait for all 20 `shard` checks on your head commit
   (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `origin/integ` (or from one unmerged PR at most; never from a PR that is itself stacked).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: add `AIL_CURRENT/tests.d/<module>.txt` (one line: the module name), `git add` every new file, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, tag, publish, change repository settings, cancel runs, or edit
   `.github/workflows`.
8. Files owned by busy lanes; do NOT edit them: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, `packaging/ail_lang/cli.py`.
   Also do not edit `DEVLOG.md` or `AIL_CURRENT/DEVLOG.md` (integration writes them). If a fix needs one of these files,
   do not make it: write a finding (file, function, what is needed, the refusal text) in your results file and go on.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.py -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it prints
  `note: ... built on the general path` on stderr. No such note = typed. `--strict` = typed path or refuse.
  `DIR/program.c` is the generated C. Use `AIL_NO_CACHE=1` for timings.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- Model test file: `AIL_CURRENT/test_ail_std_statistics.py` (build each program in a temp dir, run it, compare stdout and
  exit code with `python3 <program>`).
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS < input`. If `perf_event_open` is refused, run `sudo sysctl -w kernel.perf_event_paranoid=1`
  once; if it is still refused, use the median of 5 wall times and say so in the results.
- The oracle is CPython 3.12 (`python3`). Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints.

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
