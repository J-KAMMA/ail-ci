Lane: tutproj

# tutproj1: a six-step tutorial project (a log analyser) on the typed path, every step checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** the steps of a worked tutorial project in `examples/tutorial_project/`. Each step must build
on the typed path with `--strict` and print exactly what `python3` prints, with the same exit status. This goes from
0 today to 6 steps. Also measured: the last step's wall time against `python3` on a 50 MB generated log (median of
3), and its binary bytes. It shows the main claim on code that a user grows step by step: "write Python, get a small
fast binary". This is roadmap P4, the tutorial programs.

Base: `origin/integ`. Files you may create or edit, and no others:
- `examples/tutorial_project/` (new): `step1.py` to `step6.py`, `gen_log.py`, `sample.log`, `README.md`
- `AIL_CURRENT/test_ail_examples_tutorial_project.py` and its `tests.d` file (new)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `examples/apps/`, `docs/` or any compiler file.

## The log format

`gen_log.py SEED N` prints N lines of `TIMESTAMP METHOD PATH STATUS BYTES MILLIS`, for example
`2026-11-04T10:00:01 GET /api/items 200 5120 12`. Make it deterministic from SEED, with no `random` module
dependence on the CPython version: write a small LCG. About 2 % of lines are malformed (too few fields, or a
non-number in BYTES). One BYTES value per 10,000 lines is `99999999999999999999`, beyond int64. Commit a
`sample.log` of 200 lines.

## The steps

Each step is the previous one plus one idea. It reads the log from stdin with `sys.stdin`, line by line, and uses
plain, idiomatic, annotated Python, as the tutorial reader would write it.
1. Count lines and malformed lines.
2. Count by status code with `dict[str, int]`, printed in sorted order.
3. Sum and maximum of BYTES and MILLIS. Decide what to do with the value beyond int64 and write the reason in the
   README. Either skip it as malformed, after a length check that is plain Python, or let the program stop loudly.
   Either way the output must equal CPython's.
4. Move the parsing into `def parse(line: str) -> Entry | None` with a small class `Entry`.
5. The top 5 paths by count (`sorted` with a key), and the p50 and p99 of MILLIS by the nearest-rank method.
6. Options from `sys.argv`: `--top N` and `--status 5xx`. A bad option prints usage to stderr and exits 2.

## Sub-steps

1. **Generator and steps 1-2 (20 min).** Write `gen_log.py`, `sample.log`, `step1.py` and `step2.py`. Build each with
   `--strict` and compare it with `python3` on `sample.log`. If `--strict` refuses natural code, do not twist the
   code. Keep it, record the exact refusal in the README as a finding, and count that step as general. Commit, push,
   and open the PR.
2. **Steps 3-4 (20 min).** The same method. Probe the int64 edge lines in both the default build and
   `AIL_UNIFIED_FORCE=1`. Commit and push.
3. **Steps 5-6 and the test (20 min).** Write `AIL_CURRENT/test_ail_examples_tutorial_project.py`. For each step it
   builds the program, requires a `--strict` build for the steps the README marks typed, runs it on `sample.log`
   and on a 5,000-line generated log, and compares stdout and the exit status with `python3`. For step 6 it also
   runs 3 argument sets, one of them bad. It skips when there is no C compiler. Register the test. Commit and push.
4. **README and numbers (15 min).** Write `README.md`. Each step gets a heading, what it adds (2-4 lines), the build
   and run commands, and typed or general. Add the step-6 table: `python3` wall time, AIL wall time and AIL binary
   bytes on a 50 MB log, median of 3. Delete the 50 MB file afterwards and do not commit it. Commit, push, and wait
   for CI.

## Done-check

- 6 steps match CPython in the test.
- The README says how many steps are typed under `--strict`, with a finding for each one that is not.
- The table is filled.
- The 20 shards pass.

## Stop rule

Stop and report if fewer than 3 steps reach the typed path without twisting the code; list the refusals. Stop when
80 minutes pass. Push what is done first.

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
