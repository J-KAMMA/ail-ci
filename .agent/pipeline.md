# job job-stdlib19-10290445  started 2026-10-28T19:46:30Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"97a1cf33-8d3e-4e10-9a5c-8204722d9bae","session_id":"b1b08b3d-27a2-47d4-8c9c-53d24831e0bd"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"02416c1e-88bf-4e6c-a21e-af8dd5e870a3","session_id":"e3666619-70d9-416a-b477-ba1bb6817391"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `3cd7b09`.

- Added `struct` support: `pack`, `unpack`, `unpack_from`, `calcsize`, `error`, including native alignment, zero counts, str/bytes formats, bytearray buffers, `__index__`, and negative `unpack_from` offsets.
- New module: `AIL_CURRENT/test_ail_stdlib19.py` (4 tests); registered in `ail_check.py`.
- Required tests: 59 passed, 1 skipped across the 8 targeted modules.
- Probes: 10/10 matched CPython on both builds; 3 refusal probes failed both builds with named refusals.
- `tools/update_manifest.py --check` exits 0; DEVLOG and DIFFERENCES entries added.
[cost $0.0961, opencode tokens {"total": 11621624, "input": 148983, "output": 25082, "reasoning": 40839, "cache.write": 0, "cache.read": 11406720}]
    tool time: bash 20.6 min, edit 0.0 min, write 0.0 min, read 0.0 min
        497s bash   cd AIL_CURRENT && timeout 2400 python3 -m unittest test_ail_stdlib19 test_ail_stdlib5 test_ail_python_syntax t
        141s bash   for p in std19_zero_align std19_offsets std19_buffers std19_bounds std19_routes std19_alias std19_bytes_format
         71s bash   for p in std19_zero_align std19_offsets std19_buffers std19_bounds std19_routes; do echo "===== $p ====="; tim
         71s bash   for p in std19_zero_align std19_offsets std19_buffers std19_bounds std19_routes; do echo "===== $p ====="; tim
         43s bash   for p in std19_zero_align std19_offsets std19_buffers std19_bounds std19_routes; do echo "===== $p ====="; tim
         28s bash   for p in std19_index std19_bounds; do echo "===== $p ====="; timeout 600 bash ~/tools/cmp.sh /tmp/probes/$p.py
         24s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest test_ail_stdlib19 -v 2>&1 | tail -25
         24s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest test_ail_stdlib19 -v 2>&1 | tail -40

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: job `3cd7b09` (struct stdlib batch 6)

**What the change really does:** adds `structlib.py` + `prelude_struct.py` to lower `struct.pack/unpack/unpack_from/calcsize/error` for formats `x c b B ? h H i I l L q Q n N P s`, registers `test_ail_stdlib19`, and relaxes the `struct`→`class` wording rewrite so `struct.pack` notes survive.

**Claims checked**
- pack/unpack/unpack_from/calcsize/error and both builds: verified (q1–q4, p4, p6, q8).
- native alignment, zero counts, `str`/`bytes` formats, bytearray buffers, negative `unpack_from` offsets: verified by probes and by the new test module.
- `__index__` arguments: works for a normal `__index__`, but see defect 2.
- named refusals (float format; computed unpack format): observed.
- 4 new tests registered in `ail_check.py`: verified (2 prelude + 2 compiled tests).
- `update_manifest.py --check` rc=0, DEVLOG/DIFFERENCES present: verified.
- "59 passed, 1 skipped across 8 modules": unverified; I reran only `test_ail_stdlib19 test_ail_stdlib5 test_ail_python_syntax test_ail_safetynet` → all ok.
- "Probes 10/10 matched": unverified (worker probes not available).
- No-struct C unchanged: verified (`p7_nostruct` `program.c` identical to `/tmp/base`; only temp paths in `native_report.json` differ).
- Buffers/mutation: `p4` (mutating the bytearray after pack/unpack) matched CPython.

**Defects (both builds; base refuses `struct` entirely, so introduced here)**

1. `P` rejects negative values that CPython accepts. `prelude_struct.py:34` treats `P` as unsigned, but CPython's `PyLong_AsVoidPtr` accepts negatives.
   Probe `/tmp/rprobes/q9_p.py`:
   `print(struct.pack('@P', -1).hex())` plus `-2` and `unpack('@P', b'\xff'*8)`.
   Expected: `ffffffffffffffff`, `-2 feffffffffffffff`, `(18446744073709551615,)`.
   Actual: exits 1 with `struct.error: 'P' format requires 0 <= number <= 18446744073709551615`, no stdout.

2. Integer formats accept `__int__`-only objects that CPython rejects (`_ail_struct_value` uses `int()`, CPython uses `PyNumber_Index`).
   Probe `/tmp/rprobes/q6_index.py`: class with only `def __int__: return 5`, then `struct.pack('<b', OnlyInt())`.
   Expected: CPython raises `struct.error: required argument is not an integer` (`int err ...`).
   Actual: both builds print `int 05`.

3. (minor) Non-bytes buffer error text differs: `/tmp/rprobes/q7_misc.py`, `struct.unpack('<I', 'abcd')` caught as `TypeError`.
   Expected: `a bytes-like object is required, not 'str'`; actual: `unsupported operand type(s) for +: 'int' and 'str'`.

Pre-existing: none affecting these probes (base refuses all `struct` programs).

VERDICT: FIX
1. `struct.pack('@P', -1)` must produce `ffffffffffffffff` (and `-2` → `feffffffffffffff`), not raise.
2. `struct.pack` must reject an object defining only `__int__` with CPython's `struct.error: required argument is not an integer` (use `__index__` semantics).
3. `struct.unpack` of a `str` buffer should raise `TypeError: a bytes-like object is required, not 'str'`.
[cost $0.0337, opencode tokens {"total": 1278552, "input": 75067, "output": 8883, "reasoning": 22634, "cache.write": 0, "cache.read": 1171968}]
    tool time: bash 6.6 min
        182s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         84s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in q1_paths q2_offsets q3_alias q4_fromimport; do echo "==
         42s bash   cd /tmp/rprobes && cat > q5_unsigned.py <<'EOF' import struct  def main() -> None:     for v in (0, 9223372036
         38s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in p1_paths p2_offsets p3_alias p4_bytes p5_refusals p6_er
         20s bash   cd /tmp/rprobes && cat > q8_unsigned.py <<'EOF' import struct  def main() -> None:     u = struct.unpack('<Q',
         18s bash   cd /tmp/rprobes && cat > q9_p.py <<'EOF' import struct  def main() -> None:     print(struct.pack('@P', -1).he
          5s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q6_index q9_p; do echo "===== BASE $p ====="; timeout 300 bash 
          4s bash   cd /tmp/rprobes && cat > q8_unsigned.py <<'EOF' import struct  def main() -> None:     u = struct.unpack('<Q',

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects plus a related native `unpack_from` offset alignment bug found by the probes.

- Commit: `a4610ca`
- Probes on both builds (`g`/`d`) matched CPython: `std19_fix_p`, `std19_fix_index`, `std19_fix_buffer`, `q6_index`, `q7_misc`, `q9_p`, plus regressions `q1-q4`, `q8`, `p4`, `p6`, `p7` and native-offset probes.
- `q5`/`p1`/`p2`/`p3`/`p5` remain refusal-only probes (probe constructs or computed formats are intentionally unsupported).
- Required tests: `test_ail_stdlib19`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `tools/update_manifest.py --check` rc=0.
[cost $0.0654, opencode tokens {"total": 6843904, "input": 130695, "output": 20271, "reasoning": 22730, "cache.write": 0, "cache.read": 6670208}]
    tool time: bash 24.6 min, edit 0.0 min
        426s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 --ti
        225s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q1_paths q2_offsets q3_alias q4_fromimport q5_unsigned q8_unsig
        175s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/std19_fix_p.py /tmp/probes/std19_fix_index.py /tmp/
        139s bash   cat > /tmp/probes/std19_fix_buffer.py <<'EOF' import struct   class Box:     def __init__(self, v):         se
         51s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q6_index q7_misc q9_p; do echo "===== $p ====="; timeout 300 ba
         40s bash   cat > /tmp/probes/std19_fix_p.py <<'EOF' import struct   class Box:     def __init__(self, v) -> None:        
         39s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 -m unittest -v test_ail_stdlib19 2>&1 |
         29s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q6_index q7_misc q9_p; do echo "===== $p ====="; timeout 300 ba

## review 1
[model opencode-go/deepseek-v4.1-flash]
Reviewed `a4610ca` against `work` (`175c40f`). The diff adds a `struct` lowering (`stdlib5`/`structlib` + Python prelude) for `pack`/`unpack`/`unpack_from`/`calcsize`/`error`, plus `__index__` integer fields, negative `P`, bytes/bytearray buffers and native-relative `unpack_from` alignment. That matches the report.

Verified: negative `P`, value `__index__`, invalid-buffer and native-offset cases match CPython (`p1`, `p2c`, `p3`, `p5`); a no-`struct` program's generated C is identical to `/tmp/base` (`p7`, only `native_report.json` differs). Tests `test_ail_stdlib19`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5`, `test_ail_python_syntax`: 6 modules, 0 failed. `update_manifest.py --check` rc=0. Speed not applicable (no hot C path changed).

Pre-existing: bytes indexing with an `__index__` object differs identically on base (`p14`).

Defects:

1. No total-size limit. `/tmp/rprobes/p19b.py` (`struct.calcsize('9223372036854775808s')`): CPython raises `struct.error: total struct size too long`; AIL aborts compilation with an uncaught Python traceback at `structlib.py:176`. `/tmp/rprobes/p21b.py` (same format in `pack`): CPython prints `err total struct size too long`; AIL prints `AIL internal error: out of memory` and exits 1. `/tmp/rprobes/p20_too_long_unpack.py`: CPython `err total struct size too long`; AIL `err unpack requires a buffer of 99999999999999999999 bytes`.

2. `unpack_from` offset handling. `/tmp/rprobes/p8_offset_types.py`: offset `Ix()` with `__index__` returning 2 gives CPython `(909456435,)`; AIL runtime `TypeError: '<' not supported between instances of 'instance' and 'int'` (float/string offsets also report different TypeErrors). `/tmp/rprobes/p9_huge_offset.py`: offset `2**100` gives CPython `OverflowError: Python int too large to convert to C ssize_t`; AIL `_AilStructError unpack_from requires a buffer...`. `/tmp/rprobes/p12_index.py`: an `__index__` raising `AttributeError('boom')` gives CPython `AttributeError: boom`; AIL `_AilStructError required argument is not an integer`.

3. Buffer/format argument types. `/tmp/rprobes/p16_array_buffer.py`: `struct.unpack('<I', array('B', [1,2,3,4]))` (also `'<4c'` and `unpack_from`) gives CPython `(67305985,)` etc.; AIL raises `TypeError: a bytes-like object is required, not '_AilArray'`. `/tmp/rprobes/p10_calc_bytearray.py`: `struct.calcsize(bytearray(b'<I'))` gives CPython `TypeError: unhashable type: 'bytearray'`; AIL gives a different `TypeError` text.

4. Computed unsupported formats are runtime errors, not compile-time refusals. `/tmp/rprobes/p13_computed_float.py` (`f = '<' + 'd'`): CPython prints the packed bytes and `8`; AIL compiles, then fails at run time with `_AilStructError: the 'd' format (floating point) is not built`.

VERDICT: FIX
[cost $0.0416, opencode tokens {"total": 1495523, "input": 74081, "output": 11291, "reasoning": 32615, "cache.write": 0, "cache.read": 1377536}]
    tool time: bash 18.8 min
        496s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2000 python3 ../tools/par_check.py -j 2 test
        151s bash   cat > /tmp/rprobes/p19_too_long_calc.py <<'EOF' import struct  print(struct.calcsize('99999999999999999999s'))
        123s bash   python3 - <<'PY' import struct, sys print(sys.maxsize) for n in [9223372036854775807,9223372036854775808,18446
         55s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_widths p2_semantics p3_offsets p4_routes p5_buffer; do (time
         50s bash   cat > /tmp/rprobes/p8_offset_types.py <<'EOF' import struct  data = b'12345678' for off in (True, 1):     prin
         40s bash   cat > /tmp/rprobes/p2b_semantics.py <<'EOF' import struct  print(struct.pack('@c', b'a').hex(), struct.unpack(
         34s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 400 bash ~/tools/cmp.sh /tmp/rprobes/p2_semantics.py "$PWD" > /t
         33s bash   cat > /tmp/rprobes/p2c_semantics.py <<'EOF' import struct  print(struct.pack('@b0h', 1).hex(), struct.calcsize

FINAL VERDICT: FIX  2026-10-28T21:37:20Z
