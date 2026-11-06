**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** it adds a census script (`lab/proof/census.py`), its JSON/results and `docs/design/SAFETY_PROOF.md`; it imports the existing analyses and measures them. No compiler source is touched (verified: the diff is only the two DEVLOGs, the design doc, `lab/proof/*`). The measured ownership/bounds/reach numbers re-derive from `census.json`; the race section does not.

**Claims checked**

| claim | verdict |
|---|---|
| no compiler source touched; C unchanged | verified (`git diff --name-only work..HEAD`; no compiler file) |
| 3255 records; reach 907/1703/645 partitions exactly | verified (recomputed from `census.json`; per-corpus sums 363/769/2123) |
| blocker counts 645/252/145/106/77/59/49/47/20/14 | verified (recomputed with the script's `rank` rules; matches `census.json`) |
| why-boxed table (Decimal 198, bool 188, dunder 214, other 273) | verified (recomputed `boxed_reasons()`; equals JSON; sums 1703) |
| `self.h0`; `tally_lang/typed.py:37` bounds blocker | verified (line 13 `G.__init__` has `self.h0 = h0`; line 37 `peekop`, 2 index-negative sites) |
| `--limit 3` prints 40 programs, 31 functions (29/2) | verified (re-run produced 40/31/29/2) |
| probes own1/bnd1/race1/race2/bce1 pass both builds | verified (reran all five: CPython/g/d identical, exit 0) |
| "races: 104 = 79 safe + 25 refused, 6 named, 5 worker functions, D3 0" | **false as a corpus fact** — script output only; see defect 1 |
| "DEVLOG corrected … 219-line design" | **false** for the root `DEVLOG.md` — see defect 2 |
| test_ail_safetynet | verified (1 module, 0 failed, 164 s) |

**Defects**

1. **The race census misses every `threading.Thread` target, so the refused-access numbers and the P7/P8 plan are wrong.** `_region_targets` (`census.py:544-559`) matches `Thread` only as a bare `Name`; 10 of the 14 refused-shape programs write `threading.Thread(target=...)`. Reproducer:
   ```
   python3 - <<'EOF'
   import ast,sys; sys.path[:0]=['lab/proof','AIL_CURRENT/python/pkg-v12','AIL_CURRENT']
   import census; census._setup()
   src=open('lab/race/racy/shared_append.py').read()
   print([f.name for f in census._region_targets(ast.parse(src))])
   r=census.race_info(src, ast.parse(src)); print(r['refused'], r['refused_regions'])
   EOF
   ```
   Expected: `['work']`, then a nonzero refused count (the `xs.append` is D3). Actual: `[]`, `0 0`.
   Aggregate (same `_shared_accesses` applied to the 11 missed worker functions in `shared_append, global_add, float_cell, max_cell, mod_two, neighbour, same_list_twice, shared_dict, write_slot0, resize_while_index`): refused **79** not 25, distinct **158** not 104, D1 **11** not 2, D3 **2** not 0, D4 **6** not 4. So RESULTS' "5 worker functions … only there can accesses be classified" describes a script gap, and `SAFETY_PROOF.md` P7 ("D3 never fires: 0 accesses, 0 regions") and P8 ("D1: 2 accesses in 2 programs") are false.

2. **The root `DEVLOG.md` at HEAD still publishes the numbers the previous review rejected.** Actual: "306 programs, 4958 functions", "1552 of 4958 (31.3%)", "1703 boxed and 1703 are in refused programs", "79 of 123 shared accesses … 25 refused by a named rule", "(216 lines)". Expected (HEAD `census.json`, `AIL_CURRENT/DEVLOG.md`): 3255 functions, 907 typed (27.9%), 645 refused, 104 accesses, 6 named, 219 lines. The report's "DEVLOG corrected" is true only of the `AIL_CURRENT` file.

3. Minor: RESULTS' bounds note says the 1875 reason records exceed the 1059 kept IR sites because "a site can be reported once per build attempt". Actually 792 of the 1875 records are attached to functions with no IR record (legacy/no-index) and only 1083 are in IR functions; the reason totals (1072/282/276/245) therefore mix sites from failed IR attempts of legacy functions. The function-level blocker counts are unaffected.

Pre-existing: none (no compiler change). Unverified: full `census.py --jobs 2` regeneration (I recomputed from the committed JSON and ran `--limit 3`); `test_ail_bce/rc_borrow/files/corpus_findings3` (not edited, and not required); correctness of the recorded `pyc.last_fallback_reason` strings. Speed: N/A, no compiler/hot-code change.

VERDICT: FIX
1. `census.py:_region_targets` ignores `threading.Thread(...)`; recompute with the attribute form: refused accesses 79 (D1 11, D3 2, D4 6, unknown 60), distinct 158 — correct RESULTS, README and `SAFETY_PROOF.md` P7/P8.
2. Correct or remove the stale top-level `DEVLOG.md` entry (4958/1552/1703/123/25 named/216).
3. Correct RESULTS' bounds-reason note: 792/1875 records belong to functions with no IR record, not to per-build duplicate reporting.
[commandcode stop=end_turn turns=38 out_tokens=42835]


--- ORIGINAL TASK ---
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
