**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
Time's up on probes; I'm writing the report from what I verified.

## What the change really does

`pyfunc.py`: adds alias/forward analysis over `a = b` assignments so the row-arity refusal (`AIL0102`) names the user's variable and its heaps, points `source_line` at the first pop, and refuses only by names the user wrote (`_ail_*` never printed); also stops the `_ail_l1r = X[0]` companion temp from widening a heap capture. `ail_chatgpt.py`: records `_PRELUDE_UNITS` for every Python-syntax entry (not just `.py`), and in `_fallback_notes` remaps a note whose position is past the user's file and whose reason names a shipped-prelude definition to the user's call, appending `(this note comes from the standard library's <module> module)`. Tests/DEVLOG/DIFFERENCES/RESULTS updated. This matches the report's description.

## Verified

- Trigger `02_poprow_arity.py`: `note: p.py:78:13 ... 'entry' is bound from popping rows of different widths: 'departures', 'wait1', 'wait2', 'wait3'` — no `_ail_l1l`, position is the real first pop site (line 78, col 13). Base: `_ail_l1l ... 1 fields ... 5` with no position.
- `--json` AIL0102 `fix` `{replace_range:[78,79], with: entry_departures...}`; applying it rebuilds, removes the note, and prints the same output (verified by hand, not only by test).
- `fractions`/`decimal` notes: `pre_frac_float`, `pre_frac_neg`, `pre_frac_attr` → line 3/8 with module note; `pre_dec_fmt`, `pre_dec_dict`, `pre_dec_list` → line 3/4 with module note. Base said `:235:5` / `:1687:1` with no module.
- All 18 probes match CPython on both builds (`cmp.sh`); heap programs `row_bigger`, `row_one_heap`, `nofeature`, `pre_frac_float` produce **byte-identical `--debug-dir` `program.c`** to base.
- `test_ail_pre133` + `test_ail_agent_errors` run directly: 15 tests, OK (821 s). (Ran directly because `par_check` cannot start — see defect 1.)
- `tools/update_manifest.py --check`: **fails** (rc=1, "stale ail_chatgpt.py", "stale python/pkg-v12/pyfunc.py"); `par_check.py` dies in preflight: `ValueError: hash mismatch: ail_chatgpt.py`. Commit `c7a4a9d` edited both files after the manifest hashes were written.

## Defects

1. **Stale manifest breaks the required test path / CI.** `python3 tools/update_manifest.py --check` → exit 1, `stale ail_chatgpt.py`, `stale python/pkg-v12/pyfunc.py`; `python3 tools/par_check.py -j 2 test_ail_pre133 test_ail_agent_errors ...` → `ValueError: hash mismatch: ail_chatgpt.py` before any test runs. The report's "update_manifest and --check pass" and "5/5 modules, 0 failed" are therefore **false**.
2. **Prelude note points at the wrong user line when more than one candidate call exists** (`_prelude_call_site` returns the *last* regex match, not the failing one).
   - `/tmp/rprobes/pre_frac_wrongline.py` (fail is `float(a)` on line 3; `print(float(3))` on line 4): expected `p.py:3:7`, actual `note: p.py:4:7` — editing line 4 does not remove the note.
   - `/tmp/rprobes/pre_dec_last_fstr.py` (fail is `f"{d:.1f}"` line 3; `f"{1.5:.1f}"` line 4): expected line 3, actual `note: p.py:4:7`.
3. **Task-scope gap (unchanged from base): a prelude note whose reason does not contain the unit name is still reported at a prelude line.** `/tmp/rprobes/pre_dec_plain.py` (`d = Decimal("2.5"); print(d + d)`): expected the user's call line 3 plus the decimal module note; actual `note: p.py:318:9: ... parameter 'bn' of _dec_cmp_parts() ...`, no module note — line 318 is prelude code, exactly what rule 1 of `docs/design/AGENT_ERRORS.md` forbids. Base prints the same line, so this is an incomplete implementation rather than a regression.

## Unverified

- `test_ail_safetynet` (could not be started: preflight hash failure).
- fix-rate numbers (1.00 / 0.00) — requires model runs; not reproducible here.
- compile-time cost / `icount` of gdev programs: the change is compile-time only (no runtime/C diff seen), so I did not measure.

VERDICT: FIX
1. Stale `MANIFEST.json`/`manifest.d` hashes for `ail_chatgpt.py` and `python/pkg-v12/pyfunc.py`: `update_manifest.py --check` exits 1 and `par_check.py` aborts with `ValueError: hash mismatch: ail_chatgpt.py`, so no required test module can run. Re-run `git add` + `tools/update_manifest.py` on the final commit.
2. `_prelude_call_site` selects the last matching call, not the failing one: `pre_frac_wrongline.py` expected `p.py:3:7` (got `p.py:4:7`), `pre_dec_last_fstr.py` expected line 3 (got line 4). The note then points at a statement that does not need to change.
3. `pre_dec_plain.py` (Decimal arithmetic) still reports `p.py:318:9 ... _dec_cmp_parts() ...` with no module note; expected the user's call line 3 and `standard library's decimal module` (same as base, but required by the task).
[commandcode stop=end_turn turns=61 out_tokens=30535]


--- ORIGINAL TASK ---
Lane: err
Needs: err2

# err3: compiler-side dead ends: no `_ail_l1l` names, prelude positions mapped to the user's call site

Time budget: 120 minutes. Commit and push after each sub-step. Follow `.agent/` rules (no regressions, CI first).

**Why (owner, 2026-11-07):** AIL is for vibe coding; vibe1 found AI fix rate ~0 after AIL errors. err1 measured and
designed the fix: `docs/design/AGENT_ERRORS.md` and `lab/err/*` (on integ; if missing, `git fetch origin
job-err1-11071624` and read them from that branch). Rewritten messages raised the fix rate 0.75 -> 0.92 on the
15-message set. This job is **Step 2** of that design's "Implementation split"; read the whole section first.
Rules from the design: position is in the user's file, cause names only the user's identifiers (never `_ail_*`),
`Replace:`/`With:` is a literal edit that builds on the typed path and keeps output. Never change what a program
prints; a message rewrite must not turn a building program into a refusal.

## Do
- `AIL_CURRENT/python/pkg-v12/pyfunc.py`: the heapq/heap row capture; name the user's variables and point at both
  pop sites instead of `_ail_l1l`.
- `AIL_CURRENT/ail_chatgpt.py` `_fallback_notes`: a refusal inside a prelude (fractions, decimal, ...) points at the
  user's call site and says which module the note comes from.
- Tests: extend `test_ail_pre133.py` and `test_ail_agent_errors.py` (from err2; if err2 is not merged yet, create the
  module with only your cases).
- Re-run `lab/err/measure.py` for messages 02 and 11; record rates in `lab/err/RESULTS.md`. Target 02 >= 0.60.

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
