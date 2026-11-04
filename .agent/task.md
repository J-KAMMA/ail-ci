Lane: cmpcand

# cmpcand1: a candidate compare-lab task, `csv_rollup` (a data-processing CLI), the same algorithm in C, Rust, Go, Python and typed Python

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** the evidence behind the roadmap's niche claim ("small, fast CLI and data tools written in
Python syntax"). Today the comparison has 10 tasks, all written by an LLM in one run; none is a plain CSV
group-by, the most common data tool. Target: one new candidate task whose programs all pass every public and hidden
case, with a measured row (wall, instructions, binary bytes, peak RSS, compile time) for `ail`, `ail-py`, `c`,
`rust`, `go` and `python`. The ten-task table is NOT changed: the candidate lives in its own directory, and the
owner decides later whether it joins `lab/compare/src/`.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/compare_cand/run.py`, `lab/compare_cand/README.md`, `lab/compare_cand/RESULTS.md`
- `lab/compare_cand/toolchains.env` (a git symlink to `../compare/toolchains.env`)
- `lab/compare_cand/tasks/csv_rollup/{spec.md,gen.py,reference.py}`
- `lab/compare_cand/src/csv_rollup/{main.c,main.rs,main.go,main.py,typed.py}` (and `main.nim` only if `nim` is
  installed on the runner)
Do not edit anything under `lab/compare/` or any workflow. No compiler file is edited.

Read first: `lab/compare/README.md`, `lab/compare/tasks/term_rank/` (a stdin task: `STDIN = True`,
`cases(rng) -> (public, hidden, perf)`), and `lab/compare/src/term_rank/` (one program per language; `typed.py` is the
annotated Python that the `ail` column compiles, `main.py` is plain Python for the `python` and `ail-py` columns).

## The task (write it exactly into spec.md)

`prog < data.csv`. The first line is the header `region,product,qty,price`. Each later line has 4 comma-separated
fields: `region` and `product` are 1-16 chars of `[a-z0-9_]`; `qty` is a decimal int in -1000..1000 (a minus sign
allowed); `price` is a decimal int in 0..10000000 (cents). Lines end with `\n` (the last one may lack it). A line with
the wrong field count, an empty field, a bad character or an out-of-range number is counted as bad and skipped. For
each `(region, product)` group: `qty_sum` and `revenue = sum(qty * price)` (int64; the perf input keeps every sum
inside int64). Output, each value separated by one space:
1. `rows <good> bad <bad> groups <n>`
2. the top 10 groups by revenue descending, ties by region then product ascending (byte order): `region product
   qty_sum revenue`;
3. one line per region in ascending byte order: `region <region> revenue <sum>`;
4. `total <sum of all revenue>`.
An empty input (no header) prints `rows 0 bad 0 groups 0` and `total 0`, exit 0. Every language must run this same
algorithm: one pass, a hash map keyed by the pair, then a sort of the groups (owner rule: same algorithm everywhere).

## Sub-steps

1. **Spec, generator, reference, runner (20 min).** Write `spec.md`, `gen.py` (public: 3 small hand cases including
   bad lines and ties; hidden: 6 random cases, among them CRLF-free edge cases such as a missing last newline, `qty`
   `-0`, leading zeros, a 17-char name; perf: 4,000,000 rows over 400 regions x 300 products, from the given `rng`)
   and `reference.py` (plain CPython, the oracle). Write `lab/compare_cand/run.py`: it imports
   `lab/compare/run_task.py` as a module, sets its `HERE` to `lab/compare_cand`, and calls its `main()`, so
   `python3 lab/compare_cand/run.py --task csv_rollup --smoke --out /tmp/r.json --langs python` works. Check that
   `run_task.py` reads `HERE` only at call time; if a path is bound at import, say which in `README.md` and patch it
   in `run.py`, not in `run_task.py`. Commit, push, and open the PR against `integ`.
2. **Python and typed Python (20 min).** Write `main.py` (idiomatic, `sys.stdin.buffer` or `sys.stdin`, a dict of
   tuples) and `typed.py` (the same algorithm with annotations, in the style of `lab/compare/src/term_rank/typed.py`).
   Both must pass every case: `run.py --task csv_rollup --langs python,ail,ail-py --no-cases` for the perf run, and
   without `--no-cases` for the checks. Record whether `ail` and `ail-py` took the typed path; if one falls back,
   record the note. Do not change the algorithm to get the typed path: change only the spelling, and say what you
   changed in `README.md`. Probe a `qty * price` sum beyond int64 with a hand case outside the spec's ranges (CPython
   prints the big number; AIL must stop loudly, never print a wrong number); record the result, do not add it to the
   cases. Commit and push.
3. **C, Rust, Go (25 min).** Write `main.c` (open addressing hash, `qsort`), `main.rs` (std only, `HashMap`, no
   crates), `main.go` (std only, `map`). Same parsing rules, same output bytes. Run all six columns with
   `run.py --task csv_rollup` (full: cases plus perf). Fix any program that fails a case. Commit and push.
4. **Results (10 min).** Write `RESULTS.md`: the date, commit, runner, toolchain versions, the table that
   `lab/compare/merge.py` makes from the result JSON (run it on your one result), and one line per column: typed or
   general for the AIL columns. Commit, push, and wait for CI.

## Done-check

- `python3 lab/compare_cand/run.py --task csv_rollup --out /tmp/r.json` passes every public and hidden case in all
  columns you wrote, and prints the measured row.
- `RESULTS.md` has the table.
- `git diff --stat origin/integ` shows only files under `lab/compare_cand/`.
- The 20 shards pass.

## Stop rule

Stop and report if `run_task.py` cannot be reused from another directory without editing it; say which line binds
the path. If a toolchain is missing on the runner and cannot be installed with apt in 5 minutes, skip that column and
say so. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000` (the perf input is about 80 MB; keep each program under 1.5 GB);
   `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`. (This job adds no test module.)
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`. Do not trigger the `compare-lab` workflow.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, `cruntime.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not
   edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`.
  `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- `lab/compare/run_task.py --task T --out J [--langs a,b] [--smoke] [--no-cases]` builds and measures one task;
  `lab/compare/merge.py` makes the tables. Toolchain pins are in `lab/compare/toolchains.env`.
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
