# job job-bces2c-11050255  started 2026-11-04T17:59:55Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. The review verdict itself was ACCEPT, but the full-suite list named three modules — all reproduced and fixed.

**Defects fixed**
- `test_ail_libc_names` (real regression): `ctx.recursion_info` is an aliased read-only dict, so `_qc_setattr` set `_qc_uncacheable` and bypassed `_etype`'s memo. A 44-term left-deep sum became exponential: >180 s vs 0.8 s on `origin/integ`. Added `recursion_info` to `_QC_ALIASED_OK`; now 1.4 s.
- `test_ail_borrowed_owner`, `test_ail_c_keyword_functions`: they asserted the old `ail_depth--` / direct self-call emission. Updated to check the intended `f__d(..., ail_d + 1)` inner form and `f(..., ail_depth + 1)` wrapper.
- `test_ail_safetynet` S4: only failed under my `ulimit -v 1500000` (2000 live generator stacks); fails identically on `origin/integ` under the limit and passes in 138 s without it — not a defect.

**Verification on final commit**
- 11 targeted modules, 0 failed: bce, ir_s1/s2/s3, range_checks, files, corpus_findings3, safetynet, borrowed_owner, c_keyword_functions, libc_names.
- 5 codegen pins byte-identical to `origin/integ`; `update_manifest.py --check` clean.
- No emitted C changed (fix is compile-time only), so the earlier callgrind result (29.54e9 → 26.58e9, ratio 0.89955, stripped 88,280 → 88,280) still holds.

Committed as `1a06a59f`; working tree clean (only the job's untracked `.agent/pipeline.md`).
[commandcode stop=end_turn turns=56 out_tokens=29713]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report — bces2c fix (query cache + depth tests)

**What the change really does (one line):** it adds `recursion_info` to `_QC_ALIASED_OK` so assigning that read-only aliased dict no longer sets `_qc_uncacheable`/bypasses the query memo, and rewrites two tests that still asserted the old `ail_depth--` / direct self-call emission. This matches the report.

**Key check — is the caching sound?** `recursion_info` is built once per `to_c` (pyfunc.py:37911) from frozensets, passed by reference to every `_Ctx` (38257, 39907), and only read by `ir/lower.py:324` (`info.get('scc')`, `names`, `direct`, `reach`). Repo-wide grep finds no subscript assignment, `.update`, or `.setdefault` on it, and the memoised queries (`_etype`, `_is_str_expr`, …) never read it, so enabling the cache cannot return stale results. `AIL_QUERY_CACHE=verify` (recompute every hit) exited 0 on all four probes.

**Report claims**
- `test_ail_libc_names` regression is real and fixed: **verified** — base (`work`) compile of a 44-function probe exceeded 60 s (timeout); HEAD 1.11 s, `origin/integ` 1.13 s, same C hash (`b176d43a857a`) as integ.
- `borrowed_owner` / `c_keyword` tests updated to the intended `f__d` shape: **verified** — both pass and assert `f__d(..., ail_depth + 1)` wrapper / `ail_d + 1` self-call (test_ail_borrowed_owner.py:351-356, test_ail_c_keyword_functions.py:54-55).
- No emitted C changed: **verified** — `--debug-dir` `program.c` byte-identical HEAD vs base for 5 probes; codegen pins identical to `origin/integ` (`tools/codegen_diff.py --base origin/integ`, exit 0).
- Targeted tests: **verified for the 3 named modules + bce + safetynet** (5 modules, 0 failed; safetynet 199.7 s without `ulimit`). The remaining 6 of the "11 modules" sweep: **unverified** (per instructions, wider suite left to integrator).
- Safetynet S4 is a `ulimit` artefact: **unverified** (it just passes here; not re-tested under `ulimit`).
- `update_manifest.py --check` clean: **verified** (exit 0).
- "callgrind result still holds": **unverified** (not re-run; runtime C is byte-identical, so it follows).

**Probes** (`/tmp/rprobes`, HEAD vs `/tmp/base`, where relevant `/tmp/integ`)
- `p_self.py`, `p_mutual.py`, `p_plain.py`: outputs `900 16 2`, `9 10`, `60 5 3` = CPython; C identical on all three trees; `verify` cache mode clean.
- `p_struct.ail` (struct field + list item + dict value + recursion): `12` = CPython; C identical HEAD vs base; `verify` clean.
- `p_deep.py` (`rec(50000)`): exit 1, same trip message and stderr as base, C identical.
- `p_libc.py` (44 builtin-named functions, left-deep sum): HEAD 1.11 s vs integ 1.13 s; base timed out (>60 s); C identical to integ; `2010` = CPython.

**Pre-existing / not attributable:** recursive programs' C differs from `origin/integ` by the bce2 depth rewrite itself (e.g. `p_self`, `p_deep`), identical HEAD vs base — this is the already-accepted feature, not the fix.

No defect attributable to this change; no benchmark or source tampering (diff touches only `pyfunc.py`, two tests, manifest shards, DEVLOG).

VERDICT: ACCEPT
[commandcode stop=end_turn turns=35 out_tokens=22694]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T19:49:30Z
