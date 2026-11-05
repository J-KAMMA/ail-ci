Lane: whyail

# whyail1: `docs/WHY.md`, the "Why AIL" page: every number linked to a committed lab result, losses included

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** numbers on the 0.1 "Why AIL" page that a test traces to a committed result file. Today there is
no such page, and 0 numbers are traced. The target is a page of at most 120 lines with at least 12 numbers, each one
found by the test in its source file. The page states the 0.1 claim "Python syntax, Rust-level speed, safe binaries" and
shows where it holds and where it does not yet (for example compile time, which is slower than Rust on 10/10 tasks).

Base: `origin/integ`. Files you may create or edit, and no others:
- `docs/WHY.md` (new)
- `AIL_CURRENT/test_ail_docs_why.py` (new) and `AIL_CURRENT/tests.d/test_ail_docs_why.txt` (new, one line:
  `test_ail_docs_why`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `README.md`, `docs/ROADMAP.md`, `docs/COMPARISON.md` or any other existing doc: other lanes own them. Link to
them instead. Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`.

## Sub-steps

1. **Collect (20 min).** Read `docs/ROADMAP.md` ("Where AIL stands"), `docs/COMPARISON.md`, `lab/pyperf/RESULTS.md`,
   `examples/algos/RESULTS.md`, `lab/bigbench/RESULTS.md`, and every `lab/*/RESULTS.md` and `lab/safety/*/RESULTS.md`
   that exists on `origin/integ` today. List the candidate numbers with the file and line each comes from. Use only
   numbers that are in a committed file; never measure new ones here, and never round them differently from the source.
2. **Write the page (30 min).** Write `docs/WHY.md` in plain English, short sentences:
   - one paragraph: what AIL is (Python syntax plus optional annotations, compiled through C to one executable);
   - "Speed", "Binary size and disk", "Safety", "Python compatibility": each with 2-4 numbers;
   - "Where it is not there yet": at least 4 measured losses or gaps (compile time, `.py` typed reach, peak RSS on
     tree_fold, stdlib census);
   - after every number, a source mark `[source: <repo path>]` that links the file.
   Commit, push, and open the PR against `integ`.
3. **Trace test (25 min).** Write `AIL_CURRENT/test_ail_docs_why.py`. For each number in `docs/WHY.md` (a token with a
   digit, such as `3.1×`, `6/10`, `0.34 MB`), it takes the source mark on the same line and checks that the same string
   is in that file. A number with no mark fails the test. It also checks that every link resolves to a file in the
   repository. Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `docs/WHY.md` is at most 120 lines and has at least 12 traced numbers, at least 4 of them losses or gaps.
- `python3 AIL_CURRENT/test_ail_docs_why.py` passes, and it fails when you change one number by hand (try it, then undo).
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop if two source files give different values for the same measure; list both and use neither. Stop when 80 minutes
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
