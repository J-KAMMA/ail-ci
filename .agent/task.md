Lane: cmpjoin

# cmpjoin1: a second candidate compare-lab task, `tsv_join` (a hash join CLI), the same algorithm in C, Rust, Go, Python and typed Python

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the evidence behind the roadmap's niche claim ("small, fast CLI and data tools written in
Python syntax"). `lab/compare_cand/` has one candidate, `csv_rollup` (a group-by). No task joins two tables, the
second most common data-tool step. Target: one new candidate task whose programs all pass every public and hidden
case, with a measured row (wall, instructions, binary bytes, peak RSS, compile time) for `ail`, `ail-py`, `c`, `rust`,
`go` and `python`. The ten-task table and `csv_rollup` are NOT changed.

Base: `origin/integ`. Files you may create or edit, and no others (all new):
- `lab/compare_cand/tasks/tsv_join/{spec.md,gen.py,reference.py}`
- `lab/compare_cand/src/tsv_join/{main.c,main.rs,main.go,main.py,typed.py}`
- `lab/compare_cand/RESULTS-tsv_join.md`
Do not edit `lab/compare_cand/run.py`, `README.md`, `RESULTS.md`, anything under `lab/compare/`, or any workflow. No
compiler file is edited.

Read first: `lab/compare_cand/README.md`, `lab/compare_cand/run.py`, and `lab/compare_cand/tasks/csv_rollup/` and
`src/csv_rollup/` (a stdin task: `STDIN = True`, `cases(rng) -> (public, hidden, perf)`; `typed.py` is the annotated
Python the `ail` column compiles, `main.py` is plain Python for the `python` and `ail-py` columns).

## The task (write it exactly into spec.md)

`prog < data.tsv`. The input has two sections. A line `#users` starts the first; each later line until `#orders` is
`user_id<TAB>name<TAB>country`. A line `#orders` starts the second; each later line is
`order_id<TAB>user_id<TAB>amount`. `user_id` and `order_id` are decimal ints 1..2000000000 (digits only, no sign);
`name` is 1-24 chars of `[A-Za-z0-9 ._-]`; `country` is exactly 2 chars `[A-Z]`; `amount` is a decimal int
0..100000000 (cents). Lines end with `\n` (the last may lack it). A line with the wrong field count, an empty field, a
bad character or an out-of-range number is counted as bad and skipped. A second `users` line with an id already seen
is bad (the first one wins). An order whose `user_id` is not a known user is `unmatched`. Output, values separated by
one space:
1. `users <good> orders <good> bad <bad> unmatched <n>`
2. one line per country with at least one matched order, by total amount descending, ties by country ascending:
   `country <cc> orders <count> amount <sum>`;
3. the top 10 users by matched amount descending, ties by user_id ascending: `user <id> <name> <amount>`;
4. `total <sum of matched amounts>`.
Input without the two section lines prints line 1 with zeros and `total 0`, exit 0. Every language runs the same
algorithm: one pass that builds a hash map from user_id to (name, country), one pass over orders that accumulates per
user and per country in hash maps, then sorts (owner rule: same algorithm everywhere).

## Sub-steps

1. **Spec, generator, reference (20 min).** Write `spec.md`, `gen.py` (public: 3 small hand cases including bad
   lines, duplicate user ids, unmatched orders and ties; hidden: 6 random cases with edge cases such as a missing last
   newline, leading zeros, a 25-char name, an empty `#orders` section; perf: 300,000 users and 4,000,000 orders over 60
   countries, from the given `rng`) and `reference.py` (plain CPython, the oracle). Check that
   `python3 lab/compare_cand/run.py --task tsv_join --smoke --out /tmp/r.json --langs python` works. Commit, push, and
   open the PR against `integ`.
2. **Python and typed Python (20 min).** Write `main.py` (idiomatic) and `typed.py` (same algorithm, annotations, in
   the style of `src/csv_rollup/typed.py`). Both must pass every case with `run.py --task tsv_join --langs
   python,ail,ail-py`. Record whether `ail` and `ail-py` took the typed path; if one falls back, record the note. Do
   not change the algorithm to get the typed path: change only the spelling, and write what you changed in
   `RESULTS-tsv_join.md`. Probe a per-country sum beyond int64 with a hand case outside the spec's ranges (CPython
   prints the big number; AIL must stop loudly, never print a wrong number); record the result, do not add it to the
   cases. Commit and push.
3. **C, Rust, Go (25 min).** Write `main.c` (open addressing hash, `qsort`), `main.rs` (std only, `HashMap`, no
   crates), `main.go` (std only, `map`). Same parsing rules, same output bytes. Run all six columns with
   `run.py --task tsv_join` (cases plus perf, `ulimit -v 1500000` around AIL and Python runs). Fix any program that
   fails a case. Commit and push.
4. **Results (10 min).** Write `RESULTS-tsv_join.md`: date, commit, runner, toolchain versions, the table that
   `lab/compare/merge.py` makes from your result JSON, and one line per AIL column: typed or general. Commit, push,
   and wait for CI.

## Done-check

- `python3 lab/compare_cand/run.py --task tsv_join --out /tmp/r.json` passes every public and hidden case in all
  columns you wrote, and prints the measured row.
- `RESULTS-tsv_join.md` has the table.
- `git diff --stat origin/integ` shows only the files listed above.
- The 20 shards pass.

## Stop rule

Stop and report if `run.py` cannot run a second task without editing it; say which line. If a toolchain is missing
and cannot be installed with apt in 5 minutes, skip that column and say so. If the perf input makes a run exceed the
1.5 GB cap, halve the order count and say so. Stop when 80 minutes pass. Push what is done first.

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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
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
