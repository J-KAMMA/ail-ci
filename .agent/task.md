# wedge1: benchmark for "do not rewrite it in Rust, compile it", plus the boundary census

Lane: hybrid
Needs: cpyhyb2d

Measurement only. Do not change the compiler. The strategy behind this task is in docs/STRATEGY.md.

## Corpus

Write about 15 small Python modules under lab/wedge/corpus/. Each one stands for a kind of hot path
that real projects moved from Python to Rust through PyO3. Write them yourself; copy no third-party
code. Kinds to cover:

- tokenizing and lexing a source file;
- a CSV- or JSON-like parser;
- string normalising and validation (pydantic-like field checks);
- dataframe-like groupby, sum and filter over lists of rows;
- lint-like AST walking over nested tuples;
- graph search;
- edit distance and fuzzy match;
- hashing and checksums;
- tree building and traversal;
- numeric loops over lists of floats.

Each module needs:

- plain typed Python functions, as a user would write them;
- a driver, `run.py`, that imports the module and calls it on a fixed input big enough for about
  1-5 s under CPython;
- an expected-output file made by CPython.

## Measure, per module

1. Build it with AIL's hybrid or extension build. Count the functions that went native and the ones
   that stayed on CPython. For each one that stayed, record the refusal reason.
2. Check that the output is byte-identical to CPython. Any difference is a silent bug: list it first.
3. Wall time, median of 5, for:
   - CPython;
   - the hybrid build;
   - the standalone AIL binary where the whole program builds.
4. Where it is quick to do, also time a hand-written Rust/PyO3 version of the single hottest
   function, for 3-5 modules. That is the "rewrite in Rust" bar.

## Output

- lab/wedge/RESULTS.md with:
  - a per-module table;
  - the share of functions that went native, overall;
  - speed against CPython and against the Rust bar;
  - the refusal reasons, ranked by how much hot-path time each one keeps on CPython.
- At the end, ready-to-queue task texts, each 2 hours or less, for the top 5 reasons. Each task
  names the reason, the test that guards it, and the expected gain measured on this corpus.

## Done when

RESULTS.md answers, with numbers: what share of a typical Rust-rewrite hot path AIL compiles today,
and which boundary fix unlocks the most of the rest.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
