# `sqlite3` coverage (job-std_sqlite3-11041241)

Environment: CPython 3.12.3, libsqlite3 3.45.1, the default build
`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python` (typed path first, general path as the
fallback) and the same command with `AIL_UNIFIED_FORCE=1`. Date: 2026-11-04.

Before: the directory did not exist, so 0/12 was measured.

After: 12/12 programs build on the typed path in the default build and match CPython on stdout and exit
code. The general path refuses every one of them by name (`sqlite3 is built in typed code only`), so the
typed count is 12/12 and no program falls back to the general path.

| program | default build | `AIL_UNIFIED_FORCE=1` | matches CPython (stdout + exit) | first stderr line |
| --- | --- | --- | --- | --- |
| 01_basic_crud.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (the general path has no bytes values and no C handles)` |
| 02_named_params.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 03_bulk_aggregate.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 04_fetchone_loop.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 05_transactions.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 06_unique_error.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 07_rowcount_lastrowid.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 08_nulls.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 09_unicode.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 10_reals_repr.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 11_bigints.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |
| 12_join_script.py | typed | refused by name | yes | default: none; force: `not in the subset: sqlite3 is built in typed code only (...)` |

## Fixes

No source change was needed: the existing `sqllower.py` / `ailsql_core.h` surface already builds all
twelve programs on the typed path and their output is byte-identical to CPython. Refusals that remain
(e.g. `fetchmany`, `row_factory`, the general path) are loud and named.

## Before / After

Before: `lab/stdlib/sqlite3/` did not exist, 0/12 measured. After: 12/12 equal to CPython in the default
build (12 typed, 0 general, 0 refused).
