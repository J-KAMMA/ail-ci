# mdtable results: AIL versus CPython 3.12

**Path:** general path in both builds. The two binaries are byte-identical
(sha256 `b9ee90b51fb89f5222c95daad4f2416f41b6921f354a2025b8c8e584157f0469`), so the default
build and `AIL_UNIFIED_FORCE=1` behave the same. First note line of the default build:

```
note: mdtable.py:24:9: built on the general path (about 20x slower) because comparing a str with a number; str and bytes are separate types here and a str is never a number -- this is refused by name rather than answered. write instead: compare like with like: a byte from bytes/sys.stdin.buffer is an int (`b == 97`, or `b == ord("a")`), a character of a str is a str (`c == "a"`); convert with `chr(b)` or `ord(c)`; run with --strict to see why
```

The unified build prints no note.

Method: for each input and each option set (`default`, `--check`, `--sum 2`), run
`python3 examples/mdtable/mdtable.py` and the AIL binary and compare stdout bytes and the exit
status. That is 12 inputs x 3 option sets x 2 builds = 72 comparisons. **70 are byte- and
status-identical. The other 2 are the same allowed loud stop** (`bigsum.md --sum 2`, one per
build): stderr is `OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives
exact ints)`, stdout is empty (0 bytes), exit status 1. CPython prints the exact
`9223372036854775808`. No build printed a wrong or partial value.

`--check` exits 0 only for `formatted.md` (and for inputs with no table: `empty.md`,
`fenced.md`); every other table is rewritten, so it exits 1. CPython and AIL agree on all of
these.

| input | default | `--check` | `--sum 2` |
|-------|---------|-----------|-----------|
| `plain.md` | match | match (exit 1) | match (`n/a`, non-int author) |
| `align.md` | match | match (exit 1) | match (`n/a`) |
| `escaped.md` | match | match (exit 1) | match (`n/a`) |
| `noouter.md` | match | match (exit 1) | match (`n/a`, non-int command) |
| `ragged.md` | match | match (exit 1) | match (`n/a`, mixed/empty) |
| `twotables.md` | match | match (exit 1) | match (`1` then `n/a`) |
| `fenced.md` | match (verbatim) | match (exit 0) | match (verbatim) |
| `pipeprose.md` | match | match (exit 1) | match (`n/a`) |
| `empty.md` | match | match (exit 0) | match |
| `formatted.md` | match | match (exit 0) | match (`3`) |
| `unicode.md` | match | match (exit 1) | match (`n/a`) |
| `bigsum.md` | match | match (exit 1) | **loud stop** (exit 1, `OverflowError`, 0 bytes) |

Totals: 12 of 12 inputs match in both builds under the task's rule (exact match, or a loud
stop beyond int64); 70 of 72 raw comparisons are exactly equal.

No spelling change was needed to obtain a match; `mdtable.py` is the same program in both
builds. The only deviation from CPython is the documented int64 overflow stop in `--sum`.
