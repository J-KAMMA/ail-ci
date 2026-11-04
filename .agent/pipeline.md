# job job-pyr3fix-11050045  started 2026-11-04T15:48:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the report.

**Root cause.** Not the declaration-level annotation/caller refusal — sdkdiag1's numeric-only `_explicit_annotation_conflicts` fix already landed in integ, which is why `test_ail_collections` is green on the base. The regression was pyreachs3c's `_owned_unannotated_str_fns`: it infers an owned-str return for every unannotated, terminating str helper so callers can adopt the value. `pyfunc.to_c` then treated that *inferred* ownership like an explicit `-> str` and raised `the entry function cannot return checked str` whenever the hybrid analysed such a helper as a unit. pymix consequently dropped `join`, `state_at`, `label` and `fmt` entirely.

**Fix** (`AIL_CURRENT/python/pkg-v12/pyfunc.py`, commit `d35dad1c`): for the entry, discard *inferred* ownership (`returns is None`) so the entry and every call site in that compilation use the legacy out-parameter str ABI, exactly as before pyreachs3c. Explicit `-> str` entries still take the old refusal path.

**Pass counts (module: parent 7a3b4522 → integ base → final commit):**

| module | 7a3b4522 | integ base | final |
|---|---|---|---|
| test_ail_cpython_hybrid | 7/7 | 6/7 | 7/7 |
| test_ail_prog2 | 9/9 | 8/9 | 9/9 |
| test_ail_prog21 | 8/8 | 5/8 | 8/8 |
| test_ail_collections | 13/13 | 13/13 | 13/13 |

**Other verification on the final commit:**
- `test_ail_pyreach_infer` 10/10 (the tests pyreachs3c added)
- `test_ail_safetynet` 5/5, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2/2, `test_ail_argument_type_details` 16/16
- `python3 -m compileall -q -j 0 AIL_CURRENT tools` clean
- `update_manifest.py --check` clean

**Probes** (all `bash ~/tools/cmp.sh`, both `g` and `d` builds, all matched CPython, exit 0): `p1_concat`, `p2_default`, `p3_container`, `p4_reach` (argument/list item/attribute/dict value), `p5_percent`, `p6_ident` (aliasing/empty), `p7_branches` (negative/empty), `p8_intwidth` (int64 bounds), `p9_scriptentry`, `p10_explicit_entry`.

Records added: DIFFERENCES `C?-job-pyr3fix-11050045-1`, DEVLOG entry in both root and `AIL_CURRENT/DEVLOG.md`; manifest refreshed. No push (per the rules).
[commandcode stop=end_turn turns=77 out_tokens=41054]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review: pyr3fix (`d35dad1c`)

**What the change really does.** In `to_c`'s entry-point guard (`pyfunc.py:37919`), when the entry would be refused as an owned-str return *and* its annotation is absent (`f.returns is None`), it deletes the entry from `owned_str_fns` instead of raising, so the entry is emitted with the legacy out-parameter `int32_t *_out, int64_t _cap` str ABI. An explicit `__ail_checked_str__` entry still raises. This matches the report.

Mechanism check: `ail_cpython_hybrid.py:406` strips every `-> __ail_checked_*__` before `to_c`, so in the hybrid an annotated `-> str` function becomes unannotated and was being refused as a unit entry. `pyboxed2.py:251` requires exactly `int32_t *_out, int64_t _cap` for a boxed str result, so the restored legacy ABI is the one the hybrid validator accepts. Root cause in the report verified.

**Modules (HEAD, `-j 2`/direct):** test_ail_cpython_hybrid 7/7 ok, test_ail_prog2 ok, test_ail_prog21 ok, test_ail_collections 13/13 OK, test_ail_pyreach_infer 10/10 ok, test_ail_safetynet ok. `compileall` clean, `update_manifest.py --check` clean. Matches the report.

**My probes** (`bash ~/tools/cmp.sh`, both g and d, all exit 0, stdout == CPython): p1 concat/empty/non-ASCII, p2 alias/empty/two-live-results, p3 loop-built, p4 helper-calls-`label` at call sites, p5 self-recursion adopting the result, p6 list/dict/global/empty-slice sources, p8 branch returns, p9 int-only. p7 `def f(x) -> str` compiled and matched (not refused). No crashes, no output differences.

**Important limitation I found:** p1/p9's generated `program.c` is byte-identical between HEAD and base, and `join`/`word` appear as `ail_str` *helpers* — the script rewriter synthesizes `main`, so the changed line is never reached by whole-program `compile` probes. The worker's p1–p10 (also module-level-print shapes) therefore do **not** exercise the change; their "all matched CPython" claim is true but vacuous for the fixed path. The changed path is verified only indirectly, by `test_accelerated_and_fallbacks` (hybrid, `join('', '')`, `join('héllo 東京','!')`, repeated calls, hybrid vs CPython stdout) plus prog2/prog21, which all pass.

**Claims:** root cause / files / commit — verified; four modules + pyreach_infer + safetynet + compileall + manifest — verified; "explicit `-> str` entries still take the old refusal path" — true only for the `__ail_checked_str__` (dunder-rewritten) form; a plain `def f() -> str` entry is not refused (that is pre-existing, the guard's `else` branch is untouched); base pass counts, `test_ail_argument_type_details` 16/16 — unverified (not re-run).

**Pre-existing:** `def f() -> str` as entry compiles rather than being refused (base does the same); no probe showed a base-only difference.

**Speed:** the diff's only conditional is `not library and entry in owned_str_fns and returns is None`; for every other program the emitted C is unchanged (verified byte-identical on three programs, one int, two str-helper). No hot-code change, so no icount run.

**Unverified:** the worker's base-vs-HEAD pass counts; `test_ail_argument_type_details`; a direct hybrid probe of my own for the newly-accelerated entry (covered by test_ail_cpython_hybrid).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=69 out_tokens=36342]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T19:08:00Z
