# `enum` coverage (2026-11-01)

Twelve realistic programs, each compiled in the default mode:

    AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python -o X

`general` means the compiler selected the general path (each `enum` lowering makes one). The first
refusal line is recorded for a refused program; the `note:` lines are the precise reason.

| Program | Result | First refusal |
| --- | --- | --- |
| `empty_registry.py` | general | |
| `error_codes.py` | general | |
| `feature_flags.py` | general | |
| `file_modes.py` | general | |
| `http_status.py` | general | |
| `log_levels.py` | general | |
| `permissions.py` | general | |
| `planet_data.py` | general | |
| `traffic_light.py` | general | |
| `dynamic_enum.py` | refused | `p.py:1:1: not in the subset: import of 'enum' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: enum.Enum (not yet published in NAMES_library.json)` |
| `planet_init.py` | refused | `p.py:5:5: not in the subset: class attribute Planet.MERCURY = (3.301e+23, 2439700.0); a class attribute here is an int, float, str or bool literal (the general path could not build this program either); general path: class Planet bases on Enum, defined after it or unknown` |
| `status_registry.py` | refused | `p.py:1:1: not in the subset: import of 'enum' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path could not build this program either); general path: class Status bases on Enum, defined after it or unknown` |

Nine of twelve build and print CPython's stdout with CPython's exit code; `test_ail_std_enum.py`
compiles and compares them.

## Fixed while writing the programs

* `StrEnum` members forward the ordinary string methods (`upper`, `lower`, `title`, `replace`,
  `startswith`, `strip`, `split`, `join`, ...), indexing, containment, repetition and `<=`/`>=`.
* `IntEnum` members implement `**` and reflected `**` (`Status.OK ** 2`, `2 ** small_member`).
* Chained assignment in an enum body (`MISSING = ALSO_MISSING = 404`) makes the later name an alias,
  including `auto()` on the right and mixed member/alias order in `__members__`; `B = A` aliases an
  earlier member by name.
* `auto()` uses the largest previous int value plus one, as CPython 3.12's default does (it used the
  last literal value, which diverges after a descending value).
* An empty enum builds; calling it with one value raises CPython's
  `TypeError: <enum 'NoModes'> has no members; specify \`names=()\` if you meant to create a new, empty, enum`.
* `value in EnumClass` follows CPython's value lookup for `Enum`, `IntEnum` and `StrEnum` (it was
  identity-only before), not only for `Flag`/`IntFlag`; an unhashable value raises `TypeError`.

## Follow-ups (a big new feature each; left refused)

* `status_registry.py`, class methods on an enum:

      note: p.py:9: enum class Status: the decorator on from_code is not built

  The general path supports `@classmethod`, but an enum classmethod that iterates or calls `cls`
  needs the class receiver lowered to that class's generated member list/call helper.

* `planet_init.py`, members defined through `__init__`:

      note: p.py:8: enum class Planet: __init__ is not built (members take plain values)

  This needs member creation to call `__new__`/`__init__` with the unpacked value and to keep the
  attributes they set.

* `dynamic_enum.py`, the functional API:

      note: p.py:4: enum.Enum used here is not built: Enum, IntEnum, StrEnum, Flag, IntFlag, auto and unique are built

  This needs `Enum("Name", names)` to build a class at run time from a string, list of pairs or dict.

Each fix above is in the compiler/library lowering (`AIL_CURRENT/python/pkg-v12/enumlib.py` and
`prelude_enum.py`), never in the programs.
