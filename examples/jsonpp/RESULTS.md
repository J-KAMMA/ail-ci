# jsonpp results

- Date: 2026-11-05
- App commit: `8f48578` (`examples/jsonpp/jsonpp.py`, 482 lines)
- Oracle: CPython 3.12 on the same source
- Host: GitHub Actions runner, Linux, 4 cores

## Build path

Default build:

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/jsonpp/jsonpp.py -o /tmp/jsonpp_def
```

It builds on the **general path** (not a refusal). The exact note is:

```
note: built on the general path (about 20x slower) because Parser__peek returns a str on one path and something else on another; a str and a number have no single C return type, and a str and bytes are separate types that never mix (SEMANTICS.md section 31); run with --strict to see why
```

The cause is `Parser.peek()` returning `""` at end of input and a one-character `str`
otherwise, which AIL cannot give a single C return type. The app is written the way a
Python user writes it, so it was not annotated to force the typed path.

`AIL_UNIFIED_FORCE=1` produced a byte-identical binary:
`sha256 b459e9b7efd1537dcf01e2d0e50f00eff578b589bb94fd603066fe5267a64e8a`,
546,272 bytes. Both modes therefore run the same general path.

## Comparison with CPython

Each of the 16 inputs in `data/` was run in four option sets — default,
`--indent 4 --sort-keys`, `--compact` and `--check` — once as
`python3 -B examples/jsonpp/jsonpp.py` and once through `/tmp/jsonpp_def` (default build) and
`/tmp/jsonpp_uni` (`AIL_UNIFIED_FORCE=1`). Standard output, the last line of standard error and
the exit status were compared byte for byte.

The table has one row per input; the eight result columns are the four option sets for the
default build and then the same four for the forced build.

| Input | exit | stdout lines (max) | def: default | def: indent4+sort | def: compact | def: check | forced: default | forced: indent4+sort | forced: compact | forced: check |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bad_escape.json` | 1 | 0 | yes | yes | yes | yes | yes | yes | yes | yes |
| `control_chars.json` | 0 | 3 | yes | yes | yes | yes | yes | yes | yes | yes |
| `depth200.json` | 0 | 401 | yes | yes | yes | yes | yes | yes | yes | yes |
| `dup_keys.json` | 0 | 10 | yes | yes | yes | yes | yes | yes | yes | yes |
| `empty.json` | 0 | 11 | yes | yes | yes | yes | yes | yes | yes | yes |
| `escapes.json` | 0 | 14 | yes | yes | yes | yes | yes | yes | yes | yes |
| `extra_data.json` | 1 | 0 | yes | yes | yes | yes | yes | yes | yes | yes |
| `missing_colon.json` | 1 | 0 | yes | yes | yes | yes | yes | yes | yes | yes |
| `nested.json` | 0 | 34 | yes | yes | yes | yes | yes | yes | yes | yes |
| `nonascii.json` | 0 | 7 | yes | yes | yes | yes | yes | yes | yes | yes |
| `numbers.json` | 0 | 9 | yes | yes | yes | yes | yes | yes | yes | yes |
| `sort_keys.json` | 0 | 19 | yes | yes | yes | yes | yes | yes | yes | yes |
| `surrogate.json` | 0 | 6 | **no** | **no** | **no** | **no** | **no** | **no** | **no** | **no** |
| `top_level_scalar.json` | 0 | 1 | yes | yes | yes | yes | yes | yes | yes | yes |
| `trailing_comma.json` | 1 | 0 | yes | yes | yes | yes | yes | yes | yes | yes |
| `unterminated_string.json` | 1 | 0 | yes | yes | yes | yes | yes | yes | yes | yes |

**Score: 15 of 16 inputs match CPython in all four option sets and both builds**
(120 of 128 individual runs). The target was 14 of 16.

### The one mismatch: `surrogate.json`

This is a loud stop, not silent wrong output. CPython prints the escaped text and exits 0;
both AIL builds print nothing on stdout and this on stderr, exiting 1:

```
AIL internal error: chr() surrogate code point is unsupported
```

Input:

```json
{"pair": "\ud83d\ude42", "lone_high": "\ud800", "lone_low": "\udfff", "mixed": "a\ud83d\ude42b"}
```

CPython output (what `jsonpp.py` prints under CPython):

```
{
  "pair": "\ud83d\ude42",
  "lone_high": "\ud800",
  "lone_low": "\udfff",
  "mixed": "a\ud83d\ude42b"
}
```

AIL's `str` is 16 bits and its `chr()` refuses a surrogate code unit, so `\uD800`..`\uDFFF`
cannot be decoded at run time. This is a runtime limit, not a compiler refusal: the build
succeeds. The app is unchanged; `README.md` records the limit.

## Spelling changes made

None. The program compiled as written; the only build message is the general-path note above.
No behaviour was changed to dodge a refusal.

## Probes (beyond the 16 inputs)

Each probe was run as `python3 examples/jsonpp/jsonpp.py` and as both builds, comparing stdout,
stderr and exit status:

| Probe | Covers | Result |
| --- | --- | --- |
| `p_empty_string.json` (default, `--compact`) | empty key and value, nested empty containers | match, both builds |
| `p_int64.json` (default, `--check`, `--indent 0`, `--indent -1`) | int64 max/min, +1, a 27-digit integer | match, both builds (numbers kept as text) |
| `p_exponent.json` (default, `--compact`) | `0e0`, `-0.0`, `1E+2`, `1e-2`, `1E-999`, `5.` (error) | match, both builds |
| `p_unicode_boundaries.json` (default, `--indent 0`) | `\u001f`, `\u0020`, `\u007e`, `\u007f`, `\u0080`, `\u00ff`, `\u0100`, `\uffff` | match, both builds |
| `p_sort_dups.json` (`--sort-keys`, `--sort-keys --compact`) | stable sort with duplicate keys, leading/trailing whitespace | match, both builds |
| `p_empty_input.json` | empty stdin | match, both builds (exit 1) |
| `p_whitespace.json` | whitespace-only stdin | match, both builds (exit 1) |
| `p_top_level_number.json` (`--check`) | scalar at top level, depth 0 | match, both builds |
| `p_controls.json` (default, `--compact`) | tab and `\u0000` inside a string | match, both builds |
| argument probes | `--indent` with no value, `x`, `-1`, 26 digits, `--bogus`, `--indent 0 --compact` | match, both builds (exit 2 for the bad ones) |

Total: 34 document/option cases plus 12 argument cases, all matching in both builds.

## Follow-ups

1. **Surrogate code units (runtime limit).** Recorded above; needs a `str` that can hold a code
   unit above U+00FF..U+FFFF, which is the runtime's business, not this example's.
2. **General path (not a refusal).** Forcing the typed path would need `peek()` to return a
   sentinel that is not a `str`, which would make the program less like ordinary Python.
