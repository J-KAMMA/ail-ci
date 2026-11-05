Lane: mypyc

# mypyc2: opt-in mypyc build of the one pilot front-end module, with byte-identical C

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on mypyc1 merged with a "go" in `lab/mypyc/RESULTS.md`, and on ctimes2 and ctimes3 (lane `ctime`) merged:
this job edits a front-end file and must not overlap the ctime lane. If any of the three is not merged, or mypyc1
said no-go, stop and report.

**Number this moves:** compiler instruction count and cold front-end seconds on the 10 compare tasks, with the pilot
module compiled. The target is mypyc1's halved projection, at least 1.03x fewer instructions on 3 tasks, with 0 bytes
of generated C changed. With no `.so` present the build is the plain Python build, as today.

Base: `origin/integ`. Files you may create or edit, and no others:
- the one pilot module mypyc1 named: only annotations and the small rewrites in `lab/mypyc/patch_<module>.diff`. Run
  `git fetch` and rebase on `origin/integ` just before each push. Keep the diff under 150 lines;
- `tools/mypyc_build.py` (new): builds the `.so` for the pilot into the source tree, opt-in, with the pinned mypy;
- `.gitignore` (one line for the built `.so` and the mypyc `build/` directory);
- `lab/mypyc/RESULTS.md` (append), `AIL_CURRENT/test_ail_mypyc_pilot.py` (new) and
  `AIL_CURRENT/tests.d/test_ail_mypyc_pilot.txt` (new, one line: `test_ail_mypyc_pilot`);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Annotate in place (30 min).** Apply mypyc1's diff to the real module. Run `mypyc` on a temp copy until it
   compiles. Without the `.so`, run the hash check (C, executable, refusal text) over mypyc1's 120 inputs: 0
   differences. Commit, push, open the PR against `integ`.
2. **Build script and test (25 min).** `tools/mypyc_build.py`: creates `~/scratch/mypyc-venv` if missing, runs mypyc
   on the pilot, places the `.so` beside it and prints its path; `--clean` removes it. The default build, the
   manifest and the wheel never contain the `.so` (shipping it is an owner decision). `test_ail_mypyc_pilot.py`: skips
   when mypy is not installed; otherwise builds the `.so` in a temp copy and checks that the C hash of 3 tasks and 5
   corpus programs equals the plain build, under `PYTHONHASHSEED` 0 and 3 and `AIL_FE_JOBS` 1 and 4. Register it
   (Appendix A rule 6). Commit and push.
3. **Measure (25 min).** With and without the `.so`: compiler instruction count on the 10 tasks; cold front-end
   seconds, median of 3. Run `test_ail_ctime`, `test_ail_fe_jobs`, `test_ail_build_cache` and the new test, without
   and with the `.so`. Append price, achieved, and achieved over price to `RESULTS.md`. Commit, push, wait for CI.

## Done-check

- 0 hash differences in C, executable and refusal text over the 120 inputs, with and without the `.so`.
- Instruction count lower on at least 8 of the 10 tasks with the `.so`; without it, none higher by more than 0.5%.
- The listed tests and the 20 shards pass.

## Stop rule

Stop on any wrong output: a byte of generated C, an executable's output, or a refusal message that differs from the
plain build or from CPython. Stop if the module needs a change outside annotations and the mypyc1 diff, or more than
150 lines. Stop when 80 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `cruntime.py`, `optlib.py`,
   `ir/passes/*`, `buildcache.py`, `packaging/*` or `pyproject.toml`. In the pilot module change only annotations and
   the mypyc1 diff. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- Python imports an extension `.so` before a `.py` of the same name in one directory, so a `.so` beside the module
  takes over without a source change.
- Owner decisions on compile time (2026-10-30): gcc `-O2` stays. This job does not touch the C side.
- Laptop wall time swings up to 3x. Use instruction counts for claims made on the laptop.

## Owner decision (2026-11-05)

- mypy (pinned) may be a dev dependency. The mypyc-compiled .so does NOT ship in the 0.1 wheel, which stays pure-Python and platform-independent. Keep the build opt-in.

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
