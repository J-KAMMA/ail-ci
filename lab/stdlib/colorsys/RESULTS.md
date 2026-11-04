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

To be filled in after the module is added.

## Instructions (1M pixels)

To be filled in after `bench_pixels.py` is written.
