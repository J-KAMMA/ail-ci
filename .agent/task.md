Lane: docperf

# docperf1: `docs/PERF_TYPED.md`, a performance guide to writing typed-friendly Python, every pair built and measured by a test

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** before/after pairs in the guide that a test builds and checks. A user who writes Python and
gets the general path (20-50x slower) needs to know which spelling falls back and what to write instead. Today no
page shows it with numbers. The target is at least 12 pairs, each with: both samples matching CPython output, the
"after" sample building with `--strict`, and a measured instruction-count ratio.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `docs/PERF_TYPED.md`
- `lab/perfguide/measure.py` and `lab/perfguide/RESULTS.md`
- `AIL_CURRENT/test_ail_docs_perf.py` and `AIL_CURRENT/tests.d/test_ail_docs_perf.txt` (one line:
  `test_ail_docs_perf`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `docs/PORTING.md`, `docs/tutorial.md`, `README.md`, anything under `docs/guide/`, or
`AIL_CURRENT/test_ail_docs_blocks.py`. Link to them instead. Read `docs/PORTING.md` (refusals, not speed),
`docs/design/PY_TYPED_REACH.md`, and the `note: ... built on the general path` texts in
`AIL_CURRENT/AIL_REFERENCE.md` to find the real fallback causes.

## Sub-steps

1. **Find the pairs (20 min).** For each candidate, write a "before" program (15-30 lines, ordinary Python that
   builds on the general path today, with the note it prints) and an "after" program (the same output, built with
   `--strict`). Find at least 12 that really fall back today, for example: a list mixing ints and `None`; a function
   whose return paths differ in tuple shape; a module-level list of strings used in a hot loop; an unannotated
   parameter used as both int and float; a dict of mixed value types; a class field assigned two types. Check each
   on `origin/integ`; drop any that does not fall back. Commit, push, and open the PR against `integ`.
2. **Measure (15 min).** Write `lab/perfguide/measure.py`: it builds every pair, checks both outputs equal CPython's,
   and measures instructions with `tools/icount.c` (see that file's header for use), 3 runs, median. Give each program
   a loop big enough for at least 10^7 instructions. Write `lab/perfguide/RESULTS.md` with the ratio per pair, the
   base commit and the date. Commit and push.
3. **The page (15 min).** Write `docs/PERF_TYPED.md`: one short section per pair, the cause in one sentence, the
   before and after code blocks, the note text, and the measured ratio linked to `lab/perfguide/RESULTS.md`. Start
   with how to see the path (`--strict`, the note line). Every code block must be one of the measured programs, byte
   for byte. Commit and push.
4. **Test (10 min).** Write `AIL_CURRENT/test_ail_docs_perf.py`: it extracts the code blocks from the page, checks
   that each pair's output matches `python3`, that each "after" builds with `--strict`, and that each "before" still
   prints the general-path note. If a "before" sample becomes typed later, the test prints a message asking to update
   the page, and fails. It skips without a C compiler and does not measure instructions. Register it (Appendix A
   rule 6). Commit, push, and wait for CI.

## Done-check

- `docs/PERF_TYPED.md` has at least 12 pairs, each with a ratio from `lab/perfguide/RESULTS.md`.
- `python3 AIL_CURRENT/test_ail_docs_perf.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if a sample builds and prints output different from CPython (silent wrong output): commit it
in `lab/perfguide/RESULTS.md` first. Do not claim a speedup without an icount measure. Stop when 60 minutes pass. Push
what is done first.

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
