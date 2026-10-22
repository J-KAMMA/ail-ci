# job job-fuzz20-10230625  started 2026-10-22T21:26:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Commit `371e01a` on `job-fuzz20-10230625`.

**Fix:** `int.from_bytes` on the general path used `bytes()` constructor coercion, so `int.from_bytes(1, "big")` and `int.from_bytes(None, "big")` returned `0` instead of raising `TypeError`. `prelude_bytes._ail_from_bytes` now rejects `int`/`bool`, `None`, and `str`. Added `test_ail_fuzz20.py` and a DEVLOG/DIFFERENCES entry; manifest check passes.

**Probes** (`/tmp/probes/p01–p11`, both builds):
- p02–p06, p08–p11: same stdout, exit 0.
- p04 (the bug): previously `int.from_bytes(1)`/`(None)` printed `0`; now matches CPython, including via arguments, list items, attributes, dict values, bytearray, list/tuple iterables, and the typed `hashlib` path.
- p01: both builds error with `integer overflow` on `1 << 63` (pre-existing 64-bit limit, not silent).
- p07: general build matches; default build prints `ValueError` with an empty message for negative shifts while CPython says `ValueError negative shift count` (pre-existing, only message text).
- Named compile-time refusals seen: `memoryview`, `hex(x, 16)`, `bit_length(arg)`, bool passed to an `int` helper, and integer literals outside int64.

**Tests on final commit:** `test_ail_fuzz20`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 317s, 0 failed. `update_manifest.py --check` rc 0. No push.
[cost $0.0000, opencode tokens {"total": 3221737, "input": 75988, "output": 13376, "reasoning": 9045, "cache.write": 0, "cache.read": 3123328}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review: `371e01a` fuzz20 from_bytes fix**

Diff: adds a type guard in `prelude_bytes._ail_from_bytes` rejecting `None`, `int`/`bool`, `str`, plus tests and DEVLOG/DIFFERENCES/manifest entries. No other code paths touched.

Probes (`/tmp/rprobes`, both builds, HEAD vs base):
- `p1_invalid` — invalid sources via arg/list/dict/attribute (`1`, `None`, `"abc"`, `1.5`, `True/False`): HEAD matches CPython on both builds; base returned `0`/wrong messages. Fix verified.
- `p2_valid` — bytes, bytearray, list, tuple, range, bool iterables, both byteorders, signed/unsigned: matches both builds.
- `p3_badints` — `[256]`, `[-1]`, `[1.5]`, `[None]`, `["a"]`, `[b"x"]`, bad byteorder, empty signed: `[b"x"]` reports `'instance'` vs CPython `'bytes'`; identical on base → pre-existing.
- `p4_other_int` — `bit_length`, `bit_count`, `bin`/`hex`/`oct`, `&|^~`, `to_bytes` (0/large/signed): matches both builds.
- `p5_control` — feature-free program: `--debug-dir` `program.c` identical HEAD/base (only temp paths in report differ).
- `p6_shift63` — `1 << 63`: `integer overflow` on both HEAD and base → pre-existing.
- `p7_negshift` — default build `ValueError` empty message vs `negative shift count`; general build matches; identical on base → pre-existing.
- `p8_literal` — literal `int.from_bytes(1/None/"ab"/True, "big")`: matches CPython on both builds; base returned `0`.
- `p9_intsub` — int subclass: refused by name on both base and HEAD; acceptable.

Tests: `test_ail_fuzz20` 32.6s and `test_ail_safetynet` 117.4s, 0 failed. `update_manifest.py --check` rc 0. I did not re-run `test_ail_files`/`test_ail_corpus_findings3` (review scope), so that part of the 4-module claim is unverified. Change is not hot-path, so no icount run.

Claim check:
- Fix cause/behaviour: verified.
- Rejects `int`/`bool`, `None`, `str`: verified.
- Valid bytes-like/iterable and typed-path calls still correct: verified for static `bytes` calls; not separately inspected in hashlib lowering.
- p01 overflow and p07 message differences: verified pre-existing.
- Named refusals list: only int-subclass refusal verified; others unverified.
- Tests/manifest: verified for the two required modules and manifest.

Pre-existing (not blocking): `[b"x"]` element TypeError text; `1 << 63` integer overflow; default-build empty `ValueError` message on negative shifts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 611687, "input": 26624, "output": 4866, "reasoning": 8037, "cache.write": 0, "cache.read": 572160}]

FINAL VERDICT: ACCEPT  2026-10-22T21:46:12Z
