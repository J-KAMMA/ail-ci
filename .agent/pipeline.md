# job job-c169-10221631  started 2026-10-22T07:32:20Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `1deec0e` on `job-c169-10221631`.

**Fixes**
- `index_bound_kind` now resolves an attribute bound against the receiver’s visible class (`parameter/local annotation, constructor, alias, nested/self fields`) or returns `None`; no cross-class same-name field lookup.
- `index_name_kind` treats tuple/starred and other rebinding forms (`with`, `except`, imports, walrus, comprehension, nested defs, `del`, match) as unknown.
- `test_ail_c169.py` now builds typed-lowering coverage with `AIL_NO_GENERAL=1`, plus class-field and tuple/starred regressions.

**Probes (`bash ~/tools/cmp.sh`, general + default)**
- Class-field receivers: `attr_float_local`, `attr_float_local_rev`, `attr_float_param`, `attr_float_item`, `attr_float_dict`, `attr_nested`, `attr_rebound`, `attr_alias`, `attrs_regress`, `attr_class` — all matched CPython.
- Tuple/starred bindings: `tuple_float_ok`, `tuple_local`, `starred_local`, `tuple_regress`, `tuple_more`, `tuple_sources` — all matched CPython.
- Typed-only: `typed_attrs`, `typed_ok`, `typed_ok_param` built and matched with `AIL_NO_GENERAL=1`; the negative attribute/tuple probes refused by name there. Before the fixes, `attr_float_local` returned `ValueError` vs CPython’s `TypeError`, and `tuple_float_ok` exited 0 printing `2.0` vs CPython’s `TypeError`.

**Tests on final commit** (`-j 2`): `test_ail_c169`, `test_ail_list_ops`, `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6/6 passed. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 4873138, "input": 543764, "output": 29175, "reasoning": 12711, "cache.write": 0, "cache.read": 4287488}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Probes** (`/tmp/rprobes`, `~/tools/cmp.sh`, plus `AIL_NO_GENERAL=1` builds)
- Attribute/type boundaries: `ann_mismatch_*`, `field_float_intarg`, `subclass_field` — default builds match CPython; typed-only type checks refuse mismatches by name. No defect.
- Tuple/param rebindings: `param_tuple_uncaught`, `local_tuple_uncaught` — HEAD default matches CPython; typed-only refuses. Base typed-only wrongly printed `2.0`, so the fix works.
- Non-feature C: `plain.py`, `index_int.py` generated C identical to `/tmp/base` (`--debug-dir`).
- Cycle probes: `cycle_selfref_valid.py` exposes a regression (below).

**Defect**
1. `cycle_selfref_valid.py`:
   ```python
   class Box:
       def __init__(self, lo: int, hi: int) -> None:
           self.lo = lo
           self.hi = hi
           self.other = self
   def main() -> None:
       xs: list[int] = [10, 20, 30, 20]
       b = Box(1, 3)
       b = b.other
       print(xs.index(20, b.lo, b.hi))
   main()
   ```
   Expected: `1`, exit 0 (CPython and base general/default both do this). Actual HEAD default and general builds fail with `RecursionError: maximum recursion depth exceeded` in `name_class`/`attribute_class`; typed-only also crashes instead of base's named refusal. Cause: `value_class`/`attribute_class` restart `name_class` with a fresh `seen`, so the recursion guard never sees the cycle.

**Claims**
- Attribute receiver resolution: verified (`attr_float_local`, `_rev`, `_param`, `_item`, `_dict`, `_nested`, `_rebound`, `_alias`, `attrs_regress`, `attr_class` all match).
- Tuple/starred-as-unknown: verified; base's `attr_float_local` (`ValueError`) and `tuple_float_ok` (`2.0`, exit 0) are fixed.
- Typed-only coverage: verified; `TYPED_ATTRS` runs with `AIL_NO_GENERAL=1`. The report's "negative probes refused by name" is inaccurate: they are refused with the generic `raise requires a built-in exception value`, but that is pre-existing.
- Tests on HEAD 6/6 pass (`test_ail_c169`, `list_ops`, `typed_tuples`, `safetynet`, `files`, `corpus_findings3`); manifest `--check` passes.

**Pre-existing**
- Typed-only refusal of visibly non-index bounds with `raise requires a built-in exception value` is identical on base (`typed_literal_float`, `attr_float_local`).

No runtime speed impact: generated C for ordinary programs is byte-identical to base.

VERDICT: FIX
1. Guard the `attribute_class`/`value_class` recursion with the same `seen` set (or treat a receiver re-bound through an attribute as unknown); HEAD currently crashes with `RecursionError` on the probe above, where CPython and base print `1`/exit 0.
[cost $0.0000, opencode tokens {"total": 1579369, "input": 189825, "output": 9015, "reasoning": 40241, "cache.write": 0, "cache.read": 1340288}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fix committed on `job-c169-10221631` as `cbd78e0`.

**Defect fixed:** `value_class` and `index_bound_kind` called `attribute_class(node.value)` with a fresh `seen`, so a receiver re-bound through its own attribute (`b = b.other`) restarted `name_class` and hit `RecursionError` in both general and default builds. They now pass the live `seen` set, so the cycle resolves to unknown and the general path answers correctly; the typed-only build refuses the self-referential class by name.

**Probes** (`/tmp/probes`, `bash ~/tools/cmp.sh`, plus `AIL_NO_GENERAL=1`):
- Changed-behaviour cycle probes all match CPython in general and default builds: `cycle_selfref`, `cycle_alias`, `cycle_attribute_chain`, `cycle_bindings` (arg/list-item/dict/tuple sources), `cycle_negative_widths` (negative, int64 MIN/MAX, empty, zero), `cycle_float` (TypeError), `cycle_none` (AttributeError).
- Typed-only: all 7 are refused by name (`class Box contains itself…` or `the constant None…`), none crash.
- Ran all 33 probes in `/tmp/probes`: 32 match; one pre-existing mismatch `tuple_bind.py` (with/except/import path) is byte-for-byte the same on `/tmp/base`, unrelated to this change.

**Required tests on final commit** `cbd78e0`:
- `test_ail_c169` + `test_ail_list_ops`: 28 passed.
- `test_ail_typed_tuples`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 35 passed, 1 skipped (no zig for windows target).

`test_ail_c169.py` gained `CYCLE` plus two tests: the cycle matches CPython in general/default, and the typed path's refusal is asserted by name. DEVLOG entry added; `tools/update_manifest.py` and `--check` pass; tree clean except pre-existing untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 1744577, "input": 143589, "output": 8073, "reasoning": 6867, "cache.write": 0, "cache.read": 1586048}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review — `job-c169-10221631` (`work..HEAD`: `1deec0e`, `cbd78e0`)**

Change reviewed: typed `list.index` bound analysis in `pyfunc.py` — receiver-class resolution for attribute bounds, `_other_binding` for non-name bindings, and `seen` threading through `value_class`/`attribute_class`; tests gained typed-only (`AIL_NO_GENERAL=1`) coverage.

**Probes** (stdout, stderr, exit compared to CPython; base = `/tmp/base` at `work`; `1deec0e` checked in a temporary worktree):
- Defect 1: `t_attr_int_first` / `attr_from_list_item` (IntBox declared first, float receiver) — base default/typed gives wrong `ValueError: 20 is not in list`; HEAD default matches CPython `TypeError`, typed-only refuses instead of answering wrongly.
- Defect 2: `t_tuple_float` — base prints `2.0`/exit 0; HEAD default matches `TypeError`; `t_starred_float` refuses (base also refuses typed).
- Cycle: the test's exact `CYCLE` program raises `RecursionError` on `1deec0e` in g/d/t; HEAD g/d match CPython and typed refuses by name. All 7 cycle probes (`selfref`, `alias`, `attribute_chain`, `bindings`, `negative_widths`, `float`, `none`) match in g/d and are refused by name in typed-only.
- Widths/empty/negative/dict/list-item/param/alias attribute sources: match on HEAD.
- Non-feature C unchanged: `--debug-dir` `program.c` byte-identical to base for `g00_000`, `g24_018`, `g04_018`.

**Pre-existing** (identical on base, non-blocking):
- `tuple_bind.py`: `with open(...) as w` then `xs.index(20, w)` prints `with 1` instead of CPython `TypeError` (g and d).
- Typed build refuses non-index bounds at the generated `raise` ("raise requires a built-in exception value"), and refuses self-referential classes / `None`; identical on base.

**Claim check**
- `cbd78e0` exists on branch: verified.
- Recursion diagnosis and fix: verified (`1deec0e` reproduced in all modes; HEAD fixed).
- Cycle probes match in general/default: verified.
- Typed-only 7 cycle cases refuse by name, no crash: verified.
- 33 probes, 32 match, only `tuple_bind` differs and is pre-existing: verified by re-running all 33.
- Test counts (`28`; `35`, 1 skipped): verified directly. `par_check -j 2` on the six required modules: 0 failed.
- DEVLOG entry, manifest `--check`, clean tree except `.agent/pipeline.md`: verified.
- Speed: `icount.c` cannot run (`perf_event_open: Permission denied`), but generated C is identical on the relevant gdev programs, so runtime is unchanged.

**Observation (not a defect):** an unannotated composed field (`self.box = IntBox(...)`, then `self.box.lo`) now falls back: default matches CPython, typed-only refuses by name. This is the permitted “resolve or return `None`” branch, not a silent wrong answer.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4768789, "input": 206684, "output": 18306, "reasoning": 46775, "cache.write": 0, "cache.read": 4497024}]

FINAL VERDICT: ACCEPT  2026-10-22T09:05:28Z
