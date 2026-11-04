# `re` coverage: lab/stdlib/re

Twelve ordinary programs using `re` the way application code does (log parsing, validation, templating,
CSV fields, tokenizing, phone/date normalisation, redaction and URL rewriting). Each was built with the
default mode:

```
python3 AIL_CURRENT/ail_chatgpt.py compile <program>.py --syntax python
```

`typed` means the typed path built it, `general` means the typed path refused and the general path built
it, and `refused` means neither path built it. Every built program was run and its stdout and exit code
matched CPython 3.12.

| program | result | first refusal message |
| --- | --- | --- |
| `config_parse.py` | typed | |
| `csv_fields.py` | typed | |
| `date_normalize.py` | typed | |
| `email_check.py` | typed | |
| `ip_validate.py` | typed | |
| `log_summary.py` | refused | see below |
| `phone_fix.py` | typed | |
| `redact.py` | typed | |
| `template_render.py` | typed | |
| `tokenizer.py` | typed | |
| `url_rewrite.py` | typed | |
| `word_count.py` | typed | |

11 of 12 build; all 11 match CPython's stdout and exit code on the default (`AIL_IR=1`) and `AIL_IR=0`
builds (the new test runs both).

## Reasons fixed

Before these changes 8 of the 12 were refused. The reasons, most blocking first:

1. `re.findall` with several groups (4 programs: `config_parse`, `date_normalize`, `redact`,
   `url_rewrite`) was refused because its result is a list of tuples. It now lowers to a generated
   helper that returns `list[tuple[...]]`, with `""` for a group that did not take part (CPython's
   findall rule).
2. `re.subn` with a replacement template containing a backslash (2 programs: `phone_fix`,
   `template_render`) was refused. The existing template helper now also generates the counted form
   that returns `(text, count)`.
3. `re.split` with groups (`csv_fields`) was refused because a group that did not take part is `None`.
   It now lowers to a helper that inserts each group's text between the pieces, or `None`.
4. `m.span()` used as a value (`url_rewrite`) and `m.group(1, 2)` (`redact`) were refused as tuple
   results. They now lower to a tuple of `m.start` / `m.end` or `m.group` calls, with `None` for a
   group that did not take part.

The existing `test_ail_re` refusal list was updated because findall-with-groups and split-with-groups
are now built.

## Follow-up (out of scope here)

`log_summary.py` uses `m.groupdict()`. This needs a match object to return a `dict` of the named groups
(including `None` for a group that did not take part), which is a new value shape rather than one of the
existing scalar/tuple lowerings. Exact refusal text:

```
log_summary.py:1:1: not in the subset: import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, findall, finditer, split, sub, escape, and NAME = re.compile(literal)); the notes below name the use (the general path could not build this program either); general path: the method .groupdict() (on a value of unknown static kind)
note: log_summary.py:21: m.groupdict() is not built (tuples and None groups); built are m.group(i) / m.group("name"), m.start(i), m.end(i), and `a, b = m.span()` / `a, b = m.groups()`
```
