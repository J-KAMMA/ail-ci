**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — tccprobe1 (`cffdbed`)

**What the change really does.** Adds only `lab/tccprobe/run.py`, `lab/tccprobe/RESULTS.md`, four `fail_*.txt` excerpts, and a DEVLOG entry. It does not touch the compiler, runtime, or default C compiler. The script generates C for 10 compare tasks and 40 seeded `corpus/gdev` programs, rebuilds the saved C with `gcc -O2`, `gcc -O0`, and `tcc`, runs and times the binaries, and classifies tcc failures. This matches the report's description.

**Reproduction.** A full `python3 lab/tccprobe/run.py --runs 1` reproduced the headline numbers exactly: 50 attempted, 50 C generated, 50 gcc -O2 builds, **0 tcc builds**, buckets **23 / 19 / 8**, and the same 40-program corpus list. `python3 tools/update_manifest.py --check` exits 0. `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 3 modules, 0 failed (345 s). `cmp.sh` is not applicable: no AIL language behaviour changed.

**Claims checked.**
- tcc 0.9.27, 0/50, bucket counts, corpus list, gcc build counts and timings, required tests: **verified**.
- "23 unsized struct-array compound literals ... from `pyfunc.py:24481`": **false**. 15 are compound literals; 8 are unsized array declarations `ail_bytes spans[] = {h, old, repl};` emitted from `cruntime.py:6450/6508/6538`. Consequently the per-task "tcc first blocker = compound literal" is wrong for `echo_pack`, `ledger_bin`, `scar_life`, `tally_lang`, `term_rank`, `ticket_audit`, `tree_fold`, and corpus `g02_000`.
- Three-run determinism and the `program.c` sha256 claim: **unverified** (my rerun used `--runs 1`).
- Max C size "2.34 MB": my run gives 2,395,833 bytes (≈2.40 MB decimal), a minor unit inconsistency.

**Pre-existing:** none observed; no AIL source file changed.

### Defects

1. `run.py`'s `classify()` maps every `index too large` to `unsized struct-array compound literal from runtime values` / `pyfunc.py:24481`. Probe: compile `lab/compare/src/echo_pack/main.ail` with `--debug-dir` and run `tcc program.c -lm`. Expected per RESULTS: first error at `ail_stdout_parts((ail_str[]){...})` from `pyfunc.py:24481`. Actual: `program.c:4503: error: index too large` at `ail_bytes spans[] = {h, old, repl};`, from `cruntime.py:6450`. `/tmp/rprobes/decl.c` and `/tmp/rprobes/lit.c` show the two constructs fail independently; `/tmp/rprobes/decl_sized.c` builds. The headline 0/50 is unchanged, but the task asks for each bucket's actual construct and source line, so the bucket should be split or the attribution corrected.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1373959, "input": 74674, "output": 6033, "reasoning": 26564, "cache.write": 0, "cache.read": 1266688}]
    tool time: bash 14.9 min
        532s bash   cd /home/runner/work/_temp/w2 && date && timeout 900 python3 lab/tccprobe/run.py --runs 1 --out /tmp/rprobes/f
        346s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_saf
         12s bash   cd /home/runner/work/_temp/w2 && date && timeout 900 python3 lab/tccprobe/run.py --only corpus --corpus 1 --ru
          4s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rprobes/gen_echo && mkdir -p /tmp/rprobes/gen_echo/{cache,tmp} &&
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "exit ${PIPESTA
          0s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/rprobes/gen_echo && mkdir -p /tmp/rprobes/gen_echo/{cache,tmp,dbg
          0s bash   pwd; ls -la; date; git log --oneline -5; git status --short
          0s bash   cd /tmp/rprobes && cat > decl.c <<'EOF' typedef struct { const void *p; long n; } B; int main(void) { B h={0,0

## fix round skipped: only 48 minutes left


--- ORIGINAL TASK ---
Lane: tccprobe

# tccprobe1: does the C that AIL generates build and run correctly with tcc? (measurement only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Numbers this produces.** All of them are new, so today they are unknown:
- (a) programs whose generated C builds with tcc, out of N;
- (b) of those, programs whose output and exit status are byte-identical to the gcc -O2 build;
- (c) median C-compile wall time, tcc against gcc -O2 and gcc -O0;
- (d) median run time, tcc build against gcc -O2 build.

**Why.** Two reasons:
1. A bootstrappable self-hosted AIL. The compiler's generated C would be the seed, and tcc is the first C compiler in
   bootstrap chains such as live-bootstrap.
2. A possible fast dev-build mode. gcc is about 26% of AIL's cold build time.

This job only measures. **Do not change the compiler, the runtime, or the default C compiler.** Release builds stay
on gcc -O2 (an owner decision); a tcc mode would be a separate, opt-in follow-up for the owner to decide.

Base: `origin/integ`. Files you may create, and no others:
- `lab/tccprobe/run.py`
- `lab/tccprobe/RESULTS.md`
- `lab/tccprobe/fail_*.txt`: at most 10 short excerpts.

## Steps

1. **Setup (10 min).** Run `sudo apt-get install -y tcc` on the runner, and record `tcc -v`. Find how the AIL CLI
   keeps or emits the generated C, and how it chooses the C compiler: look for a keep-C or emit-C option, a
   `CC` environment variable, or the gcc invocation in `buildcache.py`/`cli.py`. Read them; do not edit them. If the CLI
   cannot hand you the C file and the link command, reproduce the gcc command line from the source and swap in tcc
   inside `run.py` only.
2. **Corpus (40 min).** Use the 10 compare-lab programs (`lab/compare/src/*`, AIL version) and 40 corpus programs
   from the existing tests, chosen with a fixed seed; list them in RESULTS.md. For each program:
   - generate the C once;
   - build it with gcc -O2, gcc -O0 and tcc, timing each C compile separately, median of 3;
   - run each build with the same input; compare stdout, stderr and exit status against the gcc -O2 build;
   - time the runs, median of 3.

   Sort each tcc failure into one bucket:
   - unsupported builtin or intrinsic (`__builtin_*`, vector extensions, `__int128`);
   - inline asm;
   - attribute or pragma;
   - link error;
   - wrong output.

   Count each bucket, and keep one short excerpt per bucket.
3. **Report (20 min).** Write RESULTS.md with numbers (a)-(d), the bucket counts, and for each bucket the generated-C
   construct that causes it, with file and line in the runtime or emitter source. Do not fix anything. **Wrong output
   is a stop condition.** If a tcc build prints anything different, record it first in RESULTS.md. Remember that the
   cause may be undefined behaviour in the generated C, which gcc happens to hide.

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
