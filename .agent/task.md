Lane: fa-ctpred
Needs: ctpred1

# ctpred2: memoise the pyfunc predicates that ctpred1 proved repeat with an unchanged answer, with byte-identical C

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Read `lab/profile/CTIME_PRED.md` first. If it says no-go, stop and report without editing anything.

**Number this moves:** the compiler's own instruction count and the cold front-end seconds on the 10 compare tasks.
The target is ctpred1's halved projection, and at least 1.03x fewer compiler instructions on 3 tasks, with 0 bytes of
generated C, executable or refusal text changed on `lab/profile/ccheck.py`'s inputs. Price: write `CTIME_PRED.md`'s
numbers for the predicates built here (cacheable seconds, lookup cost, projection, halved) at the top of
`lab/profile/CTIME_PRED_CUT.md` before the first edit.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: only the first three predicates on ctpred1's list, at most 80 changed lines.
  Other lanes (codegen, bce-ranges, pyreach) edit this file, so run `git fetch` and rebase on `origin/integ` just
  before each push, and keep each change inside the predicate's own function.
- `lab/profile/CTIME_PRED_CUT.md` (new)
- `AIL_CURRENT/test_ail_ctime_pred.py` and `AIL_CURRENT/tests.d/test_ail_ctime_pred.txt` (new)
- the manifest files that `tools/update_manifest.py` writes

Cache shape: one dict per build per predicate, keyed as ctpred1 keyed it. The value is `(node, result)`, so the node
stays alive and its id cannot be reused. The dict is cleared wherever `pyfunc` starts a new program, and also where
it starts a new function if ctpred1 found ids shared across functions. `AIL_PRED_CACHE=0` turns the cache off, for
measurement. Unhashable arguments bypass the cache.

## Sub-steps

1. **First predicate (20 min).** Cache the predicate with the most cacheable seconds. Run `ccheck.py` against the
   base hashes: 0 differences. Count compiler instructions on the 10 tasks (`tools/icount.c` around the child
   command, as `lab/profile/CTIME_CUT.md` describes). Commit, push, and open the PR against `integ`.
2. **Two more (20 min).** Cache the next two, if each is still at least 1.03x halved on 3 tasks by itself on top of
   the first. Otherwise skip it and say why. Run `ccheck.py` again, under `PYTHONHASHSEED` 0 and 3, and with
   `AIL_FE_JOBS` 1 and 4. Commit and push.
3. **Measure and test (20 min).** Instructions on the 10 tasks with the cache on and with `AIL_PRED_CACHE=0`; cold
   front-end seconds, median of 3, with `lab/profile/run.py --no-profile`. In `CTIME_PRED_CUT.md`, write the price,
   the achieved result, and achieved over price. The test builds 3 tasks and 5 corpus programs with the cache on and
   off, and checks that the C hashes are equal. Also run `test_ail_ctime`, `test_ail_fe_jobs` and
   `test_ail_build_cache`. Register the new test. Commit, push, and wait for CI.

## Done-check

- 0 differences in `ccheck.py` (C, executable and refusal text) under both hash seeds and both `AIL_FE_JOBS` values.
- At least 1.03x fewer compiler instructions on 3 tasks, and none of the 10 tasks higher by more than 0.5%.
- `CTIME_PRED_CUT.md` gives the price, the achieved result and the ratio; the 20 shards pass; the diff shows only the
  listed files.

## Stop rule

Stop on any `ccheck.py` difference that the cache causes (it disappears with `AIL_PRED_CACHE=0`). Revert that
predicate, record it, and do not search for a workaround. Stop if the first predicate gives under 1.01x
instructions on every task. Stop when 60 minutes pass, and push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`,
   `cruntime.py`, or `packaging/ail_lang/cli.py`. `pyfunc.py` is the one exception, and only within the predicates
   this task names. Other lanes own it too, so rebase just before each push. Do not edit `DEVLOG.md` either. Edit
   only the files this task names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet.
- Compile-time numbers: `lab/profile/run.py` (cold builds, `--fe-profile`, `--no-profile`, `--runs N`);
  `lab/profile/CTIME_2026-11.md` (phase shares), `CTIME_FE.md` (ctimes1, function and module rows),
  `CTIME_CUT.md` (ctimes2, the price of the pyfunc predicates). Instruction counts come from `tools/icount.c`. Timing on
  this laptop is noisy, so icount judges and wall time is reported as a median of 3 on the GitHub runner.
- Byte identity: build with `--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`, `AIL_SERVER=0` and a fresh `AIL_CACHE`;
  compare `sha256(program.c)`, `sha256(executable)` and the refusal text of refused programs.
- Speed-claims rule: before any edit, write the phase share, the Amdahl bound and the projection, then halve the
  projection, because this repo's estimates overshot 2-3x (2.5x estimated, 0.88x measured). A step whose halved
  projection is under 1.03x is not built.

## Owner decision (2026-11-06)

- A small, isolated edit to a restricted file (pyfunc.py, pyc.py, cli.py, ail_chatgpt.py) is allowed, but only when no other running job edits the same file. Check the open job branches before you start. Keep the edit to a minimal hook.

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
