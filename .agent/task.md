Lane: ctime

# ctimes3: tally_lang spends 0.95 s loading its source; bring `_load_sources` down to the other tasks' level

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** parent `_load_sources` seconds on the 10 compare tasks (`lab/profile/run.py`, which times it
directly). Today on the GitHub runner (CTIME_2026-11.md): tally_lang 0.946 s, the other nine 0.071-0.245 s. The
target is tally_lang at 0.30 s or less, the others not slower, and the merged source text identical.

Price (speed-claims rule):
- share of cold wall: tally_lang 17.7% (0.946 of 5.359 s), Amdahl bound 1.21x; the other nine 1.2-6.1%, bound at
  most 1.07x; pooled over 10 tasks 4.9%, bound 1.05x.
- assumed roof: tally_lang down to about the other tasks' median (0.12 s), saving 0.83 s, 1.18x on tally_lang.
  Halved for this repo's record of overshooting: about 1.08x on tally_lang, near 1.00x elsewhere. It is a small,
  cheap cut on one outlier, worth one step, not more.

Base: `origin/integ` (after ctimes2 in this lane). Files you may create or edit, and no others:
- `AIL_CURRENT/ail_chatgpt.py`: only `_load_sources` (line ~4882) and the helpers it calls that no other caller
  uses. This lane is the only one editing this function; run `git fetch` and rebase just before each push;
- `lab/profile/CTIME_LOAD.md` (new);
- `AIL_CURRENT/test_ail_load_sources_same.py` (new) and `AIL_CURRENT/tests.d/test_ail_load_sources_same.txt` (new);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Find the cause (25 min).** Profile `_load_sources` alone on tally_lang and on chain_relax
   (`python3 -m cProfile` around a call that loads the source the way `compile` does). Name the function that makes
   tally_lang 8x slower: a quadratic pass, a repeated `ast.parse`, `translate`/`python_surface`/`fold_constants`
   run more than once, or an int64 or main check that rescans. Write the numbers in `CTIME_LOAD.md`. Write a small
   script that dumps `_load_sources`' result (the merged text and every other returned value) for the 10 `typed.py`
   and 10 `main.py` compare sources and the first 200 `lab/corpus/programs`, and save the base dump hashes.
   Commit, push, open the PR.
2. **Fix (30 min).** Remove the repeated or quadratic work. Keep every output and every error message the same.
   Commit and push.
3. **Verify (25 min).**
   - the dump hashes: 0 differences over all inputs; errors of refused programs unchanged;
   - generated `program.c` hash unchanged for the 10 tasks (`--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`);
   - instruction count of the parent build step on the 10 tasks, before and after (`tools/icount.c`, see
     `lab/profile/CTIME_CUT.md` from ctimes2 for the command); none higher by more than 0.5%;
   - `_load_sources` seconds for all 10 tasks, median of 3, with `lab/profile/run.py --no-profile`;
   - `test_ail_load_sources_same.py` checks the dump hash for 3 tasks; register it (Appendix A rule 6); run it and
     `test_ail_ctime`, `test_ail_modules`, `test_ail_build_cache`.
   Write before/after, price and achieved into `CTIME_LOAD.md`. Commit, push, wait for CI.

## Done-check

- tally_lang `_load_sources` at most 0.30 s on the runner, or at most a third of its base instruction count.
- No task's `_load_sources` instruction count higher by more than 0.5%.
- 0 differences in the dump hashes and in the 10 C hashes.
- The listed tests and the 20 shards pass.

## Stop rule

Stop and report if the cause is outside `ail_chatgpt.py` (name the file and function), or if the output cannot stay
identical. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build.
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
8. Never edit `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`,
   `cruntime.py`, `optlib.py`, `ir/passes/*` or `packaging/ail_lang/cli.py`. In `ail_chatgpt.py`, edit only what this
   task names. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`.
- `lab/profile/CTIME_2026-11.md` explains the harness and the phase split; `_load_sources` is timed in the real
  parent build, not estimated.
- Laptop wall time swings up to 3x. Use instruction counts for claims made on the laptop.

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
