Lane: porting

# porting1: `docs/PORTING.md`, the 12 most common refusals and their rewrites, every pair checked by a test

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** documented refusal-to-rewrite pairs that a test keeps true. Today 0: a user who hits a refusal
has only the message. For release 0.1 a user needs one page that says "you wrote this, AIL refuses it like this,
write this instead". Target: at least 12 pairs in `docs/PORTING.md`; for each, the `before` program is refused with
the documented message text and the `after` program builds in the default mode and prints what CPython prints (which
is what the `before` program prints under CPython).

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `docs/PORTING.md`
- `AIL_CURRENT/language_examples/porting/<name>_before.py` and `<name>_after.py` (one pair per entry)
- `AIL_CURRENT/test_ail_porting_docs.py` and `AIL_CURRENT/tests.d/test_ail_porting_docs.txt` (one line:
  `test_ail_porting_docs`)
- the manifest files that `tools/update_manifest.py` writes
Do not edit `README.md`, the other docs, or any compiler file. A message that is unclear is recorded, not changed.

Model: `AIL_CURRENT/test_ail_quickstart_docs.py` and `docs/QUICKSTART.md` (`<!-- example: NAME -->` markers before
each fenced block; the block text equals the file).

## Sub-steps

1. **Pick the entries (15 min).** Take candidates from the blocker buckets in `lab/stdcensus/RESULTS.md` and their
   reproducers in `lab/stdcensus/repro/`, from the `refused by name` rows of `DIFFERENCES.md`, and from
   `AIL_CURRENT/test_ail_beginner_errors.py`. Pick 12-15 that an ordinary program hits, for example: a dict view kept
   in a name; a name imported and assigned again; one `import` line mixing local and other modules; a class-level
   constant built from a list item; a starred call argument; a decorator other than the supported ones; `with` around
   a `yield`; a caught exception type that is not an Exception subclass; `type(x)` / `id(x)` used as a value; an int
   literal beyond int64; `open()` with a non-literal mode; `sys.stdin` used as a plain value. For each, confirm on
   today's integ that a 5-20 line `before` program is refused (record the exit status and the first stderr line), and
   that a natural rewrite builds and matches CPython. Drop any entry whose rewrite is not natural Python. Commit, push,
   and open the PR against `integ`.
2. **The page (30 min).** Write `docs/PORTING.md`: a short intro (AIL's rule: CPython's output or a refusal; what a
   refusal looks like; the `--strict` flag and the general-path note), then one section per entry: the refusal message
   as a `text` block (with the path part replaced by `prog.py`), the `before` block, the `after` block, and one or two
   sentences on why AIL refuses it (from the message itself or `DIFFERENCES.md`; cite the row id). Mark each code block
   with `<!-- example: <name>_before.py -->` or `_after.py`. Commit and push.
3. **Test (20 min).** Write `AIL_CURRENT/test_ail_porting_docs.py`. It checks: every `python` block in
   `docs/PORTING.md` has a marker and equals its file; every `before` file is refused (non-zero compile exit), and the
   documented message text, with `prog.py` matched against the real file name, appears in the first stderr line;
   every `after` file builds in the default mode and prints the same stdout and exit status as `python3` running the
   `before` file. It skips the builds when there is no C compiler, and runs the builds 2 at a time at most. Register it
   (Appendix A rule 6) and run it. Commit and push.
4. **Findings (15 min).** Do not add findings to `docs/PORTING.md`. Put them in the PR description: every refusal
   message you saw that lacks the user's `file:line:`, names a compiler-internal symbol, or gives no hint, with the
   exact text. Wait for CI.

## Done-check

- `docs/PORTING.md` has at least 12 entries and `python3 AIL_CURRENT/test_ail_porting_docs.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if fewer than 8 entries have a natural rewrite that builds and matches CPython; list the ones that do
not and why. Stop when 80 minutes pass. Push what is done first.

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
