# job job-fnvfix1-11052323  started 2026-11-05T14:24:15Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

## fnvfix1 — pyproof `wrong 2` → `wrong 0`

**What I found (step 1).** The only explicit big-int facility for Python syntax is `--exact-int` / `AIL_EXACT_INT=1`; there is no per-function or per-file marker, and `wrapping_*` is AIL-syntax-only and wraps modulo 2⁶⁴ (useless for scar_life's bitmasks). `lab/compare/run_task.py`'s `EXACT_INT_TASKS` is `('rail_transfer', 'chain_relax')` — scar_life is **not** there, so compare-lab passes it no flag.

**Fix (choice per program, in order).**
- `examples/crate/fnvhash/main.py` — (a) declared flags: the crate README and `test_ail_examples_crate.py` already declare `--exact-int`. `lab/pyproof/report.py`'s mirrored `CRATE_CASES` carried `flags: []` (unused); `_build` now passes the declared flags, and fnvhash's flag applies to the crate's `main.py` only, not `bench.py`.
- `lab/compare/src/scar_life/main.py` — (c) no declaration existed, so its first line is `# ail-build: --exact-int -- the W*H cell bitmasks are wider than int64 ...`; report.py parses the leading `-` words (everything after `--`/prose is the reason) and builds with them. Both builds use the flags.
- Docs: `docs/tutorial.md` (§4, `--exact-int`) notes these declared-flag builds.

**Numbers (full census, base work `ff1dcc2`):** typed **30**/55, general **17**, refused **8**, wrong **0**. Diffing all 55 rows against the old `results.jsonl`: only `fnvhash/main.py` wrong→typed and `scar_life/main.py` wrong→general changed; refused unchanged. The literal "typed/general unchanged" is impossible once wrong is 0 — those two rows have to join their paths.

**Verification.**
- `python3 -m compileall -q -j 0 AIL_CURRENT tools` clean; `tools/update_manifest.py --check` clean.
- Tests on final commit `379062a` (`par_check -j 2`): `test_ail_pyproof_report`, `test_ail_examples_crate`, `test_ail_tutorial`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass.
- Probes (`/tmp/probes/`, harness `run_flags.py`; flagged builds replicated report.py's exact command):
  - `p_exact_values.py` (directive; big value via argument, list item + alias, attribute, dict value, zero, negative): flagged default and forced-general both match CPython; `cmp.sh` without the flag → refused by name `int64 constant expression out of range: 9223372036854775808`.
  - `p_exact_bounds.py` (2⁶³−1, +1, −2⁶³, −1, hi*hi, `int("0",2)`, `int("1"*63,2)`): flagged builds match; unflaggged stops loudly at `+` (designed A1).
  - `p_default_stop.py` (runtime `int()` from argv length, no directive): with `--exact-int` passed explicitly, both builds match CPython; with no flag the default still stops loudly `OverflowError: integer overflow in int()`, rc 1 (unchanged default).
  - `p_no_directive_plain.py` (all in int64): `cmp.sh` matches on both builds.
  - Parser edges: prose after `--` ignored, no directive → `[]`, directive past line 5 not read.

**Caveats.** `lab/pyproof/README.md` still quotes the previous run (`wrong 2`, base `88e666c`); it is outside the files this job may edit. I did not push, per the rules.
[commandcode stop=end_turn turns=69 out_tokens=47737]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: fnvfix1 (pyproof wrong 2 → 0)

**What the change really is:** docs/lab-only. It adds a `declared_flags()` helper to `lab/pyproof/report.py` that feeds `--exact-int` to both builds for `examples/crate/fnvhash/main.py` (from the crate config) and for any program carrying a top `# ail-build:` comment; `lab/compare/src/scar_life/main.py` gains that one comment line. No compiler/runtime file is touched (verified by `git diff --name-only`), so C output for all other programs is unchanged by construction; `p_plain.py` (int64-only, argument/list/attr/dict) matches CPython on HEAD and on `/tmp/base-fnv` (`work` = ff1dcc2).

**Claims checked**
- `--exact-int` is the only big-int facility; `EXACT_INT_TASKS = ('rail_transfer','chain_relax')` excludes scar_life — verified.
- fnvhash `--exact-int` is declared by `examples/crate/README.md:41` and `test_ail_examples_crate.py:28`; flags now reach `main.py` only (`bench.py` record has `build_flags: []`) — verified.
- Both builds get the flags; scar_life output now matches CPython — verified by my own re-run (`report.py --only` the two rows: fnvhash typed, scar_life general, `stdout_equal true`, wrong 0).
- Census: typed 30/55, general 17, refused 8, wrong 0; row-by-row diff against `work` shows only those two rows changed — verified from `results.jsonl`.
- `compileall`, `update_manifest.py --check`, and the six claimed test modules (`test_ail_pyproof_report`, `test_ail_examples_crate`, `test_ail_tutorial`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) — all pass on HEAD.

**Probes** (`/tmp/rprobes`): flagged probe (`--exact-int`, big values via argument, list item, attribute, dict value) matches CPython on default and forced-general, base and HEAD; same probe without the flag is refused by name `int64 constant expression out of range` on both; directive on line 3 honoured, line 6 not; only `ranked` rows unaffected.

**Defect**
1. The new directive parser dies on ordinary prose, silently removing the row from the census while the headline still says `wrong 0`. `shlex.split` is applied to the whole directive, so an apostrophe in the reason raises `ValueError`.
Probe `/tmp/rprobes/case/prog.py` (same big-int program as above, first line):
```
# ail-build: --exact-int -- the program's masks are wider than int64
```
`python3 lab/pyproof/report.py -j 1 --programs progs.txt --out /tmp/ppout2`
Expected (identical probe with `-- masks wider than int64` gives this): `build_flags ["--exact-int"]`, result `general`, `stdout_equal true`.
Actual: `result: "not run"`, `first_reason: "harness error: ValueError('No closing quotation')"`, no `build_flags`, no stdout comparison; `RESULTS.md` prints `typed 0 / 1, general 0, refused 0, wrong 0`. So a program using the sanctioned mechanism can escape the wrong count. Fix: split the reason on `--` and tokenize the flag part with `m.group(1).split()` (or catch `ValueError`), instead of `shlex.split` over prose.

**Pre-existing:** none found (the two "wrong" programs were real pre-existing outcomes, and no probe differs from `/tmp/base-fnv` where the compiler is involved).

**Non-blocking note:** `lab/pyproof/README.md:98-102` still quotes base `88e666c` and `wrong 2`; it was outside the files this job could edit, and the worker disclosed it.

**Unverified:** the other 53 census rows were not re-run by me (sampled hello.py, fallback_demo.py, libm_math.py — consistent); speed not measured (no compiler change).

VERDICT: FIX
1. `lab/pyproof/report.py` `declared_flags()`: `shlex.split(m.group(1))` raises `ValueError: No closing quotation` when the directive's reason contains an apostrophe, turning the program into `not run` with no comparison while the headline still reports `wrong 0`. Probe `/tmp/rprobes/case/prog.py` (`# ail-build: --exact-int -- the program's masks are wider than int64`): expected `build_flags ["--exact-int"]`, result general, `stdout_equal true`; actual `not run`, `harness error: ValueError('No closing quotation')`.
[commandcode stop=end_turn turns=34 out_tokens=28385]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed. Here's the short report.

**Defect fixed**
`lab/pyproof/report.py` `declared_flags()` ran `shlex.split()` over the entire directive, so an apostrophe in the reason (`-- the program's masks ...`) raised `ValueError: No closing quotation`, making the row `not run` with no stdout comparison while the headline still said `wrong 0`. It now splits off the flag part at a whitespace `--` separator and tokenizes that with plain `.split()`; only leading `-...` words are flags, the first `--`/non-flag word ends them. Existing directives (fnvhash crate config, scar_life) parse unchanged. Added a regression test to `test_ail_pyproof_report.py` (apostrophe reason, bare `because it's ...`, flag-only).

**Probes** (`/tmp/probes`, run via `bash ~/tools/cmp.sh` and `report.py -j 1`)
- `flagged.py` (directive line 1, big values via `sys.argv`, list item, attribute, dict value): `build_flags ["--exact-int"]`, general, `stdout_equal true`.
- `case/prog.py` (same, directive on line 3, apostrophe reason — review's exact text): flags `["--exact-int"]`, general, `stdout_equal true`. Was `not run` before.
- `case6/prog.py` (directive line 6): not honoured, refused by name (`int64 constant expression out of range`).
- `plain_int64.py`: typed, stdout matches.
- `big_plain.py` (big values, no directive): refused on both builds with the int64 `OverflowError` hint.
- `flagged.py` under `AIL_EXACT_INT=1`: both builds match; without it both are refused by name.

**Target rows** (`report.py --only`): fnvhash typed, scar_life general, `stdout_equal true`, `wrong 0`. Full 55-row census not re-run; existing directives parse identically and the two changed rows were remeasured.

**Tests** (all on final content): `test_ail_pyproof_report` (6), `test_ail_examples_crate` (3), `test_ail_tutorial` (15), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2) all pass. `compileall` clean; `update_manifest.py --check` passes.

**Commit:** `0331cf4` on `job-fnvfix1-11052323`. Not pushed.
[commandcode stop=end_turn turns=23 out_tokens=13837]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does (one line):** `lab/pyproof/report.py` now builds a program with flags it declares — either the crate test config (`fnvhash` → `--exact-int`, already used by `test_ail_examples_crate.py` and the crate README) or a new top-of-file `# ail-build:` comment read from the first 5 lines — plus a one-line directive on `scar_life/main.py` and a docs note. The compiler is untouched.

**Claims checked**
- Apostrophe `ValueError` in `declared_flags` → verified: the pre-fix commit passes the whole directive to `shlex.split`; the fix splits at ` -- `; direct call returns `['--exact-int']` for both review texts.
- Existing directives parse unchanged → verified (`fnvhash` `['--exact-int']`, `bench.py` `[]`, `scar_life` `['--exact-int']`).
- wrong 2 → 0, only those two rows change → verified by diffing `results.jsonl` at `work` vs HEAD (only `fnvhash/main.py` wrong→typed and `scar_life/main.py` wrong→general; refused stays 8). `fnvhash` row re-run live: typed, `stdout_equal true`.
- "Full census not re-run [after the parser fix]" → consistent: the census was written at `7eb0efb`; the later parser change does not alter either existing directive.
- Probes, tests, `compileall`, `update_manifest --check` → verified; `test_ail_pyproof_report` and `test_ail_safetynet` pass on HEAD.

**Probes** (`/tmp/rprobes`, `report.py -j 2` / `cmp.sh`, HEAD vs base `ff1dcc2` at `/tmp/base-fnv`)
- `p1_direct_argv.py` — directive (apostrophe reason), big values via argv, list item, attribute, dict value: flags `['--exact-int']`, general, stdout equal.
- `p2_direct_small.py` — same directive, small values: general, stdout equal (flag does not perturb output).
- `p3_direct_line6.py` — directive on line 6: ignored, refused by name (`int64 constant expression out of range: 18446744073709551615`).
- `q4_plain.py` — no feature: typed, both builds match; `--debug-dir` `program.c` **byte-identical** to base (only `native_report.json` paths differ).
- `q5_alias.py` — big values, no directive: refused by name identically on HEAD and base.
- `q6_docstring.py` — a `# ail-build:` line inside a docstring is honoured (`['--exact-int']`); harmless, but the regex is not comment-syntax aware.
- Value-taking flags cannot be declared (`# ail-build: --link m` → `['--link']`, loud argparse failure). No such directive today.

**Pre-existing (identical on base):** `q5_alias.py` int64-literal refusal; big-int overflow diffs without `--exact-int`; `scar_life` strict build >120 s timeout (refused before and after).

**Non-blocking:** `lab/pyproof/README.md` (lines 102, 118–120, 131–135, 144–156) still says "wrong 2" and calls `fnvhash`/`scar_life` wrong — now stale, but that file is outside the task's allowed-edit list, so the integrator should update it.

**Speed:** change is lab tooling only; compiler/runtime untouched and `program.c` identical, so no icount run was needed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=35 out_tokens=36006]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T16:59:49Z
