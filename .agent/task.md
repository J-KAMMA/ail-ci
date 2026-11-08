Lane: ctime
Needs: ctimes1

> Re-run of mypyc1: the first run stopped because ctimes1 (CTIME_FE.md) was not merged. This copy sits in lane ctime, so it starts only after ctimes1_rr1 integrates. If CTIME_FE.md is still missing on origin/integ, stop and report again.

# mypyc1: price and trial-compile one hot front-end module with mypyc, in a scratch copy only (measure only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on ctimes1 (lane `ctime`) merged into `integ`: read its `lab/profile/CTIME_FE.md` first. If it is not merged,
stop and report. This job changes no compiler file, so it does not overlap ctimes2/ctimes3, which edit the front end.

**Number this moves:** the compiler's own instruction count and cold front-end seconds on the 10 compare tasks
(`lab/compare/src/<task>/typed.py`) when ONE front-end module is compiled with mypyc, in a scratch copy outside the
repository. Unknown today. The result decides whether mypyc2 builds the pilot in the repository.

## Price first (speed-claims rule; write it in `lab/mypyc/PRICE.md` before any trial)

- Measured share: the child front end is 28.31 of 45.82 s summed cold wall, 61.8% pooled (CTIME_2026-11.md); its
  Amdahl bound is 2.62x. From `CTIME_FE.md` take, per module, the share of cold wall spent in that module's OWN
  Python code (cProfile tottime of its functions). Time inside C code (`ast.parse`, `re`, `dict`/`list` builtins,
  `compile`) is not sped up by mypyc: leave it out of the share.
- Assumed roof: mypyc reports mypy about 4x and Black about 2x (claims, not AIL measurements). AIL's front end is
  AST-walking code over CPython `ast` objects with `isinstance` dispatch, which mypyc helps less than its native
  classes. Assume 1.5x on the module's own time, not 4x. For a module with own-time share s of cold wall, the
  projection is 1 / (1 - s * (1 - 1/1.5)).
- Earlier record in this repo: estimates overshot 2-3x (2.5x estimated, 0.88x measured; 1.83-1.92x estimated,
  0.62-0.78x measured). Halve the projected gain (for 1.10x write 1.05x).
- Whole-front-end ceiling, for the report only: if 60% of the front end is own Python time and all of it reaches
  1.5x, the build gets 1/(1 - 0.618*0.6/3) = 1.14x, halved 1.07x. The survey's -30..-45% assumes 2-4x on the whole
  front end; it is an upper bound, not a projection.
- Pick the pilot: the module with the largest own-time share that is NOT `pyfunc.py`, `optlib.py`, `cruntime.py` or
  `ir/passes/*` (busy lanes). Stop if its halved projection is below 1.03x on every task.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/mypyc/PRICE.md` (new), `lab/mypyc/RESULTS.md` (new)
- `lab/mypyc/trial.py` (new): makes the scratch copy, compiles the module, runs the measurements
- `lab/mypyc/patch_<module>.diff` (new): the changes mypyc needed in the scratch copy, kept as a diff, not applied

## Sub-steps

1. **Price and setup (20 min).** Write `PRICE.md` as above. Create a venv OUTSIDE the repository
   (`~/scratch/mypyc-venv`) and `pip install mypy==1.13.0` (record `mypyc --version`; if that version does not install
   on Python 3.12, pin the nearest one that does and write which). Add nothing to the repository's requirements.
   Commit, push, open the PR against `integ`.
2. **Trial compile (35 min).** `trial.py` exports `AIL_CURRENT` to a temp dir (`git archive origin/integ AIL_CURRENT`),
   runs `mypyc <module>.py` there, so the `.so` sits beside the `.py` and Python imports it first. Record every mypyc
   error. Fix only what mypyc rejects, in the scratch copy, with the smallest change (an annotation, an `Any`, moving
   a monkey-patch); save the diff as `patch_<module>.diff`. If more than 40 errors remain after 25 minutes, stop the
   trial and record the error kinds and counts. Commit and push.
3. **Measure (25 min).** With and without the `.so` in the scratch copy:
   - the generated `program.c` sha256 for the 10 `typed.py`, the 10 `main.py` and the first 100 sorted
     `lab/corpus/programs` (`--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_FE_JOBS=1`, then once with
     `AIL_FE_JOBS=4`). Use `lab/profile/ccheck.py` from ctimes2 if it is merged; otherwise write the same loop in
     `trial.py`. The refusal stderr of refused programs must match too;
   - compiler instruction count on the 10 tasks (`tools/icount.c`, the command in ctimes2's task or
     `lab/profile/CTIME_CUT.md`);
   - cold front-end seconds, median of 3, laptop (shape only; the instruction ratio is the claim).
   Fill `RESULTS.md`: price, achieved, achieved over price, and a go/no-go for mypyc2. Commit, push, wait for CI.

## Done-check

- `PRICE.md` has the share, Amdahl bound, assumed roof and halved projection, committed before the trial commit.
- `RESULTS.md` shows 0 hash differences (C and refusal text) over all 120 inputs, or lists each difference and says
  no-go.
- Compiler instruction count before/after on 10/10 tasks, with the ratio.
- `git diff --stat origin/integ` shows only files under `lab/mypyc/`; the 20 shards pass.

## Stop rule

Stop on any wrong output: any difference in generated C, executable output or refusal text between the mypyc copy
and the plain copy, or against CPython for a program that matched before. Record it first. Stop if the halved
projection is below 1.03x everywhere. Stop when 80 minutes pass. Push what is done first.

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
8. Edit no file outside `lab/mypyc/`. Do not edit `DEVLOG.md`. Install nothing system-wide; the venv lives in
   `~/scratch`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet.
- The front end runs in a child process (`python/pkg-v12/pyc.py`); the `.so` must sit beside the module in the copied
  tree so both parent and child import it. Check with `python3 -c "import <module>; print(<module>.__file__)"` from
  the copied `python/pkg-v12`.
- `AIL_FE_JOBS` (fepar2) runs the typed front end on worker processes for 8+ functions.
- Laptop wall time swings up to 3x. Use instruction counts for claims made on the laptop.

## Owner decision (2026-11-05)

- mypy (pinned) may be a dev dependency. The compiled .so stays out of the 0.1 wheel.

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
