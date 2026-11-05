# job job-rc2-11060052  started 2026-11-05T15:53:12Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

## What I fixed

**Defect 1 — stale manifest (confirmed, fixed).** `update_manifest.py --check` reported 4 stale files; `par_check` aborted with `ValueError: hash mismatch: python/pkg-v12/ir/borrow.py`. Re-ran `tools/update_manifest.py`; `--check` now exits 0 and `par_check.py -j 2` runs to completion.

**Defect 2 — the number (re-measured, partially moved).** The previous report only compared the six `lab/rc/progs` programs. I rebuilt **all 16** (6 programs + 10 compare tasks) against the true pre-rc2 commit `5504c4b0`:

| program | change | est. instruction ratio |
|---|---|---|
| ticket_audit | −2,860,800 `ail_blist_retain`, −2,860,800 `ail_blist_release` (read-only `list[bytes]` param) | **1.0219x** |
| term_rank | −7,797,358 `ail_bytearray_retain`, −7,797,358 releases (read-only `bytearray` param) | **1.0040x** |
| objscan | −2 retains/releases (`list[Node]`) | 1.0000x |
| rbtree | +141,460 retain/release pairs (returned params now correctly refused) | 0.9994x |
| other 12 | `program.c` byte-identical | 1.0000x |

So the rule *does* elide more than the legacy scan on three programs, not one. But the brief's **1.03x-on-two-programs target is still not met**: the baseline already banks the class-instance elision, and only three of the 16 programs pass a refcounted non-class parameter to a function the IR does not lower. `RESULTS_BORROW.md` now states this with the full measurement.

**Extra defect found and fixed.** `ir/verify.py`'s borrowed-value check flagged a store if *any* operand was borrowed, so it treated `ba.push`/`list.push`/`field.set`'s **container** operand as a stored reference. That made the IR reject `echo_pack.flush` (append/extend on a borrowed bytearray), costing +738,667 retains and +5,531,711 releases (**+0.44% instructions, outside the 0.3% bar**). The check now tests only the value operands; `echo_pack.program.c` is byte-identical to pre-rc2 again. Added two verifier unit tests pinning container-vs-value.

## Verification
- `test_ail_rc_borrow`: **15 tests OK** (was 13).
- `par_check -j 2`: `test_ail_rc_borrow`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed. Also `test_ail_borrowed_owner`, `test_ail_borrowed_elements`, `test_ail_borrowed_element_fields`, `test_ail_callable_owned_results`, `test_ail_exception_resources` — 0 failed.
- 9 probes × 3 builds (default, `AIL_RC_BORROW=0`, `AIL_UNIFIED_FORCE=1`) — all match CPython.
- 60 corpus programs default vs `AIL_RC_BORROW=0` — 0 output/exit differences.
- valgrind is still not installed on this runner (ASan was the substitute previously); I did not re-run it.

Committed as `83352b8d`; manifest check passes on the committed tree.
[commandcode stop=end_turn turns=104 out_tokens=64361]

## review 0
[model commandcode/deepseek-v4.1-flash]
All checks done. Writing the report.

## Review

**What the change really does:** only the final commit is new — it narrows `ir/verify.py`'s borrowed-value check to test the *value* operands of store ops (container operand no longer counts as a store), adds two verifier unit tests, refreshes `RESULTS_BORROW.md` and the manifest hashes. That matches the report.

**Defects from review 1**
1. **Stale manifest — fixed, verified.** `update_manifest.py --check` exits 0; `par_check.py -j 2 test_ail_rc_borrow test_ail_safetynet` → `2 modules, 0 failed`. Module has 15 test methods (report says 15; earlier "7/7" is gone).
2. **The number — re-measured, reproduced exactly, still below target.** Ran `lab/rc/run.py --only ticket_audit --only term_rank` on HEAD and on a `5504c4b0` worktree: instructions 71,138,025,704 vs 72,699,307,354 → **1.0219x**, and 65,640,733,733 vs 65,903,584,907 → **1.0040x**; both `correct=True`. Emitted C confirms it: `ail_blist_retain/release(v_f)` and `ail_bytearray_retain/release(v_t)` entry/exit pairs are gone vs pre-rc2. `rbtree` gains the entry pair in `rotate_left/right` as reported. So the 1.03x-on-two-programs target is **still unmet** — disclosed in `RESULTS_BORROW.md`, which is the remedy review 1 allowed.

**Extra fix, verified.** `echo_pack` `program.c` on HEAD is **byte-identical** to the pre-rc2 build (274,532 bytes, `diff` clean) and `run.py --only echo_pack` → `correct=True`, i.e. the narrowed verifier restored the IR path for `flush`'s write-through-borrowed-bytearray (`out.append`/`out.extend`). Operand layout checked against `ir.py`: `list.set/ba.set` 3 (value at 2), `list.push/ba.push/field.set` 2 (value at 1), `list.lit/rec.push` (ref, values…), `global.store` 1 — the fix's indices are right. `dict.store`/`elem.store` are not real ops (dead entries, pre-existing).

**Probes** (`bash ~/tools/cmp.sh`, default + `AIL_UNIFIED_FORCE=1`, all match CPython incl. exit status; `h` also checked): a) borrowed `list[Node]` mutated with `append` inside callee, caller observes; b) borrowed `bytearray` `append`+`buf[0]=` (exercises `ba.set`/`ba.push`); c) bytearray slice alias then caller mutation; d) `xs[i] = Node()` on borrowed list + out-of-range `-1` (IndexError, exit 1); e) borrowed container with a stored parameter (still not borrowed, output right); f) append while iterating a borrowed list; h) int argument at the value position. Also `AIL_RC_BORROW=0` on b: matches, switch intact. Feature engagement confirmed (`add(xs, v)` has no retain on `v_xs`, no exit release).

**Non-feature C unchanged:** `binarytrees`, `deriv`, `rbtree`, `objscan` and a no-borrow program produce byte-identical `program.c` on HEAD vs the `work` base; no fallback introduced.

**Claims:** manifest (verified), 15 tests (verified), ticket/term ratios (verified exactly), echo_pack byte-identical (verified), rbtree 0.9994x (C diff verified; dynamic count not), 9 probes / 60 corpus / "other 12 byte-identical" (unverified), valgrind "not installed" (verified — `which valgrind` empty).

**Unverified:** the worker's 9 probes and 60-program corpus run; rbtree's dynamic +141,460 pairs; per-program peak-RSS figures beyond the two I re-ran (both within noise).

**Pre-existing:** none new found; `echo_pack` vs raw `main.py` input mismatch noted earlier was not re-run.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=32 out_tokens=22866]

## full suite
test_ail_bytearray_refs
test_ail_ir_s0
test_ail_ir_s3c1

## worker report (suite fix)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `e9464bcf`. All three modules now pass.

What was broken and how I fixed it:

- **test_ail_ir_s0** — `ir/verify.py` treated any IR `yield` as returning a borrowed parameter. In IR, `yield` is a region result (ternary/boolean expressions); Python generators are refused by the lowering, so it never escapes the function. Escapes are now `return` only.
- **test_ail_ir_s3c1** — `ir/borrow.py` missed container literals outside assignment/return position, e.g. `for a in [text, "x"]:`. Building that list stores `text`, which the verifier correctly rejects, but the analysis still called it borrowed. Container literals/comprehensions now demote the parameters they store, wherever they appear.
- **test_ail_bytearray_refs** — the C-shape test pinned the legacy entry retain for `total(b: bytearray)`, which rc2 intentionally elides because `total` only reads `b`. The test now asserts the borrowed shape in the default build and still checks the original retain-then-`live` invariant in an `AIL_RC_BORROW=0` build.

I added two regression tests to `test_ail_rc_borrow` (container-literal stores; region `yield` is not an escape). `test_ail_rc_borrow` (17 tests), `test_ail_safetynet`, the five related borrow modules, and the three reported modules all pass; `tools/update_manifest.py --check` is clean.
[commandcode stop=end_turn turns=68 out_tokens=35017]

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T19:18:04Z
