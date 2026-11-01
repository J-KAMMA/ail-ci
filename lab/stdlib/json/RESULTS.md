# `json` stdlib coverage: 12 realistic programs

Build command (default mode, typed path first, general path as the fallback):

    python3 AIL_CURRENT/ail_chatgpt.py compile <program>.py --syntax python -o <program>

The first census already built 10 of the 12 programs, so the 9/12 target was met without a
compiler, runtime or prelude change. Every built program is compared with CPython 3.12 by
`AIL_CURRENT/test_ail_std_json.py` (stdout and exit code).

| # | Program | Result | First refusal (if refused) |
|---|---------|--------|----------------------------|
| 01 | `01_config_roundtrip.py` | general | |
| 02 | `02_api_response.py` | general | |
| 03 | `03_jsonl_stats.py` | general | |
| 04 | `04_encoder_custom.py` | refused | `04_encoder_custom.py:18:5: not in the subset: json.dumps(..., cls=...) is not built (built: indent, sort_keys, separators, ensure_ascii, allow_nan) (the general path could not build this program either); general path: json.dumps() with the keyword argument cls is not built on the general path` |
| 05 | `05_decoder_hooks.py` | general | |
| 06 | `06_stdio_typed.py` | typed | |
| 07 | `07_decode_error.py` | general | |
| 08 | `08_nested_typed.py` | typed | |
| 09 | `09_numbers.py` | general | |
| 10 | `10_unicode_text.py` | typed | |
| 11 | `11_pretty_options.py` | general | |
| 12 | `12_dump_file.py` | refused | `12_dump_file.py:3:1: not in the subset: 'RECORDS' is a module-level list of non-numbers; only an int/float/str/bytes literal, or a numeric list or tuple, is accepted as a module constant (the general path could not build this program either); general path: json.load(f): only json.load(sys.stdin) is built on the general path; json.loads(f.read()) is the form for another file` |

Built: **10 / 12** (2 typed, 8 general). Refused: 2.

## Follow-ups (out of scope here: each needs a new feature)

1. `04_encoder_custom.py`: `json.JSONEncoder` subclasses and the `cls=` argument. This needs a
   callable encoder object (and `default=`) on the typed path, and a `JSONEncoder` equivalent on
   the general path. Exact refusal:
   `json.dumps(..., cls=...) is not built (built: indent, sort_keys, separators, ensure_ascii, allow_nan)`
   (typed) / `json.dumps() with the keyword argument cls is not built on the general path`.
2. `12_dump_file.py`: `json.dump(obj, f)` / `json.load(f)` for a file object, plus a module-level
   list of dicts and writing through a `with open(...) as f:` handle. The general path only rewrites
   `json.load(sys.stdin)`; the typed path only accepts `json.dump(obj, sys.stdout)`. Exact refusal:
   `json.load(f): only json.load(sys.stdin) is built on the general path; json.loads(f.read()) is the form for another file`,
   with the typed-path module-constant refusal quoted in the table above.
