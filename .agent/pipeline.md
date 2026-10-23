# job job-fuzz68-10231454  started 2026-10-23T05:55:18Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed (`e889067`).

**Cause:** Under the tuple pass, a mixed-type list display such as `[1, "a", None, True]` was inferred as `list[int]` from its first element, so `str()` used plain `str()` per element and printed `[1, a, None, True]` instead of CPython’s `[1, 'a', None, True]`. `seq_type` now widens only `int`+`float`; any other mismatch, including `None` mixed with another type, leaves the display as written so the general path builds it.

**Probes** (`bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`, both builds):
- `p1` list(dict) views — same
- `p2` dict from pairs/zip/tuple — same
- `p3` set(string), empty set — same
- `p4` tuple(generator), tuple(str) — same
- `p5` str(mixed list) — **DIFF before fix, same after**
- `p6` sorted(set) — same
- `p7` nesting dict/list/set/tuple — same
- `p8` empty/zero/negative/10**18 — same
- `p9` wrong types — refused by name on both (lambda value / `list()` arity)
- `p10` raw `list(set("ab"))` order — still differs both (CPython set order is hash-dependent); not changed
- `r1` mixed list via arg/item/attribute/dict value — same
- `r2` mixed set/dict plus tuple trigger — same
- `r3` int/float widening and homogeneous bool/str/nested lists — same
- `r4` `None` mixed and all-`None` — same
- `r5` class return/attribute/dict-value/nested mixed list — same

**Tests on final commit:** `test_ail_fuzz68`, `test_ail_safetynet`, `test_ail_tuples`, `test_ail_collections`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` passed.

**Record note:** this export contains no `DEVLOG` or `DIFFERENCES` file (`git ls-files` and tree search), so no entry could be added there.
[cost $0.0000, opencode tokens {"total": 3973592, "input": 202794, "output": 11536, "reasoning": 10142, "cache.write": 0, "cache.read": 3749120}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of `e889067` (fuzz68)

**Change:** `seq_type` now widens only int+float; any other known-type mismatch, or `None` beside another type, refuses in the tuple pass so the display is left to the general path. New `test_ail_fuzz68.py`, manifest/`ail_check` registration.

**Probes** (`cmp.sh`, both builds; HEAD all match CPython):
- `z_min` mixed list `[1,"a",None,True]`, `str([1,"a"])` — base: d+g `[1, a, ...]`; HEAD: both same. Original bug reproduced and fixed.
- `x1_mixed_channels` mixed list via arg/list item/attribute/dict value — same.
- `x2_intfloat` int/float widening, negative, 1e18, bool mixes — same.
- `x3_optional` `list[int|None]`, all-`None`, empty — same.
- `x4_setdict`, `y3_dict_types` (incl. None values), `y4_set_types` — same.
- `x5_nested`, `y2_list_containers` (empty/non-empty nest, tuple shapes) — same.
- `y1_list_types` (bool/int, bytes/str, None) — same.
- `y5_optional_var`, `alias` (alias + mutation) — same.
- `x6_no_feature`: `--debug-dir` `program.c` byte-identical base vs HEAD.
- `hom.py` (tuples + homogeneous lists): `program.c` identical base vs HEAD.

**Regressions:** Scanned 17 gdev programs with mixed displays + tuples; all were already on the general path on base (or failed on base, e.g. `g17_024`). No typed→general switch caused by the change. `g07_032` builds to the identical sha on base/HEAD. No speed regression found; `icount` could not run (`perf_event_open: Permission denied`).

**Tests:** `test_ail_fuzz68`, `test_ail_safetynet`, `test_ail_tuples`, `test_ail_collections` — 0 failed. `update_manifest.py --check` passes.

**Claims:** commit/cause/fix verified; `p10` set-order caveat plausible but untested; `test_ail_files` and `test_ail_corpus_findings3` not re-run by me (unverified); no DEVLOG/DIFFERENCES present — verified. Minor: `ci_shards.py --check` reports `test_ail_fuzz68` unassigned, but the workflow only uses `--shard` and spreads unmapped modules by name, so CI still runs it.

**Pre-existing:** `g17_018.py` fails both builds (`duplicate AIL name: _`); `list(set("ab"))` order is hash-randomized. Neither is caused by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1851337, "input": 124805, "output": 9126, "reasoning": 18334, "cache.write": 0, "cache.read": 1699072}]

FINAL VERDICT: ACCEPT  2026-10-23T06:30:09Z
