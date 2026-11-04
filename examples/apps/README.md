# apps — six small command-line tools in plain Python

Six ordinary Python 3 programs, written the way a user would write them (type annotations on
functions, no AIL-only imports). Each reads standard input, takes its options from `sys.argv`
and prints what CPython prints.

| tool | what it does | arguments | exit status |
| --- | --- | --- | --- |
| `wc.py` | lines, words and bytes of stdin, like `wc` without a file name | — | 0 |
| `colsum.py` | count, sum, min, max and mean of the integer values of one CSV column | `COLUMN` | 2 when the column is missing |
| `topwords.py` | the N most frequent words, `count<TAB>word`, ties by word | `N` | 0 |
| `grepn.py` | lines containing `TEXT`, as `lineno:line` | `TEXT` | 1 when no line matches |
| `jsonfield.py` | one field of every JSON Lines object, `-` when absent | `KEY` | 0 |
| `hexdump.py` | stdin as xxd-style hex dump lines | — | 0 |

`data/` holds one normal input and two edge inputs per tool: empty stdin, and an odd input (no
final newline, non-ASCII UTF-8, a quoted CSV field with a comma, ints beyond int64).

## Build and run one tool

With CPython:

```
python3 examples/apps/wc.py < examples/apps/data/wc_normal.txt
```

With AIL (default mode):

```
python3 -B AIL_CURRENT/ail_chatgpt.py compile examples/apps/wc.py --syntax python -o /tmp/wc
/tmp/wc < examples/apps/data/wc_normal.txt
```

A build without a `note: ... built on the general path` line on stderr is a typed build.

## Build results (step 2)

`typed` means the default build took the typed path; `general` means it fell back.

| tool | default build | `AIL_UNIFIED_FORCE=1` |
| --- | --- | --- |
| `wc.py` | typed | typed |
| `colsum.py` | typed | typed |
| `topwords.py` | typed | typed |
| `grepn.py` | typed | typed |
| `hexdump.py` | typed | typed |
| `jsonfield.py` | **general** | typed |

So 5 of the 6 tools are **typed** in the default build; `AIL_UNIFIED_FORCE=1` builds all six on
the unified path. Every tool's stdout and exit status equals `python3` on every input, in the
default build and in the forced build.

## Measurements

Input: one 50 MB file per tool, written by `make_big.py` (fixed seed, into `/tmp`, not git).
Wall time is the median of 5 runs; RSS is `/usr/bin/time -v` "Maximum resident set size" in
MiB; binary bytes is the compiled executable; compile seconds is a fresh build with
`AIL_NO_CACHE=1`. Outputs of the AIL binaries on the 50 MB inputs were byte-identical to
`python3` for all six tools.

| tool | build | compile s | AIL wall s | python3 wall s | AIL RSS MiB | python3 RSS MiB | binary bytes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `wc.py` | typed | 0.32 | 0.414 | 0.385 | 523 | 565 | 26,488 |
| `colsum.py` | typed | 1.74 | 0.611 | 0.269 | 137 | 87 | 82,296 |
| `topwords.py` | typed | 6.09 | 1.667 | 1.429 | 1,704 | 924 | 216,456 |
| `grepn.py` | typed | 0.37 | 0.075 | 0.101 | 2 | 10 | 26,392 |
| `jsonfield.py` | general | 4.95 | 5.359 | 1.599 | 11 | 11 | 283,856 |
| `hexdump.py` | typed | 0.42 | 3.989 | 8.191 | 4,506 | 60 | 26,496 |

`hexdump.py` and `topwords.py` were measured without `ulimit -v`; under `ulimit -v 1500000`
the AIL `hexdump` binary stops with `MemoryError` and `topwords` also exceeds the limit (their
Python counterparts do not). The `hexdump` RSS is the whole 223 MB output held in memory;
`python3` streams it. Wall times are one 4-core CI runner and vary by a few percent.

## Findings (step 2)

1. **`hexdump.py` — local kind settled by its first assignment.** The original line

   ```python
   hexpart = " ".join(cells)
   ```

   made the default build fall back with:

   ```
   note: hexdump.py:21:9: built on the general path (about 20x slower) because 'hexpart' is an int
   and is being assigned a str; a local's kind is settled by its FIRST assignment and never changes
   afterwards -- give the second kind a different name, or use the value inline without binding it
   ```

   The rewrite inlines the join into the `print` call, and the tool is typed.

2. **`topwords.py` — two strict-path notes.** The original line

   ```python
   words = [word.lower() for word in re.findall(r"[A-Za-z]+", text)]
   ```

   produced `cannot be walked inline here; bind it to a name first: part = re.findall(...) then
   walk part`. Binding `matches = re.findall(...)` first, and annotating the counter
   (`counts: Counter[str] = Counter(words)`; without the annotation the build reports `import of
   'collections' with a use that is not built: Counter ...`), makes the tool typed. The sort
   (`sorted(counts.items(), key=lambda item: (-item[1], item[0]))`) needs no change.

3. **`jsonfield.py` stays on the general path.** The default build reports

   ```
   note: jsonfield.py:13:9: built on the general path (about 20x slower) because json.loads(s):
   the type of the result is not declared here; write the type down: `data: dict[str, int] =
   json.loads(s)` (the types are int, float, str, bool, list[T], list[list[T]], dict[str, T])
   ```

   A JSON object with mixed value types has no single supported value type: declaring
   `dict[str, int]` rejects string values (`found a str ... but the declared type needs an int`),
   and `dict[str, object]` is not accepted. `AIL_UNIFIED_FORCE=1` builds it typed and the output
   still matches CPython.

4. **Ints beyond int64 stop loudly by default.** `colsum`'s `int(text)` and `jsonfield`'s
   `json.loads` reach the int64 boundary on `colsum_odd.csv` / `jsonfield_odd.jsonl`; the default
   and `AIL_UNIFIED_FORCE=1` builds exit 1 with

   ```
   OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)
   ```

   and `colsum`'s running sum can stop with `integer overflow in +`. Building those two tools
   with `--exact-int` makes both match CPython on those inputs. `--exact-int` itself falls back
   to the general path for four of the six tools; that does not affect the result.
