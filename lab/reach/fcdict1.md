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

This branch adds a second, *unconditional* call from `pyfunc.to_c` for the Python surface
(`_fc_lower_dict_records`), after `python_surface` has run.  It finishes the shapes the source
pass skipped and lowers module-level statements through a synthetic `__ail_module__` function.
It is not gated on a particular print shape, and it does not swallow errors: an exception there
is a compiler bug and surfaces (review defect 3).

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

Result: the task's reproducer (`p01`) and probes `p05`, `p07`, `p10`, `p11` build typed and match
CPython; `p08` builds typed and stops loudly at the int64 boundary (see below).  `p07` prints
`['x', 6, True] 0 False`, a str/int/bool row.

## Real blockers (measured; each is outside this lane's allowed files)

The +2 program target is **not** reachable from `pyfunc.py`/`optlib.py`/`unified.py`.  Two of the
blockers are not about dicts at all:

- **ledger_bin** — `parse()` has mixed tuple returns.  A four-line program shows the typed path
  refuses it before any dict is involved:
  `def parse(x): return None, 'bad', 0` on one path and `return (True, [1, 2]), None, 0` on
  another gives `parse returns a tuple on one path and a single value on another`.  Behind that,
  `def rv()` inside a `try` inside a `while` uses `nonlocal pos`; the lifter in `pyfunc.py`
  (`_collect_direct_nested_defs` / `_lift_in_function`) refuses both the `try` placement and
  `nonlocal` write-back.
- **ticket_audit** — the base lowering always boxes a set position as `_AilRowSet`, whose
  parameter is annotated `set[int]`; the seats are `bytes`, and this compiler accepts
  `set[int]`/`set[str]` as a parameter type but not `set[bytes]` (a *local* `set[bytes]` is
  fine).  The same pass only annotates an empty dict as `dict[int, int]` / `dict[str, int]`, so
  a bytes-keyed `events = {}` stays unannotated and the key temp is inferred `int`.  Both are in
  `ail_syntax._lower_record_dict` / `_RecordTransformer`, which this lane may not edit.
- **pyperf/run.py** — not a dict problem: `statistics.median`, `json.dumps`, an unannotated
  `Path` parameter and `preexec_fn=` are stdlib/codegen gaps; the dict blocker is one of several.

Needed to finish: `AIL_CURRENT/ail_syntax.py` (bytes set box kind and bytes-keyed empty-dict
annotation), `AIL_CURRENT/python/pkg-v12/nestfn.py` (nonlocal nested defs in a loop / `try`), and
the typed path's mixed tuple returns.  None is in this task's allow-list, so the target programs
keep their previous classification and their named refusals.

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
`ledger_bin` and `ticket_audit` stay general, `lab/pyperf/run.py` stays refused, and no program
typed at the base lost the typed path; every probe still matches CPython on the default and
unified builds (p08 excepted, by design).
