# AIL vs C and Rust benchmark, with build time — 2026-10-24

Commit `25c9481` (base arm `HEAD`), 4-core GitHub Actions runner, one CPU pinned per run. Each app:
9 windows x 16 rounds, arms interleaved, boundary controls checked and timed output compared
byte-for-byte with the Python oracle. Build times are wall seconds, median of three runs: a cold
build with a fresh build directory and fresh caches, then an incremental build after appending one
harmless comment line to the app's source with those caches warm. Build disk, binary size and RSS
are unchanged measurements from the existing pass. The `base` column of an existing column is the
AIL baseline arm; build time is measured for AIL, C and Rust as requested. Raw measurements,
including per-window data and the build-time medians in milliseconds, are in
`bench/results/2026-10-24-25c9481.json`.

| app | ms ail/base/c/rust | ail/base | ail/c | ail/rust | RSS MiB ail/base/c/rust | binary KiB ail/base/c/rust | build disk KiB ail/base/c/rust | cold build s ail/c/rust | incremental build s ail/c/rust |
|---|---|---|---|---|---|---|---|---|---|
| binary_cursor_records | 42.3/42.3/10.2/9.4 | 1.000 [0.993, 1.011] tie | 4.179 [3.952, 4.315] slower | 4.394 [4.118, 4.499] slower | 1.8/1.8/2.6/2.8 | 39/39/15/1912 | 196/196/32/1932 | 2.26/0.07/2.44 | 0.18/0.08/2.45 |
| binary_search | 110.2/109.9/85.6/262.8 | 0.999 [0.992, 1.004] tie | 1.285 [1.276, 1.291] slower | 0.419 [0.417, 0.421] faster | 65.4/65.4/65.6/65.8 | 38/38/16/1919 | 192/192/36/1936 | 2.02/0.11/2.48 | 0.18/0.11/2.43 |
| csv_table | 14.6/14.5/7.0/7.3 | 1.001 [0.995, 1.011] tie | 2.101 [2.096, 2.110] slower | 1.992 [1.957, 2.001] slower | 5.5/5.5/3.3/3.7 | 107/107/20/1928 | 400/400/44/1952 | 4.38/0.17/2.58 | 0.21/0.17/2.59 |
| json_query | 5.8/5.8/3.2/3.6 | 0.999 [0.977, 1.010] tie | 1.776 [1.763, 1.817] slower | 1.602 [1.562, 1.640] slower | 2.8/2.7/2.7/3.1 | 151/151/28/1912 | 396/396/56/1940 | 7.12/0.34/2.61 | 0.40/0.33/2.63 |
| numeric_scale_binary | 23.6/23.8/15.7/15.7 | 0.990 [0.981, 1.000] faster | 1.497 [1.487, 1.511] slower | 1.502 [1.490, 1.509] slower | 2.1/2.1/2.7/2.8 | 43/43/16/1942 | 212/212/36/1960 | 2.16/0.11/2.40 | 0.17/0.11/2.38 |

Toolchain KiB (`du -sk`, once per language): c 124048, rust 631288, ail 18436.

Time ratios are AIL / reference (median [rank-2..8 range]); lower is better. RSS is peak resident
set, binary size is KiB, and build disk is the fresh-cache/build-directory total in KiB.

## Where AIL's cold build time goes

An LD_PRELOAD exec/exit logger with monotonic timestamps (not the `time` command, and not an
estimate) split fresh-cache cold builds into the AIL front end, the C compiler (gcc driver, cc1 and
as) and linking (collect2/ld plus the final output write). For `csv_table`, the slowest front end,
the whole compile took 4.40 s: 2.54 s (58%) was the AIL front end, of which 2.35 s was the pyc
type-check and C emission after 0.20 s of process start-up and source loading; 1.77 s (40%) was the
C compiler, and 0.09 s (2%) was linking. Across all five apps the front end took 55-65% (2.54 s for
csv_table, 3.60 s for json_query), the C compiler 31-44% (1.77 s and 2.85 s), and linking 2-3%
(0.07-0.11 s); `json_query`'s separate `file_identity.o` prepare step is outside these timings. So
the build is dominated by the Python front end rather than by gcc or the linker, which together
account for roughly two fifths of a cold AIL build.
