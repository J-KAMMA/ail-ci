# `base64` coverage

Twelve realistic programs using the CPython 3.12 `base64` module, built with the default command
`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python`. `typed` means the default build
used the typed path; `general` means it fell back to the general path (the note in the build log
says why); `refused` means the build stopped.

| program | result | note |
| --- | --- | --- |
| `basic_roundtrip.py` | general | module-level `SAMPLES` list of bytes |
| `basic_auth.py` | typed | HTTP Basic header, `b64encode` / `b64decode` |
| `url_token.py` | general | `bytes(range(...))` |
| `json_payload.py` | general | a `str` token name is not statically bytes |
| `altchars_filesystem.py` | general | `bytes(range(...))` |
| `mime_lines.py` | general | `bytes(range(...))` |
| `hex_codec.py` | general | prelude bytes parameter seen with a second type |
| `base32_ids.py` | general | prelude bytes parameter seen with a second type |
| `strict_validation.py` | general | `print()` of bytes is not built on the typed path |
| `chunked_stream.py` | typed | chunked `b64encode`, `encodebytes` / `decodebytes` |
| `b85_vectors.py` | refused | follow-up, see below |
| `legacy_stream_api.py` | refused | follow-up, see below |

All ten built programs print exactly what CPython 3.12.3 prints and return the same exit code.
`AIL_CURRENT/test_ail_std_base64.py` checks every one on both `AIL_IR` builds and also pins the two
refusals.

## What was fixed

* `base64.b64encode(s, altchars=...)` and `base64.b64decode(s, altchars=..., validate=...)`
  (bytes or ASCII `str` altchars).
* `base64.b16encode` / `base64.b16decode` (including `casefold`).
* `base64.b32encode` / `base64.b32decode` (including `casefold`; `map01` stays refused).
* `base64.encodebytes` / `base64.decodebytes`.
* A `validate=` flag that is a run-time `bool`, not only a literal in the program text.
* The decoders now raise a `ValueError` subclass named `Error`, matching the class name of
  CPython's `binascii.Error`; a user binding named `Error` is refused by name instead of silently
  shadowing it.
* `_strish` no longer treats `bytes.lower()` / `bytes.upper()` as a `str` result.

## Follow-ups (out of scope here)

### `b85_vectors.py` -- b85/a85 codecs

First refusal (default build):

```
b85_vectors.py:6:9: not in the subset: base64.b85encode is not built (the general path could not build this program either); general path: base64.b85encode is not built.
  write instead: not built
```

`base64.b85encode`, `base64.b85decode`, `base64.a85encode` and `base64.a85decode` (with the
`adobe`, `foldspaces`, `wrapcol` and `pad` options) are not built. This needs the two new codec
families, so it is left as a follow-up.

### `legacy_stream_api.py` -- `base64.encode` / `base64.decode`

First refusal (default build):

```
legacy_stream_api.py:7:5: not in the subset: base64.encode is not built (the general path could not build this program either); general path: base64.encode is not built.
  write instead: not built
note: legacy_stream_api.py:6: io.BytesIO used here is not built: io.StringIO(text) is the form that is built
```

The deprecated file-object API (`base64.encode(input, output)` / `base64.decode(input, output)`)
needs binary `io.BytesIO` support, which is a larger feature; it is left as a follow-up.
