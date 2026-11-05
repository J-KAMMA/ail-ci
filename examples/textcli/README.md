# textcli: three small text tools built by AIL

Ordinary Python 3 programs with function annotations, compiled with AIL. Each reads stdin, takes
its options from `sys.argv`, and prints exactly what CPython 3.12 prints.

| tool        | what it does                                         | inputs in `data/`                          |
|-------------|------------------------------------------------------|--------------------------------------------|
| `csvcut.py` | print named CSV columns (`NAME[,NAME...]`)           | `csvcut_normal.csv`, `csvcut_empty.csv`, `csvcut_quoted.csv` |
| `uniqc.py`  | `uniq -c` style run counts, `-d` for repeated runs   | `uniqc_normal.txt`, `uniqc_empty.txt`, `uniqc_odd.txt` |
| `tsort.py`  | topological order of `a b` pairs, ties by name       | `tsort_normal.txt`, `tsort_empty.txt`, `tsort_cycle.txt` |

## Build and run

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile examples/textcli/csvcut.py -o /tmp/csvcut
/tmp/csvcut name,city < examples/textcli/data/csvcut_normal.csv
python3 examples/textcli/csvcut.py name,city < examples/textcli/data/csvcut_normal.csv
```

`--strict` builds all three on the typed path; none falls back to the general path.

## Measured on a 20 MB input

Generated with `python3 gen_big.py data` (fixed seed, one ~20 MB file per tool). Build is the
default mode; the binary was `strip`ped. Times are the median of 5 wall-clock runs, CPython 3.12
on the same input for comparison.

| tool     | path  | stripped binary | AIL median | python3 median |
|----------|-------|-----------------|------------|----------------|
| `csvcut` | typed | 71,896 B        | 847 ms     | 572 ms         |
| `uniqc`  | typed | 22,744 B        | 68 ms      | 227 ms         |
| `tsort`  | typed | 47,320 B        | 519 ms     | 865 ms         |

All three also produce byte-identical output to CPython on the 20 MB inputs.

## Follow-ups

None: every tool matches CPython on all inputs in the default build and with `--strict`.
