# fcdict1: a dict whose values are lists, sets or dicts

Base in this checkout: the single exported commit `4de81bc` (`.agent/BASE_REV` says
`staging:integ`; there is no `origin/integ` ref in this export, so the pyreachs5/pyreachs6
commit subjects the task says to read are not present in the history).

## Before

`lab/pyproof/results.jsonl` (the exported census) classes the three rows as:

| program | result | first reason |
|---|---|---|
| lab/compare/src/ledger_bin/main.py | general, matches | dict of containers (`acc[r[1]] = [r[2], r[3], True]`) |
| lab/compare/src/ticket_audit/main.py | general, matches | dict of containers (`events[ev] = [vc, cents, set()]`) |
| lab/pyperf/run.py --help | refused | dict of containers (`info['wall_cpython'] = [...]`), then `preexec_fn=` |

Those `first reason`s come from `pyfunc._explain_dict_of_containers`, which rewords *any*
refusal in a function that also stores a container into a dict. Running `--strict` with that
explainer disabled shows the real blockers on this tree:

- **ledger_bin**: 9 x `a nested def inside a loop ('rv') is not available` (`main.py:46,61,
  64,65,66,69,71,72,75`), plus `[r[2], r[3], True] mixes bools and numbers` (line 116),
  plus `a is a list or dict that gets the bool False among other values` (line 138).
  The dict use is only one of twelve blockers.
- **ticket_audit**: after the source pass (`ail_syntax.lower_dict_of_records`) rewrites the
  unrelated `per` dict, `events` is left as written because `e = events.get(ev)` is a
  one-argument `get` and `e` is also rebound by `for ev, e in top`. Strict then reports the
  one-argument `get`, `set` of bytes seats (`_AilRowSet` is hard-coded `set[int]`), and the
  bytes keys.
- **pyperf/run.py**: no dict blocker at all in the raw list:
  `preexec_fn=`, `statistics.median`, an unannotated `Path` parameter, and `json.dumps`.

## What already exists, and where

The dict-of-record/set rewriting (`d[k] = [a, b, True]`, `setdefault(k, set())`,
`d.items()`, `d.values()`, one-argument `d.get(k)` *only when proven*) is
`ail_syntax.lower_dict_of_records` and `_RecordTransformer` in
`AIL_CURRENT/ail_syntax.py`. `pyfunc.py` has no dict-of-containers typed representation:
`_mark_nested`'s `ndict` covers only an int-keyed dict whose values are freshly allocated
handles (`d[k] = []`), and the `as a dict of containers` text is only a diagnostic reworder.
`cruntime.py` has no table that stores a container handle by str/bytes key.

The task's list of writable files does not include any of the three files the work needs:
`ail_syntax.py` (the record/dict lowering), `nestfn.py` (a nested def inside a loop with a
`nonlocal` write, as in ledger_bin's `rv`), and `cruntime.py` (a str/bytes-keyed handle table
and a set-of-bytes box if the lowering is done on the typed path instead).

## Stop rule

Stopped here as the task's stop rule requires, naming the files the change needs:
`AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/nestfn.py`,
`AIL_CURRENT/python/pkg-v12/cruntime.py`. No compiler source was changed, so nothing can
regress.

## Probes (`lab/reach/fcdict1/`, both builds, CPython 3.12 oracle)

`bash .agent/cmp.sh <probe> $PWD` (default build and `AIL_UNIFIED_FORCE=1`). Every probe
matches CPython in both builds, or stops by name. Strict classification on this tree:

| probe | strict |
|---|---|
| p01_repro_alias (module-level reproducer) | refused: dict of containers (module-level dicts are not handled by the source pass) |
| p02_alias_append | refused: dict of containers (a growing row list stays fallback, as the task says) |
| p03_set_value_add | refused (set value) |
| p04_dict_of_dict_counter | refused (dict value) |
| p05_setdefault_record | **typed** |
| p06_print_record_dict | refused (print of a dict/record) |
| p07_del_alias | refused (del + alias) |
| p08_int_beyond | refused loudly at the int64 literal (exit 1, no wrap) |
| p09_int_keys | refused: one-argument `d.get(7)` needs Optional (s8) |
| p10_get_default | **typed** |
| p11_nested_alias | refused (dict-of-dict alias) |
| p12_element_store | refused (`d[k][i] = v` direct) |
| p13_bytes_keys | refused (bytes key) |
| p14_setdefault_set | refused (set) |
| p15_str_keys_record | refused (variable key + write-through alias) |

So the current typed coverage is `setdefault`/`get` with a constant key and a record
default; the write-through alias (`v = d[k]; v[i] = x`), sets, dict values, bytes keys,
printing and `del` are still on the general path.
