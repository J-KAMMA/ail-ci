# `bisect` coverage

Job `job-std_bisect-11011433`, 2026-11-01. Default build:
`python3 AIL_CURRENT/ail_chatgpt.py compile <file> --syntax python` (no `--strict`).
CPython 3.12 is the oracle. **12 of 12 programs build and match CPython's stdout and exit status**
(the task asks for at least 9).

| program | result | first message / general-path reason |
|---|---|---|
| `alias_import.py` | typed | - |
| `error_edges.py` | typed | - |
| `event_log.py` | general | a slice used where a single number is needed |
| `grade_report.py` | general | `'letter'` is a str used where a number is needed |
| `interval_lookup.py` | typed | - |
| `key_records.py` | general | `'_tu1'` is a row of `'tasks'`, not a number; read one of its fields |
| `leaderboard.py` | general | `insort(board, ...)` changes `'board'`, a list parameter, which is read-only |
| `lookup_helper.py` | general | `insort_right(values, ...)` changes `'values'`, a list parameter, which is read-only |
| `price_tiers.py` | typed | - |
| `sparse_ids.py` | typed | - |
| `star_import.py` | general | import of `'bisect'` with a function that is not built in |
| `word_index.py` | typed | - |

No program is refused in the default mode. The general-path messages above are the verbatim
first line of the compiler's note, not refusals.

## What blocked the programs, and the fix

Before this job the only default-mode refusal was `key_records.py`:

```
lab/stdlib/bisect/key_records.py:12:9: not in the subset: '_tu1' is a row of 'tasks', not a number; read one of its fields (the general path could not build this program either); general path: ail_bisect_left(): key is not supported; the bounds are lo= and hi=
```

The typed path does not model a tuple row, and the general path did not accept `key=` at all.
The general path now lowers `key=` for `bisect_left`, `bisect_right`, `bisect`, `insort`,
`insort_left` and `insort_right`. It calls the key on exactly the elements the binary search
visits, computes `key(x)` once for `insort`, and roots key results across allocating calls
(`AIL_CURRENT/python/pkg-v12/pyboxed2.py`, `BISECTKEY_C`). Programs without `key=` emit the
same C as before; the 10 `lab/compare` tasks' generated C was checked against `HEAD` and is
byte-identical wherever both revisions build (17 task/language pairs `SAME`; the three
Python-column pairs `scar_life`, `tally_lang`, `tree_fold` are refused by both revisions).

`AIL_CURRENT/test_ail_std_bisect.py` builds all twelve programs and a key-call/insort program
in the default mode and compares stdout and exit status with CPython; it is registered through
`AIL_CURRENT/tests.d/test_ail_std_bisect.txt`.

## Follow-ups (out of scope; the default build already succeeds via the general path)

1. Typed-path tuple rows / `key=` on them. Exact `--strict` text:

   ```
   lab/stdlib/bisect/key_records.py:12:9  blocks 23 lines (main)
      code:          _tu2.append(_tu1.f0)
      construct:     '_tu1' is a row of 'tasks'
      why not typed: '_tu1' is a row of 'tasks', not a number; read one of its fields
   ```

2. Mutating a list parameter with `insort`/`insort_left`/`insort_right`. Exact `--strict` text:

   ```
   lab/stdlib/bisect/leaderboard.py:4:5  blocks 17 lines (add_score, main)
      code:          insort(board, score)
      construct:     insort(board
      why not typed: insort(board, ...) changes 'board', a list parameter, which is read-only
   ```

   A list parameter is read-only by design; passing ownership or aliasing rules is a larger
   feature than this coverage job.
