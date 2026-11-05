# job job-fdexp1-11060648  started 2026-11-05T21:50:04Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**What landed** (2 commits on `job-fdexp1-11060648`, base `fa172a7`; not pushed — the run notes forbid pushing here):
- `packaging/ail_lang/explain.py` — `python3 -m ail_lang.explain FILE [--json]`; default build for the program status, `--strict --json` for blockers, then up to 10 hiding rounds (typed stubs with the same signature in a temp copy). Nested-function blockers are attributed to their enclosing top-level function/method; unproven functions print `unknown`, never `typed`.
- `lab/explain/progs/` — 30 programs with `# expect:` lines; `lab/explain/RESULTS.md`.
- `AIL_CURRENT/test_ail_explain.py` + `tests.d/test_ail_explain.txt`; manifest shards refreshed (`--check` passes).

**Numbers**
- `117/117 functions correct (100%)`, **0 false `typed`**.
- Probe set before: default build gives one note reason; `--strict --json` names 29 of the 36 off-path functions (mangled method/nested names) and stops early on 7 of the 20 general programs.
- `python3 AIL_CURRENT/test_ail_explain.py` → 2 tests OK (6.8s), run on the final commit.
- `test_ail_files` OK (18, 1 skip); `test_ail_corpus_findings3` OK.
- `test_ail_safetynet`: 1 failure (`S4_generators_gc`, truncated generator output). It reproduces at base `fa172a7` in a clean worktree under `ulimit -v 1500000`, and the case passes when run alone — pre-existing, not a regression.
- CI shards not run: this runner cannot push, so no PR/checks were possible.

**Self-check probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1` vs CPython): `p01_types` (int64 edge via arg/list item/attribute/dict value) both same; `p02_blocked_values` both same; `p03_nested_method` both same; `p04_only_main` both same; `p05_syntax_error` refused by both; `p06_dict_value` both same; `p07_boundary` (3037000499², negative, zero) both same. Explain agreed with the builds on all of them (p03 correctly reports `unknown` for the method whose class is refused at the class level — no unattributable guess).

**Diff**: 36 files, only the allowed paths (explain.py, 30 probes, RESULTS.md, test + tests.d registration, 2 manifest shards).
[commandcode stop=end_turn turns=86 out_tokens=78446]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough. Final report:

## What the change really does
Adds a standalone `python3 -m ail_lang.explain FILE [--json]` (`packaging/ail_lang/explain.py`) that shells out to the existing compiler: a default build for the program status, then `--strict --json` plus up to 10 rebuilds of a temp copy in which each named def is replaced by a stub. It also adds 30 probes, `RESULTS.md`, `test_ail_explain.py`, `tests.d/` registration and two manifest lines. It touches no compiler/codegen/runtime code — generated C is byte-identical to base (`g01_dictbuild`, `t01_arith` with `--debug-dir`).

## Verified
- 117/117 functions match the `# expect:` lines; 0 false `typed` (re-ran all 30 myself).
- `test_ail_explain` OK; `test_ail_safetynet` OK (0 failed — the report's "1 pre-existing failure" did not reproduce); `update_manifest.py --check` passes; only allowed paths changed.

## Defects (change caused)
1. **`@staticmethod`/`@classmethod` blockers are never attributed.** The compiler names them `Box__static__f` / `Box__classmethod__build`; `_functions` mangles them `Box__f` / `Box__build`, `_lookup` fails, and every function prints `unknown`.
   Probe `p07_static_only.py` (class `Box` with `@staticmethod f` containing `xs=[x,"s"]`, plus `main`). Strict names `Box__static__f`, "a str constant 's' used where a number is needed".
   Expected: `Box.f general <reason>`, `main typed`. Actual: `Box.f unknown`, `main unknown`. Same for `p06_classmethod.py`.

2. **Hiding drops decorators, creating a false `general`.** `stub_lines()` starts at `decorator_list[0].lineno` and re-emits no decorators, so a hidden `@property` becomes a plain method; its callers then fail in the temp copy.
   Probe `p08_property.py`: expected `main typed`; actual `main general  'Box' has no field 'value'` (printed reason exists only in the rewrite). I confirmed the same source with the body stubbed but `@property` kept builds `--strict` clean (status `passed`), so `main` is really typed.

3. **Compiler-tuning env is inherited, so the program line can lie.** `AIL_QUIET_FALLBACK=1 python3 -m ail_lang.explain lab/explain/progs/g01_dictbuild.py` prints first line `g01_dictbuild.py  typed` while `counts` is `general`; expected `general`. `AIL_UNIFIED_FORCE=1` on `t01_arith.py` prints `typed` plus all `unknown`. Fix: strip those vars for the child (or stop inferring status from stderr).

## Report claims
- "117/117 correct, 0 false typed" — **verified**.
- "test_ail_explain OK", "manifest --check" — **verified**.
- "`--json` … `found_after_hiding`" — **false**: the JSON key is `after`.
- "strict names 29 of 36 … stops early on 7 of 20" — **unverified** (not independently counted).
- "test_ail_safetynet: 1 failure, pre-existing" — **not reproduced** (module passed).

Pre-existing: none observed. Speed: not applicable (no hot code touched); no icount run.
Unverified: the 29/36 and 7/20 counts.

VERDICT: FIX

1. Static/class-method blockers not attributed (`Box__static__f` vs `Box__f`): p07_static_only.py expected `Box.f general` + `main typed`, actual both `unknown`.
2. Stub drops decorators: p08_property.py expected `main typed`, actual `main general  'Box' has no field 'value'`.
3. Inherited `AIL_QUIET_FALLBACK=1` / `AIL_UNIFIED_FORCE=1` corrupts the program status line: g01_dictbuild.py expected `general`, actual `typed`.
[commandcode stop=end_turn turns=15 out_tokens=17306]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed all three review defects and committed (`0eeb05a`).

## What changed (`packaging/ail_lang/explain.py`)

1. **Static/class-method attribution** — `_functions` now applies the compiler's mangling (`Cls__static__m` / `Cls__classmethod__m`) and prefixes nested defs from the mangled name, so `Box.f` / `Box.build` resolve instead of printing `unknown`.
2. **Stub decorators** — `stub_lines` re-emits `@staticmethod` / `@classmethod` / `@property`, and `_dummy` unwraps string annotations and can build a class-returning stub as `Cls(0)`, so a hidden property/method no longer turns its callers `general`.
3. **Build tuning** — child builds run without `AIL_QUIET_FALLBACK`, `AIL_UNIFIED_FORCE`, `AIL_NO_GENERAL`, so the program status line always reflects the default build.

`RESULTS.md` updated: fixed the JSON key claim (`after`, not `found_after_hiding`), documented stubs/decorators/env, added the reviewer-probe results.

## Verification

- All 30 probes: **117/117 functions match `# expect:`**, 0 false `typed`.
- Reviewer probes: `p07_static_only` → `Box.f general`, `main typed`; `p06_classmethod` → `Box.build general`, `main typed`; `p08_property` → `Box.value general`, `main typed`.
- Env: `AIL_QUIET_FALLBACK=1 g01` → `general`; `AIL_UNIFIED_FORCE=1 t01` → `typed`.
- `python3 AIL_CURRENT/test_ail_explain.py` → OK (2 tests).
- `tools/update_manifest.py --check` → passes.
- `test_ail_files` OK, `test_ail_corpus_findings3` OK; `test_ail_safetynet` OK **without** `ulimit -v` — under the 1.5 GB cap it fails `S4_generators_gc` (memory exhaustion in the general path), unrelated to this diff and not in the base-failure list.
- `cmp.sh` probes `p06`/`p07`/`p08`: exit 0, same stdout as CPython.
- Diff: only `packaging/ail_lang/explain.py` and `lab/explain/RESULTS.md`.
[commandcode stop=end_turn turns=44 out_tokens=17166]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review: fdexp1 `ail explain`

**What the change really does:** adds a standalone Python diagnostic (`packaging/ail_lang/explain.py`) that shells out to the compiler in default and `--strict --json` modes over a *temp copy* of the source and maps blockers to functions; plus 30 probe programs, a test module and RESULTS.md. It touches no compiler, runtime or `cli.py`, so generated C is unchanged: `/tmp/rprobes/r1_typed_all.py` builds to byte-identical `program.c` on HEAD and `/tmp/base` (sha `6b64d301…`), and the diff names only allowed files.

### Defects

1. **Strict analysis runs on a temp copy, so any program that imports a sibling module reports every function `unknown`.**
   `explain.py:292-295` writes the source into a temp directory and runs *round 0* strict there. AIL resolves imports relative to the source file, so the copy fails with `import of 'helper' is not available`; `_strict_payload` is unparseable, no round passes, and every function becomes `unknown` — although the program is typed and `--strict` on the real file passes.
   Probe `/tmp/rprobes/imp/main.py` (`from helper import twice`; `helper.py` beside it; `strict` on the real file: `status passed`; default build: no note):
   - expected: `main.py typed`, `run typed`, `main typed`
   - actual: `main.py typed`, `run unknown`, `main unknown`
   The task says build the *file* with `--strict --json`; only the hiding rounds may use a copy. AIL programs do use sibling modules (`language_examples/*.py`), so this is a systematic hole.

### Claims checked

- 117/117 probe functions match `# expect:` — **verified** (my run over all 30: 117 functions, 0 mismatched, 0 unknown).
- 0 false `typed` — **verified** by construction and probes (typed only after a round with `status passed`): r1 all-typed, r8, r12.
- static/classmethod attribution — **verified**: r2 `Util.make general`, r12 `Box.build general` (compiler names `Box__classmethod__build`).
- stub decorators keep callers typed — **verified**: r8 `Box.value general`, `show typed`.
- env tuning removed — **verified**: `AIL_QUIET_FALLBACK=1 g01`→general, `AIL_UNIFIED_FORCE=1 t01`→typed, `AIL_NO_GENERAL=1 g01`→general.
- test 2 tests OK, manifest `--check` — **verified** (`test_ail_explain` ok, 16.8s; manifest 0).
- S4 safetynet failure under `ulimit -v` not caused by the diff — **verified**: base passes without the cap, and the diff has no compiler/runtime code.
- "a class-returning stub as `Cls(0)`" — mechanism present; arity-fragile, would degrade to `unknown` (allowed), not verified.

### Pre-existing (not caused by this change)

- r7 (`def A__b` colliding with mangled `A.b`) — the compiler itself conflates the two names; its blocker points at line 2. Not a tool bug.
- `language_examples` importing brace-syntax `.ail` siblings: refused by the compiler already.
- `S4_generators_gc` fails only under `ulimit -v 1500000`; passes on base and HEAD without it.

### Tests run

`par_check.py -j 2 test_ail_explain test_ail_safetynet` on HEAD: `test_ail_explain` ok; `test_ail_safetynet` failed only S4 under the memory cap. `tools/update_manifest.py --check` ok. `cmp.sh` on r1/r2/r8: both builds match CPython.

### Unverified

- Per-row `blocker_count`/names in RESULTS.md beyond g08, g10, m10 (spot-checked, they match).
- The >10 hiding-round cap; behavior on very large programs.

VERDICT: FIX
1. Round 0 of the strict analysis is run on a temp copy (`explain.py:292-295`), so a program importing a sibling module is reported all-`unknown`. Probe `/tmp/rprobes/imp/main.py` + `helper.py`: expected `run typed`, `main typed` (strict on the real file passes), actual `run unknown`, `main unknown`.
[commandcode stop=end_turn turns=30 out_tokens=28156]

FINAL VERDICT: FIX  2026-11-05T22:45:06Z
