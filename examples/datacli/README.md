# datacli — two small data CLI tools

Two ordinary Python 3 scripts, each typed (`->` annotations, annotated locals)
and each compiled by AIL to the typed path in the default build. Both are
checked byte for byte against CPython 3.12 on their sample inputs.

| Tool | What it does |
| --- | --- |
| `histo.py BINS` | reads numbers on standard input and prints an equal-width histogram |
| `ini2json.py` | reads an INI file on standard input and prints JSON |

## Build and run

With CPython:

```
python3 examples/datacli/histo.py 5 < examples/datacli/data/histo_normal.txt
python3 examples/datacli/ini2json.py < examples/datacli/data/ini_normal.ini
```

With AIL (default mode, and `--strict` to refuse instead of falling back):

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/datacli/histo.py -o /tmp/histo
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/datacli/ini2json.py -o /tmp/ini2json
/tmp/histo 5 < examples/datacli/data/histo_normal.txt
```

## histo

`histo.py BINS` reads one number per line (int or float), skips blank lines and
counts a line that does not parse as a float, reporting `skipped N` on stderr.
It prints `BINS` equal-width bins from the smallest to the largest value as
`"%12.4f %12.4f %8d  "` followed by a bar scaled to at most 40 `#` characters.
The numbers are read with `float()`, so they are IEEE doubles exactly as in
CPython, and the two big integers in `data/histo_bigint.txt`
(`9223372036854775807` and `99999999999999999999`) print the same values CPython
prints instead of overflowing.

## ini2json

`ini2json.py` parses a small INI dialect by hand (no `configparser`): `[section]`
headers, `key = value` and `key: value` settings, and `;` / `#` comment lines.
Keys are lowercased, values stripped, and a key before any section goes to
`DEFAULT`. The result is printed as `json.dumps(result, indent=2,
sort_keys=True)`. A line it cannot parse prints `ini2json: line N: bad line` on
stderr and exits 1. (The typed path has no nested `dict[str, dict[str, str]]`,
so the typed build serializes one `dict[str, str]` section at a time with
`json.dumps(..., indent=2, sort_keys=True)` and joins them in the same format;
the bytes are identical.)

## Inputs

`data/` holds one normal input and three edge inputs per tool.

| File | Tool | Edge case |
| --- | --- | --- |
| `histo_normal.txt` | histo | ordinary numbers |
| `histo_empty.txt` | histo | empty stdin |
| `histo_equal.txt` | histo | all values equal |
| `histo_bigint.txt` | histo | int64 boundary and a 20-digit int, no final newline |
| `ini_normal.ini` | ini2json | ordinary sections, both delimiters, comments |
| `ini_empty.ini` | ini2json | empty stdin |
| `ini_bad.ini` | ini2json | a line with no delimiter (exit 1) |
| `ini_unicode.ini` | ini2json | non-ASCII UTF-8, no final newline |

## Comparison with CPython

Each input was run as `python3 -B <tool>.py` and as the compiled binary, in the
default build and with `AIL_UNIFIED_FORCE=1`; stdout, stderr and the exit
status were compared with `cmp`. All 8 small inputs match in both builds
(16 of 16 comparisons, including the big-int input).

Both tools build on the **typed path** in the default build: no
`note: ... built on the general path ...` line is printed, and `--strict`
builds both without a blocker.

## 20 MB benchmark

`gen_big.py [OUTDIR] [MEGABYTES]` writes `histo_big.txt` and `ini_big.ini`
(20 MB each, fixed seed) and prints their paths.

```
python3 examples/datacli/gen_big.py /tmp/big 20
```

Host: GitHub Actions runner, Linux, 4 cores, CPython 3.12.3. Median of 5 wall
times, stdout to `/dev/null`, 20 MB input, default (typed) build.

| Tool | Path | Stripped binary | AIL median | `python3` median | Speedup |
| --- | --- | --- | --- | --- | --- |
| `histo.py 20` | typed | 35,032 B | 0.214 s | 0.783 s | 3.65x |
| `ini2json.py` | typed | 92,448 B | 0.355 s | 1.240 s | 3.49x |

The 20 MB stdout also matched CPython byte for byte for both tools.

## Follow-ups

None. No output differed from CPython, so there is no repro to record.
