## 2026-10-23 - json_query: validate `bytes.decode` without copying (job-perf5-10240813)

`json_query_file` reads the whole input into a stable `bytes` local and only needs the decoded
`str` for its `string-map` mode; `batch`/`extract` scan the original bytes. The compiler emits
`ail_bytes_decode_utf8_view` for that stable local (`_decode_view_source`), so the 1.3 MB UTF-8
copy is gone and the decode performs only the strict validation pass. No `bench/apps` source was
changed. This finish pass refreshed the stale `cruntime.py` manifest pin and recorded the numbers.

Profiling used a generated-C copy of the current app with the whole-file decode validation replaced
by a no-op (a /tmp-only measurement, since `perf_event_open` is disabled on this runner): 6.757 ms
vs 6.251 ms, so the residual validation is 0.506 ms or 7.5% of the run. Amdahl's bound for removing
that residual pass entirely is 1.081x; the before/after below is larger because "before" also copied
the whole input.

| `bench/compare.py --app json_query` | before (5f10aaa) | after (412156c) |
| --- | ---: | ---: |
| AIL median | 7.834 ms | 6.801 ms |
| C median | 4.721 ms | 4.823 ms |
| AIL/C ratio (median [range]) | 1.660 [1.635, 1.669] | 1.423 [1.378, 1.447] |
| peak RSS AIL/base/C | 2784/2700/2612 KiB | 2720/2780/2612 KiB |
| binary AIL/base/C | 154936/154936/29512 B | 159416/159416/29512 B |

The ratio ranges do not overlap: 14.3% lower AIL/C. Probes in `/tmp/probes` covered literals,
arguments, slices, list items, struct/class attributes and `dict[str, bytes]` values, empty and NUL
input, 1-4 byte code points, truncation/overlong/surrogate/out-of-range sequences, unused
validate-only locals, temporary (ephemeral) decodes and aliasing after rebinding; both builds match
CPython, except a non-BMP code point, which the v2 build refuses by name.

# DEVLOG

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
