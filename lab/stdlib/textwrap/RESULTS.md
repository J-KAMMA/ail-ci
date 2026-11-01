# textwrap lab results

Build command for every program:

```
python3 AIL_CURRENT/ail_chatgpt.py compile <program>.py --syntax python -o <program>
```

All twelve programs build (12/12, no refusals) and their stdout and exit status match CPython 3.12
on the default build and on the forced general build.  Each program falls back to the general path;
the fallback note is listed below.  The three programs that only use `wrap` / `fill` / `shorten`
after the rewrite still report the helper-class note because every textwrap call now goes through
`_ail_TextWrapper`.

| program | result | first fallback note (all programs exit 0) |
| --- | --- | --- |
| `dedent_blocks.py` | general | `'text' is annotated str in the source, but the caller also supplies int` |
| `edge_errors.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `long_words.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `max_lines_notice.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `report_builder.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `shorten_titles.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `whitespace_options.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `wrap_keywords.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `wrap_paragraph.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `wrapper_flags.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `wrapper_indent.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |
| `wrapper_mutation.py` | general | `_ail_TextWrapper.__init__ must take plain positional arguments, no defaults, *args or **kwargs` |

## What was fixed

`textwrap.wrap` / `fill` / `shorten` now accept the common keyword options instead of refusing them
by name: `initial_indent`, `subsequent_indent`, `expand_tabs`, `replace_whitespace`,
`fix_sentence_endings`, `break_long_words`, `drop_whitespace`, `break_on_hyphens`, `tabsize`,
`max_lines` and `placeholder`.  `textwrap.TextWrapper` is built as a class with those attributes,
`wrap` / `fill`, and mutable fields; `from textwrap import TextWrapper` works.  The helper follows
CPython 3.12's chunking, long-word / hyphen breaking, sentence spacing and max-lines placeholder
logic.  When the same `width` is given both positionally and by keyword the call is still refused
by name, as before.

The 12 programs are registered in `AIL_CURRENT/test_ail_std_textwrap.py`; that test runs CPython as
the oracle and compares stdout and exit status on the default and general builds.

## Follow-ups (out of scope here)

* **Subclassing `textwrap.TextWrapper`.**  It still needs a class base on the general path.  Exact
  first refusal:
  `not in the subset: a non-name base class in class MyWrapper` followed by
  `note: textwrap.TextWrapper used as a value is not built; ... subclassing and the private methods are not`.
* **The typed fast path for `textwrap`.**  All textwrap calls currently take the general path
  because the injected `_ail_TextWrapper.__init__` has default arguments.  This is a performance
  note, not a refusal: the programs build and match CPython.
* **`wordsep_re=` and the other regex tuning attributes.**  Not among the common options; the
  constructor call is refused with
  `not in the subset: _ail_TextWrapper() called with an unknown keyword argument wordsep_re`.
