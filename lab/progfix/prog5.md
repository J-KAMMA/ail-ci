# prog5 typed reach: eight real programs (2026-11-01)

Hot functions from `python3 -m cProfile -s tottime` on each program.  A single run is below the
timer's resolution, so the percentages below are from executing that program's `main` 3000 times
under cProfile (stdout discarded; the same functions, in the same proportions).  Percentages are
`tottime` (own time) of the whole profile; the listed program functions and the C/CPython builtins
they call are what make up the rest.

"Typed" is the default `compile --syntax python` path.  A mixed-mode clone is not used as a
substitute: the report below says whether the function's own module builds typed; the CPython hybrid
(`docs/design/CPYTHON_HYBRID.md`) accelerates exactly those typed units.

| Program | Hot function(s) (own time) | Typed? | First reason / action |
| --- | --- | --- | --- |
| `gdev/g14_004.py` | `main` 50%, `add` 8% (plus dataclass `__init__` 8%, `print` 25%) | no | `main`: `comparison Is` at line 24 (`a.songs is b.songs`).  A copy with those two lines removed builds typed, so `add` and the rest are accepted. |
| `gdev/g10_000.py` | `bfs_order` 28%, `build_graph` 20%, genexpr 8%, `main` 5% (plus `list.append` 13%) | no | `build_graph`: `'graph' is annotated dict[int, list[int]], which this compiler has no rule for.`; `bfs_order` has the same parameter. |
| `gdev/g06_014.py` | `main` 43% (plus `print` 43%, `sorted` 14%) | **yes** | Fixed: `set(s)` over a str iterates code points, and `set(a) & set(b)` combines two `set[str]`. |
| `gdev/g15_034.py` | `probe` 26%, `main` 26%, `trigger_*` 5% each, `recover_*` 5% each (plus `print` 32%) | no | First refusal is `trigger_type_error`: `"count: " + 5` is a deliberate TypeError, and the typed path has no catchable TypeError code yet.  `Callable[[], None]` and `Callable[[Exception], str]` are now accepted (that was the earlier first reason). |
| `corpus/.../t243.py` | `main` 46%, `build_prefix` 23%, `rect_sum` 8% (plus `print` 15%) | **yes** | Already typed; kept as a regression. |
| `corpus/.../t467.py` | `main` 22%, `summarize` 17%, `render` 11%, `merge_values` 6% | no | `merge_values`: `only a struct type can be None: write Node \| None` for an Optional `list[int]` parameter; the general path also refuses with `a **kwargs call argument`. |
| `gdev/g07_022.py` | `main` 53%, `group_consecutive` 16% (plus `print` 26%) | **yes** | Fixed: the nested-list pass now recognises `rows = []; rows.append([...])` (the shape iterlower leaves after `groupby`) and `groupby` pairs. |
| `gdev/g18_038.py` | `main` 64% (plus `print` 27%, `deque.append` 6%) | **yes** | Already typed; kept as a regression. |

## Compiler changes

* `python/pkg-v12/nested_lists.py`: a plain `list` local that only receives lists in `.append`
  becomes a nested list (`infer_nested`), so the loop iterlower emits for
  `[list(group) for _, group in groupby(items)]` is lowered to rows instead of leaving a legacy
  `gridret`.  `groupby` pairs are typed as well (element/key and `list[element]` group), for the
  path where the pass sees the comprehension before iterlower.
* `python/pkg-v12/pyfunc.py` (carried in this branch's working tree): `set(str)` over code points,
  `set[str]` intersection before an annotation settles the kind, and `Exception` as an exception
  parameter annotation.
* `python/pkg-v12/callable_types.py`: `Callable[[...], None]` is `noret` and `Exception` is the
  canonical `exception` kind, so Python-spelled callable annotations parse like the AIL spelling.

## Follow-ups (not fixed here; exact message)

* `g10_000` needs a dict whose values are lists (`dict[int, list[int]]`): `'graph' is annotated
  dict[int, list[int]], which this compiler has no rule for.`  This is a new container pairing, not
  an annotation spelling.
* `g14_004` needs list-value identity (`a.songs is b.songs`): `comparison Is`.  List values are C
  structs, so an empty list has no pointer of its own; this needs a real identity field/side table,
  not a pointer compare.
* `g15_034` needs a catchable `TypeError` code for a deliberate invalid operation
  (`"count: " + 5`): `concatenating a str with a number; + joins two strs and nothing else`.
* `t467` needs `*args`/`**kwargs` plus a scalar Optional list parameter: `only a struct type can be
  None: write \`Node | None\`` (general path: `a **kwargs call argument`).

## Verification

* `AIL_CURRENT/test_ail_prog5.py` (registered in `AIL_CURRENT/tests.d/`) compiles `g07_022`,
  `g06_014`, `t243` and `g18_038` typed and compares stdout/exit with CPython, plus typed callable
  and appended-rows programs.
* Probes in `/tmp/probes`: `p5_groupby.py`, `p5_rows_append.py`, `p5_rows_sources.py`,
  `p5_set_str.py`, `p5_callable_exc.py`; all match CPython on both `cmp.sh` builds.
