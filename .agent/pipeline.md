# job job-setord2-11080440  started 2026-11-07T19:53:17Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the change really does:** it is exactly setord1's diff replayed — every construct that reveals a set's order is *refused by name* (`for`, comprehension, `list`/`tuple`, `print`/`str`/`repr`/f-string, `s.pop()`, typed and general paths). **No CPython hash-table emulation was added** (no table-size/growth/perturb/dummy code in the diff). The worker report is empty, so every claim in the task is unimplemented.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, HEAD vs `/tmp/basew` = base `work`):

| probe | HEAD | base |
|---|---|---|
| p1_ints `for x in {1,2,3}` + `print(s)` + `list(s)` | **compile refusal** | matches CPython |
| p3_pop `print({1,2,3}.pop())` | **refusal** | matches |
| p7_list `list({3,1,2})` | **refusal** | DIFF `[3,1,2]` vs `[1,2,3]` (pre-existing) |
| p10_empty / p20_emptydisp `list(set())`, `print(frozenset())` | **refusal** | matches |
| p11_typed / p12_popint typed `set[int]` walk and pop | **refusal** | n/a |
| p2_str / p6_strids str sets walked, incl. via arg/attr/dict value | **refusal** (p6: run-time TypeError, exit 1) | matches/differs by order only |
| p13_arg `list(s)` through an argument | **run-time TypeError exit 1** | (order-only) |
| p15_comp `[x*2 for x in s]` | **refusal** | (order-only) |
| p16_difflib (SequenceMatcher autojunk path) | **build fails: `stdlib/difflib.py:189` refusal** | builds, same stdout |
| p17_pprint `pprint.pprint({1,2})` | **run-time TypeError** | builds, same stdout |
| p14_tuple, p18_life, p19_noset (no set walked) | match; p19 `--debug-dir` C byte-identical to base | — |

**Defects (all introduced by this change, all named in the task as things to fix):**
1. Int/tuple/bool/None/float sets were to be *emulated*, not refused: p1_ints and p3_pop refuse on both builds, base matched CPython. The task's core deliverable (same table size, growth, perturb, dummies) is absent.
2. Str/bytes sets were to *keep building* with a deterministic order; p2_str/p6_strids/p13_arg now refuse or raise `TypeError` (exit 1) where base built and ran.
3. `s.pop()` was to return CPython's first element for deterministic-hash sets; it is refused on both paths (p3_pop, p12_popint).
4. Regression on the named gate programs: `test_ail_std_difflib` **FAILED (20 failures)** — `stdlib/difflib.py:189`; `test_ail_std_pprint` **FAILED (2)** on `p12_edge_cases.py`; p16/p17 build and match on base, fail on HEAD.
5. Over-refusal of an empty set display is still there (p10/p20), where base matched.
6. Documentation/tests encode the wrong rule: `DIFFERENCES.md` row `C?-job-setord1-…` and `test_ail_setorder.py` assert "refused by name"; no `docs/spec` note about str-set order is added, and no test compares int-set iteration/pop/repr against CPython as step 3 required.
7. The report is empty — nothing is verified against it.

**Tests run on HEAD** (`-j 2`): `test_ail_setorder` ok 91s, `test_ail_safetynet` ok 284s, `test_ail_std_difflib` FAILED 366s, `test_ail_std_pprint` FAILED 724s.

**Pre-existing:** none of the above; every diff-vs-CPython case that matched on base now refuses/crashes instead. p7_list's `[3,1,2]` ordering is pre-existing on base (base builds, orders differently) and is what the task asked to fix — also untouched.

**Unverified:** instruction counts (perf_event_open denied in this sandbox, `tools/icount` cannot run); `test_ail_fuzz81`, `test_ail_pyreach_dictrows`, `test_ail_re_value`, `test_ail_examples_algos`, `test_ail_bigint` were not re-run; mixed sets, float/None sets, mutation-during-iteration and bytes sets were not probed individually.

The approach is not wrong in principle, but the change delivers setord1 unchanged (refuse everywhere) instead of the emulation the task demanded, and it regresses the gate. The refusal-based design for int sets is fixable, so this is FIX, not REJECT.

VERDICT: FIX
1. `p1_ints.py` (`s = {1,2,3}` walked/printed) — expected CPython bytes on both builds; actual compile refusal "walking a set shows the order its elements were inserted".
2. `p3_pop.py` (`print({1,2,3}.pop())`) — expected `1`; actual refusal/hard `TypeError` on both paths.
3. `p2_str.py` / `p13_arg.py` — expected build + deterministic order (no refusal); actual compile refusal / `TypeError` exit 1.
4. `p10_emptydisp.py` (`print(set())`) — expected `set()`; actual compile refusal.
5. `p16_difflib.py` and `p17_pprint.py` — expected match on base behaviour; HEAD fails to build (`difflib.py:189`) / raises `TypeError`; `test_ail_std_difflib` 20 failures, `test_ail_std_pprint` 2.
[commandcode stop=end_turn turns=67 out_tokens=25674]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
(no final text)
[commandcode stop=? turns=? out_tokens=?]
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

## review 1
[model commandcode/deepseek-v4.1-flash]
All gate modules pass, but I have three confirmed defects. Writing the report.

**What the change really does:** replaces setord1's blanket refusal of order-revealing set walks with an emulation of CPython 3.12's open-addressed set table (`ctab` in the boxed set, `ckey/ckind` shadow in `ail_idict`/`ail_iset`), used when every element has a deterministic CPython hash, and insertion order otherwise; removes the refusals from both compilers and rewrites the affected tests.

## Verified

- `probes`: p_int, p_del, p_float, p_none_bool, p_big2, p_lit, p_empty, p_frozen, p_ctx, p_mixed, p_plain, p_str, p_strit, p_mut, p_big, p_typed, p_ops, p_collide — all match CPython on both builds (`cmp.sh`, general and default). Typed `set[int]` iteration/pop matches; typed and untyped `set[str]` build without refusal; mutation-during-iteration and empty/negative/aliasing cases match.
- Non-set program (`p_plain`): generated program statements are identical to base `/tmp/basew` under `--debug-dir`; the only C delta is the set runtime header.
- `test_ail_setorder`, `test_ail_int_dict_set`, `test_ail_collections`, `test_ail_safetynet` pass. Gate modules `test_ail_fuzz81`, `test_ail_std_difflib`, `test_ail_std_pprint`, `test_ail_pyreach_dictrows`, `test_ail_re_value`, `test_ail_examples_algos`, `test_ail_bigint` all pass (7/7, 950s).

## Defects

1. **The change's own test fails on HEAD.** `test_ail_sets_general.test_s3` (edited in this diff) still asserts that a `for x in s` walk is *refused*; the general path now builds it. `FAIL test_ail_sets_general (28s): AssertionError: 0 == 0 : general: walk_general`. The DEVLOG claim "All 16 modules ... pass" is false.

2. **Dense int sets diverge after a rehash** (task explicitly requires collisions/growth to match). `ail_setx_ct_insert_clean` advances `i` through the 9 linear probes and then computes `i = i*5+1+perturb` from the *advanced* index; CPython steps from the original slot.
```python
s = set()
for i in range(40): s.add(i * 128)
print(list(s))
```
CPython: `[0,256,384,128,512,...,1152,4096,4224,4352,4480,4608,4736,4864,4992,1280,1408,...]`
AIL (general and default): `[0,256,384,128,512,...,1152,4096,4224,4352,4480,4608,4736,4864,4992,2432,2560,2688,1280,2816,1408,...]`
A 19-element version matches; 40 does not. `test_ail_setorder`'s "growth" case never creates a 10-slot run, so it misses this.

3. **Tuple-constant displays are not folded, so their order differs.** `_folded_set_elt` returns False for `ast.Tuple`, but CPython 3.12's AST optimizer folds tuple displays of constants and the display then folds to a frozenset constant (`merge_consts_recursive` rebuild + `SET_UPDATE`).
```python
print({(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)})
print(list({(1, 2), (2, 1), (0, 0), (1, 1), (2, 2), (3, 0)}))
```
CPython: `{(1, 2), (2, 2), (2, 1), (0, 0), (1, 1), (3, 0)}`
AIL both builds: `{(1, 2), (2, 1), (0, 0), (1, 1), (3, 0), (2, 2)}` (the plain add-loop order). The 3-tuple case in `test_ail_setorder` happens to coincide, hiding it.

## Pre-existing

Base `/tmp/basew` also differs from CPython on the probes of defects 2 and 3 (it printed plain insertion order), so neither is a regression — but both were required by the task ("collisions, deletions and growth"; "tuples of these"), and the DIFFERENCES/DEVLOG rows claim byte-for-byte parity.

## Unverified

Instruction counts (`tools/icount.c`) on gdev programs not measured; the remaining edited test modules (fuzz27/28/36/70, gaps_api1/2, lang_gaps, modconst, pre133/245/341, corpus_findings, dict_delete, exc_str, fuzz_findings) not run for time. Worker final report was empty, so I checked the DEVLOG rows instead.

VERDICT: FIX
1. `test_ail_sets_general.test_s3` fails on HEAD — it still expects the removed refusal; update or delete it (expected build rc != 0, got 0).
2. `ail_setx_ct_insert_clean` must keep the pre-linear-probe slot for the perturb step. Probe `p_coll2` (40 × 128): expected CPython's `...4864, 4992, 1280, 1408, 1536...`, got `...4864, 4992, 2432, 2560, 2688, 1280...`.
3. `_folded_set_elt` must treat a `Tuple` of constants as foldable (CPython's AST `fold_tuple`). Probe `p_tuple` (6 int pairs): expected `{(1, 2), (2, 2), (2, 1), (0, 0), (1, 1), (3, 0)}`, got `{(1, 2), (2, 1), (0, 0), (1, 1), (3, 0), (2, 2)}`.
[commandcode stop=end_turn turns=46 out_tokens=32149]

FINAL VERDICT: FIX  2026-11-07T23:16:32Z
