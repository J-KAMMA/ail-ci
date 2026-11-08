**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
I've finished checking. I verified the oracles, the JSON-derived numbers, the live census/boundary for sampled modules, the Rust bar, report regeneration, the tests, and the manifest.

**What the change really does:** measurement-only; adds `lab/wedge/` (15 corpus modules + `expected.txt`, census/boundary/measure/analyse/rust_bar scripts, JSON caches, PyO3 `rust/` crate) and a `RESULTS.md`; no compiler/runtime/test change. That matches the task and the report except as noted below.

**Claims**
- 15 modules, 97 top-level defs, 24 native (24.7%): **verified** (JSON + live census of float_loops/json_parse/matrix: 8/4/8 defs, 0/3/4 native, all match).
- Committed `expected.txt` oracles: **verified** — all 15 match a fresh `python3 run.py`, byte for byte.
- `report.py` regenerates `RESULTS.md` byte-identically: **verified**.
- Table ratios/geomean 0.983x (range 0.901–1.060), §3 Rust-bar numbers (62.3x/2x/204.2x/2.8x/76.6x; whole 18.19/1.07/45.8/1.43/1.36x): **verified**; re-ran `rust_bar.py` — PY/RS digests identical to the committed ones, MATCH true on all five.
- Build artifacts untracked, `.gitignore` correct, `rust_bar.json` 2.6 KB digests: **verified**.
- tree_build `_inorder` 2.15 s of 5.80 s, methods 5.69 s: **verified** against measure.json.
- 54 of 73 refusals silent (74.0%), `list[float]` ABI mismatch, W0 text: **verified** (live boundary for float_loops/matrix, JSON for the rest).
- Tests on HEAD: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all ok (282 s); `update_manifest.py --check` exit 0: **verified**. `test_ail_cpython_hybrid` not re-run (not touched).
- Worker's five `/tmp/probes` probes: **unverified** (files not in the tree).
- "Ratio convention is hybrid/CPython everywhere": **false** — `measure.py` still prints `cpython/hybrid` = 1.017 as "hybrid/cpython speedup".
- "No wrong number left": **false** — see defects.

**Pre-existing:** none (no compiler/runtime change; nothing to compare against `/tmp/base`).

Checks: oracle diff for 15 modules; `census.py --only float_loops,json_parse,matrix`; live `boundary.census_one` for float_loops/matrix; `rust_bar.py` rebuild; `report.py` diff; AST scan of corpus functions against `_select`/`_unsafe_body`; tests; `icount` not run (no hot-code change).

VERDICT: FIX
1. The W-task "gain"/guards treat the first-gate attribution as an achievable unlock, but `_select` applies a second gate: `_unsafe_body` returns `indexing can raise` for **any** `Subscript` (AIL_CURRENT/ail_cpython_hybrid.py:309, called at :571). By AST scan of the committed corpus, bodies with a subscript: list-return-kind 8/11, tuple-parameter 7/7, nested-list-annotation 2/6, list-float-abi 2/7. Concretely, every W2 guard function indexes (`bloom_set`, `group_sum`, `mat_mul`, `window_sums`, `identity`), so after a list-return fix they are all still refused for indexing — proven by `matrix.trace` (list[int] param, int return, `m[i*n+i]`), which boundary.py reports as gate `select`, reason `indexing can raise`. W3's 7 ast_lint functions all index and call, so W3 alone accelerates none. Expected (report): "are listed as accelerated". Actual: 0 of 5, 0 of 7; W4 (indexing-can-raise) is the prerequisite, so the "which boundary fix unlocks the most" ranking/order (W1..W6) is not the achievable one.
2. W6's `float_loops` claim is wrong: `scale_into` is refused by pymix (`unresolved-return`, family list-return-kind), and the report's own table row 11 gives list-float-abi only 7 functions. With the ABI spelling fixed only `max_abs` and `sq_sum` have no other gate (`dot`/`blend` index; `mean`/`variance` divide by a non-constant; `norm` uses `**`). Expected: "goes from 0 to 8 accelerated"; actual: at most 2, and `scale_into` needs W2. Also "typed emitter accepts all 8" and "the only reason float_loops gets nothing" are false.
3. `measure.py` prints the inverse: `statistics.geometric_mean([cpython_s/hybrid_s])` labelled "hybrid/cpython speedup" → 1.017x, contradicting the report's 0.983x. Expected: reproduce the report's convention; actual: 1.017x under the report's label.
4. DEVLOG says "runs 28.17 s of CPython as 8.49 s": 28.17 s is all 15 modules, 8.49 s is only the 13 with a timed standalone binary; like-for-like is 24.70 s → 8.49 s (2.91x, not 3.32x).
5. The refusal ranking's time base is cProfile `tottime`, which is profiler-inflated: §4's total "44.2 s across 15 modules" exceeds the report's own total CPython wall time (28.17 s); e.g. ast_lint is 5.67 s of self time for a 1.739 s program, tree_build 5.80 s for 1.97 s. The headline "5.0% of the corpus's CPython self-time" and the reason shares are therefore not shares of real time; the report should say so or compute shares from wall time.
[commandcode stop=end_turn turns=45 out_tokens=47294]


--- ORIGINAL TASK ---
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
