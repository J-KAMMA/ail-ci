Lane: ctime

# ctimes1: where the cold front end spends its time, priced function by function (measure only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the share of the cold child front end that is attributed to a named function or attempt, in a
new table `lab/profile/CTIME_FE.md`. Today it is 0%: `lab/profile/CTIME_2026-11.md` (ctimeprofb/c) shows the child
front end as one block. The target is at least 90% of it attributed, on 10/10 compare tasks, with a price for each
row. This job changes no compiler file. Its table picks the cut that ctimes2 builds.

Why this phase: the child "front end to C text" is the largest phase of a cold build (CTIME_2026-11.md, GitHub
runner, 4 cores, median of 3):

| | seconds, 10 tasks | share of cold wall | Amdahl bound |
|---|---:|---:|---:|
| child front end to C text | 28.31 of 45.82 | 61.8% pooled (43.8% tally_lang .. 81.6% berth_sim) | 2.62x pooled (1.78x .. 5.43x) |
| gcc code generation | 11.90 | 26.0% pooled | 1.35x |
| parent `_load_sources` | 2.25 | 4.9% pooled (17.7% tally_lang) | 1.05x (1.21x tally_lang) |

gcc is not the target: a cached separate runtime was measured in #233 and lost up to +13% run instructions
(inlining), and the parallel gcc split (#305) is opt-in because it costs up to +0.43% run icount. The owner allows no
icount loss. Roadmap P2 asks for compile time within 5x of Rust; AIL is 9-12x today, so the whole build must get
about 2x faster, which is 76% of the front end removed. No single cut does that: price each one.

Base: `origin/integ`. Files you may create or edit, and no others:
- `lab/profile/run.py` (add an `--fe-profile` mode; keep its current output unchanged)
- `lab/profile/CTIME_FE.md` (new) and `lab/profile/CTIME_FE.json` (new)

## Sub-steps

1. **Profile hook (20 min).** Add `--fe-profile` to `lab/profile/run.py`. For each task it runs the child
   `python/pkg-v12/pyc.py` command once more under `python3 -m cProfile -o <file>` (print the command list as
   ctimeprofb did, in a scratch copy only), and once under `perf_counter` wrappers with no profiler. Record, per task:
   - the path taken (typed, general, mixed) and the fallback note;
   - whether `AIL_FE_JOBS` workers ran (fepar2: on for 8+ functions on POSIX), and the worker count;
   - the time of every attempt that ended in a refusal before the build switched paths (a typed attempt that raised
     `Unsupported`, each pymix candidate tried). This "wasted attempt" time is the first thing to measure.
   Run 3 tasks (berth_sim, tree_fold, tally_lang) with `--runs 3` under `ulimit -v 1500000`. Commit, push, open the
   PR against `integ`.
2. **All 10 tasks (30 min).** Run all 10 on the laptop for the shape, then on GitHub if a profile-lab run on your
   branch is allowed without editing `.github/workflows` (otherwise laptop only, and say so). Write
   `CTIME_FE.json`: per task, the top 25 functions by own time and by cumulative time, mapped to module, and the
   attempt times. Commit and push.
3. **Price the cuts (30 min).** Write `CTIME_FE.md`:
   - one row per candidate (a function, a module, a wasted attempt, a repeated walk): seconds per task, share of cold
     wall, Amdahl bound, and the file and function that own it;
   - for each, the assumed fraction of its roof and what earlier cuts achieved. Earlier results: ctime walk reuse
     1.15x on the front end; ctime1 34.64 -> 20.54 s Python time (reviewer); fepar2 old tree 1.208x whole build with
     4 workers. Estimates in this repo have overshot by 2-3x (2.5x estimated, 0.88x measured): halve every projection;
   - mark each row's file as free or owned by a busy lane. Busy lanes: codegen and bce-ranges (`pyfunc.py`,
     `ir/passes/*`, `optlib.py`, `cruntime.py`), pyreach and pyreach-none (`pyfunc.py`), typeshed;
   - name the pick for ctimes2: the row with the largest halved bound in a free file, at least 1.10x on 3 tasks.
     If the best row is in a busy file, name it as a follow-up for that lane, and also name the best free row.
   Commit and push.

## Done-check

- `CTIME_FE.md` covers 10/10 tasks, and the attributed time is at least 90% of the child front end for each task.
- Every row has seconds, share, Amdahl bound and the halved projection.
- `git diff --stat origin/integ` shows only the three files above; `python3 lab/profile/run.py --tasks chain_relax
  --runs 1 --no-profile` still writes the same columns as before.
- The 20 shards pass.

## Stop rule

Stop and report if the cProfile run and the plain run of a task differ by more than 2x in child wall (the profile
then misleads; report both). Stop when 80 minutes pass. Push what is done first.

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
8. Do not edit `DEVLOG.md`: put your notes in the files this task names. Edit only the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general
  path ...` on stderr.
- The compare tasks: `lab/compare/src/<task>/typed.py` (the `ail` column). `lab/profile/run.py` is the ctimeprofb
  harness; read `lab/profile/CTIME_2026-11.md` first, including "Harness bugs" (share `AIL_FE_CACHE_DIR`, keep
  bytecode, `AIL_NO_CACHE=1`, fresh `AIL_CACHE`/`TMPDIR`).
- Wall time on the WSL laptop swings up to 3x. Use it for shapes and ratios within one run; use the GitHub runner or
  instruction counts (`tools/icount.c`) for claims.
- `tools/roofcheck_v1.py` is not in this tree: price by hand (share, Amdahl bound, assumed vs achieved roof).

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
