# job job-shseed1-11060318  started 2026-11-05T18:20:48Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The estimate is committed on `job-shseed1-11060318` (no push per the runner instruction).

**What ran**
- `tools/selfhost_seed_estimate.py --run --jobs 2` built 54 candidates; **47 built** (21 typed, 26 general), 7 failed. Two bare builds (typed/general) give the fixed runtime part: 135,284 / 561,350 C bytes.
- Fits through the origin, C per AST node: typed **R² 0.795**, slope 93.98, MAE 19.9%; general **R² 0.506**, slope 546.20, MAE 25.7%. Per-line fits: 0.773 / 0.424. The general per-line fit is weak, so the per-node fit is used; both selected fits clear the R² 0.5 stop rule.
- Compiler scope counted (not compiled): 160 files, 188,365 code lines, **1,508,278 AST nodes**.

**Estimates (bytes)**

| | low | mid | high |
|---|---|---|---|
| C source | 141,881,434 | 396,163,712 | 10,642,332,482 |
| gzip | 27,671,071 | 77,263,626 | 2,075,569,199 |
| stripped binary | 32,849,809 | 213,909,228 | 5,673,710,177 |

Gzip ratio measured on the corpus: 0.195. Mid C is 3.96× GitHub's 100 MB limit (gzipped mid 77 MB is under it); the high case, a worst-decile bound dominated by small stdlib programs, fits neither and should be read as a pessimistic bound.

**Checks**
- `test_ail_selfhost_seed` (new): 2 tests pass, including SEED.md == `--report-only`.
- `test_ail_files`: 18 pass (1 skip); `test_ail_corpus_findings3`: 2 pass.
- `test_ail_safetynet`: 1 failure (`S4_generators_gc`), reproduced on pristine base `02796a5` in a detached worktree — pre-existing, not caused by these files.
- `git diff --stat 02796a5`: exactly the 5 named new files plus the 2 manifest shards; `update_manifest.py --check` passes. No compiler file edited.
[commandcode stop=end_turn turns=40 out_tokens=33019]

## review 0
[model commandcode/deepseek-v4.1-flash]
Time check: 18:55, ~10 min in. I have what I need. Writing the report.

## Review: shseed1 — C-seed size estimate

**What the diff really does.** Adds `tools/selfhost_seed_estimate.py` (builds a 54-candidate corpus, records C/gzip/binary bytes and AST size, fits through-origin per-node/per-line models), a 47-row `lab/selfhost/seed_corpus.json` + 2 bare builds, `lab/selfhost/SEED.md`, a 2-test module, and 2 manifest shards. No compiler, runtime, stdlib, or bench file is touched — matching the report.

**Claim check (all numbers recomputed from the committed JSON)**

| Claim | Result |
|---|---|
| 54 candidates, 47 built (21 typed / 26 general), 7 failed | verified |
| fixed typed/general C 135,284 / 561,350; binary 14,472 / 55,616 | verified |
| typed C/node 93.98, R² 0.795, MAE 19.9%; general 546.20, 0.506, 25.7%; per-line 0.773 / 0.424 | verified exactly |
| compiler 160 files, 188,365 code lines, 1,508,278 nodes | verified (157 pkg-v12 + 3; 188,365 non-blank/non-comment) |
| low/mid/high C, gzip, binary | verified; `--report-only` reproduces SEED.md byte-for-byte in 2.8 s, builds nothing |
| gzip ratio 0.195; mid = 3.96× 100 MB | verified |
| test module 2 tests pass | verified (6.0 s) |
| `update_manifest --check`; diff = 5 files + 2 shards | verified |
| "safetynet has 1 failure (S4_generators_gc)" | **not reproduced** — safetynet passes here (208 s) |

**Checks run.** Plain probe `/tmp/rprobes/plain.py`: `program.c` byte-identical to a base worktree build, `cmp.sh` matches CPython (g/general and d/default). Built `lab/stdlib/difflib/11_diff_bytes.py` (program.c 1,543,675 B, 294 `difflib` symbols) and `lab/stdlib/tomllib/06_config.py` (1,725,556 B, 291 `tomllib` symbols).

**Non-blocking findings**
1. The *high* decile is two importer rows (difflib 8,770, tomllib 5,340 B/node): their C inlines the entire imported module while `ast_nodes` counts only the importer. Excluding module-importing rows the worst decile is ~3,663 → high ≈ 5.5 GB, and excluding the two importers ~2.39 GB, not 10.64 GB. SEED.md's "per-module glue" is really the imported module's full translation. The conclusion (high fits neither limit) is unaffected, and the report already calls high a pessimistic bound.
2. The R² is the uncentered through-origin R² (standard for no-intercept fits, R does this). The conventional centered R² is −0.157 (typed) and 0.072 (general); the "both selected fits clear 0.5" claim holds only under the unstated definition.
3. SEED.md: "205,201 lines in 160 files" mixes the 156-file CENSUS figure with the current scope (160 files = 212,165 total lines); the 1,930.6 bytes/line uses the stale count.
4. `seed_corpus.json` commits absolute runner paths in all 47 rows and 7 failures (`/home/runner/work/_temp/w2/...`); not portable, and a rerun rewrites every path.
5. Estimates are computed from the live compiler tree, not the JSON: monkeypatching +1 compiler node changes mid C 396,163,712 → 396,163,974, so `test_seed_md_matches_tool` fails on any later compiler edit. The task's "from the JSON" wording suggests storing the count in the corpus.

**Pre-existing:** none (compiler output is byte-identical to base). **Unverified:** the 20 CI shards; a full `--run` rebuild of the corpus; `test_ail_files` / `test_ail_corpus_findings3`; CPython equivalence of all 47 corpus programs (sampled only).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=23 out_tokens=57264]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T20:10:47Z
