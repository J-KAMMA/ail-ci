Lane: apps

> Re-run of apps1_rr1, whose GitHub run was lost (no verdict 6.6 h after dispatch). If its branch job-apps1_rr1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

> Re-run of apps1, whose GitHub run was lost (no verdict 10.8 h after dispatch). If its branch job-apps1-* has work commits, cherry-pick them first and continue; otherwise do the task from scratch on origin/integ. Commit and push after every sub-step, so a cancel does not lose the work again.

# apps1: six small command-line tools in plain Python, built by AIL, checked against CPython

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** example CLI tools in `examples/apps/` that build in the default mode, reach the typed path and
print exactly what CPython prints: 0 today (there is no such directory) -> 6/6, with a table of wall time and binary
size against `python3` on a 50 MB input. This is the roadmap's P4 niche ("small, fast CLI and data tools written in
Python syntax"), shown on real tools.

Base: `origin/integ`. All new files: `examples/apps/` (new), `AIL_CURRENT/test_ail_examples_apps.py` (new),
`AIL_CURRENT/tests.d/test_ail_examples_apps.txt` (new). Do not edit any compiler file. Do not edit `docs/` or the
top-level `README.md` (another lane owns them).

## The tools

Write ordinary, idiomatic Python 3 with type annotations on functions (as a user would; no AIL-only imports). Each
reads stdin, takes its options from `sys.argv`, and exits 0 (or the status stated). Each is 20-60 lines.

1. `wc.py`: lines, words, bytes of stdin, printed like `wc` without the file name (`%7d %7d %7d`). Read bytes with
   `sys.stdin.buffer.read()`.
2. `colsum.py COLUMN`: a CSV (with the `csv` module) with a header row; for the named column print count, sum, min, max
   and mean (`%.6f`) of the values that parse as int; print the count of the rows that do not. Exit 2 if the column is
   missing, with a message on stderr.
3. `topwords.py N`: the N most frequent words (lowercased, split on non-letters with `re`), ties by word, as
   `count<TAB>word`. Use `collections.Counter`.
4. `grepn.py TEXT`: lines containing TEXT, as `lineno:line`; exit 1 if none matched (like grep).
5. `jsonfield.py KEY`: JSON Lines on stdin (`json.loads` per line); print the value of KEY of each object with
   `json.dumps`, or `-` when absent.
6. `hexdump.py`: stdin bytes as `xxd`-style lines: 8-digit hex offset, 16 bytes as hex in pairs, then the ASCII column
   ('.' for bytes outside 0x20-0x7e).

## Sub-steps

1. **Tools and small inputs (25 min).** Write the 6 tools and `examples/apps/data/` inputs: per tool one normal input and
   two edge inputs (empty stdin; one with odd content: no final newline, non-ASCII UTF-8, a quoted CSV field with a comma,
   ints beyond int64 in `colsum` and `jsonfield` input). Check every tool with `python3` first. Commit, push, open the
   PR against `integ`.
2. **Build and compare (20 min).** Build each with `python3 -B AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python
   -o X`. Record for each: typed or general (the stderr note), and stdout + exit code equal to `python3` on every input.
   Also build with `AIL_UNIFIED_FORCE=1` and compare again. A tool that falls back to the general path or differs is a
   finding: give the note or the first differing line. Do not rewrite a tool into unusual Python to dodge a refusal;
   one small idiomatic rewrite (for example a loop instead of a nested comprehension) is allowed if you write down the
   original line and the refusal it caused. Commit.
3. **Test module (15 min).** `test_ail_examples_apps.py` (model: `test_ail_std_statistics.py`): for every tool and input,
   build once, run, and compare stdout and exit code with `python3`. A `TYPED` set lists the tools that must build
   without the general-path note; assert that. Register it (Appendix A rule 6). Run
   `python3 tools/par_check.py -j 2 test_ail_examples_apps`. Commit.
4. **Measure (15 min).** A generator script `examples/apps/make_big.py` (fixed seed) writes a 50 MB input per tool into
   `/tmp` (not into git). For each tool: median of 5 wall times for the AIL binary and for `python3`, peak RSS of both,
   binary bytes, compile seconds. Write `examples/apps/README.md`: how to build and run one tool, the table, and the
   findings of step 2. Push.

## Done-check

6 tools, each equal to CPython on all inputs; the number of typed tools stated (target 6/6); the test module passes;
`examples/apps/README.md` has the table; 20 shards pass.

## Stop rule

If a tool cannot be built at all and the cause needs a compiler change, keep the tool, mark it in the test as an
expected refusal with the exact text (the test then fails loudly when the compiler starts building it), and go on.
Stop at 80 minutes; push what is done.

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
