# job job-std_struct-11020354  started 2026-11-01T18:55:21Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect: `pack_into` (module and `Struct`) now accepts writable `array.array` buffers, writes raw bytes with byte offsets/typecodes, and still names `bytes`, `None`, `str`, lists, tuples, dicts and user objects like CPython.

- Probes: `/tmp/probes/q9_arr.py` and `/tmp/probes/arr_pack_into.py` match CPython on both builds (all routes, typecodes, byte orders, negative/unaligned offsets).
- Tests: `test_ail_std_struct`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass (603 s).
- Added a `pack_into_array` edge program; `update_manifest.py --check` exits 0.
- Committed as `80d5919`.
[cost $0.0000, opencode tokens {"total": 1562586, "input": 57989, "output": 9092, "reasoning": 13137, "cache.write": 0, "cache.read": 1482368}]
    tool time: bash 12.5 min, edit 0.0 min
        604s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 --timeout 2800 test
         42s bash   cd /tmp/probes && cat > q9_arr.py <<'EOF' import array import struct  def via(b):     return b  class Box:    
         40s bash   cd /tmp/probes && python3 - <<'EOF' p='arr_pack_into.py' s=open(p).read() s=s.replace("for x in [None, b'0123'
         40s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/arr_pack_into.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail
         20s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > arr_pack_into.py <<'EOF' import array import struct  class Box
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && git status --short | head -20
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "check exit $?"; git stat
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && ls

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does.** `_ail_struct_is_array` recognises an AIL array, `_ail_struct_array_bytes`/`_ail_struct_array_set` convert its elements to/from native element bytes, `_ail_struct_store` writes packed bytes through that raw form, and `pack_into` (module and `Struct`) now accepts `bytearray` or array and uses `len*itemsize` for offsets. Adds `pack_into_array`, DEVLOG row and manifest hashes. This matches the report except that the array test is by class-name string, which is spoofable (below).

**Defect (caused by this change)**

1. `_ail_struct_is_array` uses `type(buffer).__name__ == "_AilArray"` (`prelude_struct.py:702`), so any user object whose class is named `_AilArray` is treated as a real array and accepted; CPython rejects it. Probe `/tmp/rprobes/l_fake.py`:
   ```python
   import struct
   class _AilArray:
       def __init__(self):
           self.typecode='B'; self.itemsize=1; self.data=[0,0,0,0]
       def __len__(self): return 4
   try:
       struct.pack_into('<i', _AilArray(), 0, 7); print('ok')
   except Exception as e:
       print(type(e).__name__, e)
   ```
   Expected (CPython **and base**): `TypeError argument must be read-write bytes-like object, not _AilArray`. Actual HEAD (`g` and `d`): `ok` (writes into the user object's `.data` silently). Base matches CPython. Use `isinstance(buffer, _AilArray)` against the real injected class (guarded for builds that do not inject `prelude_array`) instead of the name.

**Verified**
- `q9_arr.py`, `arr_pack_into.py` match on both builds.
- My probes `a_span`, `c_preserve`, `e_errs`, `f_struct`, `h_double`, `i_routes`, `k_max` match CPython on `g` and `d` (spanning writes, `s`/`c`/`?`/`x`, partial element writes, max `I/H/B`, big-endian/native doubles, all routes).
- `b_empty`: only the empty-buffer negative-offset message differs; `g_bempty_bytes.py` shows the same on base, so pre-existing.
- `j_roundtrip`: only the NaN-payload row differs, already declared (`C?-job-std_struct-11020025-1`).
- Non-struct program: `--debug-dir` `program.c` byte-identical to `/tmp/base`.
- `test_ail_std_struct` + `test_ail_safetynet`: 2/2 pass (599 s). `update_manifest.py --check` exit 0. Commit `80d5919` present.

**Claim checks**
- “accepts writable `array.array`” — verified for real arrays; false for a user class named `_AilArray`.
- “every supported typecode … matches CPython” — false at the unsigned 64-bit high bit: `pack_into('<q', array('Q'), 0, -1)` stops `OverflowError: integer overflow…` where CPython prints `18446744073709551615`. This is the declared int64 rule (`C?-job-std_struct-11012058-2`), so I do not count it as a defect, but the claim is overstated.
- “4/4 tests pass” — I ran 2/2 (std_struct, safetynet); `test_ail_files` and `test_ail_corpus_findings3` unverified.

**Pre-existing / declared**
- Empty-buffer negative-offset message (`g_bempty_bytes.py`), array rejection by `unpack`, NaN-payload canonicalisation.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, behaviour on a big-endian host.

VERDICT: FIX

1. User class named `_AilArray` is misdetected as an array. Probe `/tmp/rprobes/l_fake.py`; expected `TypeError argument must be read-write bytes-like object, not _AilArray` (CPython and base), actual `ok` on both HEAD builds.
[cost $0.0000, opencode tokens {"total": 1133140, "input": 23765, "output": 6830, "reasoning": 15441, "cache.write": 0, "cache.read": 1087104}]
    tool time: bash 23.7 min
        600s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 --timeout 2800 test
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 --timeout 280
        120s bash   date; cd /tmp/rprobes && for p in a_span b_empty c_preserve d_unsigned e_errs f_struct; do echo "===== $p"; ba
         86s bash   date; cd /tmp/rprobes && cat > h_double.py <<'EOF' import array, struct a = array.array('d', [0.0]) struct.pac
         79s bash   date; cd /tmp/rprobes && for p in d_unsigned e_errs; do echo "===== $p"; bash ~/tools/cmp.sh $p.py /home/runne
         74s bash   date; cd /tmp/rprobes && cat > g_bempty_bytes.py <<'EOF' import struct b = bytearray() try: struct.pack_into('
         44s bash   date; cd /tmp/rprobes && cat > j_roundtrip.py <<'EOF' import array, struct a = array.array('d', [0.0, 0.0, 0.0
         43s bash   date; cd /tmp/rprobes && cat > k_max.py <<'EOF' import array, struct a = array.array('I', [4294967295, 0, 0]) 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining defect: `_ail_struct_is_array` now checks the real injected `_AilArray` class, with a no-array fallback in `structlib.py`.

- Probes: `l_fake`, `l_fake_routes`, `i_routes`, `k_max`, `a_span`, `c_preserve`, `h_double` all match CPython on `g` and `d`.
- Tests: `test_ail_std_struct`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass.
- `update_manifest.py --check` exit 0.
- Committed as `a00a049`.
[cost $0.0000, opencode tokens {"total": 2598966, "input": 73988, "output": 7671, "reasoning": 20411, "cache.write": 0, "cache.read": 2496896}]
    tool time: bash 17.1 min, edit 0.0 min
        602s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 --timeout 2800 test
        213s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p = Path('AIL_CURRENT/python/
         34s bash   cat > /tmp/rprobes/l_fake_routes.py <<'EOF' import struct  class _AilArray:     def __init__(self):         se
         32s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh l_fake.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
         32s bash   cd /home/runner/work/ail-ci/ail-ci && git diff -- AIL_CURRENT/python/pkg-v12/prelude_array.py | cat -A | tail 
         32s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh l_fake.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -30
         21s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh i_routes.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -20
         15s bash   cd /home/runner/work/ail-ci/ail-ci && cat >> AIL_CURRENT/python/pkg-v12/prelude_array.py <<'EOF'   _AilArray_r

## review 1
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the change does.** `pack_into` now accepts AIL `array.array` buffers: `_ail_struct_store` converts the array elements to native raw bytes, patches the bytes, and writes them back (`prelude_struct.py:704-743`), with byte-length checks via `itemsize`. `_ail_struct_is_array` is a stub returning `False`; `structlib.py:63-66` textually replaces it with `isinstance(buffer, _AilArray)` when the array prelude is among the injected chunks. Adds a `pack_into_array` test, DEVLOG entries and the manifest. This matches the report, but the report omits that detection is a textual scan of injected preludes (works today; fragile).

**Defect (in the new array path)**

1. `pack_into` into an array **shorter than the packed field**, with a negative offset, prints the wrong `struct.error` text. Probe `/tmp/rprobes/p_neg.py`:
   ```python
   import array, struct
   for tc, n, off in [('B',0,-1), ('B',0,-3), ('B',1,-3), ('B',2,-3), ('B',3,-4), ('i',4,-1)]:
       a = array.array(tc,[0]*n)
       try:
           struct.pack_into('<i', a, off, 7)
           print(tc,n,off,'ok',list(a))
       except Exception as e:
           print(tc,n,off,type(e).__name__,e)
   ```
   Expected (CPython): `error no space to pack 4 bytes at offset -1`, `... -3` for `B 0 -1`, `B 0 -3`, `B 1 -3`, `B 2 -3`; only `B 3 -4` is `offset -4 out of range for 3-byte buffer`.
   Actual (HEAD, both `g` and `d`): `error offset -1 out of range for 0-byte buffer`, `offset -3 out of range for 0/1/2-byte buffer`. `Struct.pack_into` has the same code (`prelude_struct.py:925-931`).
   Base rejects arrays (`TypeError ... not _AilArray`), so these rows are new behavior from this change. The same wrong text for `bytearray` is pre-existing (see below), but the change newly exposes it on arrays. Fix shared check at `prelude_struct.py:854-860` / `:925-931`: CPython distinguishes "whole field before the buffer" (`out of range`) from "partially overlaps" (`no space to pack`). The worker's `pack_into_array` uses only 4-element arrays, so it misses this.

**Verified**
- Main defect fixed: `i_routes`, `l_fake`, `l_fake_routes`, `p_fake2`, `p_fake3`, `a_span`, `c_preserve`, `h_double`, `k_max`, `p_types2`, `p_floatbits` match CPython on `g` and `d` (all typecodes, both byte orders, unaligned/crossing writes, argument/list/attribute/dict routes, `Struct`, real array + fake-name class refused by name `not in the subset: name 'array' is not defined`).
- User class `_AilArray` without array import is rejected like CPython (`l_fake`, `p_fake2`).
- Values survive aliasing/snapshot: `p_alias`, `p_alias2` (`list(a)`, `tolist()`, alias wrote through) match.
- Non-struct program C is byte-identical: `p_nostruct2.py` `--debug-dir` `program.c` == `/tmp/base`.
- Tests on HEAD: `test_ail_std_struct`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4/4 pass (605 s, `-j 2`). `update_manifest.py --check` exit 0.
- Report claim "`_ail_struct_is_array` checks the injected `_AilArray` with no-array fallback" verified; "all listed probes match", "4/4 tests", "manifest exit 0", "commit a00a049" verified.
- No hot code touched; no `bench/apps` or `language_examples` edits.

**Pre-existing**
- `bytearray` (and now array) negative offset on a buffer shorter than the field gives `offset ... out of range` vs CPython `no space to pack ...`; identical for `bytearray` on base and HEAD (`p_short`), root of defect 1.
- `struct.unpack`/`unpack_from`/`Struct.unpack` reject `array.array` identically on base and HEAD (`p_unpackarr`: `TypeError a bytes-like object is required, not 'object'`).
- Declared int64: `pack_into` into `array('Q'/'L')` whose raw value reaches ≥2^63 stops with `OverflowError: integer overflow in *`, exit 1 (`p_qmin`), matching declared row `C?-job-std_struct-11012058-2`; NaN payload row still applies.

**Unverified:** instruction counts/speed (struct is not hot in gdev); exhaustive subnormal/NaN sweep; wider suite (by design).

VERDICT: FIX

1. `pack_into`/`Struct.pack_into` into an array shorter than the field with a negative offset yields `error offset <off> out of range for <n>-byte buffer` where CPython yields `error no space to pack <size> bytes at offset <off>`. Probe `/tmp/rprobes/p_neg.py` above; expected `no space to pack 4 bytes at offset -1` for `array('B')` offset -1 (and -3 for 0/1/2-byte arrays), actual `offset -1/-3 out of range for 0/1/2-byte buffer` on both builds. Base rejects the array with `TypeError`, so this is new behavior. Fix the shared negative-offset check in `prelude_struct.py:854-860` and `:925-931`.
[cost $0.0000, opencode tokens {"total": 2220067, "input": 94414, "output": 9687, "reasoning": 38782, "cache.write": 0, "cache.read": 2077184}]
    tool time: bash 25.0 min
        607s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1400 python3 ../tools/par_check.py -j 2 --ti
        170s bash   cd /tmp/rprobes && for p in a_span c_preserve h_double k_max; do echo "######## $p"; timeout 160 bash ~/tools/
        120s bash   cd /tmp/rprobes && cat > p_fake3.py <<'EOF' import array, struct class _AilArray:     def __init__(self):     
         82s bash   cd /tmp/rprobes && for p in p_types p_bounds p_alias; do echo "######## $p"; bash ~/tools/cmp.sh $p.py /home/r
         78s bash   cd /tmp/rprobes && cat > p_types2.py <<'EOF' import array, struct for tc in ['b','B','h','H','i','I','l','L','
         74s bash   cd /tmp/rprobes && cat > p_unpackarr.py <<'EOF' import array, struct a = array.array('B', [7, 0, 0, 0]) for ca
         70s bash   cd /tmp/rprobes && cat > p_qmin.py <<'EOF' import array, struct a = array.array('Q',[0]) try:     struct.pack_
         68s bash   cd /tmp/rprobes && cat > p_neg.py <<'EOF' import array, struct for tc, n, off in [('B',0,-1), ('B',0,-3), ('B'

FINAL VERDICT: FIX  2026-11-01T20:29:22Z
