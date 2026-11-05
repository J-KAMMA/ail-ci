Lane: rc

# rc1: where tree_fold's memory and the reference-count work go, priced for borrow inference and reuse (measure only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** two new tables in `lab/rc/PRICE.md`, unknown today:
- (a) peak RSS of tree_fold split by allocation kind (list buffers, str objects, class objects, input bytes, other),
  for `lab/compare/src/tree_fold/typed.py` and `main.py`;
- (b) dynamic retain/release (inc/dec) counts and their share of run instructions, per program, on the 10 compare
  tasks and on 6 new tree programs.
The tables decide whether rc2-rc5 are built. Baseline from compare-lab 2026-10-31: tree_fold peak RSS 605 MiB for
AIL against 315 MiB for Rust; run instructions 1.4-1.8x Rust's.

**Why measure first.** The survey proposes Koka-style reuse and Lean-style borrow inference for tree memory. But
`tree_fold/typed.py` stores the tree as parallel lists (`nm: list[str]`, `w`, `dep`, `par`), not as node objects,
and builds it once; reuse needs a node dropped and a same-size node allocated in one function, which that program
may never do. If (a) shows the memory is in list growth or string objects, rc4/rc5 will not move tree_fold, and the
report must say so instead of building them for it.

Base: `origin/integ`. Files you may create, and no others:
- `lab/rc/PRICE.md`, `lab/rc/PRICE.json` (new)
- `lab/rc/run.py` (new): builds, counts and measures
- `lab/rc/progs/*.py` (6 new programs): binarytrees (allocate and drop complete trees), rbtree insert (rebuilds a
  path per insert), cfold (constant folding on an expression tree, returning new nodes), deriv (symbolic derivative),
  a linked-list walk with a read-only helper `def total(n: Node) -> int`, and a list-of-objects scan. Each 30-80
  lines of plain Python 3.12 with class annotations, a fixed size taken from a constant, printing a checksum.

## Sub-steps

1. **Programs and counting (30 min).** Write the 6 programs; check each against `python3`. For every program and
   compare task, build with `--debug-dir`, and find in `program.c` the retain/release calls (typed objects:
   `ail_obj_retain`/`ail_obj_release`; lists, strings, bytearrays and the general path: find their inc/dec helpers in
   `cruntime.py` and `pyboxed2.py` and list the names). Count them at run time: build a second copy of the C with each
   helper wrapped by a counter (a `-D` macro or a sed on the scratch copy only, never the compiler), and record
   calls per helper. Record the source line that emits each helper (`pyfunc.py` line ~34661 and ~35034 for
   `ail_obj_retain`, `ir/emit_c.py`, ...). Commit, push, open the PR against `integ`.
2. **Memory split (25 min).** For tree_fold `typed.py` and `main.py` with the compare input
   (`lab/compare/tasks/tree_fold/gen.py`; if peak RSS passes 1 GB, use a smaller case from `gen.py` and scale, and
   say so): peak RSS by `/usr/bin/time -v`, and the split by allocation kind with an `LD_PRELOAD`-free method
   (wrap `malloc`/`realloc` in the scratch C copy by call site) or `valgrind --tool=massif` on a smaller case. Do the
   same for the 6 programs. Commit and push.
3. **Price (25 min).** Write `PRICE.md` (speed-claims rule):
   - borrow inference (rc2 parameters, rc3 loop cursors): retain/release calls that are on read-only parameters or
     loop cursors, their share of run instructions (`tools/icount.c`), Amdahl bound, assumed roof 60% of them
     removed (Lean's ablation: 1.14-1.16x on binarytrees and deriv), halved;
   - reuse (rc4) and drop specialisation (rc5): how many frees are followed by a same-size allocation in the same
     function, and the RSS and instructions of `malloc`/`free` on those; same pricing;
   - tree_fold: which of (a)'s rows each technique can touch. If none touches more than 10% of its peak RSS, say
     "rc4/rc5 do not move tree_fold" and name the row that would (for example list growth or string headers) as a
     follow-up;
   - for each of rc2-rc5: go if the halved projection is at least 1.03x run instructions or 5% peak RSS on at least
     2 programs; otherwise no-go. Name the files each would edit and whether they are busy (`pyfunc.py`, `optlib.py`
     and `ir/passes/*` are busy: codegen, bce-ranges, pyreach).
   Commit, push, wait for CI.

## Done-check

- `PRICE.md` covers 16/16 programs (10 tasks + 6) with retain/release counts per helper and their instruction share.
- tree_fold peak RSS split covers at least 90% of its peak for `typed.py`.
- Each of rc2-rc5 has share, Amdahl bound, assumed roof, halved projection and go/no-go.
- `git diff --stat origin/integ` shows only files under `lab/rc/`; the 20 shards pass.

## Stop rule

Stop on any wrong output: a new program that differs from `python3`, or a counting build whose stdout differs from
the plain gcc build (the counter changed behaviour). Record it first. Stop when 80 minutes pass. Push what is done
first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
   Measurements above about 1 GB go to GitHub or are skipped.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Edit no file outside `lab/rc/`. Do not edit `DEVLOG.md`.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. A fallback to the general path prints `note: ... built on the general path ...` on stderr.
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount ./program < input`. They repeat to 1e-7; wall time on the laptop swings up to 3x.
- Peak RSS: `lab/compare/run_task.py` uses `/usr/bin/time -v` "Maximum resident set size"; `tools/rss_phases.py`
  exists for phase splits.
- `ir/ownership.py` already removes copies and counts for lists by move/rename rules (S3b); `test_ail_borrowed_*`
  tests cover borrowed list elements and owners. Read them so rc2 does not redo existing work.

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
