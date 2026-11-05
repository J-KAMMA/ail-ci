Lane: algos

# algos1: 12 classic algorithms in plain Python, compiled unchanged: typed reach and speed against CPython

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the roadmap P1 claim, "write Python, get Rust-level speed and a small binary", on code that a
Python user writes without thinking about AIL. Today the evidence is the compare-lab `.py` sources (typed on 0/10),
`lab/pyperf/` (benchmarks) and `examples/apps/` (CLI tools). None is the textbook algorithm code people copy into
scripts. The target: 12 programs in `examples/algos/`, written as ordinary idiomatic Python 3.12 with no AIL-specific
changes; for each, the result `typed`, `general` or `refused` (first reason), CPython-identical output, and wall time
against `python3`. At least 10/12 build and match; the typed count is measured, not targeted. No compiler file is
edited: this job measures and lists blockers.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `examples/algos/*.py` (12 programs), `examples/algos/run.py` (builds, compares, times), `examples/algos/RESULTS.md`
- `AIL_CURRENT/test_ail_examples_algos.py` and `AIL_CURRENT/tests.d/test_ail_examples_algos.txt` (one line:
  `test_ail_examples_algos`)
- the manifest files that `tools/update_manifest.py` writes

## The programs

Write each one yourself (do not copy code from a website), 30-120 lines, the way a Python tutorial would: lists,
dicts, sets, tuples, `collections.deque`, `heapq`, f-strings, small classes or dataclasses where natural, no type
annotations except where a tutorial would put them. Each reads no input (a fixed seed with a hand-written LCG or
`random.seed` if `random` builds) and prints a short checksum plus a few results. A size constant at the top makes
the run take 1-3 s in CPython.
1. `sieve.py` — sieve of Eratosthenes, count and sum of primes below N.
2. `levenshtein.py` — edit distance of many word pairs, DP table as list of lists.
3. `lcs.py` — longest common subsequence length and one subsequence (backtrack).
4. `dijkstra.py` — shortest paths on a generated weighted graph, `heapq`, dict of lists.
5. `knapsack.py` — 0/1 knapsack DP, values and chosen items.
6. `huffman.py` — Huffman code lengths of a generated text, `heapq` of tuples, total encoded bits.
7. `life.py` — Conway's Game of Life on a torus, set of live cells, N generations.
8. `sudoku.py` — backtracking solver for 3 fixed puzzles.
9. `mandelbrot.py` — escape counts on a grid, floats, prints a checksum (not the picture).
10. `rpn.py` — tokenizer and RPN/shunting-yard evaluator over generated expressions, ints only; one expression's
    result exceeds int64 (`2**70`): CPython prints it, AIL must stop loudly or print the same, never a wrong number.
11. `topo.py` — topological sort (Kahn) of a generated DAG, `collections.deque`.
12. `wordfreq.py` — word frequencies of a generated text, `dict.get`, `sorted(..., key=lambda kv: (-kv[1], kv[0]))`,
    top 20.

## Sub-steps

1. **Programs (30 min).** Write the 12 programs and run each under `python3`. Commit, push, and open the PR against
   `integ`.
2. **Runner and baseline (20 min).** `examples/algos/run.py` builds each program three ways: default, `--strict`
   (records typed or the first refusal line) and `AIL_UNIFIED_FORCE=1`; compares stdout and exit status with
   `python3`; records binary bytes; and times the default binary and `python3` (median of 3, `ulimit -v 1500000`).
   For timing on this noisy laptop also record the instruction count with `tools/icount.c` if it builds. Fill
   `RESULTS.md`: one row per program with path, match, wall AIL, wall CPython, speed-up, binary bytes, first refusal
   or fallback note. Commit and push.
3. **Blockers (15 min).** Group the first refusal / fallback reasons into buckets (same text with names replaced),
   rank them by how many programs each would unblock, and add a reproducer of 3-10 lines for each of the top 3 under
   `examples/algos/repro/` (allowed: new files). Commit and push.
4. **Test (15 min).** `AIL_CURRENT/test_ail_examples_algos.py` (model: `test_ail_examples_apps.py` if it exists, else
   `test_ail_std_getopt.py`) builds every program that matched in step 2 with a small size (set by an environment
   variable the programs read, or by a `--small` argument) and compares with `python3`, default build only. It skips
   when there is no C compiler. Register it (Appendix A rule 6). Commit, push, and wait for CI.

## Done-check

- At least 10 of the 12 programs build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`.
- `RESULTS.md` has the 12-row table with the typed count, the geomean speed-up over CPython, and the ranked blockers.
- `python3 AIL_CURRENT/test_ail_examples_algos.py` passes in under 120 s.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only files under `examples/algos/` and the test files above.

## Stop rule

Never change a program to get the typed path: the point is the unchanged program. If a program is refused, record
it and go on. Stop and report a WRONG result (built, ran, printed different output with exit 0) at once, with the
smallest reproducer; that is a silent difference and outranks the rest of the job. Stop when 80 minutes pass. Push
what is done first.

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
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files
   this task names. Edit only the files this task names, plus the manifest files that `tools/update_manifest.py`
   writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT --syntax python [--strict] [--debug-dir DIR]`.
  `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general path prints
  `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- `tools/icount.c` counts instructions; use it for speed claims on this laptop, wall time is noisy.
- CPython 3.12 is the oracle: compare stdout and the exit status.

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
