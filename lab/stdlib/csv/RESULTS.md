# csv programs: build results

Built with `python3 AIL_CURRENT/ail_chatgpt.py compile <program> --syntax python -o <exe>` (default
mode). "general" means the build succeeded but the compiler printed its `built on the general path`
note; "typed" would mean no such note. Every built program's stdout and exit code were compared with
CPython 3.12.

| program | result | first refusal message |
| --- | --- | --- |
| `basic_roundtrip.py` | general | |
| `dialect_options.py` | general | |
| `dict_reader.py` | general | |
| `dict_writer.py` | general | |
| `empty_and_none.py` | general | |
| `error_handling.py` | general | |
| `file_roundtrip.py` | general | |
| `nonnumeric.py` | general | |
| `quoting_modes.py` | general | |
| `field_size_limit.py` | refused | `not in the subset: csv.field_size_limit (not yet published in NAMES_library.json)` |
| `register_dialect.py` | refused | `not in the subset: csv.register_dialect (not yet published in NAMES_library.json)` |
| `sniffer.py` | refused | `not in the subset: csv.Sniffer (not yet published in NAMES_library.json)` |

9 of 12 build and match CPython.

## Fixed

* `io.StringIO(text)` used as a csv source is turned into a list of lines by `smalllib5.py`. It now
  splits on `"\n"` only (as StringIO's iteration does) instead of `splitlines(True)`, so a lone `"\r"`
  reaches the csv parser and CPython's `csv.Error` is raised at the same point. This is done for both
  literal text (a literal list) and text only known at run time (a list comprehension).
* `csvlib.py` no longer lowers `next(reader, None)` used directly as a value: its list lowering has no
  `None`, so it would print `[]`; refusing it lets the Python-source csv (the general path) return
  `None` as CPython does. `X = next(reader, None)` with `X is None` tests is unchanged.
* `filelib_prelude.py` / `filelower.py`: the general path's `_AilTextIO` gains a generator
  `__iter__` over its lines (injected only when the boxed general path lowers files, so the typed
  path's class and its dunder check are unchanged), and the general-path csv reader can read an open
  text file. `list(file)` in user code was already lowered to `readlines(-1)` by `filelower.py`.

## Follow-ups (big new features, left refused)

* `csv.field_size_limit()`: exact refusal
  `not in the subset: csv.field_size_limit (not yet published in NAMES_library.json)`.
  Needs a per-reader field-size limit in the csv lowering and prelude.
* `csv.register_dialect()`: exact refusal
  `not in the subset: csv.register_dialect (not yet published in NAMES_library.json)`.
  Needs named dialect registration and lookup (the same gap as `csv.Dialect` subclasses).
* `csv.Sniffer`: exact refusal
  `not in the subset: csv.Sniffer (not yet published in NAMES_library.json)`.
  Needs the delimiter/quote sniffing heuristic and a dialect value that readers accept.
