# fcdict1: a dict whose values are lists, sets or dicts stays on the typed path

Base: `origin/integ` (this branch's only commit is the export of `integ` + the task).

## Before

| program | pyproof (integ ff1dcc26) | `--strict` blockers (measured on this branch) |
|---|---|---|
| lab/compare/src/ledger_bin/main.py | general | 15 blockers: 9x `a nested def inside a loop ('rv') is not available` (lines 46-75), `acc[r[1]] = [r[2], r[3], True]` (116), `acc.get(r[1])` (118, 132, 140), `acc.get(r[2])` (119) |
| lab/compare/src/ticket_audit/main.py | general | `events[ev] = [vc, cents, set()]` (98), `events.get(ev)` (111, 133) |
| lab/pyperf/run.py --help | refused | `info['wall_cpython'] = [round(expected['wall'],...` -- `info` used as a dict of containers |

The pyproof rows come from `lab/pyproof/results.jsonl` (integ ff1dcc26); the strict blocklists were
rebuilt here with `python3 -B AIL_CURRENT/ail_chatgpt.py compile <src> -o /tmp/x --strict`.

## The lowering and where it is called

The dict-of-records lowering is `ail_syntax.lower_dict_of_records` (its helpers:
`_record_candidate_names`, `_record_classify`, `_record_roles`, `_record_bound_names`,
`_RecordTransformer`, `_lower_record_dict`).  It has **one** call site: `python_surface`, at
`AIL_CURRENT/ail_syntax.py:5897`, before the surface rewrite.  It is *not* reached from
`pyfunc.to_c` and `optlib.rewrite` never calls it; an earlier note on this branch claimed that and
was wrong.  A dict the lowering cannot model is left exactly as written, and the typed path then
refuses it by name through `pyfunc._explain_dict_of_containers`.

This branch adds a second, *gated* call from `pyfunc.to_c` (see "What was built"): it runs only
after a successful `print(v)` -> `print([v[0], ..., v[n-1]])` expansion and only accepts the
lowering's result when every dict that expansion touched was actually lowered.

## What was built

`AIL_CURRENT/python/pkg-v12/pyfunc.py`:

- `_record_dict_aliases` / `_expand_record_row_prints`: find a local dict initialised `{}` /
  `dict()` whose every store is a list display of scalar constants with the same kind at each
  position, whose fetched row names are bound once and used only by constant indexes, `len`,
  membership tests and direct `print` arguments, and with no length-changing operation on any of
  them (a non-int position is only read, or stored an int value).  For those, `print(v)` is
  rewritten to the code that prints exactly CPython's list text: `print([v[0], ..., v[n-1]])`
  for an all-int row, and `print('[' + repr(v[0]) + ', ' + ... + ']')` for a mixed row.
- `_apply_record_row_prints`: runs that expansion, then calls
  `ail_syntax.lower_dict_of_records` and keeps the result only when the lowering actually lowered
  every touched dict (no `d[k] = [...]` store survives).  Otherwise the original source is
  returned unchanged, so a program the lowering cannot model keeps its exact old behaviour on
  both paths.  Called from `to_c` only for the Python surface.

Result: the task's reproducer (`lab/pyproof/repro/a-dict-of-containers-lists-sets-or-dicts-as-values.py`,
`p01`) and probes `p07`, `p10`, `p11` now build on the typed path and match CPython (`p07` prints
`['x', 6, True] 0 False`, a str/int/bool row).  `p05` and `p08` were already typed at the base
(p05 no record store printed whole; p08 a record read by index).

`lab/reach/fcdict1/p08_int64_record.py` was vacuous: it read `sys.argv[1]`, but `cmp.sh` passes no
argument, so both builds exited 1 with `IndexError` and the boundary was never exercised.  It now
falls back to `9223372036854775807 + len(sys.argv)` when no argument is given, so the default
build reaches the boundary at runtime: it builds on the typed path, prints the value, and stops
loudly with `OverflowError: integer overflow in +`; with an argument beyond int64 it stops loudly
in `int()`.  `--exact-int` refuses the shape by name (`dict of containers`) before that.

## Remaining blockers (measured after this change)

| program | result | first `--strict` blocker |
|---|---|---|
| lab/compare/src/ledger_bin/main.py | general (unchanged) | `a nested def inside a loop ('rv') is not available` |
| lab/compare/src/ticket_audit/main.py | general (unchanged) | `events[ev] = [vc, cents, set()]` uses `events` as a dict of containers |
| lab/pyperf/run.py --help | refused (unchanged) | `info['wall_cpython'] = [...]` dict of containers; the general path independently rejects `statistics.median` and an unannotated `Path` parameter |

The exact reasons the two programs still do not lower, found by instrumenting
`_lower_record_dict`:

- `ticket_audit`: (1) `e = events.get(ev)` with one argument, whose result is tested with
  `is None`, is refused (`_RecordUnsupported`) because the lowering needs Optional values (s8);
  (2) `top = sorted(events.items(), key=...)[:3]` then `for ev, e in top:` binds the row name over
  a *sliced* sorted items list, which `_record_roles` does not recognize, so the row name has more
  bindings than recognized roles; (3) the record's position 2 is a set of **bytes** seats, but the
  injected row-set box is annotated `set[int]` (`_AilRowSet.__init__(self, s: set[int])`).
- `ledger_bin`: `acc`'s lowering is refused because `with open(...) as f:` binds `f` again before
  `f = acc.get(r[1])`, and `for i, a in top:` binds `a` over a sorted generator that `_record_roles`
  does not track.  Behind it, `parse()` contains `def rv()` inside a `try` inside a `while` with
  `nonlocal pos`, refused by `pyfunc._collect_direct_nested_defs` / `_lift_in_function`.

Finishing these needs files this task does not allow: `AIL_CURRENT/ail_syntax.py` (the record
lowering: whole-row and whole-dict printing, sliced/generator `sorted(items())` roles, Optional
one-argument `get`, and a set box whose element kind is the hint's) and, for `ledger_bin`, the
nested-def lifter in `pyfunc.py` extended to `try`-nested defs with `nonlocal` write-back.  The
`pyperf` refusal is not a dict problem: its general path rejects unrelated constructs.

## Probes

`lab/reach/fcdict1/*.py` (14). Strict build result after this change:

| probe | after `--strict` |
|---|---|
| p01_repro | typed |
| p02_alias_append | refused: `d['a'] = [1, 2]` uses `d` as a dict of containers (the list grows: stays refused) |
| p03_set_add | refused: `d.setdefault('a', set())` |
| p04_dictdict_counter | refused: `d.setdefault('a', {})` |
| p05_setdefault_record | typed |
| p06_print_record | refused: `d['a'] = ['alice', 100, True]` (the whole dict is printed too (`print(d)`)) |
| p07_del_alias | typed |
| p08_int64_record | typed; default build stops loudly at the int64 boundary, `--exact-int` refuses by name |
| p09_record_grow | refused (the list grows: stays refused) |
| p10_alias_write | typed |
| p11_get_default | typed |
| p12_set_store | refused: `d['a'] = set()` |
| p13_dict_store | refused: `d['a'] = {}` |
| p14_var_index_record | refused (variable index over mixed kinds: stays refused) |

Every probe was run in both builds with `bash ~/tools/cmp.sh`: the typed ones match CPython's
stdout and exit status; the refused ones are refused by name under `--strict` and match CPython on
the default (general) build.  p08 is the only one whose default build stops loudly; that is the
documented int64 boundary, and it is what the probe must show.

## After

Typed count: 6 of 14 probes (was 2: p05 and p08).  Programs: no move.  ledger_bin and ticket_audit
stay general, `lab/pyperf/run.py` stays refused, and no program typed at the base lost the typed
path.
