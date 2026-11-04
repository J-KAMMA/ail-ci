# `colorsys` coverage results

Build command for every program:

```
AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/stdlib/colorsys/<program>.py --syntax python -o /tmp/<program>
```

The oracle is `python3 <program>.py` (CPython 3.12.3). `typed` means the default build stayed on the
typed path (no `built on the general path` note), `general` means the default build fell back to the
general path, and `refused` means the default build failed. Every built program is run and its stdout
and exit status are compared with CPython.

## Before (integ 1d44768)

The bundled `colorsys` module did not exist, so every program was refused at the import. The first
refusal line for each program is listed below; the common prefix is
`not in the subset: import of 'colorsys' is not available: this compiler builds only the modules it
models (...)`.

| program | default build | first refusal (general-path tail) |
| --- | --- | --- |
| `01_rgb_to_yiq.py` | refused | `colorsys.rgb_to_yiq (not yet published in NAMES_library.json)` |
| `02_yiq_to_rgb.py` | refused | `colorsys.yiq_to_rgb (not yet published in NAMES_library.json)` |
| `03_rgb_to_hls.py` | refused | `colorsys.rgb_to_hls (not yet published in NAMES_library.json)` |
| `04_hls_to_rgb.py` | refused | `colorsys.hls_to_rgb (not yet published in NAMES_library.json)` |
| `05_rgb_to_hsv.py` | refused | `colorsys.rgb_to_hsv (not yet published in NAMES_library.json)` |
| `06_hsv_to_rgb.py` | refused | `colorsys.hsv_to_rgb (not yet published in NAMES_library.json)` |
| `07_round_trip_yiq.py` | refused | `colorsys.rgb_to_yiq (not yet published in NAMES_library.json)` |
| `08_round_trip_hls.py` | refused | `colorsys.rgb_to_hls (not yet published in NAMES_library.json)` |
| `09_round_trip_hsv.py` | refused | `colorsys.rgb_to_hsv (not yet published in NAMES_library.json)` |
| `10_greys_and_edges.py` | refused | `colorsys.rgb_to_hls (not yet published in NAMES_library.json)` |
| `11_palette.py` | refused | `colorsys.hsv_to_rgb (not yet published in NAMES_library.json)` |
| `12_sort_by_hue.py` | refused | `colorsys.rgb_to_hsv (not yet published in NAMES_library.json)` |

Result: **0 built, 0 typed, 12 refused** (target: 12 built, at least 9 typed).

## After

`AIL_CURRENT/stdlib/colorsys.py` is now a bundled module, so `import colorsys` resolves before the
compiler treats an unknown library name as unavailable. Every program was built again in the default
build and with `AIL_UNIFIED_FORCE=1`; stdout and the exit status match CPython in both builds.

| program | default build | CPython stdout / exit |
| --- | --- | --- |
| `01_rgb_to_yiq.py` | typed | match / 0 |
| `02_yiq_to_rgb.py` | typed | match / 0 |
| `03_rgb_to_hls.py` | typed | match / 0 |
| `04_hls_to_rgb.py` | typed | match / 0 |
| `05_rgb_to_hsv.py` | general | match / 0 |
| `06_hsv_to_rgb.py` | typed | match / 0 |
| `07_round_trip_yiq.py` | typed | match / 0 |
| `08_round_trip_hls.py` | typed | match / 0 |
| `09_round_trip_hsv.py` | typed | match / 0 |
| `10_greys_and_edges.py` | typed | match / 0 |
| `11_palette.py` | typed | match / 0 |
| `12_sort_by_hue.py` | typed | match / 0 |
| `bench_pixels.py` | typed | match / 0 |

Result: **13 built, 12 typed, 0 refused**; the twelve coverage programs are **12/12 matching and
11/12 typed** (target 12/12 and at least 9/12), and `bench_pixels.py` is typed.

The one general-path program passes ints to `rgb_to_hsv` (`255, 0, 0`). The exact note is:

```
note: 05_rgb_to_hsv.py:18:5: built on the general path (about 20x slower) because an int where the
float parameter 'r' of colorsys.rgb_to_hsv() is annotated float; CPython keeps the int (annotations
convert nothing), so a later print or str() of it, or an int-valued result of arithmetic on it, shows
3 where this build would show 3.0. write instead: pass a float (`255.0`) if the value is meant to be
a float; run with --strict to see why
```

The program is not changed: CPython accepts the ints and keeps the int-valued result `v == 255`, so
the general path is the correct fallback. Making the typed path preserve int inputs through a
`float`-annotated parameter would need a compiler change (`python/pkg-v12`), outside this lane.

## Instructions (1M pixels)

`bench_pixels.py` builds on the typed path. It converts 1,000,000 pixels from a fixed LCG with
`rgb_to_hsv` then `hsv_to_rgb` and prints
`repr((sr, sg, sb)) = (500243.04967689514, 499707.93236351013, 499704.13153266907)`.
The output matches CPython exactly.

`tools/icount.c` was built, but `perf_event_open` is refused on this runner:

```
perf_event_open: Permission denied
```

So, as the task allows, the table uses the median of 5 wall-time runs instead of an instruction
count.

| metric | AIL | `python3` |
| --- | --- | --- |
| median wall time (5 runs) | 0.06 s | 1.62 s |
| executable / source size | 35,256 bytes (compiled binary) | 647 bytes (source) |
| peak RSS (`/usr/bin/time -v`) | 2,032 KiB | 10,436 KiB |

Wall times: AIL 0.06, 0.06, 0.06, 0.06, 0.07; CPython 1.57, 1.62, 1.63, 1.64, 1.57.

## Checks

* `AIL_CURRENT/test_ail_std_colorsys.py` builds all 13 sources in the default and forced-general
  builds, compares stdout and exit status with CPython, requires at least 9 typed coverage programs,
  and requires `bench_pixels.py` to stay typed. It skips without a C compiler.
* `AIL_CURRENT/tests.d/test_ail_std_colorsys.txt` registers the test module.
* Probes in `/tmp/probes/colorsys/` cover tuple returns and annotated float parameters on both
  builds; each matches CPython.
