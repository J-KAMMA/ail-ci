# job job-errux1-11050123  started 2026-11-04T16:23:59Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

## errux1 — refusal corpus and ratchet

**Corpus:** 40 programs in `lab/errux/progs/`, one distinct message each. **Baseline total: 117/160.** `lab/errux/baseline.json` records all 40 scores.

**Scoring health**
- 40/40 clean refusal status (only exits 2 and 3; no C errors, no tracebacks)
- 32/40 name `<file>.py:N:`; the 8 that don't are the follow-up list
- 40/40 name the construct; 5/40 contain a hint word
- Note: `29_tabs_and_spaces` gets the hint point only because "use" appears inside "inconsistent use of tabs and spaces" — a false positive of the string rule, documented in RESULTS.md

**Gate:** `AIL_CURRENT/test_ail_errux.py` passes in ~6 s (2 tests). It imports `lab/errux/score.py` by path, runs the baseline check, and asserts no stderr has `Traceback (most recent call last)` or `program.c:` + gcc `error: `. Registered via `AIL_CURRENT/tests.d/test_ail_errux.txt`; manifest refreshed, `--check` exits 0.

**Required tests on final commit:** `test_ail_errux` OK, `test_ail_files` OK (1 skip), `test_ail_corpus_findings3` OK, `test_ail_beginner_errors` OK. `test_ail_safetynet` has one failure, `S4_generators_gc` (deterministic, general-path generator output missing); I reproduced it identically on base `c91e0a0`, so it is pre-existing and unrelated to these new files.

**Findings recorded, not fixed:** `return` outside a function, `break` outside a loop, and `def f(a, a)` each leak a raw C compiler error (exit 4). No Python traceback appeared, so the stop rule was not triggered; they are listed in RESULTS.md and excluded from the corpus.

**Scope:** `git diff --stat c91e0a0` shows only the 40 programs, `score.py`, `baseline.json`, `RESULTS.md`, the test module, its `tests.d` file, and the two manifest shard pins written by `tools/update_manifest.py`. No compiler file touched.

**Not pushed / no PR / shards not run:** the runner instruction says commit on the current branch and do not push, and this clone has no `origin/integ` ref (only the job branch), so CI shards could not be started. Three commits are on `job-errux1-11050123`, head `74e9c19`.
[commandcode stop=end_turn turns=33 out_tokens=33796]

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** adds a 40-program refusal corpus (`lab/errux/progs/`), a scorer (`score.py`, baseline 117/160), `RESULTS.md`, and a ratchet test (`test_ail_errux.py` + `tests.d` line + manifest pins). No compiler/runtime file is touched.

**Verification (HEAD 74e9c19 vs base c91e0a0)**

- `score.py --check`: passes, total **117/160**, statuses only {2,3}, 32/40 location, 40/40 names, 5/40 hint, 0 builds — all report numbers verified.
- Gate logic exercised with fabricated results: lower score → named failure; `builds now` + CPython rejects → failure; builds + CPython accepts → pass. Correct.
- `test_ail_errux` **ok** (7.4 s); `test_ail_safetynet` **ok** (0 failed). `tools/update_manifest.py --check` exits 0.
- `--debug-dir` C for a normal program is byte-identical base vs HEAD (no compiler code changed).
- Probes p1–p5 (return/break/dup-param/yield outside, None attribute): identical on base and HEAD. The reported exit-4 C leaks reproduce (p6, p7, p8) and are pre-existing. `x = None; print(x.value)` builds and matches CPython.
- Report claims: all verified except "test_ail_safetynet has one failure, S4_generators_gc" — **false**, it passes here.

**Defects**

1. The `# line:` header is wrong in all 8 location-less programs, i.e. the field the scorer's location rule depends on. Expected the blamed line; actual:
   - 33: header 2, construct at 4 (`for` in class body)
   - 34: header 3 (`class A`), offending `class B(A + 1)` at 5
   - 35: header 2 (`# names:` comment), `s.encode(...)` at 4
   - 36: header 3 (`import`), `def gen`/`yield` at 4/5
   - 37: header 1 (`# line:` comment), `def f(*, a)` at 3
   - 38: header 5 (`class B`), `class C(A, B)` at 7
   - 39: header 3 (`a = ()`), `print(a is b)` at 5 (its own message says line 5)
   - 40: header 1 (`# line:` comment), `yield 1` at 3
   Because rule 2 compares against this header, a correct future location fix (e.g. `34_...py:5:`) would score no higher than the baseline, so the ratchet cannot register the improvement it is meant to drive.
2. `40_yield_outside_function.py` uses `# names: not a Python expression`, the generic parser preface, not the construct. It earns the rule-3 point for boilerplate rather than for naming `yield`/outside-function.

**Pre-existing (not blocking):** the three raw C leaks in RESULTS.md's "Findings" are real on base too (exit 4, `program.c: ... error:`), and 33/34/40's blame lines are cosmetically off as above.

**Not checked:** `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_beginner_errors` (per instructions), CI shards (not pushed), speed (no hot code touched).

VERDICT: FIX
1. Correct the `# line:` values in 33, 34, 35, 36, 37, 38, 39, 40 (expected the construct's line 4/5/4/4/3/7/5/3 respectively; actual 2/3/2/3/1/5/3/1), otherwise the location ratchet cannot reward a correct location fix.
2. In `40_yield_outside_function.py`, replace `# names: not a Python expression` with a substring naming the construct (e.g. `yield outside function`), which currently fails to appear in the message and would then expose the real gap instead of scoring boilerplate.
[commandcode stop=end_turn turns=18 out_tokens=19494]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Both defects are fixed and committed as `8f3bf37`.

**Fixes**
- Corrected `# line:` in the 8 location-less programs, verified each now points at its construct: 33→4, 34→5, 35→4, 36→4, 37→3, 38→7, 39→5, 40→3.
- `40_yield_outside_function.py` now uses `# names: yield outside function` instead of the parser preface.

**Verification**
- `score.py --check`: passes; total **116/160** (was 117). Program 40 correctly drops 2→1; 33–39 stay at 2, but their corrected headers now let a future location fix score above baseline. Baseline and `RESULTS.md` (table, totals, reordered follow-ups) refreshed.
- `test_ail_errux` **OK** (2 tests, 9.0 s); `test_ail_files` **OK** (1 skip); `test_ail_corpus_findings3` **OK** (2 tests); `test_ail_safetynet` **OK** (5 tests) when run without the address-space cap.
- Note: under `ulimit -v 1500000`, `S4_generators_gc` fails (truncated stdout); the same subtest passes uncapped. This is pre-existing and environmental (generator stacks need >=1.5 GB virtual space), not caused by this change — no compiler file is touched.
- `tools/update_manifest.py --check` exits 0. `git diff c91e0a0` contains only the allowed files.

Not pushed, per the runner instruction.
[commandcode stop=end_turn turns=22 out_tokens=12447]

## review 1
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Here is my review.

**What the change really does (one line).** Adds a 40-program refusal corpus under `lab/errux/`, a scorer/ratchet (`score.py`, `baseline.json`), `RESULTS.md`, and a registered test (`AIL_CURRENT/test_ail_errux.py` + `tests.d` + the two manifest shard lines); the final commit only repoints `# line:` for 33–40 at the construct (4,5,4,4,3,7,5,3) and changes 40's `# names:` from the parser preface to `yield outside function`, which drops 40 from 2→1 and the total 117→116. No compiler/runtime file is touched.

**Probes (all in `/tmp/rprobes/`).**
- Scorer on HEAD: total **116/160**, every score equals its baseline, `--check` exits 0.
- Ratchet logic (`ratchet_probe.py`): below-baseline → names the program; equal → passes; missing/no baseline → fails; `builds now` + CPython rejects → fails; `builds now` + CPython accepts → passes. CLI `--check` against a raised baseline exits 1 and names all 40.
- Rule boundaries: location needs exact `<prog>.py:N:` (rejects `140_...py:3:` and `...:33:` for N=3), names are matched case-insensitively, hint words are the five listed, status 2/3 earns the clean point.
- RESULTS table vs a fresh scorer run (`table_check.py`): **40/40 rows** match score, exit, and the 160-char trimmed line; all **40 CPython verdicts** match `python3`.
- `cmp.sh` on 33–40: each is a named refusal on both the general path and the default build, no traceback/C text; CPython verdicts match the table (34 and 40 reject, 33/35–39 accept).
- "Findings not in the corpus" reproduced: `return` outside function → exit 4 with `program.c … undeclared`; `break` outside loop → exit 4; duplicate parameter → exit 4; `None.value` builds (exit 0).
- Tests (`par_check.py -j 2` on HEAD): `test_ail_errux` **9.4s OK**, `test_ail_safetynet` **175.6s OK**; direct `test_ail_errux.py` = 2 tests OK; `update_manifest.py --check` = 0.
- `git diff --name-only work..HEAD` is only the allowed files (`lab/errux/*`, the test, `tests.d`, two manifest shards), so unrelated C output is unchanged and no speed check applies.

**Claim check.** Every claim in the worker report verified (fix commit contents, line numbers 33→4 … 40→3, 40 2→1, total 116, tests, manifest, `c91e0a0` = `work`, only-allowed files), except `test_ail_files` / `test_ail_corpus_findings3` (not re-run, per instructions) and the `ulimit`/`S4_generators_gc` environmental note (not reproduced; no compiler file changed, so pre-existing by construction).

**Minor, non-blocking documentation notes.**
- `RESULTS.md` follow-up #1 says CPython rejects program 40 "at run time". Observed: it is a **compile-time** `SyntaxError` (`compile('yield 1')` raises; a preceding `print` never runs). The table's "rejects" is correct, and the gate is unaffected.
- `RESULTS.md` still says `corpus commit: b228f88`, which predates the corrected headers and the 116 baseline; the recorded table is not reproducible from that commit.
- Hint false positives 10/11/12 (`rename` inside the `Built:` list) are not disclosed the way 29's `use ` is.

**Pre-existing.** AIL refuses 33 and 35–39 while CPython accepts them, and program 17's CPython verdict depends on `/tmp/errux_x.txt` being absent; both are corpus recordings of existing compiler behaviour, not effects of this change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=21 out_tokens=48299]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T18:34:21Z
