# job job-bces6-11060753  started 2026-11-05T22:54:47Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed as `08c238f` on `job-bces6-11060753` (not pushed, per the job rules); no background jobs left.

**What I built** (`ir/passes/ranges.py`, all behind `bce_enabled()`; `AIL_BCE=0` C is byte-identical to base):
- **(a)** `number_fields()`: each `field.get` is numbered to the earliest earlier `field.get` of the same object SSA value/field name when no path between them may write that field — a `field.set` of the name on any object of the struct, a call whose effect summary may write it (or unknown), or an outlined `try` body. `if` arms keep only common entries; loops iterate to a fixed point so a store anywhere in the loop is a kill on the back edge, and nothing survives a loop afterwards.
- **(b)** `field.get` of an `facts['fields']['nonneg']` field starts at `lo = 0`.
- **(c)** `lengths_of` returns the `bytes.len` of every load in the same numbered class, so a `bytes` field's length is one value.

**Numbers (callgrind):** ledger_bin/ail `5,394,586,605 → 5,233,458,638` instructions, **ratio 0.97013 (−2.99%)**, stripped binary `55,512 → 55,512`, same stdout/exit (`bce_census.py check` exits 0). tally_lang/ail also drops one `ail_list_span_get` check and three `ck_add` (`71,896 → 67,800` bytes, sha256-equal stdout, same exit); every other task/syntax has byte-identical C (all 20 builds checked; `tally_lang/python` and `tree_fold/python` are the same pre-existing refusals in both trees). `codegen_diff --base HEAD`: no pin changes.

**Why it stops here:** −2.99% is below the lane's 4% stop line and its 6% target. The remaining ~5.1% of hand-edited checks are in `main` (lines 49-51, 103-108), and `passes.optimize` skips that function entirely: `AIL_IR_STATS` reports `{"fn": "main", "sym": "py_main", "passes": {"skipped": "try"}}`. `AIL_BCE_EXPLAIN` on ledger_bin is empty — line 9's `r.data[r.pos]` is proven; line 105 is never seen by the range pass. I did not change the `try` handling, per the stop rule.

**Probes** (`/tmp/probes`, `cmp.sh`, both builds vs CPython): `p1_cursor_ge` (lengths 0, 1, exactly end, one short) match; `p2_cursor_gt` (`>` guard) raises at the same place, not proven; `p3_cursor_bump` (call moves `pos`) raises identically, not proven; `p4_cursor_alias` (`r2.pos = 99` alias) raises identically, not proven; `p5_cursor_negative` (`-1` reads the last byte) matches; `p6_cursor_bigtext` stops at `int()` in both builds as today. Same seven program shapes are appended to `test_ail_bce.py` (default/forced/audit) with `AIL_IR_STATS` pins (`pair` 2, `scan` 1 proven; the neighbours 0).

**Tests:** `test_ail_bce` 10/10, `test_ail_range_checks`, `test_ail_ir_s1`, `test_ail_ir_s3`, `test_ail_ir_s3b`, `test_ail_borrowed_owner`, `test_ail_boolfield`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (the four ASan/safetynet failures in the first `par_check` run were caused by my `ulimit -v`; rerun without it: green). Not run, for the record: the full ten-task callgrind census, the 300-seed difffuzz, and compile timing.
[commandcode stop=end_turn turns=216 out_tokens=92576]

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the change really does.** `number_fields()` numbers each `field.get` to an earlier load of the same object SSA value/field when no instruction between them may write that field (`field.set` on the struct type, an unknown/field-writing call, `try`); `evaluate` copies the canonical load's `Fact` and clamps `lo=0` for s4 `nonneg` fields; `lengths_of` unions `bytes.len` of loads in one numbered class. All behind `bce_enabled()`. That matches the report.

**Probes** (mine, in `/tmp/rprobes`, converted with `ail2py`, run with `cmp.sh`, general + default builds):
- `q1_guard_ge` (lengths 0/1/exact/short), `q11_readvar_loop` (readvar inline, break/err paths) — match CPython.
- `q2_guard_gt`, `q3_call_bump`, `q4_alias` (callee writes aliased `pos`), `q14_alias_local` (`q = r; q.pos = 99`) — raise `IndexError` at the same place; not proven.
- `q5_neg_param`, `q12_neg_arith` (`len()-2`), `q13_dict_value` (`d["p"] = -1`) — negative `pos` reads the last byte as CPython; s4 fact dropped.
- `q7_loop_store` (store in loop before index), `q10_loop_nostore` — correct (exception / same value).
- `q6_bytes_callwrite`, `q8_len_after_set` — mutated `bytes` field, out-of-range index still raises; length not reused across the write.
- `q9_two_structs` — same-named field on another struct is not treated as a kill; value correct.
No mismatch, crash, or wrong exit in either build. No pre-existing differences surfaced.

**C checks.** A non-feature gdev program (`g00_000`) and two struct gdev programs (`g05_024`, `g10_014`) produce byte-identical `program.c` (and binaries) vs `/tmp/base`. `AIL_BCE=0` on a feature-using probe (`q1`) gives C identical to base's default build; `AIL_BCE=1` removes exactly the two `ail_bytes_get` checks in `pair`. Codegen pins identical (`codegen_diff.py --base work`; note the report's `--base HEAD` compares the worktree to HEAD and is vacuous, but the conclusion holds).

**Tests.** `par_check.py -j 2 test_ail_bce test_ail_safetynet` → both `ok` (0 failed).

**Claims.** (a)-(c) implementation: verified. `AIL_BCE=0` identical: verified. test_ail_bce/safetynet: verified. No pin changes: verified. ledger −2.99%, binary unchanged, tally_lang sha256-equal stdout, "all other tasks C identical": unverified (callgrind census not run; change is removals-only and the two gdev C diffs I did check were identical). "main is skipped as `try`": confirmed — `main.ail` has `try` at line 33, and `optimize` returns `{'skipped':'try'}` for such functions, so the 6% target is unreachable without touching `try` handling; the stop rule (4%) was invoked and documented, which the task authorizes.

**Unverified:** full callgrind census/compile timing, 300-seed difffuzz, the other listed test modules.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=84 out_tokens=47538]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T01:51:08Z
