Lane: cmplog

# cmplog1: a candidate compare-lab task, `log_scan` (an access-log summary CLI), the same algorithm in C, Rust, Go, Python and typed Python

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** the evidence behind the roadmap's niche claim ("small, fast CLI and data tools written in
Python syntax"). `lab/compare_cand/` holds two candidates (`csv_rollup`, `tsv_join`); neither parses free-form text
lines with string methods, which is what a log tool does and where the `.py` path is weakest. Target: one new
candidate task whose programs all pass every public and hidden case, with a measured row (wall, instructions, binary
bytes, peak RSS, compile time) for `ail`, `ail-py`, `c`, `rust`, `go` and `python`. The ten-task table is NOT
changed, and the owner decides later whether the candidate joins `lab/compare/src/`.

Base: `origin/integ`. Files you may create or edit, and no others (all new unless stated):
- `lab/compare_cand/tasks/log_scan/{spec.md,gen.py,reference.py}`
- `lab/compare_cand/src/log_scan/{main.c,main.rs,main.go,main.py,typed.py}` (and `main.nim` only if `nim` is
  installed on the runner)
- `lab/compare_cand/RESULTS-log_scan.md`
- `lab/compare_cand/README.md`: add one line naming the new task (existing file)
Do not edit `lab/compare_cand/run.py`, anything under `lab/compare/`, or any workflow. No compiler file is edited.

Read first: `lab/compare_cand/README.md` (how `run.py` reuses `lab/compare/run_task.py`), `lab/compare_cand/tasks/
csv_rollup/` and `lab/compare_cand/src/csv_rollup/` (a stdin task: `STDIN = True`, `cases(rng) -> (public, hidden,
perf)`; `typed.py` is what the `ail` column compiles, `main.py` is plain Python for `python` and `ail-py`).

## The task (write it exactly into spec.md)

`prog < access.log`. Each line is `IP - - [DD/Mon/YYYY:HH:MM:SS +0000] "METHOD PATH HTTP/1.1" STATUS BYTES`, where IP
is four dot-separated decimal ints 0-255, `Mon` is one of the 12 English month abbreviations, METHOD is one of `GET`,
`POST`, `PUT`, `DELETE`, PATH is 1-64 chars of `[A-Za-z0-9/._-]` starting with `/`, STATUS is 100-599 and BYTES is a
decimal int 0..10^12 or `-` (counts as 0). Lines end with `\n` (the last may lack it). A line that does not match
exactly (one space between fields, the literal ` - - `, the brackets and quotes) is counted as bad and skipped.
Output, each value separated by one space:
1. `lines <good> bad <bad>`;
2. `status 2xx <n> 3xx <n> 4xx <n> 5xx <n>` (1xx lines count as good but are not in this line);
3. `bytes <sum>` (int64; the perf input keeps it inside int64);
4. per hour `00`..`23` that has at least one line, ascending: `hour HH <count> <bytes>`;
5. the top 10 paths by count descending, ties by path ascending (byte order): `path <path> <count> <bytes>`;
6. `ips <distinct IP count>`.
An empty input prints `lines 0 bad 0`, `status 2xx 0 3xx 0 4xx 0 5xx 0`, `bytes 0`, `ips 0`, exit 0. Every language
runs this same algorithm: one pass with a hand-written field scanner (no regex library), a hash map for paths, a hash
set for IPs, then a sort of the paths (owner rule: same algorithm everywhere).

## Sub-steps

1. **Spec, generator, reference (20 min).** Write `spec.md`, `gen.py` (public: 3 small hand cases including bad
   lines, `-` bytes, ties and a missing last newline; hidden: 6 random cases with edge cases such as IP `256.1.1.1`,
   a 65-char path, status `600`, two spaces between fields, a lowercase method; perf: 1,500,000 lines over 2,000 IPs
   and 5,000 paths, from the given `rng`) and `reference.py` (plain CPython, the oracle). Check that
   `python3 lab/compare_cand/run.py --task log_scan --smoke --out /tmp/r.json --langs python` works. Commit, push, and
   open the PR against `integ`.
2. **Python and typed Python (20 min).** Write `main.py` (idiomatic: `sys.stdin`, `str.split`, `str.partition`, a dict
   and a set) and `typed.py` (the same algorithm with annotations, in the style of
   `lab/compare_cand/src/csv_rollup/typed.py`). Both must pass every case (`run.py --task log_scan --langs
   python,ail,ail-py`). Record whether `ail` and `ail-py` took the typed path; if one falls back, record the note. Do
   not change the algorithm to get the typed path: change only the spelling, and say what you changed in
   `RESULTS-log_scan.md`. Probe a BYTES sum beyond int64 with a hand case outside the spec's ranges (CPython prints the
   big number; AIL must stop loudly, never print a wrong number); record the result, do not add it to the cases.
   Commit and push.
3. **C, Rust, Go (25 min).** Write `main.c` (open addressing hash, `qsort`), `main.rs` (std only, `HashMap`/
   `HashSet`, no crates), `main.go` (std only, `map`). Same parsing rules, same output bytes. Run all six columns with
   `run.py --task log_scan` (full: cases plus perf). Fix any program that fails a case. Commit and push.
4. **Results (10 min).** Write `RESULTS-log_scan.md`: the date, commit, runner, toolchain versions, the table that
   `lab/compare/merge.py` makes from the result JSON, and one line per AIL column: typed or general. Add the task to
   `README.md`. Commit, push, and wait for CI.

## Done-check

- `python3 lab/compare_cand/run.py --task log_scan --out /tmp/r.json` passes every public and hidden case in all
  columns you wrote, and prints the measured row.
- `RESULTS-log_scan.md` has the table.
- `git diff --stat origin/integ` shows only files under `lab/compare_cand/`.
- The 20 shards pass.

## Stop rule

If a toolchain is missing on the runner and cannot be installed with apt in 5 minutes, skip that column and say so.
Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (Follow C:\Users\bluec\ail-work\agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000` (the perf input is about 120 MB; keep each program under 1.5 GB);
   `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`. (This job adds no test module.)
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`. Do not trigger the `compare-lab` workflow.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `cruntime.py`, `unified.py`, `buildcache.py`, `pyboxed2.py`, `ir/emit_c.py`, or
   `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit `DEVLOG.md` either: put your notes in the files this
   task names. Edit only the files this task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--syntax python] [--strict] [--debug-dir DIR]`.
  `-o` must not exist yet. A fallback to the general path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- `lab/compare_cand/run.py --task T --out J [--langs a,b] [--smoke] [--no-cases]` builds and measures one candidate
  task through `lab/compare/run_task.py`; `lab/compare/merge.py` makes the tables. Toolchain pins are in
  `lab/compare/toolchains.env`.
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
