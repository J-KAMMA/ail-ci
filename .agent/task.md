**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: pyreach9 (census + design only)

**What the change really does:** adds `lab/pyreach9/census.py` (compiles 134 programs with `--strict --json` and the default build), `classify.py` (reason bucketing over `census.jsonl`), `RESULTS.md`, `programs.txt`, and `docs/design/PYREACH_NEXT.md`; **no compiler/runtime file is touched** (`git diff work..HEAD --stat` = DEVLOG + 6 lab/design files). That matches the report's "no compiler change".

**Independent checks**
- `classify.py` output reproduces every table in `RESULTS.md`; `--dump` is byte-identical to `programs.txt`.
- Re-ran `census_one` on `g11_002`, `g03_032`, `g06_008`, `g08_002`: path, `strict_incomplete` and blocker text match `census.jsonl`. Data is not fabricated.
- Totals: 134 = 37 typed / 81 general / 16 refused; 41 incomplete of 97 — correct.
- `tools/update_manifest.py --check` rc=0; tree clean except `.agent/pipeline.md`.
- `par_check -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 3 modules, 0 failed (347 s).
- Speed: no hot code changed, skipped. No `cmp.sh` probes: no emitted C changed.

**Report claims:** (1) array=2/incomplete, deque+g03_032 incomplete, g01_008/g04_010/g16_006/g16_038 complete — **verified**; (2) `_ail_l1l` sole blocker of `berth_sim/ail-0` — **verified**; (3) g06_008 has no NamedTuple and its two blockers are the generated `_ail_trepr_s_i` tuple-repr helper (`_AilT_s_i` caller conflict) + `sset` — **verified** (the name is the blocker's `function` field); g01_022 extras — verified; (4) five vibe refusals, `rail_transfer/python-0` general — **verified**; (5) `scar_life` flags `[]`, only compare chain_relax/rail_transfer get `--exact-int` — **verified**; (6) classifier fallback fix + regenerated dump — **verified**; (7) HEAD has no `Co-Authored-By`, earlier commits carry Claude — **verified**. But the lane's own design still overstates move counts.

### Defects
1. `PYREACH_NEXT.md:212` step 2b "moves 1 (`rail_transfer`)". Census (`census.jsonl`): `compare/rail_transfer/main.py` has four reasons (`none-optional`, `tuple-unpack`, `str-number-concat`, `int64-literal`), and its int64 blocker is "`main()` shifts beyond int64", while `INF = 1 << 200` is a list element/assignment/`==` — which the doc itself (line 168) says must stay refused. `vibe/rail_transfer/python-0.py` has **no** int64 blocker (7 array-prelude blockers). Expected move: **0**.
2. `PYREACH_NEXT.md:284` step 3c "moves 1 (`ledger_bin/python-0`)". That program's reasons are `dict-of-containers, parameter-readonly, str-number-concat, tuple-unpack, value-kind-lost`; it is not sole. Expected: **0**.
3. `PYREACH_NEXT.md:348` step 4b "moves 2". `g16_030.py` also blocks on `unsupported-builtin` (`min()`, `next()`); only `g16_000` is sole. Expected: **1**.
4. `PYREACH_NEXT.md:389-405` §5 move counts (json 5-6, statistics 3, itertools 4, collections 4-5). From the sole data those are *touched* programs, not moves: json **1** (`g21_022`), statistics **1** (`g03_032`), itertools **1** (`g14_022`, labelled `other`), collections **0**.
5. Wrong census counts: `:363`/`RESULTS.md:166` say "`json` 8 programs" — 6 programs carry json blockers (`g13_024, g21_000, g21_004, g21_008, g21_012, g21_022`); 8 only results from matching the refusal boilerplate "… re, json" in `g15_024`/`g15_028` (traceback/logging). `RESULTS.md:166` "itertools/functools/re 1-2 each" — itertools blockers occur in **5** programs (`g06_026, g14_022, g16_032, g18_014, g18_026`), as the design's own "4" contradicts.
6. Minor, `classify.py:33` generated-prelude regex misses `_AilEnum` (only `_AilIntEnum` is listed), so 6 prelude dunders in `g25_000`/`g25_022` are labelled `class-dunders`. It does not change the ranking, but the per-reason blocker counts are wrong.

### Pre-existing
None identified (no compiler change; nothing to diff against base).

### Unverified
Full census re-run (~31 min) not repeated; I verified 4 records by recompilation and the classifier end-to-end. Speed not applicable.

VERDICT: FIX
1. `docs/design/PYREACH_NEXT.md:212` — step 2b claims 1 move (`compare/rail_transfer/main.py`); expected 0. Evidence: `classify.program_categories` on that record returns `{int64-literal, none-optional, tuple-unpack, str-number-concat}`; the int64 blocker is "`main() shifts beyond int64`" and `INF = 1 << 200` is used as `[INF] * n`, `best = INF` and `== INF`, which line 168 says stays refused.
2. `PYREACH_NEXT.md:284` — step 3c claims 1 move (`ledger_bin/python-0`); expected 0. Evidence: its categories are `{dict-of-containers, parameter-readonly, str-number-concat, tuple-unpack, value-kind-lost}`.
3. `PYREACH_NEXT.md:348` — step 4b claims 2 moves; expected 1. Evidence: `g16_030.py` categories are `{generator-yield, unsupported-builtin}`.
4. `PYREACH_NEXT.md:389-405` — §5 "moves" (json 5-6, statistics 3, itertools 4, collections 4-5) are touched counts; sole moves are json 1 (`g21_022`), statistics 1 (`g03_032`), itertools 1 (`g14_022`), collections 0.
5. `PYREACH_NEXT.md:363` / `RESULTS.md:166` — "json 8 programs" should be 6 (`g13_024, g21_000, g21_004, g21_008, g21_012, g21_022`); the 8 only matches the boilerplate module list in `g15_024`/`g15_028`. `RESULTS.md:166` "itertools … 1-2 each" should be 5 programs (`g06_026, g14_022, g16_032, g18_014, g18_026`).
6. `lab/pyreach9/classify.py:33` — add `_AilEnum` (and its helper names) to the generated-prelude pattern; 6 `_AilEnum` dunder blockers in `g25_000`/`g25_022` are currently counted as `class-dunders`.
[commandcode stop=end_turn turns=34 out_tokens=36159]


--- ORIGINAL TASK ---
Lane: pyreachdesign

# pyreach9: why plain `.py` still falls to the general path after pyreachs1-8, and the next steps (census + design only)

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).
Do not change the compiler. Output: `lab/pyreach9/*` and `docs/design/PYREACH_NEXT.md`.

**Why (owner, 2026-11-07):** roof1 (`lab/roof/RESULTS.md`) measured 6 of 8 compiling compare `main.py` builds on the
general path at 1.6x-143x C, while the annotated `typed.py` runs at 1.31x C (median); getting plain Python onto the
typed path is worth 12-122x on those programs, more than every hardware feature combined. vibe1
(`lab/vibe/RESULTS.md`) found every AI-written AIL program on the general path (0 typed / 8 general). The owner chose
to work on this first.

## Census (`lab/pyreach9/RESULTS.md`), on current `origin/integ`
Corpora: the 10 compare `main.py`; the AI-written programs in `lab/vibe/programs` (all languages' Python versions,
since an AI writes plain Python); 100 `corpus/gdev` programs (fixed seed). For each program: path (typed / general /
refused), and for every general or refused program the full list of reasons (not only the first: use `--strict` and
the compiler's explain output, or iterate by locally patching the source in a throwaway copy until it types, noting
each blocker in order). Rank reasons by "programs that would become typed if this reason alone were removed" (count
programs whose only remaining blocker is it, and programs it appears in). Note which reasons are AI-typical (from the
vibe programs) vs corpus-typical.

## Design (`docs/design/PYREACH_NEXT.md`)
For the top 5 reasons: what Python semantics must hold (CPython-identical output, or a loud refusal by name; never a
silent difference), which compiler file/function decides it, the change, the proof obligations, and the expected
programs moved (from the census). Split into implementation steps of at most 2 hours each, with files, tests,
`.agent/cmp.sh` probes, and the number each moves, written as ready-to-queue task text at the end. Mark any step that
changes language semantics as "needs owner decision" with the options.

## Sub-steps
1. (70 min) Census. Commit, push.
2. (50 min) PYREACH_NEXT.md. Commit, push.

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
