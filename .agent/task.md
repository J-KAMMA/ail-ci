Lane: bigint

# bigbench1: exact big-int programs, AIL --exact-int against CPython, and one core speed-up

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** a new measurement, then a better one: the geomean over 5 big-int programs of
instructions(AIL `--exact-int`) / instructions(CPython 3.12), plus each program's peak RSS. Step 4 lowers the geomean
by speeding up the hottest big-int core routine, with the output unchanged.

Base: `origin/integ`. Files you may edit: `AIL_CURRENT/python/pkg-v12/bigint_core.py` (the C core: `ail_bn_*`,
base 2^32 limbs; Karatsuba from `AIL_BN_KARATSUBA` = 40 limbs; Knuth D `ail_bn_divmod`; `ail_bn_to_dec` at about line 231
is quadratic by design), `AIL_CURRENT/python/pkg-v12/bigint_obj.py`, `AIL_CURRENT/python/pkg-v12/tint_typed.py`,
`AIL_CURRENT/test_ail_bigint.py`, and the new directory `lab/bigbench/`. Do not edit `bigcap.py`, `biggate.py`,
`cruntime.py`, or any file in Appendix A rule 8. Read `AIL_CURRENT/docs/design/BIGINT.md` sections 3, 4 and 15 first.

## Sub-steps

1. **Programs (15 min).** Write 5 annotated programs in `lab/bigbench/` (each prints a few lines; every printed int
   stays under CPython's 4300-digit `str()` limit, so print `x % 10**50` or a digit sum, not the whole number):
   - `pidigits.py`: the Gibbons unbounded spigot (the benchmarks-game algorithm), 2000 digits, 10 per line.
   - `fib_big.py`: iterative Fibonacci to n = 50000; print the last 40 digits and the bit length.
   - `fact_mod.py`: factorial of 4000 as a big int; print `f % (10**9 + 7)`, `f.bit_length()` and the sum of the base-10^9
     limbs obtained by repeated `divmod(f, 10**9)`.
   - `powmod.py`: 300 calls of `pow(b, e, m)` with 1024-bit `b`, `e`, `m` built from a fixed LCG; print a checksum.
     If 3-argument `pow` on big ints is refused, write square-and-multiply in the program instead, and say so.
   - `collatz_big.py`: the Collatz step count of `2**300 + k` for k in 0..199; print the total.
   Each must print exactly what `python3` prints. Commit, push, open the PR against `integ`.
2. **Measure (15 min).** Build each with `compile --exact-int --syntax python` (note whether it is typed or general).
   For each: AIL output == CPython output; instructions of the AIL binary and of `python3 prog.py` (icount, Appendix B);
   peak RSS of both; AIL compile time and binary bytes. Write `lab/bigbench/RESULTS.md` with one table and the
   geomean ratio. Commit.
3. **Profile (10 min).** For the two worst ratios, `perf record` (or `valgrind --tool=callgrind`) the AIL binary and list
   the top 5 functions with their share. Note any RSS that grows with run length (BIGINT.md says typed-path big values
   are freed only at exit) as a finding with numbers; do not change memory ownership in this job.
4. **One core speed-up (25 min).** Pick the single hottest `ail_bn_*`/`ail_big_*`/`ail_tint_*` routine from step 3 and
   speed it up without changing results. Allowed examples: a single-limb fast path in multiply/divide, avoiding a
   malloc of a working copy, a 64-bit-at-a-time inner loop. Not allowed: changing the limb base, the 4300-digit rule,
   or any printed text. Then run `python3 tools/par_check.py -j 2 test_ail_bigint` (the C core is checked against
   CPython there; about 11 minutes) and re-measure all 5 programs: every output still equal, and the step-2 table gets
   an "after" column. Keep the change only if the geomean improves by at least 3% and no program gets slower by more
   than 1%. Otherwise revert it and record the numbers. Commit, push.

## Done-check

`lab/bigbench/RESULTS.md` has before/after instruction ratios, RSS and the profile findings; 5/5 outputs equal to CPython;
`test_ail_bigint` passes; 20 shards pass.

## Stop rule

If a program cannot be built with `--exact-int` and the refusal needs a compiler change outside the files above, keep
the program, mark it "refused" with the text, and measure the others. If step 4 gives no kept gain in 25 minutes, revert
it and report the measurement only. Stop at 80 minutes and push what is done.

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
