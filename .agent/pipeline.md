# job job-fbnarrow1_rr1-11060751  started 2026-11-05T22:54:10Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Commit `29f8b37` on `job-fbnarrow1_rr1-11060751`; tree clean except the harness's `.agent/pipeline.md`.

**Defects fixed**
- **(1) stale (a)** — regenerated the table from `census` in `NARROW.json`: peak **292.67 MiB**, in the **sort/rebuild** path; `compact:*`/`do_prune:ir5` are **0 B** at the peak; 39 rows ≥1 MiB; `ticket_audit` 3.41, `term_rank` 27.22.
- **(2) (b) described the wrong patch** — rewritten around the committed `treefold_i32.patch`; `NARROW.json` now carries the `emulate` block (55/55 cases + perf stdout/exit identical).
- **(3)/(4) illegal `f_w` narrowing** — `w` (T field and every local) is no longer narrowed: `do_fold` accumulates `wt` into it, so no sub-int64 bound is provable. The committed patch now narrows only `dep`/`par` fields+locals and `keep`/`mp`/`ord`/`ni`/`cs`, and applies to a fresh `program.c` byte-identically (`PATCH_APPLIES_IDENTICAL`).
- **(5) done-check** — explicitly stated: 292.67/384 = **76.2%**, below the 80% bar.

**Measured on the committed patch** (`/usr/bin/time -v`, median of 3; callgrind `Ir` at N=300k — no CPU PMU, valgrind installed locally):
- peak RSS 415,468 → 379,132 KiB = **−8.75%**
- `Ir` 893,477,046 → 945,832,434 = **+5.86%**
- phases default 406.2 → 370.3 MiB; fixed 369.4 → 335.1 MiB
- verdict still **no-go** (needs ≥10% RSS, ≤+1% instructions)

**Probes / tests**
- Emulated build vs plain: all 55 public+hidden cases and the 27,859,349 B perf input matched; census tracked-vs-plain still `match: true` for 16/16 (unchanged, reviewer-reproduced).
- `test_ail_safetynet`: 1/1 ok (139 s). No test module was added or edited, so there was nothing else to run.
- `tools/update_manifest.py` and `--check` both pass; diff touches only the four `lab/mem/` files.
[commandcode stop=end_turn turns=60 out_tokens=26243]

## review 0
[model commandcode/deepseek-v4.1-flash]
Date check done (started 23:05, now 23:13). I've finished verifying. Here is my review.

## Review of fbnarrow1_rr1 (`29f8b37`, one commit, `lab/mem/` only)

**What the change really does.** It is a documentation/harness-only revision: `NARROW.md` is rewritten from the committed census JSON (peak 292.67 MiB in the sort/rebuild path), `NARROW.json` is re-nested as `{census, emulate}`, and `narrow_census.py`'s emulation no longer narrows any `w` list. No compiler/runtime/C file is touched (`git diff --stat work..HEAD` = `lab/mem` only; a probe's `--debug-dir/program.c` is md5-identical base vs HEAD).

**Probes / checks run**
- 3 AIL probes in `/tmp/rprobes/` (int32-boundary list + negative index + copy/aliasing, mutation-during-iteration + list in dict/attribute, non-feature arithmetic/tuple/dict): all `same stdout` in both the general and default builds. Generated C identical base vs HEAD (`c58a8847…` both).
- 55/55 tree_fold cases: rebuilt int32 binary (from the committed patch, regenerated `PATCH_IDENTICAL: True`) matches the plain build.
- Perf input (27,859,349 B): plain == i32 == **CPython** (`PYTHONPATH=AIL_CURRENT`, rc 0), byte-identical.
- 6 extra random trees (N=1, 2, 5k, 10k, 50k, 100k; chain 0–0.9): plain == i32, rc 0.
- Peak RSS ×3: plain 415,468, i32 379,120 KiB → **−8.75%** (JSON 379,132). callgrind Ir @300k: 893,477,060 → 945,832,389 → **+5.86%** (JSON 893,477,046 → 945,832,434). `rss_phases.py`: 406.2/369.4 vs 370.3/335.1 — all reproduce.
- `test_ail_safetynet` 1/1 ok (140.6 s). `tools/update_manifest.py --check` rc 0. `census` JSON block is **byte-identical** to the base commit's tree (verified semantically), so the earlier census verification carries over.

**Claim check.** (1) stale (a) regenerated — verified (292.67, compact/do_prune 0 B at peak, 39 rows, ticket_audit 3.41, term_rank 27.22). (2) emulate block present, 55/55 + perf identical — verified. (3)/(4) `w` no longer narrowed (`f_w`, `v_w`, `ir3`, `_sp4` all left int64) — verified. (5) 76.2% stated — verified. RSS/Ir/phases/safetynet/manifest/scope — all verified. No report claim is false.

**Defect**
1. `NARROW.md` line 109 overstates the `w` share of the peak set: "those account for **96 MiB** of the 292.67 MiB peak set". The census peak set has exactly two `w` sites: `parse_tree:(v_t)->f_w` 32.0 MiB + `rebuild:v_w` 32.0 MiB = **64.0 MiB** (`do_fold:v_w` and `compact:v_w` are 0 B at that peak). Expected 64.0 MiB, actual 96 MiB. The go/no-go decision (RSS −8.75% ≥5% stop, Ir +5.86% > +1%) is unaffected, but the sentence is the md's derived-number claim and is wrong.

**Pre-existing / not applicable.** None in program semantics (base and HEAD emit identical C). Minor tool wart (read from code, not run, since it rewrites the committed JSON): `census()` still writes the old top-level format, so `--census` alone drops the `emulate` section; the documented census→emulate order restores it. One-line doc nits: "24 B/element ≈ 72 MiB" is 68.7 MiB, and one `do_sort` key column (`v__t5`) is int32 though described as leaving int32.

**Unverified.** Full 16-program census rerun (its code is untouched and JSON byte-identical to base; I relied on the prior review's tree_fold rerun); the 20 CI shards.

VERDICT: FIX
1. `lab/mem/NARROW.md` line 109: `w` columns at the peak are **64.0 MiB**, not 96 MiB. Check: `python3 -c 'import json;d=json.load(open("lab/mem/NARROW.json"));print(sum(r["peak_bytes"] for r in d["census"]["all_measured_rows"] if r["program"]=="tree_fold" and r["peak_bytes"] and (r["label"].endswith("f_w") or r["label"].endswith("v_w")))/1048576)'` → expected `64.0`, actual md says `96 MiB`.
[commandcode stop=end_turn turns=39 out_tokens=38386]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `ac03b0a`. Summary:

**Defect fixed**
- `NARROW.md` go/no-go paragraph: the two live `w` sites (`parse_tree:(v_t)->f_w` + `rebuild:v_w`) hold **64.0 MiB** of the 292.67 MiB peak, not 96 MiB. The reviewer's check now prints `64.0`.

**Other wrong claims the review named**
- `ail_pslist` 24 B/element at 3M is **68.7 MiB**, not 72 MiB.
- The "no sub-int64 bound" sentence now names the actual overflow: one `do_sort` key column (`v__t11`, negated folded `sub`) reaches −5.3e10; `sub` is a copy of `w`, so no `w`-derived list is bounded by int32. (`v__t5` is int32 on this input.)
- `narrow_census.py`: `--census` now merges into `{census, emulate}` instead of rewriting the top-level doc and silently dropping `emulate`. Probe `MERGE_OK` confirms the emulate block is preserved byte-for-byte.

**Probes re-run**
- Committed patch applied fresh to `dbg/program.c` → `PATCH_IDENTICAL` (cmp against `program_i32.c`).
- Fresh plain vs i32 builds: **55/55** public+hidden cases match; perf input (27,859,349 B) byte-identical (22,555,652 B output, same as the reviewer-verified artifact); 3k-node case identical.

**Tests**
- `test_ail_files` ok 73.4 s, `test_ail_corpus_findings3` ok 152.5 s, `test_ail_safetynet` ok 135.1 s.
- Note: running the suite under `ulimit -v 1500000` produces a false `S4_generators_gc` failure (`AIL internal error: generator: no stack`, rc 1) unrelated to this change; unbounded, it passes. `tools/update_manifest.py` and `--check` pass.
- Diff remains `lab/mem/` only (`NARROW.md`, `narrow_census.py`); `NARROW.json` untouched.
[commandcode stop=end_turn turns=42 out_tokens=18072]

## review 1
[model commandcode/deepseek-v4.1-flash]
All checks are complete. Here's my report.

## Review of fbnarrow1 fix (`work..HEAD`, 2 commits, +2858/−2645)

**What the change really does.** It is still measurement-only (`lab/mem` only; no compiler/runtime/C change). It drops `f_w` from the int32 emulation patch, records the re-measured emulate block (RSS 415,468→379,132 KiB, Ir 893.48M→945.83M), rebuilds the (a) table/labels from the committed census (peak 292.67 MiB in sort/rebuild), states the 76.2% vs the 80% done-check, and makes `--census` preserve the `emulate` section. Matches the review's four required fixes.

**Verification I ran** (no AIL-language semantics changed, so the probes target the artifact):
- Fresh `--debug-dir` build of tree_fold: `program.c` sha256 `3f3245bd…` identical base (`/tmp/base`, 63a3a6f) vs HEAD.
- Applied the committed patch to that fresh `program.c`: result is byte-identical to `edit_i32()` output and to the worker's `emulate/program_i32.c`. Plain vs patched: 55/55 public+hidden cases match (stdout+exit); perf input (27,859,349 B) output matches the worker's `plain.out`/`i32.out` byte-for-byte (22,555,652 B).
- One `/usr/bin/time -v` run each: plain 414,944 KiB, patched 379,132 KiB (JSON: 414,944 / 379,132; delta 8.75%). Callgrind Ir reproduced: 893,476,955 vs 945,832,315 (+5.86%, JSON +5.8597%).
- `f_w`: generated patched C keeps `ail_list f_w`, `ail_list v_w`, `ail_list *ir3`; no `+` line in the patch touches `f_w`/`v_w`.
- Census facts vs `NARROW.json`: peak 292.67 MiB, 10 peak rows summing to it, `compact`/`do_prune` sites 0 B, 39 rows ≥1 MiB, ticket_audit 3.41, term_rank 27.22, berth 260.67, echo 244.14, `w` share = 2×32.0 = 64.0 MiB, pslist 24×3M = 68.7 MiB, `do_sort:v__t11` min −53,207,644,260, `v__t5` int32. All md numbers match JSON.
- `python3 tools/update_manifest.py --check` rc 0. `test_ail_safetynet` ok 139.7 s (1/1). No test module added/edited, so nothing else rerun.
- 3 probes (slice/aliasing, attr+dict list mutation, empty/sorted copy) match CPython in both default and `AIL_UNIFIED_FORCE=1`, identical on base — no regressions.

**Claim check:** fixed-commit ✓; 64.0 MiB w share ✓; 68.7 MiB pslist ✓; `v__t11`/`v__t5` statement ✓; `PATCH_IDENTICAL` ✓; 55/55 ✓; perf output 22,555,652 B ✓; "diff lab/mem only" ✓; `--census` merge logic correct by inspection (worker's `MERGE_OK` probe not on disk → that one probe unverified). The report's `test_ail_files`/`test_ail_corpus_findings3` runs are unverified by me (not required here).

**Pre-existing:** the committed patch calls `i32_free()` on three `ail_list *` locals (`do_mirror`'s `v_pos`, `do_prune`'s `v_sub`); with the project's `-Werror=incompatible-pointer-types` flags that is a compile error, but the script's own recipe passes `-w`, under which it builds and behaves identically (same struct layout; `free` only). Same lines exist in the base patch. Not caused by this change and not a semantic defect.

**Unverified:** full 16-program census rerun; the worker's `test_ail_files`/`test_ail_corpus_findings3` timings; the `MERGE_OK` probe itself.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=46 out_tokens=31511]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T00:46:17Z
