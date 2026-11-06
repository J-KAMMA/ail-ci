Lane: proof

# proof1: design + census for "Rust's safety without writing lifetimes": how much of real Python code can AIL prove memory-safe and race-free at compile time

Time budget: 150 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler behaviour change.

**Why (owner, 2026-11-07):** the owner wants a goal that actually beats Rust, not "Rust-level when Rust is overkill".
The candidate claim: *write plain Python; the compiler infers ownership and proves memory safety and the absence of
data races for typed code; where it cannot prove, it falls back to a runtime check that stops loudly and tells you
which line it could not prove.* Before anyone builds this, we need a measured answer to: what fraction of real
functions does today's analysis already prove, and what blocks the rest.

**Numbers this produces** (`lab/proof/RESULTS.md`, `lab/proof/census.json`):
For every typed function in three corpora: `lab/compare/src/*/typed.py` and `main.py`, `lab/pyproof/` programs, and the
first 200 programs of the corpus the repo already uses for C-diff checks (find it via `tools/` / `lab/corpus`):
1. **Ownership:** share of RC operations (retain/release sites) that the existing analyses (`ir/borrow.py` rc2 borrows,
   rc3 cursors if merged, `ir/effects.py`) already elide, vs. the share still needed; per function: "fully proved"
   (no runtime RC op needed except at owner creation/destruction), "partly", "none".
2. **Bounds:** share of list/array index sites whose bound check is already removed by proof (job `bce` work) vs kept.
3. **Races:** for functions that run under the existing parallel constructs (lab/race, `ex.map`, parallel loops),
   share of shared-state accesses the race rules D1-D5 already classify as safe, refused, or unknown.
4. **Blockers:** the top 15 reasons a function is not fully proved (e.g. "object stored into a list then mutated",
   "call to unknown function", "global", "aliasing through attribute"), each with count and one minimal example.
Report the census numbers by corpus and overall, measured, not estimated.

**Design** (`docs/design/SAFETY_PROOF.md`, at most 250 lines): the claim in one paragraph; what "proved" means for each
of the three properties (precise rule, no hand-waving); how a failed proof degrades (runtime check + diagnostic line);
the diagnostic format (`file:line: could not prove <property>: <reason>; runtime check kept`); which existing modules
each part builds on; a staged plan of jobs of at most 2 hours each, ordered by how many census blockers each removes,
each with the number it moves; and an honest section "what Rust still proves that this cannot".

Base: `origin/integ`. Files you may create or edit, and no others (all new): `lab/proof/*` (census script, results,
json, README) and `docs/design/SAFETY_PROOF.md`. Read compiler files freely; to collect numbers, call the existing
analyses from the census script (import them), do not edit them. If an analysis has no API to ask, record that as a
blocker instead of patching it.

## Sub-steps
1. (50 min) Census script over corpus 1 (compare-lab), ownership + bounds. Commit, push.
2. (40 min) Corpora 2 and 3, races, blocker ranking. Commit, push.
3. (50 min) `SAFETY_PROOF.md`. Commit, push.
4. (10 min) `RESULTS.md` summary: 5 lines with the headline percentages. Commit, push.

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
