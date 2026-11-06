Lane: fb-narrow
Needs: fbnarrow1

# fbnarrow2: a width-adaptive int list in the runtime: int32 storage that widens to int64 on the first value that does not fit (runtime part and C tests only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

Depends on fbnarrow1's `lab/mem/NARROW.md` saying "go". If it says no-go, stop and report.

**Number this moves:** instructions per operation and bytes per element of the new `ail_ilist` against `ail_list`,
in `lab/mem/ILIST.md`, at n = 1M and 10M: push, get, set, a summing loop, pop, sort, and one widening. Targets:
- 4 bytes per element while narrow;
- push, get and set on the narrow path within 1.15x of `ail_list`'s instructions per operation;
- widening an n-element list costs at most 3 instructions per element, once;
- 0 wrong values in a randomized differential test of 1,000,000 mixed operations against `ail_list`, with values
  drawn near 0, +-2^31 and +-2^63.

**The type.** `typedef struct { void *p; ail_len_t n, cap; int32_t wide; } ail_ilist;`. While `wide == 0`, `p` is an
`int32_t *`; after the first store of a value outside `[INT32_MIN, INT32_MAX]`, `ail_ilist_widen` reallocates to 8 bytes
per element and converts from the top index down, in place, and sets `wide = 1`; it never narrows back. Every store
checks the range, so no value is ever truncated. Operations: `new`, `reserve`, `push`, `get`, `set`, `pop`, `clear`,
`len`, `sort` (the same algorithm and result as `ail_list`'s sort), `copy`, `slice`, `from_list` and `to_list` (for a
callee that takes `ail_list`). Index errors use exactly `ail_list`'s messages and exception kinds.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/cruntime.py`: one new part `ILIST` (its `SOURCE`, `REQUIRES` and `ORDER` entries), placed
  after `LIST`. No edit to any existing part. A program that does not use `ail_ilist` must not carry it. `cruntime.py`
  is busy (codegen, bce-ranges, pyreach): run `git fetch` and rebase on `origin/integ` just before each push;
- `AIL_CURRENT/test_ail_ilist_runtime.py` (new): a C harness compiled from the part text, plus the differential test;
  `AIL_CURRENT/tests.d/test_ail_ilist_runtime.txt` (new);
- `lab/mem/ILIST.md`, `lab/mem/ilist_bench.c` (new);
- the manifest files that `tools/update_manifest.py` writes.

## Sub-steps

1. **The part (25 min).** Write `ILIST` and a smoke test that pushes 0..9, widens with 2^40 and reads everything back.
   Commit, push, open the PR against `integ`.
2. **Differential test and bench (25 min).** The 1,000,000-operation test against `ail_list`, run under ASan/UBSan
   once; the bench table at 1M and 10M with `tools/icount.c`. Commit and push.
3. **No change elsewhere (10 min).** `program.c` hash equal to the base for the 10 compare `typed.py` tasks and the first
   100 `lab/corpus/programs`. Write `ILIST.md`. Commit, push, wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_ilist_runtime.py` passes, including the ASan/UBSan run.
- The bench table meets the targets above, or `ILIST.md` names the operation that misses and by how much.
- 0 `program.c` hash differences on the 110 programs; the 20 shards pass.

## Stop rule

Stop on any wrong value in the differential test. Record the operation sequence first. Stop and report if narrow-path
get costs more than 1.3x `ail_list`'s instructions: fbnarrow3 would then lose on icount. Stop when 60 minutes pass.
Push what is done first.

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
8. Edit only the files listed above. No edit to an existing `cruntime.py` part. Do not edit `DEVLOG.md`.

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
