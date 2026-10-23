# job job-fuzz71-10231501  started 2026-10-23T06:02:45Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Local commit `e0e0647` (`job fuzz71: stop truncating huge fixed-point float formats`), not pushed.

- **Root cause fixed:** huge fixed-point float output overflowed fixed buffers in `ail_fmt_spec_float`, both `ail_obj_format` paths, and the full runtime’s float formatter; `.format` also silently clamped precision above 300. All now grow dynamically.
- **Tests:** added and registered `test_ail_fuzz71`; manifest updated and `--check` passes. Required targeted run passed: `test_ail_fuzz71`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4, 0 failed. No full suite run.
- **Self-check:** probes `p36`–`p42` now match CPython on both default and general builds; `p31`–`p33` rechecked clean.
- **Other differences observed, left pre-existing:** `%d` with floats errors instead of matching, `%c` above U+FFFF aborts, `%d` list error text differs, `"" * 10**12` hangs on the general path, and non-BMP literals are refused there.
- No `DEVLOG`/`DIFFERENCES` files exist in this export, so none were changed. Untracked `.agent/pipeline.md` was left alone.
[cost $0.0000, opencode tokens {"total": 8553209, "input": 369306, "output": 27885, "reasoning": 25330, "cache.write": 0, "cache.read": 8130688}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: fuzz71 — huge fixed-point float formatting

**Change:** grows the fixed buffers in `ail_fmt_spec_float`, both `ail_obj_format` float paths, and `safetyrt`'s float body; removes the 300-digit precision clamp. Adds `test_ail_fuzz71`.

**Probes** (all in `/tmp/rprobes`, each on default + general builds, HEAD):
- `p1_huge_fixed`: general path now matches CPython for `1e308:.0f` (base general emitted binary garbage). Default build drops the `+` flag in `f"{x:+.0f}"` — identical on base.
- `p2_huge_prec`, `p11_big`: precision 300/511/600/1000/100000/250000 for `f`, `e`, `g`, `%`, general/type-0; both builds match.
- `p4_containers`, `p16_specs`: huge values via arg, list item, dict value, attribute; dynamic specs; loop concatenation — both match.
- `p6_normal`, `p10_strbuild`: join, `+=` loops, `*`, normal formats — both match.
- `p7_formats`: `%`, `str.format`, f-string with huge values/precision — both match.
- `p8_int_specs`, `p13_alt`: ints with float specs (`f/e/g/%`), `#`, `n`, zero-fill, width — both match.
- `p9_widths`: widths up to 1200 with fill/align/zero/sign — both match.
- `p12_group_big`: grouping with precision 600/1000 still truncates (`1e308:,.600f` gives 510/910 vs 1012). Base is also wrong -> pre-existing.
- `p14_overflowf`, `p15_overflowf` (precision > INT_MAX): both builds wrong, identical on base -> pre-existing.
- `p3` discarded (probe itself was invalid CPython).

**Unchanged-codegen check:** simple join/`+=`/`*` program compiled with `--debug-dir`; HEAD and base `program.c` byte-identical (`diff rc=0`).

**Tests:** `test_ail_fuzz71`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed (`-j 2`). `tools/update_manifest.py --check` rc 0.

**Speed:** `tools/icount` unavailable (`perf_event_open: Permission denied`). Wall-clock microbench of 2M `f"{x:.2f}"`: HEAD 0.19s vs base 0.19–0.20s; no regression. Small precisions stay on the stack path.

**Claims:** root cause and `.format` clamp removal verified; test registration/manifest verified; 4/4 run verified; no DEVLOG/DIFFERENCES files confirmed. `p36`–`p42` and `p31`–`p33` unavailable -> unverified. "All now grow dynamically" holds for the listed float buffers, but `safetyrt`'s grouping buffer is still fixed (pre-existing, unlisted in the report).

**Pre-existing:** default-build `+` flag loss; grouping truncation/ignored for huge precision; precision > INT_MAX handling. None differ from base.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1836805, "input": 154675, "output": 10562, "reasoning": 21008, "cache.write": 0, "cache.read": 1650560}]

FINAL VERDICT: ACCEPT  2026-10-23T06:59:25Z
