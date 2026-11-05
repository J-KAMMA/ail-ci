# advparse results

- Date: 2026-11-05
- App: `examples/advparse/advparse.py` (303 lines)
- Oracle: CPython 3.12.3
- Host: GitHub Actions runner, Linux, 4 cores
- Modes: default build and `AIL_UNIFIED_FORCE=1`

## Build path

Both builds are the **general path**. The first note line is:

```
note: examples/advparse/advparse.py:20:1: built on the general path (about 20x slower) because 'ROOMS' is a module-level dict that a function cannot read: a module-level table must be a non-empty literal whose keys are all ints, all strs or all bytes (or tuples of ints / strs) and whose values are all one kind -- no empty one, no computed one, no bool, and no name bound twice or changed at module level. write instead: build it in main() (`rooms: dict[str, int] = {...}`) and pass it to the functions that read it as a parameter, or build it inside the one function that reads it; run with --strict to see why
```

The app is an ordinary Python program with a module-level dict of `Room` objects, so it uses
the general path rather than `--strict`. `AIL_UNIFIED_FORCE=1` produced a byte-identical
binary (322,280 bytes, `sha256 1044d77756ef6c56e8f3ce8231d99b38a0bbf7a30b1e62ef4b662f3b1694abc4`),
so both modes use the same code generation.

## Comparison with CPython

Each case was run as `python3 -B examples/advparse/advparse.py < scripts/NAME.txt`,
`/tmp/advparse_def < scripts/NAME.txt` and `/tmp/advparse_uni < scripts/NAME.txt`
(`AIL_UNIFIED_FORCE=1`). Standard output was compared byte for byte with `cmp`, and the exit
status with `$?`. Standard error was empty in every run. All eight scripts match in both
builds (8 of 8).

| Script | commands | stdout bytes | exit | CPython == default | CPython == forced |
| --- | --- | --- | --- | --- | --- |
| `scripts/win.txt` | 21 | 1,496 | 0 | yes | yes |
| `scripts/synonyms.txt` | 25 | 2,118 | 0 | yes | yes |
| `scripts/ambiguous.txt` | 16 | 1,096 | 0 | yes | yes |
| `scripts/containers.txt` | 24 | 1,426 | 0 | yes | yes |
| `scripts/errors.txt` | 26 | 1,201 | 0 | yes | yes |
| `scripts/spacing.txt` | 15 | 851 | 0 | yes | yes |
| `scripts/quiet.txt` | 16 | 1,049 | 0 | yes | yes |
| `scripts/locked.txt` | 19 | 1,467 | 3 | yes | yes |

`win.txt` ends with `score 50 of 50 in 21 moves`; `locked.txt` ends with
`the door will not move.` and exit status 3, matching CPython.

## Spelling changes

None. The first build matched CPython on all eight scripts.
