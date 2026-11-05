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
