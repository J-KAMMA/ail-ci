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

(To be filled in after the module and the test run.)
