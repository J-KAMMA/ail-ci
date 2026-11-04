Lane: array

> Re-run of arrt6, whose GitHub run was lost (no verdict 10.8 h after dispatch). If its branch job-arrt6-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# arrt6: land ail_array T6 (2-D f64 arrays, exact ta.matmul on the CPU) on today's integ

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** ail_array T6 case files that pass on `integ`: 0/6 today (`array_t6_cases/` is only on the stale,
conflicting PR #260, branch `array-matmul`) -> 6/6, in a fresh PR with all 20 shards green. Second number:
instructions of a 256x256 `ta.matmul` against the same triple loop in C (`gcc -O2`). The GPU kernel (PR #288) needs this
first.

Base: `origin/integ`. Branch `job-arrt6` from `origin/integ`. Do NOT rebase, push to, close or comment on PR #260 or
#288. Files you may edit: `AIL_CURRENT/ail_array.py`, `AIL_CURRENT/python/pkg-v12/ailarray.py`,
`AIL_CURRENT/python/pkg-v12/prelude_ailarray.py`, `AIL_CURRENT/array_t6_cases/*` (new), `AIL_CURRENT/test_ail_array_t6.py`
(new), `AIL_CURRENT/test_ail_array_ref.py`, `AIL_CURRENT/test_ail_array_t2.py`, `AIL_CURRENT/docs/design/TYPED_ARRAY.md`,
`AIL_CURRENT/tests.d/test_ail_array_t6.txt` (new). Do not take PR #260's changes to `ir/passes/*`, `bce_cases/*`,
`test_ail_bigint.py`, `test_ail_ir_bce.py`, `test_ail_debug_lines.py`, `ail_check.py`, `DEVLOG.md` or `tools/ci_shards.json`:
those came from another job that is already on integ in its own form.

## Sub-steps

1. **Port (15 min).** `git fetch origin array-matmul`. `MB=$(git merge-base origin/integ origin/array-matmul)` (it is
   `3fe55003`). Apply only the array files:
   `git diff $MB origin/array-matmul -- AIL_CURRENT/ail_array.py AIL_CURRENT/python/pkg-v12/ailarray.py
   AIL_CURRENT/python/pkg-v12/prelude_ailarray.py AIL_CURRENT/array_t6_cases AIL_CURRENT/test_ail_array_t6.py
   AIL_CURRENT/test_ail_array_ref.py AIL_CURRENT/test_ail_array_t2.py AIL_CURRENT/docs/design/TYPED_ARRAY.md | git apply -3`.
   Resolve any conflict by keeping integ's behaviour and adding T6's. Register `test_ail_array_t6` with a `tests.d` file
   instead of the `ail_check.py` edit #260 made (Appendix A rule 6). Commit, push, open the PR against `integ`; in the
   PR body say it carries the array part of #260.
2. **Make it pass (25 min).** Run `python3 tools/par_check.py -j 2 test_ail_array_t6 test_ail_array_t2 test_ail_array_ref`.
   Fix failures caused by integ having moved on (renamed helpers, changed C names, the manifest). Do not weaken a test's
   expected output; if a T6 expectation is wrong, show CPython's value (the cases are checked against a pure-Python
   reference in the test) before changing it. Commit after each green module.
3. **No regressions (15 min).** Build the 10 `lab/compare/src/*/main.py` with `--syntax python --debug-dir` before
   (on `origin/integ`) and after (on your branch): `program.c` must be byte-identical for every program that does not
   import `ail_array` (none of them do). Run `python3 tools/par_check.py -j 2 test_ail_gpu_g1 test_ail_gpu_g2
   test_ail_std_array`. Commit.
4. **Measure (15 min).** A program `lab/array/matmul256.py` (new) that fills two 256x256 f64 arrays from a fixed LCG,
   calls `ta.matmul`, and prints a checksum (sum of all elements with `%.17g`) and three elements. Write
   `lab/array/matmul256.c` with the same fill and the naive i-k-j loop, built with `gcc -O2`. Same printed values
   (exact matmul has a fixed sum order: say which order and check the C uses the same). Record instructions (icount)
   and wall (median of 5) of both, and the same for `python3` with a pure-Python triple loop, in `lab/array/RESULTS.md`.
   Push.

## Done-check

6/6 T6 case files pass in `test_ail_array_t6`; T2 and ref tests pass; the compare-lab C is unchanged; the matmul table is
written; 20 shards pass.

## Stop rule

If `git apply -3` leaves conflicts in `ailarray.py` or `prelude_ailarray.py` that you cannot resolve in 15 minutes, stop
and report the conflicting hunks (file and line). If a T6 failure needs a change in a file outside the list above
(for example `pyfunc.py`), stop and report the failure text. Stop at 80 minutes; push what is done.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. Turning a
   correct program into a refusal or a stop is a regression. When a new fast path cannot handle a case, keep the old route.
2. Probe ints beyond int64 wherever ints come from text, fields or arithmetic. Run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, and compare both with `python3`.
3. Push early and open the PR against `integ`. Wait for all 20 `shard` checks on your head commit
   (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `origin/integ` (or from one unmerged PR at most; never from a PR that is itself stacked).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: add `AIL_CURRENT/tests.d/<module>.txt` (one line: the module name), `git add` every new file, run
   `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, tag, publish, change repository settings, cancel runs, or edit
   `.github/workflows`.
8. Files owned by busy lanes; do NOT edit them: `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`,
   `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `pyc.py`, `buildcache.py`, `pyboxed2.py`, `packaging/ail_lang/cli.py`.
   Also do not edit `DEVLOG.md` or `AIL_CURRENT/DEVLOG.md` (integration writes them). If a fix needs one of these files,
   do not make it: write a finding (file, function, what is needed, the refusal text) in your results file and go on.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC.py -o OUT [--syntax python] [--strict] [--exact-int]
  [--debug-dir DIR]`. `-o` must not exist yet. The default build tries the typed path first; when it falls back it prints
  `note: ... built on the general path` on stderr. No such note = typed. `--strict` = typed path or refuse.
  `DIR/program.c` is the generated C. Use `AIL_NO_CACHE=1` for timings.
- One test module: `python3 tools/par_check.py -j 2 test_ail_<name>`.
- Model test file: `AIL_CURRENT/test_ail_std_statistics.py` (build each program in a temp dir, run it, compare stdout and
  exit code with `python3 <program>`).
- Instruction counts: `cc -O2 -w -include signal.h -include stdlib.h -o /tmp/icount tools/icount.c`, then
  `/tmp/icount PROG ARGS < input`. If `perf_event_open` is refused, run `sudo sysctl -w kernel.perf_event_paranoid=1`
  once; if it is still refused, use the median of 5 wall times and say so in the results.
- The oracle is CPython 3.12 (`python3`). Peak RSS: `/usr/bin/time -v PROG` ("Maximum resident set size").
- AIL is Python syntax plus optional annotations. Ints are int64 by default and overflow stops loudly;
  `--exact-int` gives exact ints.

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
