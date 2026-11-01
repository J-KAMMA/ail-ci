# job job-std_struct-11020025  started 2026-11-01T15:29:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `d25ed7f` on `job-std_struct-11020025`.

Fixed all five review defects:
- Default/unprefixed float format now uses native `@` mode.
- Subnormal doubles now scale by the full exponent (`-1074`), so `b'\x01'+b'\x00'*7` round-trips as `5e-324` / `0100000000000000`.
- `pack_into` checks item count first, reports `pack_into expected ...`, and rejects immutable buffers with CPython’s writable-bytes TypeError.
- `p` wrong-type errors now name `p`.
- `calcsize` raises `struct.error: total struct size too long` at the int64 boundary.

Declared two limits that cannot be exact in this runtime: NaN payload preservation through `d`/`f` (`C?-job-std_struct-11020025-1`) and `unpack('0p', b'')` raising `struct.error` instead of `SystemError` (`-2`).

Verification:
- Probes `/tmp/probes/struct_native_float.py`, `struct_subnormal.py`, `struct_pack_errors.py` match CPython on both builds.
- Declared probe confirms only the two declared differences.
- `test_ail_std_struct`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4/4 passed, 0 failed.
- `update_manifest.py --check`: exit 0.
[cost $0.0000, opencode tokens {"total": 5759975, "input": 87389, "output": 19272, "reasoning": 21570, "cache.write": 0, "cache.read": 5631744}]
    tool time: bash 38.0 min, read 0.0 min
        539s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 --timeout 2400 test_ail_std
        537s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 --timeout 2400 test_ail_std
        512s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
        508s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
        104s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/struct_native_float.py /tmp/probes/struct_subnormal
         39s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/struct_subnormal.py "$PWD"
         35s bash   cat > /tmp/probes/struct_declared.py <<'PY' import struct  def main():     try:         struct.unpack('0p', b'
          1s bash   mkdir -p /tmp/probes && cat > /tmp/probes/syserr.py <<'PY' class SystemError(Exception):     pass try:     rai

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does.** In `prelude_struct.py` only: unprefixed formats now use native `@` float overflow, `_ail_struct_scale` loops for the full negative exponent, `pack_into` checks item count before writable buffer/offset and names `pack_into`, `_ail_struct_bytes` names `p`/`s`, and `calcsize` enforces an int64 total-size limit; adds 3 edge programs, DEVLOG, and two declared DIFFERENCES rows. Matches the report.

**Probes** (`/tmp/rprobes`, HEAD vs CPython, both `g` and `d`):
- `a_native.py` native `f`, `' f'`, `1f`, `2f`, `10f`, `0f`, `@f`, via arg/list/attr/dict and `pack_into`: **same**; standard `=f <f >f !f` still `OverflowError`: **same**.
- `b_subnormal.py` 60 double/f32/f16 bit patterns incl. max subnormal, min normal, negative, both endian: **same** except NaN-payload lines (declared `-1`).
- `c_packinto.py` count/type/offset ordering, all buffer types, `p`/`s` errors: **same for bytes, str, int, float, bool, list, tuple, dict**; count-first and `pack_into expected` verified; **differs for `None` and user class** (below).
- `d_calcsize.py` 28 overflow/boundary formats incl. 19/20-digit counts, `x/s/p/c`, unit 4/8, alignment overflow: **same**.
- `e_alias.py`/`f_alias2.py` mutate bytearray after `unpack`/`unpack_from`, reuse buffer, pack `bytes` from arg/list/attr/dict: **same**.
- `i_declared.py` `unpack('0p')`, NaN payload, bytes format/`calcsize(b'2i')`: only the two declared rows differ.
- `g_nostruct.py` with `--debug-dir`: `program.c` and executable byte-identical to base `work`; `native_report.json` differs only in temp/cwd paths.
- `j_buffer_routes.py` writable bytearray via arg/list/attr/dict, module and `Struct`: **same**.

**Defect**

1. **`pack_into` buffer type name is wrong for `None` and user-defined classes.** New check `not isinstance(buffer, bytearray)` → `_ail_struct_tname`, which returns `NoneType`/`object` where CPython uses `None`/the class name.
   ```python
   import struct
   class Foo: pass
   for b in [None, Foo(), Foo]:
       try: struct.pack_into('<i', b, 0, 1)
       except Exception as e: print(type(e).__name__, e)
   ```
   Expected (CPython, both module and `Struct.pack_into`):
   ```
   TypeError argument must be read-write bytes-like object, not None
   TypeError argument must be read-write bytes-like object, not Foo
   TypeError argument must be read-write bytes-like object, not type
   ```
   Actual (both builds):
   ```
   TypeError argument must be read-write bytes-like object, not NoneType
   TypeError argument must be read-write bytes-like object, not object
   TypeError argument must be read-write bytes-like object, not object
   ```
   (`struct.Struct('<i').pack_into(...)` gives the same mismatch.) Base is also wrong here but with a different message, so this is not a pre-existing identical difference.

**Report claims.** Native float, subnormal round-trip, `pack_into` count-first text, immutable `bytes` text, `p` error, calcsize limit, NaN/`0p` declared rows, test 2/2, `update_manifest.py --check`: **verified**. “Probes match CPython on both builds” and “rejects immutable buffers with CPython’s writable-bytes TypeError”: **false** for the `None`/class cases above.

**Pre-existing.** `struct` probes using `memoryview` fail to build identically on base `work`; `Struct()` custom-class name says `object` there too.

**Unverified.** `test_ail_files`, `test_ail_corpus_findings3` (not re-run per instruction); gdev instruction counts (no non-struct hot path).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1018079, "input": 66570, "output": 8803, "reasoning": 24306, "cache.write": 0, "cache.read": 918400}]
    tool time: bash 15.5 min
        517s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 --timeout 2400 test
        100s bash   cd /tmp/rprobes && for p in c_packinto d_calcsize e_alias; do echo "===== $p HEAD"; timeout 1200 bash ~/tools/
         71s bash   cat > /tmp/rprobes/i_declared.py <<'EOF' import struct for call in ['module', 'class']:     try:         if ca
         70s bash   cd /tmp/rprobes && for p in a_native b_subnormal; do echo "===== $p HEAD"; timeout 1200 bash ~/tools/cmp.sh /t
         52s bash   cat > /tmp/rprobes/h_memview.py <<'EOF' import struct b = bytearray(4) m = memoryview(b) try:     struct.pack_
         50s bash   cd /tmp/rprobes && for p in h_memview f_alias2; do echo "===== $p BASE"; timeout 1200 bash ~/tools/cmp.sh /tmp
         32s bash   cat > /tmp/rprobes/j_buffer_routes.py <<'EOF' import struct  class Box:     def __init__(self, b):         sel
         30s bash   cd /tmp/rprobes && echo "=== BASE c_packinto ===" && timeout 1200 bash ~/tools/cmp.sh /tmp/rprobes/c_packinto.

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed review 2's remaining defect and committed as `4cd7197`.

- `pack_into` (module and `Struct`) now names non-writable buffers like CPython: `None`, class names, builtin types, and `bytes` (`prelude_struct.py:37`).
- Added `pack_into_buffer_type` edge program covering module/class calls, literal and argument/list-item/dict-value routes, and successful `bytearray` packing.
- Probes `n_rwtype`, `n_review`, `c_packinto`, `j_buffer_routes`, `a_native`, `d_calcsize`, `i_declared`: match CPython on both builds; `i_declared` shows only the two declared rows.
- Final-commit tests: `test_ail_std_struct`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 passed (556s). `update_manifest.py --check` exit 0.
[cost $0.0000, opencode tokens {"total": 1019085, "input": 41266, "output": 4984, "reasoning": 4899, "cache.write": 0, "cache.read": 967936}]
    tool time: bash 24.2 min, edit 0.0 min
        557s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3600 python3 tools/par_check.py -j 2 --timeout 2400 test_ail_std
        552s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3600 python3 tools/par_check.py -j 2 --timeout 2400 test_ail_std
        162s bash   cd /tmp/rprobes && for p in c_packinto j_buffer_routes a_native d_calcsize i_declared; do echo "===== $p"; bas
        120s bash   grep -rn "read-write bytes-like" /usr/lib/python3.12 /usr/local/lib 2>/dev/null | head; find / -name '_struct.
         32s bash   mkdir -p /tmp/probes && cat > /tmp/probes/n_rwtype.py <<'EOF' import struct  class Foo:     pass  class Bar:  
         30s bash   ls /tmp/rprobes 2>/dev/null || echo "no rprobes"; cat > /tmp/probes/n_review.py <<'EOF' import struct class Fo
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** Fixes the five review-1 `struct` defects: default/unprefixed float mode is now native, `_ail_struct_scale`'s negative branch loops over the full exponent, `pack_into` checks item count before offset and says `pack_into expected …`, `p` names itself in its wrong-type error, and non-`bytearray` buffers get CPython's read-write-buffer text. Adds three edge programs, DEVLOG/DIFFERENCES rows and refreshes the manifest. This matches the report, except the buffer guard is broader than "non-writable buffers" (below).

**Defect (caused by this change)**

1. `pack_into` now rejects writable `array.array` buffers. The new guard `isinstance(buffer, bytearray)` at `AIL_CURRENT/python/pkg-v12/prelude_struct.py:778` (module) and `:851` (`Struct.pack_into`) rejects `array.array`, which CPython accepts and which the base `work` accepted.
   Probe `/tmp/rprobes/q9_arr.py`:
   ```python
   import array, struct
   a = array.array('B', [0, 0, 0, 0])
   struct.pack_into('<i', a, 0, 7); print(list(a))
   # same via Struct.pack_into, argument, attribute, list item, dict value
   ```
   Expected (CPython and base): `[7, 0, 0, 0]` for every route.
   Actual (HEAD, both `g` and `d`): `TypeError argument must be read-write bytes-like object, not _AilArray`.
   The test's `pack_into_buffer_type` edge program does not include `array.array`, so it missed this.

**Verified**
- Default float: `q1_fmt`, `q7_float` match CPython on `g` and `d` for `'f'`, `' f'`, `'2f'`, `'10f'`, `@/=/</>/!` and `Struct`; only the declared NaN-payload rows differ.
- Subnormal: `q4_sub` matches for subnormal/normal/boundary doubles, f32 and f16; only the declared NaN-payload rows differ.
- Errors: `q5_errs` matches `pack_into expected …`, `p`/`s` wrong-type text, and count-before-offset; only the declared `0p` `SystemError`→`struct.error` row differs.
- Precedence and buffer names: `q6_prec` matches bad-format > count > buffer-type > offset, and names `None`/`Foo`/`type`/builtins/`bytes` correctly.
- `calcsize` boundary: `q2_size` matches CPython at the int64 boundary and for 20-digit counts.
- Non-struct C: `g_nostruct` `--debug-dir` `program.c` is byte-identical to `/tmp/base`.
- Tests on HEAD: `test_ail_std_struct` + `test_ail_safetynet` 2/2 pass (545 s); `update_manifest.py --check` exit 0.
- Worker probes `n_rwtype`, `n_review`, `c_packinto`, `j_buffer_routes`, `a_native`, `d_calcsize` match on both builds; `i_declared` differs only on the declared rows.

**Pre-existing (same on base)**
- `memoryview` + `struct` does not compile (type-inference refusal) on base and HEAD.
- `struct.unpack`/`unpack_from`/`Struct.unpack` reject `array.array` on base and HEAD (`q11_unpackarr`).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (worker claims pass), exhaustive subnormal sweep beyond the tested boundaries.

VERDICT: FIX

1. `pack_into` rejects `array.array`: accept `_AilArray` (or any AIL writable buffer) in both `_ail_struct_pack_into_values` and `_AilStruct.pack_into`, while still naming `bytes`/other non-writable types like CPython. Probe `/tmp/rprobes/q9_arr.py`, expected `[7, 0, 0, 0]` per route, actual `TypeError … not _AilArray`.
[cost $0.0000, opencode tokens {"total": 2159944, "input": 96994, "output": 10129, "reasoning": 18517, "cache.write": 0, "cache.read": 2034304}]
    tool time: bash 21.7 min
        547s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 --timeout 2400 test_a
        164s bash   date; cd /tmp/rprobes && for p in n_rwtype n_review c_packinto j_buffer_routes a_native d_calcsize i_declared;
         71s bash   cd /tmp/rprobes && cat > q11_unpackarr.py <<'EOF' import array import struct a = array.array('B', [7, 0, 0, 0]
         69s bash   cd /tmp/rprobes && cat > q9_arr.py <<'EOF' import array import struct  def via(b):     return b  class Box:   
         62s bash   cd /tmp/rprobes && echo "=== i_declared diff"; cat /tmp/cmp*/diff_g.txt 2>/dev/null | tail -0; ls -td /tmp/cmp
         39s bash   date; cd /tmp/rprobes && bash ~/tools/cmp.sh q4_sub.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -40
         35s bash   date; cd /tmp/rprobes && bash ~/tools/cmp.sh q5_errs.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -40
         34s bash   cd /tmp/rprobes && cat > q7_float.py <<'EOF' import struct vals = [1e40,1e308,float('inf'),float('-inf'),float

FINAL VERDICT: FIX  2026-11-01T17:30:58Z
