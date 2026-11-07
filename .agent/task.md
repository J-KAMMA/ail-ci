**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — fe1 measurement + design

**What the change really does.** Adds a cold/warm measurement harness (`lab/fe/prof.py`, `timed_outer.py`, `timed_inner.py`), a renderer (`report.py`), `results.json`, `RESULTS.md`, `docs/design/FRONTEND_SPEED.md`, and DEVLOG entries. The compiler is untouched: `git diff 4cfea81..HEAD -- AIL_CURRENT tools bench corpus` is empty, so no behaviour probes apply and generated C cannot change. The report's one-line description matches the diff.

**Checks run**
- `par_check.py -j 2 test_ail_safetynet test_ail_frontend_speed` on HEAD: 2 modules, **0 failed** (154.6 s, 3.9 s). (`test_ail_files`, `test_ail_corpus_findings3` not re-run, per instructions.)
- `report.py` re-renders `RESULTS.md` **byte-identically**; `update_manifest.py --check` rc 0.
- Every cell of the §1/§3/§4 tables matches `results.json` (0 mismatches); 15 sampled top-20 `file:line` entries are exact. Recomputed: 54.4/32.6/50.4/7.3/46.6/23.5/15.5/5.3/64.7/63.9/70.5/7.76x — all match.
- No `icount`: no hot code touched.

**Report claims**
- Sections match the ranked table; DEVLOG 54.4/32.6; gcc 64.7/63.9/70.5; 10-of-14 typed attempts incl. `g14_014` 0.061/`g14_004` 0.068; three warm outliers named — **verified**.
- "46.6% × E/W 50.4% = 23.5%; mypyc > hot decided by timed-wall numbers" — arithmetic verified, but **partly false**: 46.6% is a cProfile ratio (top-20 self / profiled emitter cumulative); only E/W is timed.
- "16/16 checks", byte-identical render, manifest, "no probes applicable" — **verified**.
- "g17_004 refused before the emitter" — **unverified** (typed attempt 0.0093 s, not 0).

**Defects**
1. `FE-SPEED-A0` warm target is wrong. From `results.json`: `ticket_audit` warm median 25.5054 s, warm `other` 23.329 s → **2.18 s**, not `≤1.7 s`. The doc subtracted the *cold* `other` (23.801) from the warm wall (25.505−23.801=1.704).
2. `FE-SPEED-A0` `scar_life` cold target is unreachable: 97.381−10.938 = **86.44 s**, not `≤86 s`.
3. The per-function cache's "Amdahl bound (cold / edit)" = 50.4% is wrong for a cold build: a cache hit rate of zero on a cache miss means the cold bound is 0. 50.4% (=E/W) is an edit-only upper bound, and the doc's own text gives the realistic edit bound as `E/W×(N−1)/N`. So "ranked #1 by measured share" is not established.
4. The `parse` row is not a timed phase: 5.92 s is cProfile cumulative. It is **0.63%** of the profiled wall, not "1.6% of wall" (that divides cProfile time by the timed wall). The brief asked for parse in the wall split; wrapping `ast.parse` was possible.
5. Server option's "58% of the warm residual" uses the all-30 median load (0.193) against the fast-27 wall (0.468). Consistent fast-27 medians are 0.0263+0.1758+0.0549 = **55%** (speedup 2.2x, not 2.4x).
6. Process: commit trailers say `Claude Sonnet 5.5`, but the worker model tag is `commandcode/deepseek-v4.1-flash`; the task says non-Claude models omit the line.

**Pre-existing:** none (no probe differences; no source change).

**Unverified:** mypyc `k=2.5` (a guess, and the task said "not guesses"); "analysis and C emission interleave so cannot be split without a compiler change"; `test_ail_files`/`test_ail_corpus_findings3` (2 of the 4 claimed modules); machine-dependent absolute seconds.

VERDICT: FIX
[commandcode stop=end_turn turns=29 out_tokens=56541]


--- ORIGINAL TASK ---
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
