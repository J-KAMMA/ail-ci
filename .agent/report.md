Final report

**Fixed 3 causes** (commit `0d05467`):
- `bytearray` `repr()`/`str()` now escapes a lone single quote like CPython: `bytearray(b"\'")`.
- `bytes.split(None, n)` / `rsplit(None, n)` keep the whitespace on the unprocessed side of the remainder once `n` is reached.
- Bytes/bytearray `%r` now preserves the bytes-like argument, so `b"%r" % b"ab"` is `b"b'ab'"` (`%s`/`%b` still unwrap; `*` width/precision still work).

**Probes:** ~76 programs run with `bash ~/tools/cmp.sh`, including 30 generated seeds (`r01`–`r30`) and hand-written cases `p0`, `p01`–`p45`, plus focused probes. All fix probes (`fix_repr`, `fix_split`, `fix_percent`, `fix_percent_types`, `p32`, `p32t`, `p33`, `p33t`, `ppercent`) match CPython on both builds. Probe coverage included empty/negative/huge indices, arguments, list items, dict values, attributes, aliasing, and both builds.

**Not fixed, listed for later:**
- `bytearray` `+=`/`*=` rebind instead of mutating, so a second name goes stale (`p24`, `p34`).
- Empty assignment to an extended `bytearray` slice raises `ValueError` where CPython accepts it (`r18`, `pslice2`).
- Ordering `bytes` against an equal `bytearray` crashes with `AttributeError` (`p13b`, `p35`, `r28`).
- Decoding a non-BMP UTF-8 code point (e.g. U+1F600) hits the 16-bit runtime internal error (`p26`).
- `%b`, `%a`, and mapping-key bytes formats remain unbuilt/unsupported (`p17`, `fix_percent_map`).
- Multi-argument `print` of a bytearray mutated by a later argument evaluates the repr too early (`p0`).

**Tests on final commit:** 14 modules, 0 failed, including `test_ail_fuzz12`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, and the targeted bytearray/silent modules. The earlier broad run also showed two unrelated pre-existing failures: `test_ail_fuzz1` (missing `tools/difffuzz.py`) and `test_ail_silent6` (`Lambda.lineno`). Manifest updated and `--check` passes.
[cost $0.1523, opencode tokens {"total": 13371927, "input": 525775, "output": 32015, "reasoning": 26425, "cache.write": 0, "cache.read": 12787712}]
