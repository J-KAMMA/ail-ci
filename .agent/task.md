Lane: errux

# errux1: a scored corpus of 40 refusal messages and a ratchet test, so no compile error gets worse unnoticed

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** refusal messages under a regression gate, and their total score. Today 6 messages are checked
(`AIL_CURRENT/test_ail_beginner_errors.py`), and nothing measures whether a message names the user's line, the
construct and a fix. Target: 40 programs, each triggering a distinct common refusal, scored 0-4; the baseline total
recorded; a test that fails when any message scores lower than its baseline or when a compile prints a Python
traceback or a raw C compiler error. The list of the lowest-scoring messages becomes the input for follow-up fix jobs.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/errux/progs/*.py` (40 programs), `lab/errux/score.py`, `lab/errux/baseline.json`, `lab/errux/RESULTS.md`
- `AIL_CURRENT/test_ail_errux.py` and `AIL_CURRENT/tests.d/test_ail_errux.txt` (one line: `test_ail_errux`)
- the manifest files that `tools/update_manifest.py` writes
No compiler file is edited. A bad message is recorded, not fixed.

## Scoring (write it into RESULTS.md)

Each program starts with header comments: `# line: N` (the line CPython or a reader would blame), `# names: TEXT`
(a short substring that names the construct, for example `dict view` or `starred`). The first non-`note:` stderr line
of the default build scores one point for each of:
1. the compile exits with a clean refusal status (3 for a subset refusal, 2 for a syntax error), not 1 with a Python
   traceback and not a C compiler error;
2. it starts with `<file>.py:N:` where `<file>` is the program's own file name and N is the header line;
3. it contains the `names` text (case-insensitive);
4. it gives a rewrite hint: it contains `write instead`, `use `, `did you mean`, `rename` or `instead` (list the
   exact hint words in `score.py`).

## Sub-steps

1. **Programs (30 min).** Write 40 programs, 3-15 lines each, one refusal per program, no two from the same message
   template. Sources: the blocker buckets of `lab/stdcensus/RESULTS.md` and `lab/stdcensus/repro/`, the
   `refused by name` rows of `DIFFERENCES.md`, the cases of `test_ail_beginner_errors.py`, and beginner mistakes
   (wrong arity, undefined name in a nested function, `return` outside a function, a typo in a method name, a missing
   `self`, mixing tabs and spaces, an int literal beyond int64, a missing module, an attribute of `None`). Put the
   user-facing error in a non-first line so a missing location is visible. Check each under `python3` too and note
   whether CPython also rejects it. Commit, push, and open the PR against `integ`.
2. **Scorer (20 min).** Write `lab/errux/score.py`: it builds each program in a temp dir (`AIL_NO_CACHE=1`,
   `ulimit -v 1500000`, timeout 120 s, 2 at a time), scores it, and prints a table. `--write-baseline` writes
   `baseline.json` (`{program: score}`); `--check` exits 1 when any program scores below its baseline and names it.
   A program that now builds is reported as `builds now` and fails `--check` only if CPython rejects it. Run it and
   write the baseline. Commit and push.
3. **Results and test (20 min).** Write `RESULTS.md`: date, commit, the scoring rules, the table (program, score,
   exit status, first stderr line trimmed to 160 chars), the total out of 160, and "Follow-ups": the 10 lowest scores
   with the exact message and what is missing. Write `AIL_CURRENT/test_ail_errux.py`: it runs the scorer's `--check`
   logic in-process (import `lab/errux/score.py` by path) and also asserts no program's stderr contains `Traceback
   (most recent call last)` or `error: ` from gcc/clang (`program.c:`). It skips when there is no C compiler, and its
   failure message says how to refresh the baseline after a deliberate improvement. Register it (Appendix A rule 6)
   and run it. Commit and push.
4. **CI (10 min).** Wait for the 20 shards. If the test is longer than 4 minutes on one core, cut it to the 20
   programs with the highest score (they guard the best messages) and say so.

## Done-check

- 40 programs, `baseline.json`, and `RESULTS.md` with the total score and the follow-up list.
- `python3 AIL_CURRENT/test_ail_errux.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a compile prints a Python traceback for one of the programs (a compiler crash is a P0 finding: give
the program and the traceback's last 5 lines, then continue with the rest). Stop when 80 minutes pass. Push what is
done first.

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
