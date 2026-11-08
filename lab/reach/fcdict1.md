# fcdict1: a dict whose values are lists, sets or dicts stays on the typed path

Base: `origin/integ` (export `be77484`, tree equivalent to integ `eb8b28cf` for
`AIL_CURRENT/ail_syntax.py`; `lab/pyproof/results.jsonl` rows carry `integ_sha ff1dcc26`).

## Before

| program | pyproof (integ ff1dcc26) | first `--strict` blocker on this branch |
|---|---|---|
| lab/compare/src/ledger_bin/main.py | general, matches | `a nested def inside a loop ('rv') is not available`; then `parse` returning a tuple on one path and a single value on another (see "Real blockers") |
| lab/compare/src/ticket_audit/main.py | general, matches | one-argument `events.get(ev)` / `events[ev] = [vc, cents, set()]`; the strict build exceeds the 120 s pyproof budget |
| lab/pyperf/run.py --help | refused | `info['wall_cpython'] = [...]` dict of containers; the general path also rejects `statistics.median`, an unannotated `Path` parameter and `preexec_fn=` |

The pyproof rows come from `lab/pyproof/results.jsonl`; the strict blocklists were rebuilt with
`python3 -B AIL_CURRENT/ail_chatgpt.py compile <src> -o /tmp/x --strict`.

## The lowering and where it is called

The dict-of-records lowering is `ail_syntax.lower_dict_of_records` (helpers:
`_record_candidate_names`, `_record_classify`, `_record_roles`, `_record_bound_names`,
`_RecordTransformer`, `_lower_record_dict`).  It has **one** call site in the source pass:
`python_surface`, `AIL_CURRENT/ail_syntax.py:5897`.  `optlib.rewrite` never calls it.

This branch adds a second call from `pyfunc.to_c` for the Python surface
(`_fc_lower_dict_records`), after `python_surface` has run.  It finishes the shapes the source
pass skipped and lowers module-level statements through a synthetic `__ail_module__` function.
The call is *additive and safe*: the lowered source is compiled first, and if the typed path
refuses a shape the lowering introduced, `to_c` recompiles the program **as written**.  A
program whose lowered form types keeps it; a program that does not type anywhere keeps exactly
its base refusal, so a diagnostic names the program's own construct (`events[ev] = [vc, cents,
set()]`) and never an internal `_rkey`/`_rval` temp from a partial lowering.  An exception other
than `Unsupported` (a compiler bug) still surfaces.

## What was built

`AIL_CURRENT/python/pkg-v12/pyfunc.py`:

- `_fc_syntax`: imports `ail_syntax` whether or not `AIL_CURRENT` is already on `sys.path`.
- `_fc_hint` / `_fc_record_roles` / `_fc_bound_names`: the record pass's own helpers with the
  steps that reach a bytes value through input parsing (`parts = line.split(b'|')`,
  `ev, vc, ... = parts[1:]`, `f.read()`), a `sorted(d.items(), ...)[:n]` slice recognised as the
  items list, and a `with ... as f` target renamed so it is not mistaken for a row name.  The key
  hint is patched during the lowering so a bytes-keyed `d = {}` is annotated.
- `_FcRecordMixin`: the record transformer with
  - a bytes set box (`_AilRowSetBytes`) when a set position holds bytes, `_AilRowSet` otherwise;
  - a one-argument `d.get(k)` whose result is tested `is None`: the row is `d.get(k, -1)` and
    `r is None` becomes `r < 0`, so a missing row is still distinguishable without Optional
    values;
  - `print(row)` and `print(d)` written as CPython's list/dict text;
  - `sorted(d)` walking the keys, and a `(key, row)` comprehension yielding the slot.
- `_fc_lower_dict_records`: lowers every function and the module body, appending the box class
  only when the lowered code uses it.  A program that does not use the shape is returned byte for
  byte unchanged.
- `_FcRecordMixin._store_row`: a key or value that is already a plain name or constant is emitted
  in place, with no `_rkey`/`_rval` temp.  A temp was default-bound to `int` by `_promote_floats`
  before its bytes assignment, so a lowered store reported an internal name (the review's
  `'_rkey__' is an int ...` diagnostic) instead of the source construct; the in-place form has the
  same evaluation order CPython uses because a plain read has no side effect.

Result: the task's reproducer (`p01`) and probes `p05`, `p07`, `p10`, `p11` build typed and match
CPython; `p08` builds typed and stops loudly at the int64 boundary (see below).  `p07` prints
`['x', 6, True] 0 False`, a str/int/bool row.

## Real blockers (measured, and corrected from the first report)

The +2 program target is **not** reachable from `pyfunc.py`/`optlib.py`/`unified.py` alone, and
the first report was wrong to say every blocker sat outside this lane's files: two of them are in
`pyfunc.py`.  They are separate features, not the dict-of-containers bucket this task names.

- **ledger_bin** — `parse()` has `def rv()` inside a `try` inside a `while`, using `nonlocal pos`.
  The nested-function lifter in `pyfunc.py` (`_collect_direct_nested_defs` /
  `_lift_in_function`, the refusal at `pyfunc.py:37459`) accepts a `def` that is a direct
  statement of a loop body, but refuses a `def` one level deeper (in a `try`) and has no
  `nonlocal` write-back.  Behind that, `parse()` returns tuples whose shapes differ by path
  (`None, 'header', 0` vs `(strict, recs), None, 0`), which the typed return-kind join refuses in
  `pyfunc.py` (`_join_return`, the refusal at `pyfunc.py:33555`).
- **ticket_audit** — the bytes set box (`_AilRowSetBytes`, added here) and the bytes-keyed empty
  dict annotation are now handled, but the typed path still stops on two pre-existing items: the
  name `cents` holds an `int` in the `E` branch and `bytes` in the `END` branch (one function,
  two kinds; `rebinding.py` can split branch-scoped names but is not reached because of the next
  item), and the regex helper `_ail_re_testB(s: bytes)` is called at one site with a value the
  typed path reads as `int`.  With `cents` manually renamed, `--strict` still stops on
  `_ail_re_testB` with the lowering switched off too, so this is not caused by the dict pass.
- **pyperf/run.py** — not a dict problem: `statistics.median`, `json.dumps`, an unannotated
  `Path` parameter and `preexec_fn=` are stdlib/codegen gaps; the dict blocker is one of several.

Because none of these can be made exact here, the target programs keep their named compile-time
refusals (never a crash or a silent difference).  The lowered-source fallback above guarantees
each refusal names the program's own construct.

## Probes

`lab/reach/fcdict1/*.py` (14).  Results after this change (default build and
`AIL_UNIFIED_FORCE=1` compared with CPython; `--strict` classified):

| probe | default | `--strict` |
|---|---|---|
| p01_repro | matches | typed |
| p02_alias_append | matches | refused (the list grows) |
| p03_set_add | matches | refused |
| p04_dictdict_counter | matches | refused |
| p05_setdefault_record | matches | typed |
| p06_print_record | matches | refused (prints the whole dict) |
| p07_del_alias | matches | typed |
| p08_int64_record | loud `OverflowError` | typed |
| p09_record_grow | matches | refused (the list grows) |
| p10_alias_write | matches | typed |
| p11_get_default | matches | typed |
| p12_set_store | matches | refused |
| p13_dict_store | matches | refused |
| p14_var_index_record | matches | refused (variable index over mixed kinds) |

`p08` is intentionally loud on the default build: it adds to `INT64_MAX` and must stop rather
than wrap; with an argument beyond int64 it stops in `int()`.  `--exact-int` refuses the shape by
name.

## After

Typed probes: 6 of 14 (p01, p05, p07, p08, p10, p11) were 2 (p05, p08).  Programs: no move.
`ledger_bin` and `ticket_audit` stay general, `lab/pyperf/run.py` stays refused.  Under `--strict`
both programs now refuse exactly as at the base: `ledger_bin` names `a nested def inside a loop
('rv')`, `ticket_audit` names `events[ev] = [vc, cents, set()]` -- not an internal `_rkey` temp.
No program typed at the base lost the typed path; every probe still matches CPython on the default
and unified builds (p08 excepted, by design).  `test_ail_fcdict1` passes (7 tests), and the
manifest is regenerated.

The +2 target is not delivered; the reasons are the two pre-existing features listed under "Real
blockers", both of which this lane either may not or cannot finish exactly.  They are left as
named refusals rather than crashes or silent differences.
