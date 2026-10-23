# DEVLOG

## 2026-10-23 - csv_table: inline small leaf loops (job-perf4-10240813)

`field += ch` was already in place and its slow path is about 1% of calls, so this job took
the next cost. Profiling a 132 MB three-million-row input (`gprof -pg`) put
`csv_table_group_scan` at 79% and `parse_int64_decimal` at 2.15% flat. Flat cost understates
it: replacing the parse with a constant saved 7.3% of wall time, while asking gcc to inline
that same nine-statement leaf loop saved 20% (1.24 s -> 0.99 s, user 1.08 s -> 0.84 s). The
extra is the call boundary in the row loop, not the digit loop. The feed/chunk copy was a
larger upper bound (14.5% if the chunk buffer is reused unsafely) but safe per-chunk ownership
saved only 1.6%, so it was rejected.

The compiler now asks for `always_inline` on a function whose body is one `for` loop, no
other loop/try/with/yield, no call to another function or class constructor, a scalar numeric
return, at most 12 statements and 180 AST nodes; recursion, entry points and the existing
straight-line rule are unchanged. In `csv_table` this fires on `parse_int64_decimal` and
`parse_int64_decimal_bytes` only. String/list/object returns are excluded: inlining
`json_quote` as well measured 1.42 s, slower than 1.25 s.

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 14.5/14.5/6.1/6.9 | 0.995 [0.992,1.016] tie | 2.390 [2.341,2.456] slower | 2.093 [2.053,2.252] slower |
| 12.1/14.6/6.1/6.9 | 0.829 [0.818,0.843] faster | 1.989 [1.943,1.995] slower | 1.762 [1.730,1.801] slower |

RSS 5.5/5.5/3.3/3.8 -> 5.5/5.5/3.3/3.7 MiB, binary 107/107/20/1928 -> 111/107/20/1928 KiB,
build disk 400/400/44/1952 -> 412/400/44/1952 KiB. The app's boundary controls and Python
oracle still pass byte-for-byte.

Tests: `test_ail_integer_codec test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_csv_writer test_ail_utf8_stream_fuzz test_csv_column_stats_stream` (24 tests) and
`test_ail_safetynet test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass.
Probes `/tmp/probes/loop_inline.py` and `/tmp/probes/loop_inline_objects.py`
(`bash ~/tools/cmp.sh`) cover negative/empty/invalid parse paths, early return, break/continue,
loops reached through arguments, list items and dict values, and string/list/dict mutations;
both builds match CPython stdout on every case.

## 2026-10-23 - csv_table: one UTF-8 scan per chunk (job-perf4-10240013)

`field += ch` was already in place. The generated code calls `ail_str_cat`, whose first
cases return the existing value or a view when the operands are adjacent, and whose
remaining case appends into the newest arena block with amortized growth
(`AIL_SARENA_TOPS`). The slow path is about 1% of calls; forcing the builder-local path
(`ail_bl_append`, which copies `key = field` per row) measured 3.29 s against 2.48 s on a
263 MB file, so it was rejected.

Profiling the rest (`gprof -O3 -pg`, same file) put `_utf8_complete_length` at 11.2% and
`ail__utf8_validate` at 9.1%: `utf8_decode_feed` scanned `combined` to find the last
character boundary and then `decode("utf-8")` scanned it again to validate. A chunk only
ends mid-character at a chunk boundary, so `_utf8_tail_complete` now checks the final byte
(and at most three continuation bytes) and sends the whole buffer straight to decode. The
full `_utf8_complete_length` scan still runs for the rare split chunk, so the pending bytes,
the feed on which an error is reported, and the decoded text are unchanged. Amdahl bound
about 11%; measured 7.0% on the app (AIL/base 0.930).

`python3 bench/compare.py --app csv_table`, before -> after:

| ms ail/base/c/rust | ail/base | ail/c | ail/rust |
| --- | --- | --- | --- |
| 16.5/16.5/6.9/7.8 | 1.006 tie | 2.387 slower | 2.126 slower |
| 15.5/16.7/7.0/8.0 | 0.930 faster | 2.200 slower | 1.933 slower |

RSS 5.5/5.5/3.2/3.8 -> 5.5/5.5/3.2/3.6 MiB, binary 107/107/20/1928 KiB unchanged, build
disk 400/400/44/1952 KiB unchanged. The app's boundary controls and the Python oracle still
pass byte-for-byte.

Tests: `test_ail_utf8_stream_fuzz test_csv_group_scan test_ail_csv_rewrite_stream
test_ail_splitlines_utf8 test_csv_column_stats_stream` (18 tests) and `test_ail_safetynet
test_ail_files test_ail_corpus_findings3` (25 tests, 1 skipped) pass. Probe
`/tmp/probes/utf8_tail.py` (`bash ~/tools/cmp.sh`) compares the old and new boundary logic
on 5,232 curated and random byte strings: same stdout, 0 mismatches, in both builds.

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
