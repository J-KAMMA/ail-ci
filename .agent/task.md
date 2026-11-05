Lane: cmpbfs

# cmpbfs1: a candidate compare-lab task, `grid_bfs` (shortest path on a character grid), the same algorithm in C, Rust, Go, Python and typed Python (measurement only)

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** a compare-lab candidate that stresses flat int arrays and a queue, where Rust and C are
strongest and `.py` sources most often fall back. The ten tasks and the three candidates have no grid search. Target:
one new candidate whose programs all pass every public and hidden case, with a measured row (wall, instructions,
binary bytes, peak RSS, compile time) for `ail`, `ail-py`, `c`, `rust`, `go` and `python`. The ten-task table and
`lab/compare/` are not changed.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/compare_cand/tasks/grid_bfs/{spec.md,gen.py,reference.py}`
- `lab/compare_cand/src/grid_bfs/{main.c,main.rs,main.go,main.py,typed.py}`
- `lab/compare_cand/RESULTS-grid_bfs.md`
Do not edit `lab/compare_cand/run.py`, `README.md`, `RESULTS.md`, the other candidates, anything under `lab/compare/`,
or any workflow. No compiler file is edited.

Read first: `lab/compare_cand/README.md` (how `run.py` reuses `lab/compare/run_task.py`), and
`lab/compare_cand/tasks/log_scan/` with `lab/compare_cand/src/log_scan/` as the model of a stdin task.

## The task (write it exactly into spec.md)

`prog < grid`. Line 1 is `H W Q` (ints, 1 <= H, W <= 2000, 0 <= Q <= 20). Then `H` lines of exactly `W` bytes from
`.` (open) and `#` (wall). Then `Q` lines `r1 c1 r2 c2` (0-based). For each query, run a breadth-first search with
4-neighbour moves in the order up, down, left, right, using one flat int array of distances (reset per query) and an
array used as a FIFO queue, and print `dist D seen S`: `D` is the number of moves from `(r1, c1)` to `(r2, c2)`, or
`-1` if unreachable or if either cell is a wall; `S` is the number of cells taken from the queue before the search
stops (it stops when the target is taken from the queue, or the queue is empty). Last line: `total T`, the sum of all
`D` that are not `-1`. A malformed grid (a short row, a bad byte, a query outside the grid) exits 2 with nothing on
stdout. Every language runs this same algorithm (owner rule: same algorithm everywhere).

## Sub-steps

1. **Spec, generator, reference (15 min).** Write `spec.md`, `reference.py` (plain CPython, the oracle) and `gen.py`
   (`STDIN = True`, `cases(rng) -> (public, hidden, perf)`; public: 3 small hand cases including an unreachable
   target and a start on a wall; hidden: 6 random cases including `1 x 1`, `1 x 2000`, a query with start equal to
   target, and `Q = 0`; perf: `2000 x 2000` at 30% walls with 20 queries from the given `rng`). Check with
   `python3 lab/compare_cand/run.py --task grid_bfs --smoke --out /tmp/r.json --langs python`. Commit, push, and open
   the PR against `integ`.
2. **Python and typed Python (15 min).** Write `main.py` (plain, `sys.stdin.buffer`, lists) and `typed.py` (the same
   algorithm with annotations, in the style of `lab/compare_cand/src/log_scan/typed.py`). Both pass every case. Record
   whether `ail` and `ail-py` took the typed path, with the note if one falls back. Change only the spelling, never
   the algorithm, and say what you changed in `RESULTS-grid_bfs.md`. Commit and push.
3. **C, Rust, Go (20 min).** Write `main.c`, `main.rs` (std only, `Vec`, `VecDeque` is not allowed: use the same flat
   array queue) and `main.go` (std only) with the same bytes out. Run all six columns with `run.py --task grid_bfs`
   under `ulimit -v 1500000`. Fix any program that fails a case. Commit and push.
4. **Results (10 min).** Write `RESULTS-grid_bfs.md`: date, commit, runner, toolchain versions, the table that
   `lab/compare/merge.py` makes from the result JSON, and typed or general for each AIL column. Commit, push, and wait
   for CI.

## Done-check

- `python3 lab/compare_cand/run.py --task grid_bfs --out /tmp/r.json` passes every public and hidden case in all six
  columns and prints the measured row.
- `RESULTS-grid_bfs.md` has the table; the 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop at once and report if an AIL column passes the smoke run but prints a different line from `reference.py` on any
case (silent wrong output): commit the case and both outputs in `RESULTS-grid_bfs.md` first. Do not tune any program
for speed beyond the spec's algorithm. Stop when 60 minutes pass. Push what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `packaging/ail_lang/cli.py`, or these files
   in `AIL_CURRENT/python/pkg-v12/`: `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
   `ir/*`, `parallel.py`, `typedpar.py`, `buildcache.py`, `stubcalls.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
