# job job-covi64c1-11011014  started 2026-11-01T01:16:23Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `04cc3c52` on `job-covi64c1-11011014`.

- Added `AIL_CURRENT/docs/design/I64_CONSTANTS.md`: census of the 34 module constants, classified as bounds, masks, hash multipliers, sentinels, thresholds, fixtures; safe subset documented, no wrapping.
- Added `test_ail_i64_constants.py` + `tests.d` registration: refusal with `--exact-int` hint on default and general paths, safe folds/masks against CPython, exact-mode build.
- No compiler/codegen source changed, so lab/compare generated C is unchanged by construction.
- Probes (10, both builds): 3 safe probes matched CPython; 7 refusal probes stopped by name with the hint (`i64_ref_*`, `p_mask_var`, `p_hash`, `i64_exact_all`).
- Tests on final commit: `test_ail_i64_constants` (4), `test_ail_int64_default` (6), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2) — all OK.
- `python3 tools/update_manifest.py --check` exits 0.
[cost $0.0216, opencode tokens {"total": 1431895, "input": 62490, "output": 5182, "reasoning": 8447, "cache.write": 0, "cache.read": 1355776}]
    tool time: bash 8.3 min, edit 0.0 min
        177s bash   (cd AIL_CURRENT && python3 -B test_ail_safetynet.py > /tmp/f_safe.log 2>&1; echo $? > /tmp/f_safe.rc) & (cd AI
        157s bash   cd AIL_CURRENT && (python3 -B test_ail_safetynet.py > /tmp/t_safe.log 2>&1; echo $? > /tmp/t_safe.rc) & (cd AI
         50s bash   (cd AIL_CURRENT && python3 -B test_ail_int64_default.py > /tmp/f_i64.log 2>&1; echo $? > /tmp/f_i64.rc) & (cd 
         49s bash   cd AIL_CURRENT && (python3 -B test_ail_int64_default.py > /tmp/t_int64.log 2>&1; echo $? > /tmp/t_int64.rc) & 
         34s bash   (cd AIL_CURRENT && python3 -B test_ail_corpus_findings3.py > /tmp/t_corpus.log 2>&1; echo $? > /tmp/t_corpus.r
         13s bash   cd AIL_CURRENT && python3 -B test_ail_i64_constants.py 2>&1 | tail -5; cd .. && python3 tools/update_manifest.
          9s bash   cd AIL_CURRENT && timeout 1200 python3 -B test_ail_i64_constants.py -v 2>&1 | tail -40
          7s bash   mkdir -p /tmp/probes; for p in /tmp/probes/i64_*.py /tmp/probes/p_mask_const.py /tmp/probes/p_mask_var.py /tmp

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** docs + tests only. `AIL_CURRENT/docs/design/I64_CONSTANTS.md` documents the int64-constant census and the safe subset; `test_ail_i64_constants.py` (registered via `tests.d`) locks refusals, safe folds/masks and exact mode. No compiler/runtime/codegen source changed.

**Probes** (`/tmp/rprobes`, both builds via `cmp.sh`):
- `safe_folds.py`, `safe_const_mask.py`, `safe_mask_var.py`, `doc_safe_exact.py` — same stdout/exit as CPython on default and general paths (masks through argument, list item, attribute, dict value, negatives and INT64_MIN/MAX).
- `refuse_allones_var.py`, `refuse_allones_literal.py`, `refuse_augassign.py`, `refuse_values.py`, `refuse_list_item.py`, `refuse_dict_value.py`, `refuse_containers.py`, `refuse_range.py` — named compile-time refusals with the `--exact-int` hint on both paths.
- `signed_hash2.py` — signed FNV spelling builds and matches CPython.
- `notfeature.py` — `program.c` byte-identical to `/tmp/base`; `native_report.json` differs only in temp paths.

**Tests:** `test_ail_i64_constants` (4), `test_ail_int64_default` (6), `test_ail_safetynet` (5), `test_ail_files` (18), `test_ail_corpus_findings3` (2) all pass with `-j 2`; `update_manifest.py --check` exits 0. Counts match the report.

**Claim check:** census count/line numbers spot-checked (34 rows, `ail_chatgpt.py` lines 92/870/1942/4347 correct); safe/refused behaviour, test counts, manifest, no-source-change and unchanged generated C — all verified. Minor wording only: the doc's §3 table groups the signed FNV spelling with refused patterns, though the signed literal alone builds; its rationale column still explains this, so not a defect.

**Pre-existing:** none observed.
**Unverified:** full lab/compare corpus and instruction counts not run; no hot-path code changed.

VERDICT: ACCEPT
[cost $0.0200, opencode tokens {"total": 1174314, "input": 46867, "output": 5020, "reasoning": 11003, "cache.write": 0, "cache.read": 1111424}]
    tool time: bash 7.2 min, write 0.0 min
        224s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_finding
        139s bash   date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_i64_constants test_ail_safety
         53s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_int64_default 2>&1 | tail -8
         11s bash   date; for p in /tmp/rprobes/*.py; do echo "===== $p ====="; timeout 300 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 |
          3s bash   date; for p in /tmp/rprobes/doc_safe_exact.py /tmp/rprobes/refuse_allones_literal.py /tmp/rprobes/refuse_augas
          1s bash   timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/signed_hash2.py "$PWD" 2>&1 | tail -12
          1s bash   date; rm -rf /tmp/dbgH /tmp/dbgB; AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile /tmp/nf.ail --synt
          1s bash   date; for p in /tmp/rprobes/refuse_list_item.py /tmp/rprobes/refuse_dict_value.py; do echo "===== $p ====="; t

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T03:09:43Z
