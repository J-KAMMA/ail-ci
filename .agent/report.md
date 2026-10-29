# job job-stdlib43-10291548  started 2026-10-29T06:56:56Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"d6625d31-5193-415f-8770-a3f11e923f8e","session_id":"a5167182-e08b-44dd-ad63-71b7debbf6c4"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"111bfb44-e2c1-4d60-8434-5bd8a919eebf","session_id":"57ef4848-85e0-45d8-9508-1ac455a3c04d"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented `struct` support (the most-used still-refused import: 6 files) via `structlib.py`, lowering literal-format `pack`, `unpack`, `calcsize`, `pack_into`, and `unpack_from`. Unsupported codes and non-literal formats remain named refusals. Added and registered `test_ail_stdlib43.py`, plus DEVLOG/DIFFERENCES entries and manifest pins.

Commits: `991b405` (implementation), `c31d2ef` (probe-note correction).

Tests on final commit, `-j 2`: 7 modules, 0 failed, 411s:
`stdlib43`, `stdlib_batch4`, `stdlib5`, `python_syntax`, `safetynet`, `files`, `corpus_findings3`. `update_manifest.py --check` passes.

Probes in `/tmp/probes/stdlib43`:
- Match CPython both builds: `p1_formats`, `p2_errors`, `p3_routes`, `p4_imports`, `p6_star`.
- Refused by name both builds: `p5_error_value`, `p7_memoryview`, `p8_error_repr`, and `r1_float`, `r2_double`, `r4_pascal`, `r5_nonliteral`, `r6_struct_class`, `r7_iter`, `r8_alias_value`.
- `r3_half` (`calcsize('<e')`) matches CPython, since `calcsize` supports every valid format.
[cost $0.0534, opencode tokens {"total": 4188391, "input": 114828, "output": 17417, "reasoning": 22738, "cache.write": 0, "cache.read": 4033408}]
    tool time: bash 22.2 min
        460s bash   python3 tools/par_check.py -j 2 test_ail_stdlib43 test_ail_stdlib_batch4 test_ail_stdlib5 test_ail_python_synt
        412s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_stdlib43 test_ail_stdlib_
         68s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_stdlib43.py') s=p.read_text() old="""  
         68s bash   python3 tools/update_manifest.py && python3 tools/par_check.py -j 2 test_ail_stdlib43 2>&1 | tail -30
         67s bash   python3 tools/par_check.py -j 2 test_ail_stdlib43 2>&1 | tail -40
         52s bash   python3 tools/par_check.py -j 2 test_ail_stdlib43 2>&1 | tail -100
         40s bash   mkdir -p /tmp/probes/stdlib43 cat > /tmp/probes/stdlib43/p1_formats.py <<'PY' import struct   def main() -> No
         26s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/structlib.py') s=p.read_text() ol

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds `structlib.py` and hooks it from `stdlib4.rewrite_text`/`ail_syntax.python_surface`; literal-format `struct.pack/unpack/calcsize/pack_into/unpack_from` are folded or lowered to generated AIL helpers for `bBhHiIlLqQnNP?csx`, `struct.error` in `except` is replaced by a locally generated class, and all other struct uses are named refusals. This matches the report apart from the two defects below.

**Probes** (both builds via `cmp.sh`, `/tmp/rprobes/`):
- `f1_formats` (59 formats incl. native/`=`/`!`, whitespace, zero counts, `s`/`c` repeats): same as CPython both builds.
- `f4_fuzz` (140 random formats, pack/unpack/calcsize): same both builds.
- `f5_offsets_fuzz` (120 random `pack_into`/`unpack_from`, positive/negative/out-of-range offsets and errors): same both builds.
- `f2_routes_buffers` (values via argument/list/dict/attribute; `s` padding preserved; mutate bytearray after `unpack_from`; `pack_into` aliasing): same both builds.
- `f7_bytes_formats` (bytes format literals): same both builds.
- `n1_substring` (class `structure`, no struct import): `program.c` byte-identical to base `/tmp/base43`; only `native_report.json` paths differ.
- Worker probes `p1,p2,p3,p4,p6` re-run: same both builds; `p5,p7,p8` refused with the reported names.
- **`f3_error_name`, `f10_bool_off_err`: differ both builds (defects).**

**Defects**

1. `struct.error` is renamed when the program itself binds the name `error`, so the exception type name differs. `structlib.py:447` chooses `_AilStructError`, and no `__name__` correction is applied.
   Probe `/tmp/rprobes/f3_error_name.py`:
   ```python
   import struct
   def main() -> None:
       error = 5
       try:
           struct.pack('<b', 200)
       except struct.error as e:
           print('name', type(e).__name__)
           print('msg', str(e))
       print(error)
   main()
   ```
   Expected (CPython): `name error` / `msg 'b' format requires -128 <= number <= 127` / `5`.
   Actual (both builds): `name _AilStructError` / same msg / `5`.
   (Any program with a local variable/parameter/loop target named `error` triggers this.)

2. A `bool` offset is not converted to an index before being formatted into error text. `structlib.py:64-67` returns the original bool, so messages say `offset True` where CPython says `offset 1`.
   Probe `/tmp/rprobes/f10_bool_off_err.py`:
   ```python
   import struct
   def main() -> None:
       try:
           struct.unpack_from('<i', b'ab', True)
       except struct.error as e:
           print('uf2', str(e))
       try:
           struct.pack_into('<i', bytearray(2), True, 1)
       except struct.error as e:
           print('pi2', str(e))
   main()
   ```
   Expected (CPython): `uf2 unpack_from requires a buffer of at least 5 bytes for unpacking 4 bytes at offset 1 (actual buffer size is 2)` / `pi2 pack_into requires a buffer of at least 5 bytes for packing 4 bytes at offset 1 (actual buffer size is 2)`.
   Actual (both builds): identical text but `at offset True`.

**Pre-existing:** `from re import error` / `from zlib import error` programs are refused identically on base and HEAD (re invalid-pattern and zlib `error` not exported); not caused by this change.

**Report claims:** most-used still-refused module and 6 `struct` files: verified (6 files). Literal `pack/unpack/calcsize/pack_into/unpack_from` support, all byte orders, native alignment, padding, empty/zero formats, repeat counts: verified. Refusals for float/double/half/Pascal/non-literal/`Struct`/`iter_unpack`, `struct.error` as a value, memoryview: verified by tests/probes. “Error texts reproduce CPython”: **false** (defect 2). “`struct.error` catchable via module/from/alias”: verified, but its class name is wrong when `error` is bound (defect 1). Manifest `--check`: verified. The 7-module test run is only partly verified: `test_ail_stdlib43` and `test_ail_safetynet` pass on HEAD (`-j 2`, 82 s); the other five modules were not re-run per instructions.

**Not checked:** native mode on a big-endian/LP32 host; speed (change is compile-time and non-struct C is unchanged).

VERDICT: FIX

1. `/tmp/rprobes/f3_error_name.py`: expected `name error`, actual `name _AilStructError` on both builds.
2. `/tmp/rprobes/f10_bool_off_err.py`: expected `... at offset 1 ...`, actual `... at offset True ...` on both builds.
[cost $0.0498, opencode tokens {"total": 2386698, "input": 96697, "output": 10817, "reasoning": 36880, "cache.write": 0, "cache.read": 2242304}]
    tool time: bash 5.7 min
         83s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_st
         73s bash   cd /tmp/probes/stdlib43 && for f in p1_formats p2_errors p3_routes p4_imports p6_star; do echo "=== $f"; bash 
         57s bash   cd /tmp/rprobes && cat > gen2.py <<'PY' import random random.seed(43) codes=['b','B','h','H','i','I','l','L','
         29s bash   cd /tmp/rprobes && cat > gen3.py <<'PY' import random, struct random.seed(7) signed=set('bhilqn') def values(f
         25s bash   cd /tmp/rprobes && for f in f2_routes_buffers.py f3_error_name.py; do echo "===== $f"; bash ~/tools/cmp.sh $f 
         20s bash   cd /tmp/rprobes && sed -i "s/'  <2i',//" gen.py && python3 gen.py && bash ~/tools/cmp.sh f1_formats.py /home/r
         19s bash   cd /tmp/rprobes && cat > f6_re_error_collision.py <<'PY' import re import struct from re import error   def ma
         13s bash   cd /tmp && python3 - <<'PY' import struct def s(l,f):     try: print(l,'->',f())     except Exception as e: pr

## fix round skipped: only 68 minutes left

FINAL VERDICT: FIX  2026-10-29T10:43:49Z
