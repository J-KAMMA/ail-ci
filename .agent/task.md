**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1 skipped: only 11 minutes left


--- ORIGINAL TASK ---
Lane: guide

# guide1: the 0.1 user guide (`docs/guide/`), every code sample built and checked against CPython by a test

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** user-guide code samples that a test builds with AIL, runs, and checks against CPython,
byte for byte. Today there are 0: `docs/tutorial.md` exists, but there is no guide. Target: **≥ 40 samples** in 4
chapters. Each claim in the text must be one that a sample shows, or one that cites a file in the repository.
This is the roadmap's P4 item "docs", the 0.1 user guide.

Base: `origin/integ`. Files you may create or edit, and no others:
- `docs/guide/README.md`, `docs/guide/01-typed-and-general.md`, `docs/guide/02-text-bytes-files.md`,
  `docs/guide/03-errors-and-exit.md` and `docs/guide/04-modules-and-c.md` (all new)
- `AIL_CURRENT/test_ail_guide.py` and `AIL_CURRENT/tests.d/test_ail_guide.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `docs/tutorial.md`, `README.md`, `docs/INSTALL.md`, `docs/COMPARISON.md`, `docs/QUICKSTART.md`,
`docs/FFI.md` or `AIL_CURRENT/test_ail_tutorial.py`. Other lanes own them. Link to them instead.

## The sample format

Use the format of `docs/tutorial.md` exactly, so that readers see one style. Read the docstring of
`AIL_CURRENT/test_ail_tutorial.py`. Each sample is an HTML comment, `<!-- sample: NAME [general] [refuse] [stop]
[args=A,B] -->`, followed by a ```python block and an optional ```output block. Copy that file's `parse()` logic
into `test_ail_guide.py`. Do not import it or edit it. Then extend the test to every `docs/guide/*.md` file. Sample
names must be unique across the guide.

## Sub-steps

1. **Test harness and chapter 1 (20 min).** Write `test_ail_guide.py`. For every sample it does three things:
   - builds it with the default command;
   - runs it, and requires stdout and the exit status to equal `python3`'s on the same file;
   - if the chapter shows an ```output block, requires that block to equal CPython's stdout.
   A `general` sample must print the general-path note. A `refuse` sample must be refused, with the shown line in
   the compiler's message. A `stop` sample must stop with a non-zero status, and so must CPython where CPython also
   fails. Do not compare paths or hashes.
   Chapter 1, `01-typed-and-general.md` (≥ 10 samples):
   - what reaches the typed path: annotated functions, `int`, `float`, `str`, `list[int]`, `dict[str, int]`, and a
     small class;
   - how to read the general-path note, and what `--strict` does;
   - int64 by default, and an overflow that stops loudly (a `stop` sample);
   - how to keep exact big ints, if `integ` has a way. Find it in `AIL_CURRENT/AIL_REFERENCE.md`, or leave it out.
   Commit, push, and open the PR against `integ`.
2. **Chapter 2 (15 min).** `02-text-bytes-files.md` (≥ 10 samples): `str` and `bytes`; f-strings and `%` formatting;
   `split`, `join` and `strip`; reading `sys.stdin` by line and `sys.stdin.buffer` as bytes (feed stdin from the
   test, as the tutorial's test does); writing and reading a file in a temporary directory; `sys.argv` (`args=`).
   Commit and push.
3. **Chapter 3 (15 min).** `03-errors-and-exit.md` (≥ 10 samples): `try`/`except`/`else`/`finally`; raising and
   catching `ValueError` and `KeyError`; a user exception class; `sys.exit(n)` statuses; an uncaught exception. For
   the uncaught one, show the runtime error text, which names the exception and the source line. Check that the
   text is what the default build prints today. Also show `int("x")` and division by zero. Commit and push.
4. **Chapter 4 and the index (20 min).** `04-modules-and-c.md` (≥ 10 samples): standard modules that build today
   (`math`, `re`, `json`, `csv`, `collections`, `heapq`, `bisect`, `statistics`, `shlex`); keep only those whose
   sample passes. Add one `ail_ffi` sample calling libm `cbrt`, as in `examples/ffi/libm_math.py`. Mention
   multi-file programs only with a link to the docs that cover them; do not invent behaviour. `docs/guide/README.md`
   lists the chapters with one line each and links to `docs/tutorial.md` and `docs/INSTALL.md`. Register the test
   and run it. Commit, push, and wait for CI.

Rules for the text: short sentences and plain English. No speed or size number unless it is quoted from
`docs/COMPARISON.md`, with that link. Do not describe a feature without a sample that shows it.

## Done-check

- `python3 AIL_CURRENT/test_ail_guide.py` passes with ≥ 40 samples (print the count).
- Every chapter has ≥ 10 samples.
- `git diff --stat origin/integ` lists only the files above.
- The 20 shards pass.

## Stop rule

Stop and report if the tutorial's sample format cannot be reused. Also stop if a chapter cannot reach 6 passing
samples without a compiler change: list the refusals. Stop when 80 minutes pass. Push what is done first.

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
