# DEVLOG

## 2026-10-23 - `-2**63` no longer overflows (job-pre3-10240008)

`print(-2**63 < 0)` and comparisons chained over it raised `integer overflow` on both builds;
CPython prints `False`. The value is INT64_MIN and is inside int64, but Python parses the spelling
as `-(2**63)`, so evaluating the positive power first overflows before the minus can bring it back
into range. Only a one-line `print(<expression>)` escaped, by falling back to the general path.

The spelling is now recognised in every emitter:

* `pyfront.is_negative_int64_min_power` identifies `UnaryOp(USub, BinOp(Pow, 2, 63))`.
* `pyboxed2.expr_UnaryOp` (general path) boxes INT64_MIN directly.
* `pyfunc._expr` (typed legacy emitter) returns the INT64_MIN constant.
* `ir/lower.py` (the default typed emitter) lowers it to the same constant. This path was the
  missing one: the legacy `_expr` special case ran during its probe compile, but the final C came
  from the IR, which evaluated `ail_ipow(2, 63)` and then `ck_neg`.

`test_ail_pre3.py` covers the reported chain plus `==`, `!=`, `<=`/`>=`, function arguments, list
items, dict values, class attributes, aliasing, empty containers, float operands and the adjacent
int64 literals. Each program is built with the general path forced, the default IR build and the
typed legacy build (`AIL_IR=0`); stdout and exit status match CPython in all three.

No new DIFFERENCES row: this removes the difference instead of documenting one. Forms that still
compute an out-of-range intermediate are unchanged, e.g. `2**63`, `-2**64`, `-2**63 - 1` and
`-(2**63 - 1)`.

## 2026-10-23 - C compiler step cache (job-ctime3-10232149)

The base export already contains the content-addressed `cc` layer in
`AIL_CURRENT/python/pkg-v12/buildcache.py` (`buildcache.run_cc`, activated by `--cache`, stored under
`$AIL_CACHE` / `~/.cache/ail`, off with `AIL_NO_CACHE=1` or `--no-cache`). The task says not to add
a second cache when one already exists, so this job verifies and measures that layer and adds a
regression test for the exact reuse case:

* `test_changed_source_with_the_same_generated_c_hits_the_cc_cache` changes a typed local's name,
  which changes the merged source text (a new front-end entry) but not the generated C: the C
  compiler step is skipped and the executable is byte-identical.

Measurement on this 4-core runner, gcc 13.3, median of 5 runs, `AIL_CACHE` in a temporary
directory. "before" is `AIL_NO_CACHE=1`; "after" is a cache warm from the same C text with a new
front-end key (a renamed local), so the front end runs but the C compiler step hits. Wall time is
the whole `ail_chatgpt.py compile`; C time is the sum of the compiler wrapper's own runs (after
includes the cache's one-time toolchain probes).

| gdev program | wall before | C before | wall after | C after | outputs |
| --- | ---: | ---: | ---: | ---: | --- |
| g00_000 | 1.245 s | 0.241 s | 1.177 s | 0.013 s | identical |
| g00_002 | 1.427 s | 0.393 s | 1.186 s | 0.012 s | identical |
| g00_004 | 2.540 s | 1.418 s | 1.279 s | 0.012 s | identical |

Output SHA-256 values were equal for every before/after pair. With an unchanged source the whole
front-end cache also hits, so the compiler step is not run at all.
