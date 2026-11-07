Lane: fedesign

# fe1: where the Python front end spends compile time, and a design to cut it (measurement + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/fe/*` and `docs/design/FRONTEND_SPEED.md`.

**Why (owner, 2026-11-07):** tcc1 (`lab/tcc/RESULTS.md`) showed the C compiler can be made 121x faster but the cold
edit-run only 1.6x faster, because AIL's Python front end is the fixed cost. vibe1 (`lab/vibe/RESULTS.md`) measured
AIL's write-run loop at 111 s vs 1 s for CPython. AIL is for vibe coding; this loop is the product.

## Measure (`lab/fe/RESULTS.md`)
On the 10 `lab/compare/src/*/main.py`, their `typed.py`, and the 14 programs timed in lab/tcc (same list):
1. Cold compile wall split into: interpreter start + imports (`python3 -X importtime`), parse, each front-end pass
   (find the pass boundaries in the driver; `cProfile` cumulative per top-level pass function), C emission, C
   compile, link. Median of 3, cold cache. Show both the typed and the general path (programs that fall back to the
   general path: how much time is spent on the failed typed attempt before falling back?).
2. Top 20 functions by self time across all programs (cProfile), with file:line.
3. Warm (cache hit) breakdown: what still runs on a hit.
4. Memory peak of the front end (`/usr/bin/time -v`).

## Design (`docs/design/FRONTEND_SPEED.md`)
Rank options by measured share (Amdahl bound for each, from the table, not guesses), each with risk, files touched and
how output equality is proven (byte-identical generated C on the whole corpus):
lazy imports; skipping the doomed typed attempt early (decide fallback from a cheap pre-scan); caching per-function
results across edits (only the changed function is re-analysed); algorithmic fixes in the top-20 hot functions;
compiling the front end itself (mypyc / Cython / AIL self-hosting of the hot part); a long-lived compile server
(`ail run` reuses a warm process). Then split the chosen top 2-3 into implementation steps of at most 2 hours, each
with its own files, test and number, written as ready-to-queue task text at the end of the doc.

## Sub-steps
1. (60 min) Harness `lab/fe/prof.py` + RESULTS.md tables. Commit, push.
2. (60 min) FRONTEND_SPEED.md with ranking and step split. Commit, push.

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
