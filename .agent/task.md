Lane: fb-narrow
Agent: opus

# fbnarrow1: how much of tree_fold's peak is 8-byte ints that would fit in 32 bits, priced by a hand-edited C copy (measure only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** two numbers in `lab/mem/NARROW.md`, unknown today:
- (a) bytes held by `list[int]` buffers at tree_fold's peak, split per list (`w`, `dep`, `par`, the rebuild temporaries
  `idx`, `cs`, `ord`, `ni`, `stack`, and any int sort-key column), each with its observed minimum and maximum value;
- (b) peak RSS and run instructions of a scratch copy of tree_fold's `program.c` in which the lists from (a) whose
  values fit in int32 are stored as `int32_t`, against the plain build.
Baseline: 405 MiB on the runner (`docs/design/ARENA1.md`) against Rust's 315 MiB. The table decides fbnarrow2-4: go if
(b) lowers peak RSS by at least 10% and run instructions are not worse by more than 1%.

Base: `origin/integ`. Files you may create, and no others:
- `lab/mem/NARROW.md`, `lab/mem/NARROW.json` (new)
- `lab/mem/narrow_census.py` (new): builds, instruments a scratch copy of the C, runs and tabulates
- `lab/mem/treefold_i32.patch` (new): the hand edit of the scratch C, kept for the record

## Sub-steps

1. **Census (25 min).** For the 10 `lab/compare/src/*/typed.py` tasks and the 6 `lab/rc/progs` programs, build with
   `--debug-dir`. In a scratch copy of each `program.c` only, wrap `ail_list_push`, `ail_list_reserve` and every
   element store with a tracker keyed by call site (a site id from a sed on the scratch copy, never the compiler):
   number of lists, largest `n`, smallest and largest stored value, live bytes at the program's peak. Check that the
   tracked build prints exactly what the plain build prints. Write one row per site that holds at least 1 MiB at the
   peak, with the narrowest width that holds its range (int8, int16, int32, int64). Commit, push, open the PR against
   `integ`.
2. **Emulate (25 min).** For tree_fold only, hand-edit the scratch C so that the lists whose range fits int32 use a
   local `int32_t *p` list type with its own push/get/set (store the edit as `treefold_i32.patch`). Measure the plain
   and edited builds: peak RSS (median of 3), run instructions, and `tools/rss_phases.py --n 3000000`. Check identical
   stdout on every public and hidden case of `gen.py`. Commit and push.
3. **Price (10 min).** Write `NARROW.md`: the census table, the emulation numbers, the go/no-go line by the rule above,
   and the list of operations that tree_fold applies to each narrowed list (append, index read/write, `len`,
   `for x in`, `sort`/`sorted` with or without `key`, slicing, copying, passing to a function). fbnarrow3 must support
   every one of them or leave that list as int64. Commit, push, wait for CI.

## Done-check

- The census covers 16/16 programs; tracked builds match the plain builds.
- (a) accounts for at least 80% of tree_fold's list-buffer bytes at the peak (rc1: 384 MiB).
- (b) has peak RSS, run instructions and phase peaks for both builds, with identical output on every case.
- `NARROW.md` ends with "go" or "no-go" for fbnarrow2-4 by the rule above.
- `git diff --stat origin/integ` shows only files under `lab/mem/`; the 20 shards pass.

## Stop rule

Stop on any wrong output: a tracked or edited build whose stdout differs from the plain build. Record it first. If
(b) lowers peak RSS by less than 5%, write "no-go" and stop. Stop when 60 minutes pass. Push what is done first.

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
8. Edit no file outside `lab/mem/`. Do not edit `DEVLOG.md`.

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
