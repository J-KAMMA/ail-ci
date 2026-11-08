Lane: fb-narrow
Needs: fbnarrow3

# fbnarrow4: narrow int lists through slices, copies and sorts, then the default-on decision (tree_fold against Rust)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** tree_fold's peak RSS in the default build, on the GitHub runner. Today 405 MiB; Rust 315 MiB.
The target is at most 330 MiB, stretch 315 MiB or less, with every int list that `lab/mem/NARROW.md` names stored narrow.

**Default-on gate.** `AIL_NARROW_INT` becomes on by default (`AIL_NARROW_INT=0` turns it off) only if all of these hold
on the 10 compare tasks and the 6 `lab/rc/progs` programs: run instructions none worse by more than 0.3% (tree_fold by
more than 1%), peak RSS none higher by more than 1%, binary size none larger by more than 2%, 0 output differences on
every public and hidden case, the first 100 `lab/corpus/programs` unchanged in output, and the 20 shards green. If any
fails, the variable stays opt-in and `NARROW_RESULTS.md` says which row failed.

**Add to the supported set:** `x[a:b]` and `x[a:b:c]` give an `ail_ilist` of the same width; `x.copy()`, `list(x)`,
`x + y` (narrow only if both are narrow); `x.sort()`, `sorted(x)`, and a key sort whose key column is an int list
(the `_ail_sk1_*` columns) stores that column narrow when the source list is narrow. Widening during a sort or a copy is
not possible (no new values), so the width carries over.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/ir/narrowint.py` (fbnarrow3's file);
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: at most 60 more changed lines in fbnarrow3's hook and emitters; rebase on
  `origin/integ` just before each push;
- `AIL_CURRENT/python/pkg-v12/cruntime.py`: the `ILIST` part only;
- `AIL_CURRENT/test_ail_narrow_int.py` (new test methods), `lab/mem/NARROW_RESULTS.md`;
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **Slices, copies, sorts (25 min).** Tests first (slices across the int32 boundary, a sort of a widened list, a key
   sort with equal keys, which must keep CPython's stable order), then the code. Commit, push, open the PR.
2. **Gate on the laptop (20 min).** The gate numbers above with the variable on, as a table in `NARROW_RESULTS.md`.
   If every row passes, flip the default in `narrowint.py`. Commit and push.
3. **compare-lab (15 min).** One run: `gh workflow run compare-lab -R J-KAMMA/ail-ci --ref <your branch>
   -f tasks='tree_fold'` (do not cancel runs). Record AIL's and Rust's peak RSS, wall time and binary size. Commit, push,
   wait for CI.

## Done-check

- The gate table is complete, and the default is flipped only if every row passes.
- tree_fold's runner peak RSS is recorded against Rust's from the same run.
- The 20 shards pass with the default as finally set.

## Stop rule

Stop on any wrong output, in either setting. Record it first. Stop when 60 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
   Measurements above about 1 GB go to GitHub or are skipped. Run TSan and ASan builds one at a time.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`,
   `optlib.py`, `ir/passes/*` or `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general
  path ...` on stderr. For a `program.c` hash check use `--debug-dir`, `PYTHONHASHSEED=0`, `AIL_NO_CACHE=1`.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly with OverflowError.
  Silent wrong output is never allowed.
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount ./program < input`. They repeat to 1e-7; wall time on the laptop swings up to 3x. rc1 ran where
  `perf_event_open` failed (no PMU). If that happens, say so and use `valgrind --tool=callgrind` `Ir` on a smaller
  input for every go/no-go number; never a gcov estimate.
- Peak RSS: `/usr/bin/time -v` "Maximum resident set size", median of 3 (`lab/compare/run_task.py` does the same);
  `tools/rss_phases.py` splits a run into phases.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where the task says so.
- Lists: `ail_list` is `{int64_t *p; ail_len_t n, cap;}` (`cruntime.py` ~line 204), `ail_slist` holds a 24 B
  `ail_str` per element (~2946), `ail_pslist` is the dense str list (~4137). List buffers carry no refcount.
- `lab/rc/PRICE.md` (rc1): list buffers are 95% of tree_fold's peak (384 of 404 MiB); class objects already reuse
  memory through the per-size pool (`ail_pool_head`). `docs/design/ARENA1.md`: after arena1s1-s4 the runner peak is
  405 MiB; "the 8-byte ints make every temporary 2x the size of C's int32".
- tree_fold: `lab/compare/src/tree_fold/typed.py`, input from `lab/compare/tasks/tree_fold/gen.py` at N = 3,000,000.
  Rust's peak RSS on compare-lab 2026-10-31: 315 MiB. The owner's bar: AIL must beat Rust on peak RSS too.

## Owner decision (2026-11-06)

- Do NOT switch a default yourself. When the numeric gate passes, stop and report the numbers. The maintainer decides whether to make it the default.

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
