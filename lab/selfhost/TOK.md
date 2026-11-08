# shtok1: a Python 3.12 tokenizer written in AIL

Measured 2026-11-06 on branch `job-shtok1-op1106` (base `origin/integ` 8c2c99c18), WSL Ubuntu 24.04,
Python 3.12.3, gcc 13.3 `-O2`.  Measurement only; no compiler file was edited.

- `selfhost/src/ailtok.py`: `tokenize(text) -> list[Tok]`; a `Tok` holds type name, string, start
  row/col and end row/col.  It imports nothing.
- `selfhost/ref/tok_ref.py` (stage 0, CPython `tokenize.generate_tokens`), `selfhost/drv/tok_drv.py`
  (stage 1 under CPython, stage 2 as the AIL build).  Dump: `TYPE r1,c1 r2,c2 repr(string)`, OP tokens
  by exact type.  Files are read with `newline=""`, so CRLF reaches both tokenizers.
- `tools/selfhost_diff.py --ref CMD --cand CMD --list LIST --jobs 2` counts identical, different,
  refused and missing files.  A candidate that dies on a file is restarted after it, and that file is
  counted refused with the exit line.

## Results

| corpus | files | stage 1 = stage 0 | stage 2 = stage 1 | stage 2 refused | different |
|---|---:|---:|---:|---:|---:|
| S376 (`selfhost/CORPUS.txt`) | 376 | 376 | 376 | 0 | 0 |
| every `.py` under `AIL_CURRENT`, `lab/pyproof` (+ `programs.txt`), the 197 `lab/stdcensus` stdlib modules | 1625 | 1625 | 1542 | 83 | 0 |

No file gives wrong output at either stage.  The 83 stage-2 refusals are all files that hold a code
point above U+FFFF (all 83 checked), and every one stops with the same line:

    AIL internal error: stdin code point above U+FFFF in the 16-bit v2 runtime

Edge cases (in `AIL_CURRENT/test_ail_selfhost_tok.py`, stage 1 and stage 2): nested f-strings, `{{`/`}}`,
`!r`, nested format specs, `=` debug fields, `\N{...}`, same-quote nesting, every string prefix in any
case, triple quotes, backslash and implicit continuation, tabs, form feed, CRLF, non-ASCII identifiers,
numbers with underscores / complex / exponents, `:=`, `->`, `...`, a comment at end of file, no final
newline, a whitespace-only last line, the empty file.  Mutations of all S376 files (CRLF, no final
newline, a trailing comment, 4-space indents turned into tabs) also match stage 0, except inputs with
a lone carriage return, which ailtok refuses by name (`a carriage return not followed by a newline is
not supported`); CPython itself rejects or mis-positions those.

## Build

`AIL_PATH=selfhost/src python3 -B AIL_CURRENT/ail_chatgpt.py compile selfhost/drv/tok_drv.py -o tok_drv`
builds on the **general** path (24.5 s, 39 MB peak RSS for the build, 570,184-byte binary):

    note: built on the general path (about 20x slower) because ailtok.Tokenizer.toks would hold a
    list, set or dict; a field is int64, float or bytes only (SEMANTICS.md section 25)

`--strict` names that as the only blocker it can see (with "the list may be incomplete").

## Speed and memory (report only, no claim)

Three runs each, output to `/dev/null`, one process, `ulimit -v 2500000`; median seconds and peak RSS
(`/usr/bin/time`).  The time includes reading files and formatting the dump in all three columns.

| list | CPython `tokenize` (stage 0) | stage 1 (CPython + ailtok) | stage 2 (AIL general build) |
|---|---:|---:|---:|
| 156 compiler files | 2.14 s, 63 MB | 5.36 s, 152 MB | 12.19 s, 541 MB |
| S376 | 2.10 s, 63 MB | 5.52 s, 152 MB | 11.84 s, 583 MB |

Stage 2 is about 5.7x slower than CPython's tokenize and uses about 8.6x the memory on the general
path.  RSS grows with the input (541 MB to 583 MB), so the general build does not appear to return the
per-file token lists.

## Compiler gaps hit (blockers for later ports)

1. **Typed path: class fields are int64/float/bytes only.**  A field holding a `list` or `str` sends the
   whole program to the general path.  Every AST port (`ailast`, nodes with `_fields`, list and str
   fields) hits this; see also the shport0 class probe in `PORT_ORDER.md`.
2. **General runtime strings are 16-bit.**  Any input with a code point above U+FFFF stops the program
   (`stdin code point above U+FFFF in the 16-bit v2 runtime`).  83 of 1625 front-end-adjacent files hold
   such a character (none of S376).
3. General-path memory: peak RSS grows with total input (above).
