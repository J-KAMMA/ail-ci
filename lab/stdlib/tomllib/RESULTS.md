# toml1: `import tomllib` as a bundled AIL package

Lane: toml. Branch `job-toml1-11041630`, base `origin/integ` (`612b780`).
The twelve programs in `lab/stdlib/tomllib/` each parse a TOML string with
`tomllib.loads` (or `tomllib.load` on a `BytesIO`-like reader) and print the
result the way ordinary Python does.

"typed" means the default build with no fallback note, "general" means the
build printed `note: ... built on the general path ...`, "refused" means the
default build stopped with `not in the subset` (exit 3).

## Before (integ 612b780)

The AIL tree has no `tomllib`; CPython 3.12's `Lib/tomllib` was copied next
to each program and the program was built with the default command.

| program | result | first refusal |
| --- | --- | --- |
| 01_scalars | refused | `not in the subset: a required keyword-only parameter recursive in def set (this cut requires every keyword-only parameter to have a default)` |
| 02_tables | refused | same |
| 03_arrays | refused | same |
| 04_datetimes | refused | same |
| 05_parse_float | refused | `not in the subset: datetime.datetime() with the keyword argument tzinfo is not built on the general path` |
| 06_config | refused | `not in the subset: a required keyword-only parameter recursive in def set ...` |
| 07_load_bytes | refused | same |
| 08_errors | refused | same |
| 09_big_int | refused | same |
| 10_multiline | refused | same |
| 11_keys | refused | same |
| 12_inline_arrays | refused | same |

Before: **0 of 12**.

## After (branch job-toml1-11041630)

`AIL_CURRENT/stdlib/tomllib/` is a hand-rewritten port with CPython's
messages and positions (see the docstring of `__init__.py` for the rewrites).

| program | default | `AIL_UNIFIED_FORCE=1` | path |
| --- | --- | --- | --- |
| 01_scalars | matches, exit 0 | matches, exit 0 | general |
| 02_tables | matches, exit 0 | matches, exit 0 | general |
| 03_arrays | matches, exit 0 | matches, exit 0 | general |
| 04_datetimes | output differs | output differs | general |
| 05_parse_float | matches, exit 0 | matches, exit 0 | general |
| 06_config | matches, exit 0 | matches, exit 0 | general |
| 07_load_bytes | matches, exit 0 | matches, exit 0 | general |
| 08_errors | refused | refused | - |
| 09_big_int | output differs | output differs | general |
| 10_multiline | output differs | output differs | general |
| 11_keys | matches, exit 0 | matches, exit 0 | general |
| 12_inline_arrays | matches, exit 0 | matches, exit 0 | general |

After: **8 of 12** build and match CPython in both builds.

The eight passers take the general path because a parser result that can
hold booleans next to numbers (`[pos + 5, value]` in `_parse_value`) is
reported as "`[pos + 5, value]` mixes bools and numbers ... built on the
general path (about 20x slower)". That is a performance note, not a
refusal; the values are correct.

### Build time

`AIL_NO_CACHE=1`, median of 3, default build:

| program | median |
| --- | --- |
| `hello.py` (`print("hello")`) | 0.21 s |
| `lab/stdlib/tomllib/01_scalars.py` | 18.6 s |

Both are dominated by compiling the package (the general path is ~20x slower
at run time, but the build cost here is the package's size).

## Failures and ranked follow-ups

Ranked by how many of the twelve each blocks (all four block one program).

1. **`datetime.time` is not built** (blocks `04_datetimes`). Exact refusal:
   `not in the subset: datetime.time is not built on the general path`.
   Related, same program: `datetime.datetime` values print
   `type(v).__name__` as `_AilDT` rather than `datetime`/`date`, so the
   program's type-name lines cannot match even if `time` were built.
   The parser already returns local times as their source text instead of
   calling `datetime.time`, so the rest of the package builds.
2. **`issubclass` is not a known builtin** (blocks `08_errors`). Exact
   refusal: `not in the subset: the name 'issubclass' is not a known
   function/class/builtin; did you mean 'issubclass'?`. The package's
   `TOMLDecodeError` messages themselves match CPython (probed for the
   duplicate-key, unclosed-string, invalid-value, duplicate-table,
   unclosed-array, duplicate-inline-key and leading-zero cases).
3. **Non-BMP characters** (blocks `10_multiline`). Exact runtime stop:
   `AIL limit: chr_non_bmp` for `"\U0001F600"`. The multi-line, escape and
   line-ending-backslash parts of the program match before that point.
4. **Integers beyond int64** (blocks `09_big_int`). Exact runtime stop:
   `OverflowError: integer overflow in int() (ints are 64-bit; --exact-int
   gives exact ints)`. CPython prints the exact integer; the program stops
   loudly, as the task allows.
