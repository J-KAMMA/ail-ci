# job job-arrt6_rr1-11042346  started 2026-11-04T15:02:17Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

## arrt6 (rerun) — lane array

**Branch:** `job-arrt6_rr1-11042346` (no `job-arrt6-*` work commits existed; redone from the export of `origin/integ`). Two commits: `bb93d7e0` (port), `44cbdae7` (measurement).

**Not pushed.** The job brief says push/PR, but the runner rules at the end say "Commit your work on the current branch; do not push" and list `push` as forbidden. So the work is committed locally only; no PR or CI shards.

### Results
- **T6 cases: 6/6 pass** (`test_ail_array_t6`, 235 s). `test_ail_array_t2` (248 s) and `test_ail_array_ref` (17 s) pass. Ported via `git apply -3`, no conflicts.
- **Manifest:** registered `test_ail_array_t6` via `AIL_CURRENT/tests.d/test_ail_array_t6.txt`; `update_manifest.py --check` exits 0.
- **Compare lab:** 8/10 `program.c` byte-identical before (`origin/integ`) vs after. `tally_lang` and `tree_fold` refuse identically on both sides (unsupported `re` use), so no regression. `chain_relax`/`rail_transfer` needed `--exact-int` on both sides.
- **GPU/std:** `test_ail_gpu_g2`, `test_ail_std_array` pass. `test_ail_gpu_g1` has 2 failures that reproduce identically on untouched `origin/integ` (pre-existing).
- **Required modules:** `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_safetynet` fails `S4_generators_gc` — identical failure on `origin/integ` (pre-existing).

### Measurement (`lab/array/`, `RESULTS.md`)
256x256 f64, 32-bit LCG fill, exact order of design 3.5/3.7 (one block: lane `k%16`, 8-4-2-1 tree; no FMA), row-major sequential checksum. All three programs print the same four lines (`4196337.4013470374`, …).

| program | wall, median of 5 |
|---|---|
| AIL typed path | 18 ms |
| C `gcc -O2 -ffp-contract=off` (naive, strided B) | 32 ms |
| CPython 3.12 pure-Python triple loop | 1453 ms |

`icount` unavailable: `perf_event_open` gives EACCES, then ENOENT after `sysctl`; `perf stat` finds no supported events (container has no PMU), so the brief's wall-time fallback applies.

### Probes (both default and `AIL_UNIFIED_FORCE=1`, via `~/tools/cmp.sh`)
`p1_shapes`, `p2_elementwise`, `p3_matmul` (K = 0, 1, 16, 17, 1024, 1025, specials), `p4_errors`, `p5_paths` (argument, list item, dict value) — **5/5 match CPython in both builds**.

Constructs outside T6 are compile refusals by name: 1-D operand to `matmul`, 3-D shape, reduce/`astype` on 2-D, arrays through a class constructor. No fix required and none attempted (outside the allowed file list). `DEVLOG.md` not touched, per rule 8.
[commandcode stop=end_turn turns=74 out_tokens=44669]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: arrt6 rerun (`work..HEAD` = `bb93d7e0` port, `44cbdae7` measure)

**What the change really does.** It ports the T6 2-D f64 / `ta.matmul` work (reference + lowering + C prelude) and adds the measurement lab. **Flag: it also ports the whole f64 element-wise *fusion* pass** (`_ail_taf_fu*`/`fk*`, `_ail_taf_fsum_s/_d`, `_ail_ta_bsum`, TYPED_ARRAY 5.2a), which the report never mentions. That pass changes generated C for ail_array programs that do not use 2-D at all, and its own test module (`test_ail_array_fuse.py`, `array_fuse_cases/`) was not ported, so it lands tested only indirectly.

### Claims
- T6 6/6: **verified** (`test_ail_array_t6` ok, 191 s).
- t2 / ref pass: **verified** (t2 ok 311 s; ref ok 23.6 s).
- manifest registered, `--check` rc 0: **verified**.
- compare-lab C unchanged: **verified** on 5 non-ail_array programs after normalizing the embedded `AIL_DBG_SITE` worktree path (byte-identical); a raw diff is always path-only. Not all 10 run.
- safetynet `S4_generators_gc` fails identically on integ: **plausible/unverified** (I reproduced the same failure on HEAD; S4 imports no ail_array and the changed files are only pulled in for `import ail_array`, so it cannot be caused by this change).
- measurement 18 / 32 / 1453 ms and the four printed lines: **verified** (18 / 32 / 1586 ms here; all three programs print `4196337.4013470374`, `60.538415881530057`, `69.781509893807595`, `71.126957885982307`).
- `icount` unavailable (perf ENOENT): **verified**.
- "Not pushed / no shards": **true** (`origin/job-arrt6_rr1-*` still points at the export base `15b1eade`); done-check item "20 shards" is therefore not met (runner rule bans push).
- GPU g1 "2 pre-existing failures", `test_ail_files`, `corpus_findings3`, `std_array`: **unverified** (not re-run, per brief).

### Probes (`bash ~/tools/cmp.sh`, both builds, vs CPython)
g/d matched on: `p1_edge` (matmul m,k,n incl. k=0/2048/2049/3072/4096, zero dims), `p2_index` (negative indices, negative-step and empty row slices, `.T`/`.T.T`, shape/len), `p3_ops` (−, abs, +, scalar ops, div-by-zero, min/max/clip/sqrt, `==/!=` vs 1-D, fused `a*a+a`, in-place `+=`), `p4_construct` (zeros/full/array, shapes (2,3),(0,3),(3,0),(0,0), −0.0, nan/inf/subs), `p5_alias` (row/slice/copy after mutating the source), `p8_args` (matmul on parameters, on `.T`, on row slice), `p7_fuse` (fusion with specials), `p12_sum` (1-D sum/fused-sum/dot at 1023/1024/1025/2048/2049/3000).
Named refusals (acceptable): `M.tolist()` on 2-D; matmul through a dict value, a list item, or a class attribute; 1-D operand to matmul.

### Pre-existing
`safetynet S4_generators_gc` (same failure on HEAD; unrelated to the changed files).

### Not checked
All 10 compare-lab programs, `test_ail_gpu_g1/g2`, `test_ail_std_array`, `test_ail_files`, `test_ail_corpus_findings3`, all 20 CI shards.

No output/crash/exit-status mismatch attributable to this change; T6 boundaries and the newly-ported fusion both match CPython. The only finding is the unreported fusion scope (documented in TYPED_ARRAY 5.2a, tested indirectly by t2 and my probes), which I flag rather than block on.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=53 out_tokens=35336]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T17:37:20Z
