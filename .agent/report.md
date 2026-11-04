# job job-guide1-11041926  started 2026-11-04T10:27:08Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
All checks pass and the work is committed. Final state verified.

## Report

**Review:** skipped ("only 11 minutes left"), so no named defects. I verified the current code against the task's own done-check and probed the guide's claims.

**Verified as already done (not redone):**
- 43 samples, unique names, per chapter 13 / 10 / 10 / 10.
- `python3 -B AIL_CURRENT/test_ail_guide.py` → 45 tests OK, prints `guide samples: 43`.
- `test_ail_safetynet` → 5 tests OK (re-run on final tree).
- `test_ail_files` → 18 tests OK (1 skipped); `test_ail_corpus_findings3` → 2 tests OK.
- `tools/update_manifest.py` + `--check` → OK; `tests.d/test_ail_guide.txt` registered.

**Defects found and fixed** (commit `e711c438`):
- `01-typed-and-general.md`: claimed "integers are exact" under `--exact-int`. Probe `x9` shows a value passed through several annotated call sites still stops with `OverflowError: integer overflow in a conversion to int64`. I narrowed the text to a big `int` local plus arithmetic and extended the `c1_exact` sample (`big + 1`) so the claim is shown.
- `02-text-bytes-files.md`: stdin paragraph now says the newline is kept and that the sample trims it with `strip` (probe `n1` matches CPython in both builds).
- `03-errors-and-exit.md`: "catches every kind" → "catches the built-in error kinds", matching the sample (probe `q12`).

**Probes** (`/tmp/probes`, run via `bash ~/tools/cmp.sh`):
- `q1_bounds` — int64 max/min, floor div/mod: same stdout both builds.
- `q3`–`q8` (add, min−1, ×2, unary −, `min // −1`, through list item/dict value/field): loud `OverflowError`, exit 1, both builds; expected since the value cannot be computed in int64.
- `q9_text`, `q10_errors`, `q11_general`, `q12_catch_all` — same stdout as CPython in both builds.
- `x1`–`x9` exact-int characterization; `AIL_EXACT_INT=1` build verified against CPython.
- Known compiler limitation (unmodified, not silent): `--exact-int` still stops loudly when a value crosses multiple annotated call sites (`x9`); the guide no longer overclaims it.

**Commit:** `e711c438` on `job-guide1-11041926` (3 doc files). Working tree clean except the untracked pipeline note.
[commandcode stop=end_turn turns=35 out_tokens=20771]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review

**What the change really does:** docs-only. It tightens three prose claims in `docs/guide/01/02/03` (exact-int scope, stdin newline/strip, `except Exception`) and extends the `c1_exact` sample with `big: int = 9223372036854775808; print(big + 1)`. No compiler/runtime/test file is touched, so `--debug-dir` C is unchanged by construction (only these three `.md` files are in `work..HEAD`).

**Report claims**
- 43 samples, 13/10/10/10 per chapter, unique names: **verified** (`grep -c`, Structure test).
- Guide test 45 tests OK, prints `guide samples: 43`: **verified**.
- `update_manifest.py --check`, `tests.d/test_ail_guide.txt`: **verified** (exit 0).
- Three doc defects fixed as described: **verified** by diff; new claims hold under probes.
- `test_ail_safetynet` 5 OK: **verified without a memory cap**; under `ulimit -v 1500000` `S4_generators_gc` fails identically on base — pre-existing/resource, not this change.
- `x9` "exact-int still stops through several annotated call sites": **not reproduced** (e4/e8 matched CPython); no effect on the narrowed text. `test_ail_files`/`test_ail_corpus_findings3`: **unverified** (out of review scope).

**Probes** (`/tmp/rprobes`, `cmp.sh` or `--exact-int`/`AIL_EXACT_INT=1` vs `python3`)
- `e1_local`, `e5_arith`, `e6_loop`, `e9_ops`: big literal/local, all ops incl. `// % ** << >> / ~`, exact build — same stdout/exit.
- `e12_textops` (big value from `sys.argv`, typed path, no note), `e13_containers` (list item, dict value), `e7/e8`: same stdout/exit.
- `e2/e3` default build: named compile-time refusal (`int64 literal out of range ... --exact-int`), acceptable.
- `x1_except`: RuntimeError/ValueError/KeyError/ZeroDivisionError caught and printed as CPython; only the deliberate int64 overflow case stops (pre-existing loud stop).
- `i1_stdin` (last line without newline): same stdout in both builds.
- `AIL_EXACT_INT=1` produces the same bytes as `--exact-int`.

**Pre-existing:** `S4_generators_gc` under `ulimit -v 1500000` truncates at the first line (exit 1) on both HEAD and `/tmp/base`; passes without the cap.

No defect found in this change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=50 out_tokens=25575]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T12:16:13Z
