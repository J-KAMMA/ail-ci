Lane: cli

> Re-run of rundiff1, whose GitHub run was lost (no verdict 6.5 h after dispatch). If its branch job-rundiff1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# rundiff1: `ail run --diff`: run the program natively and under CPython with the same input, and stop loudly on any difference

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).

**Why (owner, 2026-11-07):** AIL is for vibe coding (docs/ROADMAP.md). The worst failure of AI-written code is plausible
wrong output. AIL is Python syntax, so CPython is a free oracle: if the native build and CPython disagree, one of them
(usually our compiler, sometimes the program's reliance on unspecified behaviour) is wrong, and the AI should be told
at once.

**Number this moves:** a new command mode with tests; in `lab/rundiff/RESULTS.md`, run it over the 10
`lab/compare/src/*/main.py` programs on their public cases and over 50 corpus programs: count agree / differ /
loud-stop-by-design, with each "differ" listed (that list is a bug list for the compiler: do not fix them here).

## Behaviour (implement exactly; put it in `docs/CLI.md` under a new heading, creating the file if it does not exist)

`ail run --diff [--python PATH] [--timeout SEC] [--json] prog.py [args...]`
1. Build as `ail run` does. Read stdin fully once (if stdin is not a TTY) into a temp file; feed the same bytes to both
   runs. Run the native program, then `PATH prog.py args...` (default: the `python3` that runs `ail`, i.e.
   `sys.executable`), same cwd, same args, same environment, each with the timeout (default 60 s).
2. Compare stdout bytes and the exit code. For an uncaught exception compare the exception type name only (from the
   last line of stderr), not the traceback text.
3. Outcomes, printed on stderr after the program's own output, one line, prefixed `ail diff:`:
   - `agree` (exit with the program's exit code);
   - `DIFFER: stdout line N` with both lines (truncated to 200 chars), or `DIFFER: exit code A vs B`, or
     `DIFFER: exception X vs Y` → exit code 3 (reserve it; say so in docs);
   - `loud stop by design: <reason>` when the native run stopped with one of AIL's documented loud errors where CPython
     continued (int64 overflow, AIL's own refusals); exit code 4. Read the reason from the native stderr; list the
     recognised messages in one table in the code and in docs/CLI.md.
   - `timeout: native|cpython` → exit code 124.
4. `--json`: print one JSON object on stdout at the end instead of the stderr line:
   `{"outcome":..., "line":N|null, "native":..., "cpython":..., "exit":[a,b], "seconds":[t1,t2]}`.
5. The native program's stdout/stderr are shown live as in `ail run`; CPython's are captured, not shown (except in the
   DIFFER line).
6. Docs must warn: the program runs twice, so file writes, network calls and other side effects happen twice.

Base: `origin/integ`. Files you may create or edit, and no others:
- `packaging/ail_lang/cli.py` (the `run` command and its argument parsing only; keep `ail run` without `--diff`
  byte-for-byte unchanged in behaviour);
- `docs/CLI.md`;
- `AIL_CURRENT/test_ail_rundiff.py` (new) and its registration the way other test modules are registered
  (`AIL_CURRENT/tests.d/test_ail_rundiff.txt` if that is the pattern; check `tools/update_manifest.py`);
- `lab/rundiff/*` (new) and the manifest files `tools/update_manifest.py` writes.

## Tests (`test_ail_rundiff.py`)
agree on a small program with stdin; DIFFER on stdout using `--python` pointing to a tiny fake interpreter script that
prints a different line; DIFFER on exit code; exception-type compare (same type → agree even if traceback text
differs); loud stop by design (int64 overflow program); timeout with `--timeout 1`; `--json` shape. Skip cleanly if no C
compiler is available, as other CLI tests do.

## Sub-steps
1. (50 min) Implementation + docs. Commit, push.
2. (40 min) Tests, register, run `test_ail_rundiff` and the existing CLI test modules (find them by grepping for
   `cli.py`/`cmd_run` in `AIL_CURRENT/test_ail_*.py`). Commit, push, wait for CI.
3. (30 min) `lab/rundiff/RESULTS.md` census. Commit, push.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
