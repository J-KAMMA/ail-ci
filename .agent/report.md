Done on `job-fuzz14-10220830`, commit `6163b3f`.

**Fixed (2 causes)**
1. General-path slice reads read bounds with `(v).i`: `a[None:None]` became empty and float/str bounds read payload bits. Now converted via `ail_op_getslice_obj` (None = omitted, wrong type = TypeError).
2. `list.index`/`tuple.index` start/stop and `list.insert`/`pop` index used `.i`: now validated via `ail_op_index_bound` / `ail_op_int_index`, including CPython’s `list.index` None rejection and integer-conversion TypeErrors.

**Probes**
- 174 small list/sort programs written; final 33-probe verification all matched CPython on both builds (2/2):
  `s01–s10`, `t01–t07`, `t10–t12`, `p01,p03,p05,p08,p12,p15,p17,p22,p27,p32,p34,p41,p44`.
- Covers literal/dynamic None, wrong types, arguments, list items, dict values, attributes, slice objects, huge/negative/out-of-range indexes, sort key/reverse stability, slice assignment, del, repetition/nested aliasing.

**Remaining observed differences (not fixed)**
- NaN sorting: typed path raises ValueError by declared contract (`q01`, `r11`, `r32`); general keyed NaN sort follows merge order, not Timsort (`q02`).
- NaN membership: typed `list.index` refuses by name (declared C119; `r10`).
- `str.find/rfind/endswith` with a None stop still treats it as 0 (`t08`); outside this list/sort job.

**Tests**
- New `test_ail_fuzz14.py`: 5/5 pass.
- On final commit: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_list_ops`, `test_ail_sort_keys`, `test_ail_fuzz14` all pass.
- Also passed: `test_ail_nested_lists`, `test_ail_fuzz3`, `test_ail_int_sort`, `test_ail_ir_s3c3`, `test_ail_dunders`.
- `test_ail_fuzz1`: 27/29; 2 generator tests fail because `tools/difffuzz.py` is absent from this export, unrelated to these changes.

Manifest updated and `--check` passes; DEVLOG and placeholder DIFFERENCES rows added.
[cost $0.2071, opencode tokens {"total": 14390540, "input": 795311, "output": 45590, "reasoning": 33095, "cache.write": 0, "cache.read": 13516544}]
