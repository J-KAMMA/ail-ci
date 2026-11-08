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

## What was built

Nothing that survives. The work in this session did not reach a state that keeps a program on the
typed path; the working tree carries no change to `pyfunc.py`, `optlib.py` or `unified.py`.

What was learned and measured (so the next attempt does not repeat it):

- The dict-of-records lowering (`ail_syntax.lower_dict_of_records`) is reached from
  `ail_syntax.python_surface` **and again** from `pyfunc.to_c` (through `optlib.rewrite`), so a
  second lowering pass must be idempotent over the first pass's `_rkey*` / `_rslot*` temps. A
  partial lowering of only *some* dicts in a function leaves the remaining dict as written and the
  first dict's temps in place; the compiler then reports the temp names (`'_rkey__' is an int and
  is being assigned a bytes`) instead of the property, which is worse than the base.
- `ticket_audit` needs two independent things the lowering does not model today: `events[ev] = [vc,
  cents, set()]` (a **set** at row position 2, which needs the `_AilRowSet` box) and
  `for ev, e in sorted(events.items(), key=lambda kv: ...)[:3]` (a sliced `sorted(...)` row list).
  Lowering the rows without the `sorted(...)[:3]` role binding leaves `e` unbound.
- `ledger_bin` is blocked first by 9 `nested def inside a loop ('rv')` refusals in `parse()`, which
  are outside this job's files; the dict work alone does not make it typed.
- `p05_setdefault_record.py` and `p08_int64_record.py` are already typed at the base.

## Probes

`lab/reach/fcdict1/*.py` (14). Strict build result at the base, i.e. what the next attempt has to
move:

| probe | base `--strict` |
|---|---|
| p01_repro | refused: `d['a'] = [1, 2]` uses `d` as a dict of containers |
| p02_alias_append | `d['a'] = [1, 2]` |
| p03_set_add | `d.setdefault('a', set())` |
| p04_dictdict_counter | `d.setdefault('a', {})` |
| p05_setdefault_record | typed |
| p06_print_record | `d['a'] = ['alice', 100, True]` |
| p07_del_alias | `d['a'] = ['x', 1, True]` |
| p08_int64_record | typed |
| p09_record_grow | `d['a'] = [1, 2]` (must stay refused: the list grows) |
| p10_alias_write | `d['a'] = [1, 2]` |
| p11_get_default | `d['a'] = [10, 20]` |
| p12_set_store | `d['a'] = set()` |
| p13_dict_store | `d['a'] = {}` |
| p14_var_index_record | `d['a'] = [1, 'x', True]` (variable index over mixed kinds: must stay refused) |

## After

Unchanged: no program moved. ledger_bin and ticket_audit stay general, `lab/pyperf/run.py` stays
refused, and no program typed at the base lost the typed path (no compiler file changed).
