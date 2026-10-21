**Result:** 1 silent-difference cause found and fixed; 0 other silent differences in the sampled space.

**Fuzzing:** 384 random programs (144 generator-1 + 240 generator-2) run with `bash ~/tools/cmp.sh` on both builds. Generator-2 combined split/rsplit maxsplit, strip chars, replace count, find/rfind/count/startswith/endswith windows, center/ljust/rjust, zfill, expandtabs, partition/rpartition, splitlines, casefold, and negative/huge/zero-step slices.

**Fix (commit `7ef8660`):**
- General path `ail__win` in `AIL_CURRENT/python/pkg-v12/cruntime.py` collapsed an inverted or past-the-end window into the empty window at the clamped start. E.g. `"aXbXc".find("", 10, 0)` printed `5` instead of `-1`; `"abc".find("", 4)` printed `3`.
- `ail__win` now reports window validity and never clamps `start` above `len`; all find/rfind/index/rindex/count/startswith/endswith callers, plus list/tuple `index`, use that answer.

**Tests:** Added `AIL_CURRENT/test_ail_fuzz3.py` (4 tests: windows, methods/slices, zero-step, list/tuple index), registered in `ail_check.MODULES`. Final-commit run: 12 modules, 0 failed (255s), including `test_ail_fuzz3`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, and the str targeted modules.

**Probes (all in `/tmp/probes/` unless noted):**

| probes | result |
|---|---|
| `windows_ascii`, `indexwin`, `listindexwin`, `win_arg`, `win_list`, `win_dict`, `win_attr`, `index_arg`, `/tmp/fuzz3/progs/f21.py`, `/tmp/fuzz3/smoke.py` | same stdout both builds |
| `slices`, `sliceint64b`, `listslice`, `splits`, `replace`, `strip`, `padtab`, `splitlines`, `ws`, `casefold`, `partition_ascii` | same stdout both builds |
| `zerostep`, `zerostep_var` | both builds exit 1, same stdout, `ValueError: slice step cannot be zero` |
| `casefold_nonascii` | default same; general path named `AIL limit: str_lower_nonascii` (not silent) |
| `astral` | default same; general path named build refusal: non-BMP literal |
| `translate2` | both builds refuse by name `.translate()` |

**Records:** Added `DEVLOG.md` and `DIFFERENCES.md` row `C?-job-fuzz3-10220508-1`. `update_manifest.py --check` returns 0. No push.
[cost $0.22, turns 113]
