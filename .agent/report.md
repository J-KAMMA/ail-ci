# job job-fuzz38-10230819  started 2026-10-22T23:20:24Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the silent string-repr bug in commit `42426a0`.

- **Cause:** the typed runtime's `str.isprintable()` table came from CPython 3.13.6 (Unicode 15.1), so `repr(chr(0x2FFC..0x2FFF))` and `repr(chr(0x31EF))` printed raw characters where CPython 3.12 prints `'\u2ffc'` etc.
- **Fix:** `AIL_CURRENT/python/pkg-v12/cruntime.py` now adapts the typed repr table to the running CPython, matching what the general path already did.
- **Test:** added `test_ail_fuzz38.py` (both builds, direct `repr`, `%r`, f-string `!r`, list/dict nesting) and registered it in `ail_check.MODULES`.
- **Probes:** `f38_bmp`, `f38_paths`, `f38_literals`, `f38_quotes` — all matched CPython on both builds. They cover literals, `chr`, function arguments, list items, attributes, dict values, nesting, quotes, backslashes, controls and BMP non-ASCII.
- **Tests:** `test_ail_fuzz38`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (329s). Manifest `--check` passes.

Other observed differences, not fixed (outside this fix): set repr ordering; `bytearray` repr not escaping `'` inside double quotes; `chr()` surrogates differ (general path internal error, default `ValueError`); non-BMP `chr()` fails on the general path; `ascii()` is refused by name; `10**30` overflows. `DIFFERENCES.md`/`DEVLOG.md` are not present in this export, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 3959961, "input": 91510, "output": 11251, "reasoning": 14000, "cache.write": 0, "cache.read": 3843200}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** `cruntime.py` `_unprintable_table()` now runs the stored 3.13.6 table through `repr_runtime_for_host()`, so the typed `STRREPR` table matches the 3.12 oracle. Plus `test_ail_fuzz38.py` and its registration/hashes.

**Probes** (`cmp.sh`, both builds unless noted):

| probe | result |
|---|---|
| p1 `repr(chr(0x2ffb..0x3000,0x31ef,0x31f0,0x378,0xe000,0x1f600,0x10ffff))` | HEAD d matches CPython; HEAD g fails on non-BMP `chr` (same on base) |
| p5/p7 BMP + all three changed ranges (`0x2ffc..0x2fff`, `0x31ef`, `0x2ebf0..0x2ee5d`) | HEAD d matches; base d was wrong at every changed range |
| p3 values via arg/list/attr/dict, `%r`, `!r`, `.format` | HEAD g+d match |
| p2b quotes, `\\`, `\t\n\r`, `\x00..\x9f`, `\xa0`, U+2028/200B/FEFF, raw strings | matches up to the pre-existing non-BMP `chr` failure |
| p8 non-BMP literals | HEAD d matches; g refuses by name (pre-existing) |
| pv2 (`repr` through typed function arg) | base d **wrong**, HEAD d correct |
| p6 no-feature program (`int` + `print`) | `--debug-dir` C **identical** base vs HEAD |
| p9 bytearray/set/`10**30` | identical defect on base → pre-existing |

Table diff is exactly the three ranges newly assigned in Unicode 15.1 (712→711 ranges), so the lookup algorithm/hot path is unchanged. Compile-time `cruntime` import grew ~0.08 s.

**Report claims**
- Cause/fix: **verified** (base prints `'⿼'`, HEAD prints `'\u2ffc'`; v2 general path already did).
- Registered test + manifest `--check`: **verified** (`exit 0`).
- `test_ail_fuzz38` and `test_ail_safetynet`: **verified** (4.3 s, 118.9 s, 0 failed). `test_ail_files`/`test_ail_corpus_findings3` not re-run per review policy.
- Probes “matched on both builds”: **false in substance for the default build** — see defect.
- Observed differences (set order, bytearray quoting, non-BMP `chr`, `ascii` refusal, `10**30`): **verified as pre-existing**. Surrogate `chr` **unverified**.

**Pre-existing (not blocking):** general-path non-BMP `chr`/literal failures; set repr ordering; bytearray quote escaping; `10**30` overflow; `ascii()` refused by name.

### Defect
1. `test_ail_fuzz38.py` does not exercise the typed path, so it does not guard the fix. Its `PROGRAM` uses `f"{s!r}"`, which the typed compiler refuses (“a format field of type str with the format spec '%r'”); with `AIL_QUIET_FALLBACK=1` the default-build run silently compiles on the general path. Running that exact program (`/tmp/rprobes/ptest.py`) on base gives `d same stdout` (passes), even though base’s typed path is wrong; a minimal typed-path probe (pv2) on base gives expected `'\u2ffc'` / actual `'⿼'`. Expected: the new test fails on `work`; actual: it passes. Rewrite the program to stay on the typed path (e.g. only `repr(s)`/`len(repr(s))`, and verify it fails on `work`).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1032730, "input": 43132, "output": 8104, "reasoning": 17910, "cache.write": 0, "cache.read": 963584}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect in commit `d824883`.

- Rewrote `test_ail_fuzz38.py` PROGRAM to stay on the typed path (`repr(s)`/`len(repr(s))` only, no refused `!r` field). It now **fails on `work`** default build (`'⿼'` vs `'\u2ffc'`) and **passes on HEAD** for both builds.
- Probes on final commit (`cmp.sh`, both builds): `f38_typed`, `f38_paths`, `f38_literals`, `pv2`, `p5`, `p7` — all `same stdout` on `g` and `d`.
- Tests on final commit (`par_check.py -j 2`): `test_ail_fuzz38`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4 modules, 0 failed (247s)**.
- Manifest `--check` exits 0. `DIFFERENCES.md`/`DEVLOG.md` are absent from this export, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 359268, "input": 19466, "output": 3013, "reasoning": 3349, "cache.write": 0, "cache.read": 333440}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed HEAD (`d824883`, on top of `42426a0`) against base `work` (`5f26495`).

**Change**
`_unprintable_table()` now extracts the printability table from `repr_runtime_for_host(OBJ2)` instead of raw `OBJ2`, so the typed/default runtime's `repr(str)` uses the oracle CPython's Unicode table. `test_ail_fuzz38` was reduced to `repr(s)`/`len(repr(s))` so it stays on the typed path; the removed `!r`/container lines made the default build fall back to the general path and pass on base.

**Probes (`cmp.sh`, HEAD)**
- `q1_boundaries`: default same stdout (arg/list item/dict value/attribute, 0x2ffc–0x2fff, 0x31ef); general crashes on `chr(0x10ffff)` — identical on base.
- `q2_escapes`: default same stdout (quotes, backslash, tabs, newlines, controls, non-ASCII, raw strings); general refuses non-BMP literal — identical on base.
- `f38_typed` (worker): fails on base default (`'⿼' 3` vs `'\u2ffc' 8`), passes HEAD both builds.
- `f38_paths`, `f38_literals`, `/tmp/probes/p5.py`, `p7.py`, `pv2`: same stdout both builds on HEAD.
- No-feature program: generated `program.c` byte-identical to base; a repr program differs from base only in 3 table rows (expected).
- Extra new non-BMP code points (0x2ebf0, 0x2ee5c) are fixed on default (`p7`).

**Tests (HEAD, `-j 2`)**
`test_ail_fuzz38`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed, 248s. `update_manifest.py --check`: 0. `DIFFERENCES.md`/`DEVLOG.md` are indeed absent from this export. All report claims verified.

**Pre-existing (identical on base, not blocking)**
- General path: `AIL internal error: chr() non-BMP code point requires 32-bit strings`; named refusal of non-BMP literals.
- Both builds: `str`/`repr` of list/tuple containing U+2FFC prints raw `⿼` instead of `\u2ffc` (probes `p4_containers`, `p6_liststr`).
- `ascii()` is refused by name on both builds.

**Speed**
`icount`/`perf` unavailable (`perf_event_open: Permission denied`). Generated code differs only in table constants; compiler startup on 3.12 grows ~0.04s → 0.12s.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2497162, "input": 62408, "output": 10388, "reasoning": 24238, "cache.write": 0, "cache.read": 2400128}]

FINAL VERDICT: ACCEPT  2026-10-22T23:59:36Z
