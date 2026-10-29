# job job-stdlib39-10291432  started 2026-10-29T05:45:27Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"57f32b87-fd00-414a-a473-be555eb78b37","session_id":"640c42b9-4f16-49a7-ae3a-6e54eb05c836"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"3bfe618f-cae1-4d27-b9a6-02911a99b732","session_id":"1da3aa08-f2fa-4e56-aa64-929d4f984b2e"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed `struct` support on branch `job-stdlib39-10291432`.

- Commit: `97f449c` (`stdlib39: support struct pack/unpack/unpack_from/calcsize`)
- Added `structlib.py` lowering for literal formats: `pack`, `unpack`, `unpack_from`, `calcsize`.
- Supported fields: `x c b B ? h H i I l L q Q n N P s`; standard and native layouts.
- Named refusals remain for `f`, `e`, `d`, `p`, dynamic formats, `Struct`, `iter_unpack`, `pack_into`, keywords/`*args`.
- Added `test_ail_stdlib39.py` (3 tests, both AIL_IR builds) and registered it in `ail_check.MODULES`.
- Updated `DEVLOG.md`, added `DIFFERENCES.md` row `C?-job-stdlib39-10291432-1`; manifest `--check` passes.

Probes in `/tmp/probes`:
- Match CPython on both builds: `p39_basic`, `p39_widths`, `p39_width_errors`, `p39_native`, `p39_formats`, `p39_fromimport`, `p39_routes`, `p39_errs3`, `p39_unpack_exact`, `p39_unpack_from`, `p39_byteslike`, `p39_err_neg2`, `p39_program`.
- Refused by name: `p39_float`/`p39_refuse_d` (`d`), `p39_refuse` (`pack_into`), `p39_refuse_struct`, `p39_refuse_dynamic`, `p39_refuse_kw`.

Final-state tests: `test_ail_stdlib39`, `test_ail_stdlib5`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 48 tests OK, 1 skipped. Not pushed.
[cost $0.0696, opencode tokens {"total": 6444392, "input": 151903, "output": 24500, "reasoning": 22357, "cache.write": 0, "cache.read": 6245632}]
    tool time: bash 26.1 min, read 0.0 min, edit 0.0 min, write 0.0 min
        665s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_stdlib39 test_ail_stdlib5 te
        299s bash   cd /tmp/probes && cat > p39_unpack_exact.py <<'PY' import struct  try:     print(list(struct.unpack('<I', b'')
        181s bash   cd /tmp/probes && cat > p39_formats.py <<'PY' import struct  print(struct.calcsize('')) print(struct.pack(''),
         94s bash   cd /tmp/probes && cat > p39_native.py <<'PY' import struct  for fmt in ['@b', '@h', '@i', '@l', '@q', '@bh', '
         61s bash   cd /tmp/probes && cat > p39_widths.py <<'PY' import struct  for fmt, vals in [     ('<b', [-128, -1, 0, 127]),
         60s bash   cd /tmp/probes && cat > p39_native.py <<'PY' import struct  def show(fmt, *vals):     b = struct.pack(fmt, *va
         32s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_stdlib39 2>&1 | tail -60
         26s bash   cd /tmp/probes && cat > p39_err_neg.py <<'PY' import struct  def check(fn):     try:         print(fn())     e

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** adds `AIL_CURRENT/python/pkg-v12/structlib.py`, a source-to-source pass hooked into `ail_syntax.python_surface` when `"struct"` appears in the source. It lowers literal-format `struct.pack`, `unpack`, `unpack_from`, `calcsize` (and `struct.error` → `ValueError`) to helpers, computes the layout at compile time, registers `test_ail_stdlib39.py`, and updates DEVLOG/DIFFERENCES/manifest. This matches the report.

**Probes (all `/tmp/rprobes`, both builds via `cmp.sh`):**
- `sizes.py` (163 native/standard formats, calcsize + pack/unpack): match.
- `zero_edges.py` (`0s`, `0c`, empty format offsets ±): match.
- `errors2.py` (range/char/str/float/unpack/offset errors and messages): match.
- `q_unpack.py` (`Q`, `q`, `L` at 64-bit boundaries): match.
- `fe_shadow.py`, `fe_shadow_pack.py` (shadowed `error`/`pack`): refused by name, base also cannot compile `struct`; not blocking.
- `ba_type.py`: **fails** (below).
- `unpack_text.py`: **fails** (below).

**Tests:** `test_ail_stdlib39`, `test_ail_safetynet`, `test_ail_files` — 3/3 ok (145 s). `tools/update_manifest.py --check` exits 0.

**Report claims:** commit/files/manifest/DEVLOG/test registration verified; fields and native sizes verified by `sizes.py`; refusals verified by code and tests; `struct.error`→`ValueError` and the `Q > 2**63-1` pack limit are as declared. The claim that the bytearray probe matches is only true for the probe as written (`p39_byteslike.py` tests integer unpack and pack, not `c`/`s` unpack), so it missed both defects below.

**Defects**

1. `unpack`/`unpack_from` of `c`/`s` return the buffer's slice type instead of `bytes`.
   Probe `/tmp/rprobes/ba_type.py`:
   ```python
   import struct
   b = bytearray(b'a')
   x = struct.unpack('<c', b)[0]
   print(isinstance(x, bytes), isinstance(x, bytearray))
   y = struct.unpack_from('<c', b, 0)[0]
   print(isinstance(y, bytes), isinstance(y, bytearray))
   ```
   Expected `True False` / `True False`; actual `False True` / `False True` (same for `s`). Root cause: `_ail_struct_pieces` returns raw slices for `c`/`s`.

2. `unpack`/`unpack_from` accept `str` buffers and return characters instead of raising `TypeError`.
   Probe `/tmp/rprobes/unpack_text.py`:
   ```python
   import struct
   try:
       print('c', struct.unpack('<c', 'a'))
   except TypeError:
       print('c typeerror')
   try:
       print('ufs', struct.unpack_from('<1s', 'abc', 1))
   except TypeError:
       print('ufs typeerror')
   ```
   Expected `c typeerror` / `ufs typeerror` (exit 0, caught); actual `c ('a',)` / `ufs ('b',)`. Integer fields happen to error in `int.from_bytes`, but the same missing bytes-like validation lets `c`/`s` silently return wrong values.

**Not checked:** wider suite, speed (not a speed task), local (non-top-level) `struct` imports.

VERDICT: FIX
[cost $0.0321, opencode tokens {"total": 1013203, "input": 68914, "output": 6355, "reasoning": 25294, "cache.write": 0, "cache.read": 912640}]
    tool time: bash 5.0 min
        146s bash   ls /home/runner/work/ail-ci/ail-ci/tools/par_check.py 2>&1; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && 
         43s bash   cd /tmp/rprobes && for p in ba_unpack shadow_error zero_edges; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rp
         29s bash   cd /tmp/rprobes && python3 - <<'PY' fmts = [] for p in ['@','<','>','=']:     fmts += [p+x for x in ['bq','qb'
         21s bash   cat > /tmp/rprobes/ba_type.py <<'PY' import struct  b = bytearray(b'a') x = struct.unpack('<c', b)[0] print(is
         19s bash   cat > /tmp/rprobes/unpack_text.py <<'PY' import struct  try:     print('c', struct.unpack('<c', 'a')) except T
         15s bash   cat > /tmp/rprobes/q_unpack.py <<'PY' import struct  print(struct.unpack('<Q', b'\xff\xff\xff\xff\xff\xff\xff\
         13s bash   cd /tmp/rprobes && python3 - <<'PY' s=open('errors.py').read() s=s.replace("""try:     struct.pack('<i') excep
         12s bash   cat > /tmp/rprobes/ba_unpack.py <<'PY' import struct  b = bytearray(b'ab') print(struct.unpack('<c', b)) print

## fix round skipped: only 28 minutes left

FINAL VERDICT: FIX  2026-10-29T10:12:18Z
