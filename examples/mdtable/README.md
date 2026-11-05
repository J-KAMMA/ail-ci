# mdtable: a Markdown pipe-table formatter built by AIL

`mdtable.py` reads Markdown from stdin, rewrites every pipe table with even column widths,
and writes the document to stdout. It is an ordinary Python 3.12 program, built with AIL and
checked byte for byte against `python3`.

```
mdtable.py [--check] [--sum COL] < input.md
```

Lines that are not part of a pipe table pass through unchanged. A table is a header row, a
delimiter row (`---`, `:---`, `---:`, `:---:`) and body rows. The program:

- splits cells on unescaped `|` (`\|` stays in the cell), strips cell spaces, and allows rows
  with or without the outer pipes;
- pads rows with fewer cells, and keeps extra cells as extra columns;
- writes each table again with every column as wide as its widest cell (`len()` of the text;
  at least 3), aligned as its delimiter says, `| a | b |` style;
- leaves fenced code blocks (` ``` `) alone;
- `--check`: prints `tables T rows R cols C` per table and exits 1 if any input table was not
  already formatted;
- `--sum COL`: appends a body row with the sum of column COL (1-based) where every cell is an
  int, and `n/a` if any is not. The sum uses Python ints; a sum beyond int64 must print the
  exact value or stop loudly.

## Canonical form

The rewrite is a normalisation, so a table that is already canonical is unchanged:

- widths are `max(3, len(cell))` over the header and body cells of that column;
- left cells are emitted as `---`, right cells as `---:`, centered cells as `:---:`, and an
  explicit left colon (`:---`) is normalised to `---`;
- every row is emitted with outer pipes and one space of padding on each side of a cell;
- a short body row is padded with empty cells, and a long one widens the table;
- the delimiter row is regenerated from the alignment flags, so its dash count follows the
  column width.

Escaped pipes are kept with their backslash (`a \| b`), so the table round-trips.

`--check` writes only the per-table summary lines (not the document). `rows` counts the
header, delimiter and body rows of that table; `cols` is the column count after extra cells.
With `--sum COL`, `COL` is 1-based; a column beyond the widest row yields `n/a` and widens the
table. An empty body sums to `0`.

AIL integers are 64-bit. The `--sum` total is accumulated as an AIL int, so a total beyond
int64 stops the program with an `OverflowError` line on stderr and a non-zero exit instead of
printing a wrapped value. The big-sum input below checks exactly that.

## Build and run

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile examples/mdtable/mdtable.py -o /tmp/mdtable
/tmp/mdtable < examples/mdtable/data/plain.md
python3 examples/mdtable/mdtable.py < examples/mdtable/data/plain.md

AIL_UNIFIED_FORCE=1 python3 AIL_CURRENT/ail_chatgpt.py compile \
    examples/mdtable/mdtable.py -o /tmp/mdtable-unified
```

Both builds are on the general path (the first note line is recorded in `RESULTS.md`), and
both produce byte-identical stdout and the same exit status as CPython for every table input.

## Inputs in `data/`

| input | what it covers |
|-------|----------------|
| `plain.md` | a plain three-column table with prose around it |
| `align.md` | every alignment: `---`, `:---`, `---:`, `:---:` |
| `escaped.md` | escaped pipes (`a \| b`), including one inside backticks |
| `noouter.md` | rows without the outer pipes |
| `ragged.md` | rows with fewer cells and one row with an extra cell |
| `twotables.md` | two tables with prose between them |
| `fenced.md` | a table inside a ` ``` ` code fence, left alone |
| `pipeprose.md` | non-table lines containing a pipe |
| `empty.md` | an empty file (no output, exit 0) |
| `formatted.md` | an already canonical table (`--check` exits 0) |
| `unicode.md` | non-ASCII cells (`naïve`, `résumé`, `東京`, `✓`) |
| `bigsum.md` | `--sum 2` totals `9223372036854775808`, beyond int64 |

Test: `python3 AIL_CURRENT/test_ail_examples_mdtable.py`.
