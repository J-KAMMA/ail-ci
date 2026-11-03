Lane: ctime

**Finish ctimeprof: the phase table for compile time, and why a front-end cache hit is barely faster.** The run on
branch `job-ctimeprof-11032049` wrote a harness and raw data, then ran out of model quota, so it got no verdict.

Start on a branch from `origin/integ`. Take only the measurement files:

```
git fetch origin job-ctimeprof-11032049
git checkout origin/job-ctimeprof-11032049 -- lab/profile/run.py lab/profile/CTIME_2026-11.json
git commit -m "ctime: take the ctimeprof harness and raw data"
```

Do NOT apply that branch's change to `pyfunc.py`. It changes type inference and is out of scope.

# ctimeprofb: where a build's time goes, and the cache-hit gap

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** `lab/profile/CTIME_2026-11.md` has a per-phase table for 10/10 compare tasks (today: none).
It also measures the build time on an `AIL_FE_CACHE=1` hit. For chain_relax that is 3.99 s today, against 4.09 s cold:
the hit saves 2%. The target is a hit of 1.5 s or less, if the cause lies in the files this job may edit.

Base: `origin/integ`.

**Measured 2026-11-04 on integ 095e0321 (WSL laptop, `lab/compare/src/chain_relax/typed.py`):**
- A cold build takes 3.69 CPU s. Python is 3.05 s (83%) and gcc is 0.64 s.
- The parent process spends 0.56 s in `_load_sources`, and the child process `python/pkg-v12/pyc.py` spends 3.0 s.
- Importing `pyc` and `pyfunc` takes 0.14-0.27 s with bytecode cached and 1.0 s without. `_compiler_python` already
  lets the child write `__pycache__`.
- With `AIL_FE_CACHE=1` and one shared `AIL_FE_CACHE_DIR`, the second build logs `hit` yet still takes 3.99 s.
- The old json logged `miss` on its "hit" runs because every run used a fresh cache dir. That is a harness bug.

## Sub-steps

1. **Harness (15 min).** In `lab/profile/run.py`, make each hit run share `AIL_FE_CACHE_DIR` with its cold run, and
   assert that the `AIL_FE_CACHE_LOG` file says `hit`. Run 3 tasks, median of 3, under `ulimit -v 1500000`.
   Commit, push, open the PR.
2. **Phase table (25 min).** For all 10 tasks, median of 3, measure:
   - parent Python: CLI, `_load_sources` and the front-end checks;
   - child `pyc.py`: import, then everything up to the C text, then C emission;
   - gcc, split with `tools/compile_phases.py` into reading the text (`-fsyntax-only`) and the full compile;
   - link.

   To profile the child, print the `command` list once in a scratch copy (do not commit it). It is built just before
   `native_build.invoke(...)` at about line 6556 of `AIL_CURRENT/ail_chatgpt.py`. Run that command under
   `python3 -m cProfile -s cumtime`.
   Write `lab/profile/CTIME_2026-11.md` with, for each phase: seconds, share, and the Amdahl bound `1/(1-share)` for
   removing it. Commit, push.
3. **The hit path (15 min).** Profile the child on a cache hit. List its top 10 functions by cumulative time and say
   in one paragraph why a hit costs nearly a cold build. The lookup is at `pyc.py` about lines 973-1000; find what
   runs before it. Commit, push.
4. **Cut or hand off (20 min).** You may cut only in these files:
   - `python/pkg-v12/fecache.py`
   - `python/pkg-v12/fastwalk.py`
   - `python/pkg-v12/pipeline.py`
   - `ail_native_build.py`
   - `lab/profile/`

   Other lanes edit `pyc.py`, `pyfunc.py`, `buildcache.py`, `ail_chatgpt.py` and `tools/compile_phases.py`: do not
   edit them.
   Any cut must keep `program.c` byte-identical on all 10 tasks (`--debug-dir`, compared with
   `git worktree add /tmp/base origin/integ`), and it must report compile time and instruction count before and
   after.
   If the cause is outside those files, do not cut. Write a "Next cuts" section in the .md instead: file, function,
   line range, what to skip on a hit, and the measured bound. Commit, push.

## Done-check

- The .md has 10 task rows with every phase listed, the hit timings, and a top-10 table for the hit path.
- Any cut keeps 10/10 `program.c` identical.
- `test_ail_fe_cache` and `test_ail_safetynet` pass.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- A cut needs a file outside the allowed list.
- A `program.c` changes.
- 80 minutes pass.

Keep `-O2`. Do not use LTO or `-O1` (owner decision, 2026-10-30).

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- Build: `python3 AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--debug-dir DIR]`. A cold build needs a fresh
  `AIL_CACHE` and `TMPDIR` each run. `AIL_SERVER=0` disables the compile server.
- The front-end cache, `AIL_CURRENT/python/pkg-v12/fecache.py`:
  - `AIL_FE_CACHE=1` turns it on;
  - `AIL_FE_CACHE_DIR` sets the cache dir;
  - `AIL_FE_CACHE_LOG=FILE` appends `hit KEY` or `miss KEY` lines.

  Its key is built in `pyc.py` (about line 905). The design is in `docs/design/FE_CACHE.md`.
- `tools/compile_phases.py SRC --runs N` gives the python and gcc CPU split plus `-ftime-report`. Use it read-only.
- Owner (2026-10-30): a cached, separately compiled runtime at `-O2` is allowed if the instruction count shows no loss.
- compare-lab tasks are in `lab/compare/src/<task>/typed.py`. rail_transfer and chain_relax build with `--exact-int`.

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
