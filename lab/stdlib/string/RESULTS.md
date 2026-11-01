# `string` coverage results

Twelve programs in this directory, built with the default command
`ail_chatgpt.py compile X.py --syntax python`.  Every built program was also run and compared with
CPython 3.12 (stdout and exit code), on the default and forced-general (`AIL_UNIFIED_FORCE=1`)
paths; all match.

## Before the fixes

Six programs built (the constants-only ones); six were refused:

- `string.capwords(...)` with the `sep=` keyword (and with `s=`): 3 programs
  (`slugify`, `name_formatter`, `initials`).
- `string.Template`: 2 programs (`template_email`, `template_config`).
- `string.Formatter`: 1 program (`formatter_table`).

The first refusal for the capwords-keyword group was
`not in the subset: string.capwords() with these arguments is not built`; for the Template group,
`not in the subset: string.Template() with these arguments is not built`.

## Final result

| program | result | first refusal / first general-path reason |
| --- | --- | --- |
| `word_stats.py` | general | `word_stats.py:23:5: built on the general path ... with key= columns (sorted/sort/d.items()): counts.keys() cannot be walked inline here` |
| `slugify.py` | general | `slugify.py:15:5: built on the general path ... 'raw' is an int and is being assigned a str` |
| `password_rules.py` | typed | - |
| `name_formatter.py` | general | `name_formatter.py:7:22: built on the general path ... the default for 'sep' must be a compile-time int, float or bool constant` |
| `csv_punctuation_report.py` | general | `csv_punctuation_report.py:17:9: built on the general path ... clean() where a str is needed` |
| `identifier_check.py` | typed | - |
| `hex_parser.py` | general | `hex_parser.py:7:5: built on the general path ... 'text' is a parameter and cannot be reassigned` |
| `text_sanitizer.py` | general | `text_sanitizer.py:24:9: built on the general path ... sanitize() where a str is needed` |
| `initials.py` | general | `initials.py:12:20: built on the general path ... the default for 'sep' must be a compile-time int, float or bool constant` |
| `template_email.py` | general | `template_email.py:10:1: built on the general path ... *args, **kwargs, positional-only and keyword-only parameters are refused` |
| `template_config.py` | general | `template_config.py:11:5: built on the general path ... passing ('obj', '_AilStringTemplate') where _ail_tpl_is_valid() wants int` |
| `formatter_table.py` | refused | `formatter_table.py:1:1: not in the subset: string.Formatter() with these arguments is not built (see the note below)` |

11 of 12 build and match CPython.  The general-path reasons above are advisory notes, not refusals;
the default build falls back to the general path for those programs.

## What was changed

- `ail_syntax.py` now accepts `string.capwords(s, sep)` with either argument passed as a keyword
  (`s=` / `sep=`), including `sep=None`, runtime separators and the existing error cases.
- `string.Template` is lowered to a small prelude object: `substitute`, `safe_substitute`,
  `is_valid`, `get_identifiers`, the `template` attribute and `$$` / `$name` / `${name}` are
  built.  Missing keys raise `KeyError`, invalid placeholders raise CPython's
  `ValueError: Invalid placeholder in string: line L, col C`, and `safe_substitute` keeps invalid
  or missing placeholders as written.  Keyword substitution values override a positional mapping,
  as CPython's `ChainMap` does.  A subclass of `string.Template` is still refused by name.
- `test_ail_stdlib1.py`'s old "string template is refused" case now checks `string.Formatter`
  instead.

## Follow-up (out of scope: a new class)

`string.Formatter` is not built.  The exact refusal is:

```
formatter_table.py:1:1: not in the subset: string.Formatter() with these arguments is not built (see the note below)
note: formatter_table.py:5: string.Formatter() with these arguments is not built; the string module is built as its constants (ascii_lowercase, ascii_uppercase, ascii_letters, digits, hexdigits, octdigits, punctuation, whitespace, printable), capwords() and the Template class with substitute / safe_substitute / is_valid / get_identifiers
```

Implementing `Formatter` means its `parse` / `format` / `vformat` / `get_field` / `get_value` /
`convert_field` / `format_field` protocol (nested fields, conversion flags, format specs) as a new
class; that is a larger feature than the Template lowering above.
