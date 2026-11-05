# `nturl2path` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/nturl2path/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). The programs need no command-line
arguments. Each prints `repr()` of every result; the two error programs catch `OSError` and print
`str(e)`.

## Before

No bundled model or source for `nturl2path` existed. Every program was refused at the first call,
in the default build and with `AIL_UNIFIED_FORCE=1`, with the same one-line message:

```
not in the subset: nturl2path.url2pathname (not yet published in NAMES_library.json)
```

(the `pathname2url` programs say `nturl2path.pathname2url`).

| program | default build | first refusal |
| --- | --- | --- |
| `01_url2pathname_drive.py` | refused | `nturl2path.url2pathname (not yet published in NAMES_library.json)` |
| `02_url2pathname_unc.py` | refused | `nturl2path.url2pathname (not yet published in NAMES_library.json)` |
| `03_url2pathname_relative.py` | refused | `nturl2path.url2pathname (not yet published in NAMES_library.json)` |
| `04_url2pathname_escapes.py` | refused | `nturl2path.url2pathname (not yet published in NAMES_library.json)` |
| `05_pathname2url_drive.py` | refused | `nturl2path.pathname2url (not yet published in NAMES_library.json)` |
| `06_pathname2url_unc.py` | refused | `nturl2path.pathname2url (not yet published in NAMES_library.json)` |
| `07_pathname2url_relative.py` | refused | `nturl2path.pathname2url (not yet published in NAMES_library.json)` |
| `08_errors_url.py` | refused | `nturl2path.url2pathname (not yet published in NAMES_library.json)` |
| `09_errors_path.py` | refused | `nturl2path.pathname2url (not yet published in NAMES_library.json)` |
| `10_roundtrip.py` | refused | `nturl2path.pathname2url (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 10 refused**.

## After

`AIL_CURRENT/stdlib/nturl2path.py` is CPython 3.12's `Lib/nturl2path.py` with the two functions
and every error text unchanged. Two compiler facts shaped it:

* An `import` inside a function is refused, and moving `import urllib.parse` to the top of the
  file is not enough: urllib is built on the typed path only, so a program built with
  `AIL_UNIFIED_FORCE=1` refuses the whole module with `urllib is built on the typed path only
  (bytes and the exception records are not on the general path)`. The module therefore carries
  its own `_quote`/`_unquote`, holding `urllib.parse.quote` (UTF-8, `safe='/'`) and
  `urllib.parse.unquote` (UTF-8, `errors='replace'`) rules; it was compared with `urllib.parse`
  on 91 URL/path inputs and a codec corpus (invalid escapes, overlong forms, surrogates, four
  byte UTF-8, empty strings) with zero differences.
* The typed path refuses rebinding a parameter, so each function copies `url`/`p` into a local.
  The typed-only build (`AIL_NO_GENERAL=1`) is still not built: it has no `ord()`. That is not a
  regression, and the default build and `AIL_UNIFIED_FORCE=1` both build every program.

Each program was compiled in the default build and with `AIL_UNIFIED_FORCE=1`, then run beside
`python3` on the same source. All ten pass in both builds; the default build reaches them through
the general path and prints the usual `note: ... built on the general path ...` on stderr (stdout
and the exit status still match).

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_url2pathname_drive.py` | general | general | yes |
| `02_url2pathname_unc.py` | general | general | yes |
| `03_url2pathname_relative.py` | general | general | yes |
| `04_url2pathname_escapes.py` | general | general | yes |
| `05_pathname2url_drive.py` | general | general | yes |
| `06_pathname2url_unc.py` | general | general | yes |
| `07_pathname2url_relative.py` | general | general | yes |
| `08_errors_url.py` | general | general | yes |
| `09_errors_path.py` | general | general | yes |
| `10_roundtrip.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 10 build and match** in both builds. The test is
`AIL_CURRENT/test_ail_std_nturl2path.py` (registered in `AIL_CURRENT/tests.d/`).

The `\\\\?\\` prefix strips down to `Bad path: foo` and `Bad path: ab`, and `Bad URL:` prints the
text after `:` became `|`, exactly as CPython does (`09_errors_path.py`, `08_errors_url.py`).
