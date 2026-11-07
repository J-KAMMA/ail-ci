**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
## What the change really does

Adds `lab/vibe2/` (`STRICT_SPEC.md`, `NEW_SURFACE.md`, an AIL-N→AIL-Python translator `translate.py`, its tests, `RESULTS.md`, `results.json`) and extends `lab/vibe/run.py` with `ail-strict`/`ail-new` arms, reply-token accounting, `--programs`, per-model `Store` keys and surface-error feedback. No compiler/runtime/benchmark file is touched, so `cmp.sh`/`icount` probes do not apply. The report's one-line description matches the diff.

## Claims

- Missing deliverables added, 55 rows, 1 model × 1 seed, cut stated — **verified** (`results.json`: 55 rows, 5 arms × 11; logs 10:24–11:55; summary/ail_errors per model).
- Surface-error path fixed; `rail_transfer` recovered — **verified** (round 1 records `line 33: 'best' is a let binding…`, round 2 passes all 24 cases when rebuilt).
- `Store` keyed by `(task, lang, seed, model)`, per-model summary — **verified** (two-model probe: 2 rows, both summaries).
- Numbers in the main table — **verified** by recomputation (correct 9/7/8/6/5; 19 timeouts; tokens/correct 17365/12759/19056/22378/29452; paths 0/8/0, 2/5/0, 0/5/0; ticket_audit `random4` loud stop exit 6 vs 0 reproduced).
- Tests: `test_ail_safetynet` ok, `test_translate.py` 13/13 ok, `update_manifest.py --check` pass — **verified**; `test_ail_files`, `test_ail_corpus_findings3` not re-run per review scope — **unverified**. `tests.d` would break preflight (`registry_problems` requires `AIL_CURRENT/test_translate.py`) — **verified** by reading `ail_check.py`.
- Second model callable but not run; pre-fix crash; the `/tmp` probes — **unverified**.
- Compiler-message table/counts — **false** (below).
- Saved-program provenance — **false** for 2 rows.

## Defects

1. **`div_ceil` is wrong for a negative divisor.** `lab/vibe2/translate.py` emits `(a+b-1)//b`.
   Probe `write(str(div_ceil(5, -2)))` → generated code runs and prints `-1`; ceiling division is `-2`. Any AI solution that uses this advertised builtin with a signed divisor gets wrong arithmetic.
2. **The translator accepts constructs its own surface forbids**, so the `ail-new` arm is not the surface described in `NEW_SURFACE.md`:
   - `let s: str = rf"x{1}"` is accepted (surface: "No f-strings"); the f-string test only matches `f"`/`f'`.
   - A nested `fn` is accepted and emitted as a nested `def` (surface: "no nested function").
   - `match 3: case 0: …` with no `_` is accepted as an `if` with no `else`, and duplicate `case 0` arms are accepted (surface: "exhaustive", "`_` last only").
   Also, a top-level `let g` reassigned after an intervening `fn` is refused with `declare the binding first…` instead of the `let … cannot be reassigned` message (wrong diagnostic, still a refusal).
3. **`RESULTS.md` misreports the compiler-message table.** It says "The general-path notes (10 of 13 messages) are not errors … the two typed-path errors it saw were fixed half the time." Observed: 14 occurrences over 10 distinct messages, *all* general-path notes; three rows (Tree.weights/`unsupported`, dict-of-containers, `format()`/`refuses`) are misclassified as `error` by `compiler_messages`' substring rule, and not one is a typed-path error. The `surface 1 / 1.0` row shown in RESULTS.md is absent from `results.json`'s `ail_errors` (table truncated by `rows[:10]`).
4. **Two referenced programs do not exist.** `results.json` records `program: lab/vibe2/programs/berth_sim/ail-new-0.nw` and `…/echo_pack/ail-new-0.nw`, but neither file is in the tree, so those two "correct" `ail-new` rows cannot be checked. (The three present `.nw` files do reproduce 0 failures.)
5. Minor: `meta.started`/`completed_attempts` reflect only the last invocation (says started 11:48, 2 completed) although the 55 rows span 10:24–11:55.

Pre-existing: none applicable (no compiler/runtime change; `cmp.sh` probes not relevant).

Unverified: `test_ail_files`, `test_ail_corpus_findings3`; second-model callability; the report's `/tmp/probes/*`; the two missing `ail-new` programs; seed-to-seed spread (one seed).

VERDICT: FIX
1. `lab/vibe2/translate.py` `__div_ceil` returns `-1` for `div_ceil(5, -2)`; expected `-2` (ceiling division).
2. `translate.py` f-string check misses `rf"…"`/`fr"…"`; nested `fn` and non-exhaustive/duplicate `match` arms are accepted although `NEW_SURFACE.md` forbids them — the `ail-new` arm did not enforce its documented surface.
3. `RESULTS.md` compiler-message analysis is false: 14 occurrences, all general-path notes, three rows mislabeled `error`; the reported `surface` row is missing from `results.json` because `ail_error_table` truncates to 10.
4. `results.json` points at two nonexistent programs (`berth_sim/ail-new-0.nw`, `echo_pack/ail-new-0.nw`); commit them or clear the fields.
[commandcode stop=end_turn turns=27 out_tokens=32520]


--- ORIGINAL TASK ---
Lane: vibe

# vibe2: is Python syntax right for an AI language, or only familiar? A/B of three surfaces on the vibe1 tasks

Time budget: 240 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-07):** the owner asked whether AIL is the right language for AI, or whether Python syntax was
chosen only because models have seen a lot of it. vibe1 (`lab/vibe/RESULTS.md`) found correct-program rate Rust
100%, Python 84%, AIL 64%: the most-trained syntax was not the most correct; strict checking with feedback was. The
owner's direction (2026-11-07) is AIL as a future standard: Python surface for now, AIL's own semantics. This job
measures whether the surface itself should change. Report losses plainly; the answer may be "keep Python syntax".

**Arms** (same tasks, same harness as vibe1: reuse `lab/vibe/run.py`, extend it, do not fork it):
- `py`: CPython, prompt note "Python 3.12" (baseline, re-run so all arms share model and date).
- `rust`: rustc -O, "Rust 2021, std only" (baseline, re-run).
- `ail`: AIL on plain Python with vibe1's `lab/vibe/AIL_FOR_AI.md`.
- `ail-strict`: AIL, same syntax, but the prompt carries `lab/vibe2/STRICT_SPEC.md` (at most 80 lines you write from
  `docs/SPEC/` if present, else from docs/SEMANTICS.md and the compiler's refusals): every def and container
  annotated, no dynamic features, int64 with loud overflow, what is refused and the rewrite for each. Tests whether
  telling the model the real rules closes the gap to Rust without changing syntax.
- `ail-new`: an AI-oriented surface you design in `lab/vibe2/NEW_SURFACE.md` (at most 80 lines): explicit `let`/`var`,
  required types on every binding, exhaustive `match`, explicit error results instead of exceptions, no implicit
  conversions, one way to write each construct. It must translate mechanically to AIL Python: write
  `lab/vibe2/translate.py` (at most 400 lines, line map kept so errors point at the AI's lines) and compile the
  result with AIL. If the translator cannot be made reliable in step 1, drop this arm and say why; never hand-fix
  outputs.

**Models:** two, to see whether the gap moves with model strength (the expectation is that stronger models adapt to
a new surface from a short spec): the free model this worker runs on, and one stronger free model available to the
same CLI. Same settings for every arm; name both in RESULTS.md. No API keys or secrets; if only one model can be
called, run one and say so.

**Numbers** (`lab/vibe2/RESULTS.md`, `results.json`), per arm x model, 2 seeds (3 if time allows):
correct % (public + hidden cases), median fix rounds (max 5), silent-wrong count, loud-stop count, loop seconds,
reply tokens per correct program (cost), and for ail arms the typed/general/refused split and the AI fix rate per
compiler message. Plus: the share of `ail-new` failures caused by the surface itself (translator/syntax errors) vs
by the program logic.

**Decision table at the end** (do not decide, state what the numbers support):
- `ail-new` beats `ail-strict` by more than the seed-to-seed spread on correct % or silent-wrong -> evidence to change
  the surface.
- `ail-strict` reaches Rust's correct % -> the gap is rules and messages, not syntax; keep Python syntax.
- Neither -> list the top 3 failure causes per arm.

Base: `origin/integ`. Files you may create or edit: `lab/vibe2/*` (new) and `lab/vibe/run.py` (extend only; vibe1's
arms must still run unchanged). No compiler files, no workflows (a proposed workflow goes to `lab/vibe2/vibe2.yml`).
Do not show the AI the solutions in `lab/compare/src/`.

## Sub-steps
1. (60 min) STRICT_SPEC.md, NEW_SURFACE.md, translate.py with tests (`lab/vibe2/test_translate.py`: every construct
   in NEW_SURFACE.md round-trips to AIL Python that CPython runs identically); dry run 1 task x 5 arms x 1 seed.
   Commit, push.
2. (140 min) Full run (cut to 1 seed or 1 model if short, and say so). Commit, push after each arm.
3. (40 min) RESULTS.md: tables, per-task detail, failure causes, the decision table. Commit, push.

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
