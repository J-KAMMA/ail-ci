# job job-bces2c-11042316  started 2026-11-04T14:18:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Everything is committed and verified. Final summary:

## Report

**What I did:** The lost `job-bces2-11040407` work was not on `origin/integ`, so I cherry-picked its three work commits (`b87dccc`, `ab67edd`, `fdc2b75`) onto the current integ export and finished/validated them.

**Adaptations needed on integ**
- Preserved integ's current trip message `"maximum recursion depth exceeded"` (the old branch base said `"recursion depth exceeded"`).
- Closed a soundness hole in eligibility: non-`Name` (method/computed) calls are now treated as unresolved callees and keep the global counter, so a recursive method cannot bypass rule 3.
- Fixed the probe harness for integ's newer runtime diagnostics (oracle now reuses the head source name; `_last_line` skips `raised near`; accepts `IndexError: bytes ...`).
- Fixed `bce_census.check` to build the base from the head tree's source path (all builds embed the absolute source path in `AIL_DBG_SITE`; otherwise every task differs and binary size carries the path length) and to treat identical base/head build failures as pre-existing, not regressions.

**Numbers (callgrind; perf_event denied on the runner)**
- `tally_lang/ail`: 29,542,790,615 → 26,575,248,821 instructions, **ratio 0.89955 (10.05% drop)**, output identical.
- Stripped binary **88,280 → 88,280 bytes** (unchanged); executable 95,088 → 95,120 (+0.03%, allowed under the owner rule with a ≥1% icount drop).
- `bce_census.py check --base /tmp/base`: **exit 0**. All 17 other task/syntax pairs `same C`; `tally_lang/python` and `tree_fold/python` fail identically in both trees (pre-existing).
- Codegen pins: 5/5 hashes unchanged.
- Compile phases (tally, median of 5): gcc 0.96 vs 0.96 s, total 0.09 vs 0.09 (within 3%).

**Tests:** `test_ail_bce`, `test_ail_ir_s1/s2/s3`, `test_ail_range_checks`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 8 modules, 0 failed. No recursion-specific test module exists in the tree.

**Probes** (all match CPython in default and forced-general via `cmp.sh`, plus IR depth probes default/force/audit vs the `AIL_BCE=0` oracle): `p_self`, `p_mutual`, `p_helper`, `p_raise`, `p_values` (arg/list/attribute/dict), `p_method` (method-call disqualification); depth 49,999/50,000/50,001, mutual g/h, raise-at-30k then reuse, helper eligible/refused, `f__d` collision, tally-like `ev` — all pass, audit clear (no exit 86).

**Not done:** CI shards/PR (push is forbidden in this runner) and no recursion test module to register. Commits are on `job-bces2c-11042316`, working tree consistent, no background jobs left.
[commandcode stop=end_turn turns=135 out_tokens=63599]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report — bce s2 (depth in a register)

**What the change really does (one line):** it exposes SCC/reach/direct-call info from `pyfunc.to_c`, makes `ir/lower.py` keep the global counter unless a recursive IR function's SCC is exactly `{f}`, has no `try`/list-return/checked-exceptions/unknown callee/inner-symbol clash, and makes `ir/emit_c.py` emit `f__d(..., int64_t ail_d)` with the same trip check, self-calls rewritten to `f__d(..., ail_d+1)`, and `f(...)` as a wrapper calling `f__d(..., ail_depth+1)`; audit keeps the old increment/decrement plus `ail_d == ail_depth`. This matches the report.

**Report claims**
- Cherry-pick of the lost branch / integ message kept / non-Name calls disqualified: **verified** in the diff and generated C (`"maximum recursion depth exceeded"`).
- `AIL_BCE=0` oracle equals base: **verified** (byte-identical `program.c`).
- 17 other task/syntax pairs same C, `tree_fold/python` and `tally_lang/python` identical failures: **verified** all 20 pairs by compiling base vs head from the same source path (including `--exact-int` for `chain_relax`/`rail_transfer`); only `tally_lang/ail` differs, and its diff is exactly the depth rewrite inside `ev`.
- tally callgrind 29,542,790,615 → 26,575,248,821 (0.89955): **verified** independently: 29,542,790,355 → 26,575,248,561 = **ratio 0.89955 (10.05% drop)**, identical output. Stripped 88,280 → 88,280 bytes; exe 95,088 → 95,120.
- 5/5 codegen pins unchanged: **verified** (paths don't use recursion).
- `test_ail_bce` + `test_ail_safetynet`: **verified** (2 modules, 0 failed). The report's 8-module sweep was not re-run (my instructions say only edited modules + safetynet).
- Manifest consistent: **verified** (`update_manifest.py --check` exits 0). No `AIL_CURRENT/*recurs*` test module: **verified**.
- Compile-time within 3%: **unverified** (not measured).
- CI shards/PR and `bce_census.py check` end-to-end exit 0: **unverified** (push forbidden; I reproduced the substance across all 20 pairs instead).

**Probes** (`/tmp/rprobes`, head vs base, default/forced/audit/`AIL_BCE=0`): `p_self` 49999/50000/50001/-1; `p_pair` 49978/49979 (trip point identical); `p_mutual_deep`, `p_method_deep`, `p_helper_deep`, `p_listparam_deep`, `p_defaults`, `p_ownlist`, `p_raise` (raise at 30k, reuse 30k: no false trip); `p_shadow` (`f__d` collision keeps global), `p_reach` (guarded callee refused), `p_try`, `p_listret`, `p_class`/`p_indirect` (callables stay legacy); value sources `p_dict`, `p_float`, `p_strparam`, `p_zero`, `p_str`, and CPython comparisons. Audit builds contain the assert and never exited 86.

**Pre-existing (identical on base, not blocking):**
- `AIL_UNIFIED_FORCE=1` counts no depth for these programs at all; base and head emit identical C there (base segfaults/flaky at 50k, head returns).
- Deep forced-general recursion (~40k+ frames) segfaults on both trees under a 16 MB stack.
- AIL's 50,000 limit vs CPython's 1,000, and int64 overflow refusals, are by design.

No defect attributable to the change, no benchmark/source tampering (`lab/compare/src`, `bench`, `.github` untouched), and the speed/regression numbers hold.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=130 out_tokens=62461]

## full suite
test_ail_borrowed_owner
test_ail_c_keyword_functions
test_ail_libc_names

## suite fix skipped: only 140 minutes left

FINAL VERDICT: FIX  2026-11-04T16:52:46Z
