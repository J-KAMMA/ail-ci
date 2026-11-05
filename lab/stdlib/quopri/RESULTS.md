# `quopri` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/quopri/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). The programs use fixed inputs from their own
source; none reads stdin or a file.

## Before

Every program was refused at its first `quopri` call. The common first-refusal forms are:

```
lab/stdlib/quopri/<program>.py:<line>:<col>: not in the subset: quopri.encodestring (not yet published in NAMES_library.json)
lab/stdlib/quopri/<program>.py:<line>:<col>: not in the subset: quopri.decodestring (not yet published in NAMES_library.json)
```

| program | default build | first refusal after the location |
| --- | --- | --- |
| `01_ascii_roundtrip.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `02_equals_and_controls.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `03_high_bytes.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `04_all_bytes_roundtrip.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `05_quotetabs.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `06_header.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `07_long_lines.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `08_decode_escapes.py` | refused | `quopri.decodestring (not yet published in NAMES_library.json)` |
| `09_crlf.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |
| `10_large.py` | refused | `quopri.encodestring (not yet published in NAMES_library.json)` |

Result before: **0 built, 0 typed, 10 refused**.

## After

All ten build and match CPython in the default build and with `AIL_UNIFIED_FORCE=1`. Every one uses
the general path: the typed path cannot pin the return kind of `needsquoting`, which returns a bool
on some paths and a number on others (the build note points at `needsquoting`). `AIL_CURRENT/test_ail_std_quopri.py` builds each one in both
builds and compares stdout and the exit status with `python3`.

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_ascii_roundtrip.py` | general | general | yes |
| `02_equals_and_controls.py` | general | general | yes |
| `03_high_bytes.py` | general | general | yes |
| `04_all_bytes_roundtrip.py` | general | general | yes |
| `05_quotetabs.py` | general | general | yes |
| `06_header.py` | general | general | yes |
| `07_long_lines.py` | general | general | yes |
| `08_decode_escapes.py` | general | general | yes |
| `09_crlf.py` | general | general | yes |
| `10_large.py` | general | general | yes |

Result after: **10 built, 0 typed, 0 refused; 10 build and match**.

## Module notes

`AIL_CURRENT/stdlib/quopri.py` keeps the public names `needsquoting`, `quote`, `encodestring`,
`decodestring`, `ishex` and `unhex`, plus `ESCAPE`, `MAXLINESIZE`, `HEX` and `EMPTYSTRING`. Per the
brief it drops the optional `from binascii import a2b_qp, b2a_qp` import and the `main()`
command-line tool, and records the PSF license in the module docstring. `io.BytesIO` is not built
by this compiler, so CPython's file-object `encode`/`decode` are omitted (also noted in the
docstring); `encodestring`/`decodestring` do their own line handling.

CPython's installed `quopri` answers through the `binascii` accelerator, which differs from the
pure-Python fallback in CR/CRLF handling, trailing whitespace at a line end and a trailing `=` on
decode. The module reproduces the accelerator's documented behaviour so that compiled programs
print exactly what `python3` prints; independent probes over all 256 byte values, CR/CRLF inputs,
76/77-character lines, `quotetabs` and `header` combinations, bad escapes and soft breaks agree.

## Follow-ups

None needed: all ten programs build and match. The default build reports `general path` for every
program; making bytes-heavy helpers typed is a compiler follow-up, not a `quopri` refusal.
