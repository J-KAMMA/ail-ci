# jsonpp: a JSON pretty-printer and checker in plain Python

`jsonpp.py` is an ordinary Python 3.12 program with no `import json`, compiled with AIL. It reads
JSON from standard input and prints it re-indented, or checks it and prints a count line.

```
jsonpp.py [--indent N] [--sort-keys] [--compact] [--check] < input
```

| option        | meaning                                                              |
|---------------|----------------------------------------------------------------------|
| (none)        | 2-space indent, one member per line, `": "` after keys               |
| `--indent N`  | N spaces per level; `N` < 0 means newlines without indentation       |
| `--sort-keys` | members sorted by the byte order of the decoded key                  |
| `--compact`   | `,` and `:` with no spaces, all on one line                          |
| `--check`     | print `ok <objects> <arrays> <strings> <numbers> <max_depth>` only   |

## How it works

The parser is recursive descent over the text read with `sys.stdin.read()`. It builds a tree of
tuples:

```
("obj", [(key, node), ...])   object, members in source order
("arr", [node, ...])          array
("str", text)                 string, already unescaped
("num", text)                 number, kept as its source text
("lit", "true"|"false"|"null")
```

Numbers stay as their source text and are never converted, so `-0`, `1e400` and
`12345678901234567890123` are printed unchanged; nothing overflows. Duplicate object keys are kept
in order. The tree is then emitted with the requested indent, and strings are re-escaped the way
`json.dumps(..., ensure_ascii=True)` does: `\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t` for those
characters, `\uXXXX` (lowercase hex) for anything below U+0020 or above U+007E, and a surrogate
pair for a code point above U+FFFF.

`--check` counts every object, array, string (object keys included) and number, and reports the
maximum container nesting: a top-level scalar has depth 0, `{}` and `[]` have depth 1, and a child
container is one deeper than its parent.

A syntax error prints `error: line L col C: <message>` on standard error and exits 1, with the
position of the offending character. An unknown option prints a usage line on standard error and
exits 2.

## Inputs in `data/`

| input                     | what it covers                                                  |
|---------------------------|-----------------------------------------------------------------|
| `nested.json`             | nested objects and arrays, booleans and null                    |
| `empty.json`              | `{}` and `[]`, empty and nested inside other containers         |
| `escapes.json`            | every short escape, `\/`, `\u00e9`, `\u0000`, `\u007f`          |
| `surrogate.json`          | a `\u` surrogate pair and lone surrogates                       |
| `nonascii.json`           | raw UTF-8 keys and values (Latin, Japanese, Cyrillic)           |
| `numbers.json`            | `-0`, `1e400`, 23-digit integer, `1.5E-3`, exponents            |
| `depth200.json`           | 200 nested arrays                                               |
| `sort_keys.json`          | keys that sort differently from source order, nested            |
| `control_chars.json`      | `\u0001` .. `\u001f`                                            |
| `top_level_scalar.json`   | a bare string outside any container                             |
| `dup_keys.json`           | duplicate keys at two levels                                    |
| `trailing_comma.json`     | syntax error: `[1, 2, 3,]`                                      |
| `missing_colon.json`      | syntax error: `{"a" 1}`                                         |
| `bad_escape.json`         | syntax error: `"one\qtwo"`                                      |
| `unterminated_string.json`| syntax error: a string that reaches end of input                |
| `extra_data.json`         | syntax error: `{"a": 1} {"b": 2}`                               |

## Build and run

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile examples/jsonpp/jsonpp.py -o /tmp/jsonpp
/tmp/jsonpp --indent 4 --sort-keys < examples/jsonpp/data/nested.json
python3 examples/jsonpp/jsonpp.py --indent 4 --sort-keys < examples/jsonpp/data/nested.json
```

The default build falls back to the general path; the exact note and the comparison with CPython
are in [RESULTS.md](./RESULTS.md).

## Checked by hand against `python3 -m json.tool`

The default and `--indent 4 --sort-keys` output was compared with `python3 -m json.tool` and
`json.dumps` for `nested.json`, `escapes.json` and `nonascii.json`: the bytes agree. The one
deliberate difference is number formatting, because `json.tool` parses numbers into Python `int`
and `float`: `-0` becomes `0`, `1e400` becomes `Infinity`, and `1.5E-3` becomes `0.0015`. `jsonpp`
prints each number in its source spelling, which is what the task asks for.

## Limits

AIL's 16-bit `str` cannot hold a surrogate code unit and its `chr()` refuses one, so `surrogate.json`
stops the AIL builds loudly with `AIL internal error: chr() surrogate code point is unsupported`
(exit 1) where CPython prints the escaped text. The other 15 inputs match CPython exactly. The raw
non-ASCII input is BMP only, for the same reason.
