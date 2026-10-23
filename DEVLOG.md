# DEVLOG

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
