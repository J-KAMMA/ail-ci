**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I have enough to report. Let me summarize the evidence.

**What the change really does:** adds a 21-item `docs/MIGRATING.md` checklist, 21+1 sample programs, a `lab/migrating/RESULTS.md` class table, and a differential test that checks the page's code blocks against the files and each sample's class. It touches no compiler or runtime source (`program.c` for a plain program is byte-identical to base), and the allowed-file list is respected.

**Probes** (`bash ~/tools/cmp.sh … $PWD`, default + `AIL_UNIFIED_FORCE=1`):

| probe | result |
|---|---|
| r1 recursion 60000 | default: same stderr `RecursionError: maximum recursion depth exceeded`, exit 1. Forced-general prints 60000, exit 0 (base-identical) |
| r13 recursion 49999 / 50001 | 49999 prints, exit 0; 50001 stops → the guard is a **fixed 50,000-frame counter**, not the C stack |
| r3 `print(2 ** -1)` | 0.5, exit 0, both builds = CPython |
| r4/r15 literal 2**63 and −2**63−1 | build refused on both paths, `int64 literal out of range` |
| r5–r8, r14 overflow via argument / list item / attribute / dict value / int64-min | loud `OverflowError: integer overflow in +|-`, exit 1, both paths |
| r9 `except Exception` around `sys.exit(3)` | exit 3, same stdout |
| r16 literal-mode `open`, r18 `float(2) ** -1`, r19 `abs(-4.0) ** .5`, r21 flush-then-overflow | same as CPython / `before` flushed |
| r20 utf-16 file read as `rb` then `.decode("utf-16")` | **build refused** on both paths: `bytes.decode() with the encoding 'utf-16' … built: utf-8, ascii, latin-1` |
| r22 `x=-4.0; n=0.5; print(x**n)` | default build prints `nan`, exit 0 (silent wrong; base-identical); `AIL_UNIFIED_FORCE=1` exits 3 |
| r10 `a = "x"+"y"; b="xy"; print(a is b)` | `False` vs CPython `True`, identical on base — pre-existing, correctly logged in RESULTS "Bugs" |
| r12 plain program, `--debug-dir` | `program.c` identical HEAD vs `/tmp/base` |

**Tests:** `par_check.py -j 2 test_ail_docs_migrating test_ail_safetynet` → the new module passes; `test_ail_safetynet` `S4_generators_gc` fails (`'5530537\n'` vs five lines) and fails identically on base `/tmp/base` → pre-existing. `tools/update_manifest.py --check` exit 0. 21 checklist items, 21 code blocks, 21 result rows.

**Claims:** rlimit-as-`preexec_fn` (3 call sites, no `setrlimit` in the parent) — verified by inspection; BIGINT link and every link in the page resolve — verified; items 10/12/19 now link `PORTING.md` and the thread speed figure is gone — verified; "8 tests OK" and "28 tests OK" — not reproducible here (safetynet fails on base too), so unverified; "3 files changed" is true only for the last commit, the whole change is 24 files/721 insertions — misleading, but every file is on the allowed list.

**Defects (the page describes behaviour no sample shows, and two of them are false):**

1. `docs/MIGRATING.md` item 3 bullet: "Deep recursion stops at the real C stack limit" — it stops at a fixed 50,000-frame guard (its own section says so). Probe r13: `down(49999)` prints 49999 exit 0; `down(50001)` stops with `RecursionError`. Expected per bullet: a stack-exhaustion stop; actual: a counter at 50,000 (and the true stack limit in the forced-general build is a SIGSEGV, r13 at 200000, exit 139).
2. Item 14 bullet: "An integer raised to a negative exponent stops" — the item's own text admits a constant exponent does not. Probe r3 `print(2 ** -1)` → `0.5`, exit 0, both builds.
3. Item 11 bullet: "A complex result is refused" — only a constant is. Probe r22: the default build builds and prints `nan`, exit 0 (the general build exits 3), so a user is told a refusal happens where the default build silently answers.
4. Item 16 "What to do instead: … read the bytes with `"rb"` and decode them yourself" — probe r20: `bytes.decode("utf-16")` is refused on both paths; the advice cannot be followed.
5. Footer: "the default build falls back and prints one `note:` line" contradicts item 18 and the measurement: `threads.py` builds with **two** `note:` lines (`grep -c '^note:'` = 2).

VERDICT: FIX
1. `docs/MIGRATING.md` item 3 bullet — replace "the real C stack limit" with the 50,000-frame guard (probe `/tmp/rprobes/r13_rec_49999.py` prints `49999`, exit 0; `r13_rec_50001.py` stops with `RecursionError`, exit 1).
2. `docs/MIGRATING.md` item 14 bullet — qualify it (constant negative exponent gives the float); probe `/tmp/rprobes/r3_const_neg_exp.py` expected stop, actual `0.5`, exit 0.
3. `docs/MIGRATING.md` item 11 bullet — say constant operands are refused and non-constant ones stop (or are a bug); probe `/tmp/rprobes/r22_complex_nonconst.py` expected refusal, actual default build `nan`, exit 0.
4. `docs/MIGRATING.md` item 16 advice — drop "read the bytes and decode them yourself"; probe `/tmp/rprobes/r20_decode_utf16.py` expected the text, actual build refusal `bytes.decode() with the encoding 'utf-16'`.
5. `docs/MIGRATING.md` footer — say two note lines for a fallback with a second reason (as item 18 does); measured build of `threads.py` prints two.

Pre-existing (does not block): `test_ail_safetynet` S4_generators_gc (same on base), `is` on str (`True`→`False`), `nan` for a non-constant negative fractional power, and the `AIL_UNIFIED_FORCE=1` deep-recursion exit-139 at 200,000 — all identical on `/tmp/base`.

Unverified: the CI shards (nothing pushed), the required 28-test suite (only the two allowed modules were run), and the report's `getrlimit` after-run value.
[commandcode stop=end_turn turns=24 out_tokens=31623]


--- ORIGINAL TASK ---
Lane: docmigr

# docmigr1: `docs/MIGRATING.md`, a "migrating from Python" checklist, every item checked by a test

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** checklist items with a sample that a test runs under both CPython and AIL. `docs/PORTING.md`
covers refusals and their rewrites. It does not cover the programs that build but behave differently on purpose: int64
overflow stops, deep recursion stops, no `eval`, and so on. A Python user needs that list before the first build.
Today it is scattered across `docs/spec/DIFFERENCES.md` and `AIL_CURRENT/AIL_REFERENCE.md`. The target is a checklist
of at least 15 items, each with a sample whose CPython result and AIL result the test checks.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `docs/MIGRATING.md`
- `lab/migrating/*.py` (one sample per item) and `lab/migrating/RESULTS.md`
- `AIL_CURRENT/test_ail_docs_migrating.py` and `AIL_CURRENT/tests.d/test_ail_docs_migrating.txt` (one line:
  `test_ail_docs_migrating`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `docs/PORTING.md`, `docs/spec/DIFFERENCES.md`, `README.md` or `docs/QUICKSTART.md`. Link to them.

## Sub-steps

1. **The items (25 min).** Read `docs/spec/DIFFERENCES.md` and the owner decisions in `docs/ROADMAP.md`. Pick at
   least 15 differences a user will meet, each confirmed on `origin/integ` with a 5-20 line sample, for example:
   - an int beyond int64 stops with `OverflowError` (CPython prints the big number); how to keep exact big ints if
     `integ` has a way;
   - deep recursion stops with `RecursionError` near the real stack limit, not at 1000;
   - `eval`/`exec`/`compile` and dynamic `import` are refused, with the refusal text;
   - catching `SystemExit` is not supported;
   - threads keep a GIL in the hybrid; a shared int `+=` in typed parallel code is refused;
   - float sums in parallel code keep a fixed order only when opted in;
   - which standard modules build (link to the stdlib table), and what happens on one that does not;
   - the build is one executable: no `__file__` loader, no `.pyc`;
   - `--strict` and the general-path note.
   Classify each sample's AIL result: `same`, `loud stop` (non-zero exit with a named error) or `refused` (the build
   says why). A sample whose AIL output differs silently is a bug, not an item (see the stop rule). Write
   `lab/migrating/RESULTS.md` with one row per sample. Commit, push, and open the PR against `integ`.
2. **The page (20 min).** Write `docs/MIGRATING.md` as a checklist: one `- [ ]` line per item with one sentence, then
   a short section per item with the sample, CPython's output, AIL's result, and what to do instead. Link refusals to
   `docs/PORTING.md`. Code blocks are the files in `lab/migrating/` byte for byte. Commit and push.
3. **Test (15 min).** Write `AIL_CURRENT/test_ail_docs_migrating.py`: for each item, check the code block equals the
   file, run it with `python3` and with the AIL build (default mode), and check the class in `RESULTS.md`: `same`
   means equal stdout and exit status; `loud stop` means non-zero exit and the named error in stderr's last line;
   `refused` means the build fails with the quoted text. Skip without a C compiler. Register it (Appendix A rule 6).
   Commit, push, and wait for CI.

## Done-check

- `docs/MIGRATING.md` has at least 15 items, each with a sample and its class.
- `python3 AIL_CURRENT/test_ail_docs_migrating.py` passes; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if a sample builds and prints output different from CPython without a loud stop (silent wrong
output): commit it in `lab/migrating/RESULTS.md` under "Bugs" first. Do not describe behaviour that no sample shows.
Stop when 60 minutes pass. Push what is done first.

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
