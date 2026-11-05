# `chunk` coverage results

Build command for every program (default build, `-o` must not exist yet):

```
python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/chunk/<program>.py -o /tmp/<program>.out
```

The oracle is `python3 <program>.py` (CPython 3.12.3). CPython prints
`DeprecationWarning: 'chunk' is deprecated and slated for removal in Python 3.13` on stderr for
`import chunk`; stdout and the exit status are compared, not stderr. Each program builds its own
IFF/RIFF file in the current directory and needs no arguments.

## Before

`AIL_CURRENT/stdlib/chunk.py` did not exist, so every program was refused at the import. The
common first-refusal line `P` (with the program's own file name and line 2) is:

```
not in the subset: import of 'chunk' is not available: this compiler builds only the modules it
models (math, sys, collections, itertools, functools, heapq, bisect, re, json) (the general path
could not build this program either); general path: chunk.Chunk (not yet published in
NAMES_library.json)
```

| program | default build | first refusal (after the file:line prefix) |
| --- | --- | --- |
| `01_basic_read.py` | refused | `not in the subset: import of 'chunk' is not available: ... chunk.Chunk (not yet published in NAMES_library.json)` |
| `02_partial_reads.py` | refused | same as `01` |
| `03_seek_skip.py` | refused | same as `01` |
| `04_riff_little_endian.py` | refused | same as `01` |
| `05_align_odd.py` | refused | same as `01` |
| `06_inclheader.py` | refused | same as `01` |
| `07_walk_chunks.py` | refused | same as `01` |
| `08_errors.py` | refused | same as `01` |
| `09_huge_size.py` | refused | same as `01` |
| `10_nested_and_bounds.py` | refused | same as `01` |

Result before: **0 built, 0 typed, 10 refused**.

## After

| program | default build | forced general | matches CPython stdout + exit |
| --- | --- | --- | --- |
| `01_basic_read.py` | general | general | yes |
| `02_partial_reads.py` | general | general | yes |
| `03_seek_skip.py` | general | general | yes |
| `04_riff_little_endian.py` | general | general | yes |
| `05_align_odd.py` | general | general | yes |
| `06_inclheader.py` | general | general | yes |
| `07_walk_chunks.py` | general | general | yes |
| `08_errors.py` | refused | refused | no (refused; compiler follow-up below) |
| `09_huge_size.py` | general | general | yes |
| `10_nested_and_bounds.py` | general | general | yes |

Result after: **9 built, 0 typed, 1 refused; 9 build and match**.

`python3 -B AIL_CURRENT/test_ail_std_chunk.py` rebuilds all nine passing programs in both modes and
compares stdout and the exit status with `python3`: 2 tests, OK. Every passing program lands on the
general path because `Chunk.__init__` takes defaulted positional arguments, which the typed path
does not model.

### Compiler follow-up: `08_errors.py`

```
08_errors.py:28:5: not in the subset: passing a nested function ('short_header') as an argument is
not available: a closure as a value needs a lifetime this compiler does not give it; call it in
place instead (the general path could not build this program either); general path: read() called
without a required argument size
```

This is a program-structure limit (a nested `def` passed to a helper), not a `chunk` behaviour: the
same calls written inline build and match CPython. The program is left unchanged.
