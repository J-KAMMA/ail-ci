# job job-fuzz46-10231202  started 2026-10-23T03:03:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- **First silent difference:** `p08.py`, `f"{1e300:.2f}"`. Both builds exited 0 but printed 65 bytes of valid text followed by stack memory. Cause: `ail_obj_format` formatted floats into `char buf[66]` while using `snprintf`'s full return length (302) as the text length, causing an over-read.
- **Fix:** size the buffer from `snprintf(NULL, 0, ...)`, heap-allocate it, and free it after padding (`AIL_CURRENT/python/pkg-v12/cruntime.py`).
- **Probes:** p01–p06, p08–p11 match CPython on both builds, covering nested quotes, calls, dict/list/attribute/argument values, conditionals, nested specs, self-documenting `=`, empty/zero/negative/huge floats, `.0f/.2f/.400f`, width/alignment, and inf/nan.
- **Other difference:** p07/p07a exit 1 with `integer overflow` from `2**63`/`-2**63`; confirmed identical on base `fc8ef9c`, pre-existing, not silent.
- **Tests:** `test_ail_fuzz46`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 0 failed (205s).
- **Records:** this CI export contains no DEVLOG/DIFFERENCES files, so no entry was possible.
- Manifest `--check` and `ci_shards --check` pass. Commit: `d9053b1`.
[cost $0.0000, opencode tokens {"total": 4267483, "input": 109907, "output": 9335, "reasoning": 9361, "cache.write": 0, "cache.read": 4138880}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `fuzz46` (`d9053b1`)**

**Change:** `ail_obj_format`'s float branch now sizes its buffer via `snprintf(NULL, 0, ...)`, heap-allocates `need + 2`, and frees it after padding. Adds `test_ail_fuzz46.py`, manifest, shard and `ail_check` entries.

**Probes (`/tmp/rprobes`, HEAD, general/default vs CPython):**
- `p1` huge fixed fields with grouping, signs, space, zero-pad, center: general same; default differs (ignores `,`/`_`/sign) — identical on base.
- `p2` values via call, list item, attribute, dict: both same.
- `p3` `.400f` / `.1000f` / negative / width: general same; default wrong at ≥1000 digits — identical on base.
- `p4` wrong types (`str:.2f`, `str:d`): AIL `TypeError`, CPython `ValueError`, both builds — identical on base.
- `p5` no f-string formatting: both same; generated C differs only in the embedded runtime branch.
- `p6` int/str fields, grouping/sign/width: general same; default grouping/sign differs — identical on base.
- `p7`/`p12` nested braces, dynamic width/precision, `!r`/`!s`, self-documenting `=`: both same.
- `p8` half-even rounding, subnormals, `1.797e308`: both same.
- `p9` repeated/aliased large results and slices: general same; default grouping differs — identical on base.
- `p10` large exponent, concatenation, equality: both same.
- `p11` nested same-type quotes, dict access, conditionals: both same.
- `p13` `.3000000000f`: general prints `1.000000`; CPython raises `ValueError` — identical on base.
- `p14` inf/nan/-0.0 with signs, grouping, zero-pad: both same.
- `p7a` `2**63`/`-2**63`: exit 1 “integer overflow”, general; base same.

**Pre-existing (all reproduced on `/tmp/base`):** default-build ignores float/int grouping and sign flags; default-build mishandles precision ≥1000; wrong-type format raises `TypeError` instead of `ValueError`; oversized precision is not refused; `2**63` overflow refusal.

**Tests:** `test_ail_fuzz46` 5.0s, `test_ail_safetynet` 93.2s, `test_ail_files` 104.3s, `test_ail_corpus_findings3` 158.7s — 0 failed. Manifest and `ci_shards --check` pass (rc 0).

**Speed:** `icount`/`perf` unavailable (`perf_event_paranoid=4`). A 1M-iteration `f"{12345.6789:.2f}"` microbenchmark went 0.25s → 0.40s from the extra `snprintf`/malloc, but gdev programs format only a handful of floats, so no material impact.

**Report claims:** cause and fix verified; p07 verified on base; tests and record-file absence verified; exact p01–p11 sets not inspectable, but equivalent probes pass on the general path. The worker’s “both builds” claim is not true for default-build grouping/sign, which is pre-existing.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1168094, "input": 37909, "output": 7423, "reasoning": 9162, "cache.write": 0, "cache.read": 1113600}]

FINAL VERDICT: ACCEPT  2026-10-23T03:28:05Z
