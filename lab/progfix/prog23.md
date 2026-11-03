# prog23: typed reach of eight real programs

CPython 3.12.3, `python3 -m cProfile -s tottime`, each program on its largest task input
(`lab/corpus/tasks/<t>/in2.txt`) or no input for the self-contained `gdev` programs.  Times are tiny
because the published inputs are tiny; the table lists every project function in own-time order and
the share is of the whole profiled run (including interpreter/import builtins).  `typed before`
means the same program compiled fully on the typed path with `--strict` before these changes.

| program | hot function (own time) | own share | cum share | typed before | typed now | first reason before |
| --- | --- | ---: | ---: | --- | --- | --- |
| g02_026 | `compute_sigma_table` | 86.6% (9795 us) | 86.6% | yes | yes | -- |
| g02_026 | `find_max_abundancy` | 11.4% (1293 us) | 11.4% | yes | yes | -- |
| g02_026 | `main` | 0.2% (27 us) | 98.3% | yes | yes | -- |
| g15_004 | `main` | 12.2% (11 us) | 23.2% | no | no (follow-up) | `raise ... from ... in a program that reads __cause__, __context__ or __traceback__; the cause of an exception is not kept here` |
| g15_004 | `load_setting` | 4.3% (4 us) | 4.3% | no | no (follow-up) | same exception-chaining reason |
| g15_004 | `ConfigError` | 0.9% (1 us) | 0.9% | no | no (follow-up) | same class used by the refused `raise` |
| g25_026 | `describe` | 6.1% (74 us) | 14.0% | no | no (follow-up) | `dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...)` |
| g25_026 | `main` | 3.8% (46 us) | 26.3% | no | no (follow-up) | same generated-Enum dunder reason |
| g25_026 | `Role` | 1.4% (17 us) | 16.5% | no | no (follow-up) | same generated-Enum reason |
| g25_026 | `combined_permissions` | 0.7% (9 us) | 5.9% | no | no (follow-up) | same generated-Enum reason |
| g18_030 | `main` | 16.1% (12 us) | 54.7% | yes | yes | -- |
| g18_030 | `build_graph` | 14.5% (11 us) | 18.5% | yes | yes | -- |
| t102 | `main` | 17.6% (29 us) | 79.9% | yes | yes | -- |
| t069 | `process_line` | 16.1% (19 us) | 36.4% | yes | yes | -- |
| t069 | `main` | 13.6% (16 us) | 76.6% | yes | yes | -- |
| t069 | `longest_word` | 4.2% (5 us) | 13.4% | yes | yes | -- |
| t115 | `main` | 27.3% (24 us) | 75.0% | no | **yes** | `a tuple target over a sequence (... built for enumerate(xs), zip(a, b) and d.items() only).` |
| t143 | `main` | 48.9% (57 us) | 80.1% | no | **yes** | `ListComp is not one of the expression shapes this compiler builds` (inside the conditional at lines 6/7); after that, the unannotated set operation |

## Fixed here

1. **Tuple/list targets bound from matching tuple/list expressions** (`python/pkg-v12/iterlower.py`).
   `known_sequences` treated every non-`Name` assignment target as unknown, so
   `first, second = words[:mid], words[mid:]` marked both names bad and the later
   `for a, b in zip(first, second)` was refused as a tuple target over a sequence.  A tuple or list
   target with the same number of elements as a tuple/list right-hand side now classifies each name
   from its own element expression.  This makes `t115` fully typed; its output matches CPython on
   `in0`, `in1` and `in2`.
2. **A conditional producing a numeric list** (`python/pkg-v12/pyfunc.py`, `_numeric_field_kind`).
   `first = [...] if cond else []` is now recognised as `LIST`/`FLIST` when both branches are the
   same numeric-list kind and one may be empty.  Before, `t143` was refused at the conditional on
   lines 6/7, which also made the later `join(map(str, diff))` look unsupported.
3. **Unannotated set values built by set operators** (`python/pkg-v12/pyfunc.py`).  `a & b`,
   `a | b`, `a - b` and `a ^ b` over unannotated sets are now recognised as sets, the assignment is
   materialised through the existing `_set_value` path into the destination's own table, and the
   preliminary float pass no longer claims those names `int` (the same provisional claim also covered
   integer bitwise operators).  `_promote_floats` follows `set(...)` bindings and plain aliases so
   `set_b = second_set` is known before `common = set_a & set_b`.  This makes `t143` fully typed; its
   output matches CPython on `in0`, `in1` and `in2`.

4. **Review 0 fix: str/bytes-keyed `set(...)` and a rebind to an int set operation**
   (`python/pkg-v12/pyfunc.py`).  A first `c = set(["x", "y"])` followed by `c = a & b` over int
   sets used to emit `ail_tab_put`/`ail_tab_copy` into a name declared as `ail_stab`, so the
   default build failed in gcc.  A str/bytes-keyed `set(...)` is now refused before the typed
   fill, and an int set-operator assignment refuses a destination already bound to a str/bytes
   set; the function then takes the general path and matches CPython, while `--strict` names the
   blocker.  This covers all four operators, a branch binding, tuple/list/name sources, bytes sets
   and the reverse bind order.

Both changes affect only programs that previously were refused.  The generated C of the ten
`lab/compare` tasks is byte-identical to the base commit (`AIL_IR=0`; all ten `main.ail` builds
compared); the review fix leaves those ten files byte-identical too.

## Follow-ups (left by name)

* `lab/census/programs/gdev/g15_004.py`: needs exception chaining that preserves `__cause__`, a
  scalar `ConfigError | None` local, and conditional class values.  Exact first message:
  `raise ... from ... in a program that reads __cause__, __context__ or __traceback__; the cause of an exception is not kept here`
  (then `only a class type can be None here ...` and `a conditional class value is unsupported`).
* `lab/census/programs/gdev/g25_026.py`: needs typed `Enum`/`auto()` lowering, including the
  generated `_AilIntEnum` dunder methods and module-level enum tables.  Exact first message:
  `dunder method _AilIntEnum.__lt__; only __init__ is supported here, no other dunder (__eq__, __repr__, __len__, __add__, ...)`
