# job job-fuzz31-10230632  started 2026-10-22T21:33:20Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `02a3d37`.

- Found first silent stdout diff in probe `f5` (default build): positive `+`/space signs were dropped in f-string floats (`{0.5:+.1f}` → `0.5`). Cause: `ir/lower_text.py:fmt_value` used only the small padding formatters and ignored general specs.
- Fix: `fmt_value` now refuses general-format specs by name (`NotS0`), so the legacy emitter handles them via `ail_fmt_gen`. This also covers `#`, grouping, `=`, type-less floats, and `g`/`e`/`%`.
- Added `AIL_CURRENT/test_ail_fuzz31.py` (2 tests) and registered it in `ail_check.py`; manifest updated and `--check` passes.

Probes on final commit (`/tmp/probes/f1`–`f14`, `iso1`, `iso2`): all match CPython on both builds except:
- `f8` general build: pre-existing garbage output for huge `{1e308:f}` (confirmed same on base).
- `f10`: both builds exit 1; stderr wording differs (“division by zero” vs “float division by zero”).

Tests on final commit: `test_ail_fuzz31` 2/2, `test_ail_safetynet` 5/5, `test_ail_files` 18/18 (1 skipped), `test_ail_corpus_findings3` 2/2 — 4 modules, 0 failed.

Records note: this checkout has no `DEVLOG` or `DIFFERENCES` file, so no entries were added there.
[cost $0.0000, opencode tokens {"total": 10659734, "input": 152953, "output": 18542, "reasoning": 22575, "cache.write": 0, "cache.read": 10465664}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** `ir/lower_text.py:fmt_value` now raises `NotS0` when `_fmt_general_needed(spec, kind)` is true, so f-string/`%` fields with sign, `#`, grouping, `=`, non-space fill, type-less floats, or `g/e/%` fall back to the legacy emitter instead of silently dropping the flag. The new `test_ail_fuzz31.py` is registered and in the manifest. Commit `02a3d37` is clean.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`, both builds):

| probe | HEAD | base |
|---|---|---|
| p1 general float specs (+/space/#/,/_/=/fill/e/g/%) | matches CPython; huge general-build garbage (see pre-existing) | same exe as HEAD; default matches |
| p2 small float specs, 0.1+0.2 | both match | identical C (`exe` sha) |
| p3 int sign/group/hex + str fill | both match | default dropped signs/fill |
| p4 lone/multi signed f-string | both match | default dropped sign even for a lone field |
| p5 `%` formatting | both match | identical |
| p6 empty/0/±0/1e±308 | both match | identical |
| p7 `{int:.2f}` | both match | identical |
| p8 unrelated program | both match | identical C (`exe` sha) |
| p9 sign via arg/list/dict/attr | both match | default dropped `+` |
| p10 `.format()`/`format()` | both match | identical |
| p11 `{str:05}` | pre-existing wrong (below) | identical `exe` |
| p12 tiny/huge small specs | default matches; general garbage (pre-existing) | identical `exe` |
| p13 huge `{1e308:+.2f}` | default fixed; general garbage (pre-existing) | default dropped sign; general identical `exe` |
| p14 huge `{1e308:,.2f}` | both match | default dropped grouping |
| p15 .5 ties, negative zero, width/sign | both match | identical |

**Pre-existing (identical on base, not blocking):**
- General build (`AIL_UNIFIED_FORCE=1`) prints NUL/uninitialized heap bytes for large fixed-point floats with sign/align/general specs (p1/p12/p13, worker's f8). `exe` byte-identical to base.
- `{s:05}` on a str prints `[0000a]`, CPython `[a0000]` (p11); `exe` identical to base.
- f10 division-by-zero stderr wording differs (`division by zero` vs `float division by zero`); same on base, stdout/exit match.

**Claims:** verified — commit/fix/cause, fallback behaviour, spec coverage, test registration, manifest `--check` (rc 0), f8 and f10, and absence of DEVLOG/DIFFERENCES. `test_ail_fuzz31` + `test_ail_safetynet` pass (`-j 2`, 0 failed); `test_ail_files`/`test_ail_corpus_findings3` not rerun (reviewer rule). Minor non-blocking: the new test docstring says the sign loss happened only when a field followed another field; p4 shows a lone `f"{x:+.1f}"` also lost the sign on base.

**Speed:** gdev `g03_004` and `g18_026` executables are byte-identical HEAD vs base (same sha), so instruction counts cannot change; `icount` itself is unavailable (`perf_event_open` EACCES). `g13_038` is refused on both.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1454796, "input": 65455, "output": 8493, "reasoning": 18416, "cache.write": 0, "cache.read": 1362432}]

FINAL VERDICT: ACCEPT  2026-10-22T22:02:51Z
