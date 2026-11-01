# job job-std_struct-11012058  started 2026-11-01T12:01:37Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Final report

- `lab/stdlib/struct/`: 12 programs (24–58 lines); all 12 build in default mode on the general path and match CPython 3.12 stdout/exit code. 0 refused. Results recorded in `lab/stdlib/struct/RESULTS.md`.
- Tests on final commit `975f4e3`:
  - `test_ail_std_struct` — 1/1 OK (634 s)
  - `test_ail_safetynet` — 5/5 OK
  - `test_ail_files` — 18 OK, 1 skipped
  - `test_ail_corpus_findings3` — 2/2 OK
  - `test_ail_stdlib5` — 10/10 OK
- `python3 tools/update_manifest.py --check` — exit 0; no manifest drift.
- Probes (`cmp.sh`, both builds): `probe_struct`, `types`, `errors`, `buffers`, `starred` match CPython exactly. `s_all` is refused by name on the known starred-call limitation (documented follow-up), not silently miscompiled.
- Lab/compare generated C: all 10 `.ail` builds byte-identical; for `main.py`, 7/10 build and are byte-identical, while `tree_fold`, `scar_life`, `tally_lang` refuse identically before and after (no C generated).
- DIFFERENCES/DEVLOG/test registration/pipeline exclusions are in place.
[cost $0.0158, opencode tokens {"total": 891967, "input": 48644, "output": 4250, "reasoning": 5793, "cache.write": 0, "cache.read": 833280}]
    tool time: bash 61.4 min
        911s bash   sed -i 's|src=$wt/lab/compare/src/$task/main.$syntax|if [ "$syntax" = python ]; then ext=py; else ext=ail; fi;
        634s bash   cd AIL_CURRENT && python3 -m unittest test_ail_std_struct -v 2>&1 | tail -30
        462s bash   cd AIL_CURRENT && python3 -m unittest test_ail_corpus_findings3 2>&1 | tail -20
        384s bash   cd AIL_CURRENT && wc -l test_ail_stdlib5.py && python3 -m unittest test_ail_stdlib5 2>&1 | tail -10
        374s bash   cd AIL_CURRENT && python3 -m unittest test_ail_safetynet 2>&1 | tail -20
        338s bash   for p in probe_struct types errors buffers starred s_all; do echo "########## $p"; bash ~/tools/cmp.sh /tmp/pr
        253s bash   cd AIL_CURRENT && python3 -m unittest test_ail_files 2>&1 | tail -20
        150s bash   cd /tmp && d=$(mktemp -d /tmp/labcmpXXXX) && AIL_NO_CACHE=1 python3 /tmp/base_ail/AIL_CURRENT/ail_chatgpt.py c

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds `structlib.py` (import rewriter) and an 850-line general-path prelude built from Python source: `pack/unpack/calcsize/pack_into/unpack_from/iter_unpack/Struct/error`, format parsing, native alignment, float bit conversions. Every `struct` program falls back to the general path because the prelude uses module-level dicts; the typed path is untouched.

**Claims checked**
- 12 lab programs, 24–58 lines, all build and match CPython: **verified** (`test_ail_std_struct` 272 s, 12/12 subtests).
- `test_ail_std_struct` and `test_ail_safetynet` pass on HEAD: **verified** (`par_check -j 2`: 0 failed).
- `update_manifest.py --check` exit 0: **verified**.
- Registration/diff docs/DIFFERENCES row (including `iter_unpack` list difference): **verified** in diff.
- Lab/compare C byte-identical: **verified for echo_pack, berth_sim** (C same base vs HEAD); no `main.py` contains `struct`, so the new trigger cannot affect them.
- Non-feature C unchanged: **verified** with a `restructure` program; same output sha256.
- “Probes … match CPython exactly”: **false** — five independent probes below differ.
- `s_all` refused by name: **unverified for that probe**; a `from struct import *` probe is refused by name as expected.

**Probes** (`/tmp/rprobes/`, both builds, HEAD): `pack_into_native`, `state_leak`, `pascal`, `negzero`, `edges`, `matrix`, `floats`, `uint64`, `struct_kw`, `star_import`, `nostruct`. `matrix`/`floats` (other than negative zero) and `struct_kw` match. No pre-existing differences (base has no `struct`).

VERDICT: FIX

1. **`pack_into` never sets native float mode** (prelude_struct.py:736/755). `struct.pack_into('@f', buf, 0, 1e40)` should write `0000807f` (CPython does; `@f` overflows to inf); AIL exits 1 with `OverflowError: float too large to pack with f format` and no stdout. Converse: after `struct.pack('@f', 1e40)`, `struct.pack_into('<f', buf, 0, 1e40)` should raise `OverflowError`; AIL prints `no error 0000807f` (silent wrong value). Probe: `/tmp/rprobes/pack_into_native.py`, `/tmp/rprobes/state_leak.py`.
2. **`p` unpack rejects an overlarge length byte instead of clamping** (prelude_struct.py:641). Probe `pascal.py`: CPython `struct.unpack('5p', b'\xffabcd')` → `(b'abcd',)`, `('3p', b'\x05ab')` → `(b'ab',)`, `('1p', b'\xff')` → `(b'',)`; AIL prints `error unpack requires a buffer of N bytes` for all three.
3. **Unpacking negative zero loses the sign for `e`, `f` and `d`** (prelude_struct.py:380/398/623: `r = 0.0 - r` yields `+0.0`). Probe `negzero.py`: CPython prints `-0.0` for `<d`, `<f`, `<e`, `@d`, `=d` and for `Struct.pack`/`unpack_from`/`iter_unpack` round-trips; AIL prints `0.0` everywhere (bytes are correct).
4. **Whitespace between a repeat count and its specifier is accepted** (prelude_struct.py:83). Probe `edges.py`: CPython `struct.calcsize('3 i')` raises `struct.error: bad char in struct format`; AIL returns `12`.
5. **Out-of-range negative offsets give the wrong error text** (prelude_struct.py:726/742). Probe `edges.py`: CPython `struct.unpack_from('<i', b'0123456789', -20)` → `error offset -20 out of range for 10-byte buffer`; AIL → `error not enough data to unpack 4 bytes at offset -20` (and `pack_into` similarly says `no space to pack…`). A program that catches and prints this differs.
6. **64-bit unsigned values ≥ 2^63 cannot be unpacked and this is undocumented** (`Q`/`P`, prelude_struct.py:572). Probe `uint64.py`: CPython prints `Q (9223372036854775808,)`, `P (9223372036854775808,)`; AIL exits 1 with `OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)` and no stdout. Stopping loudly respects the int64 rule, but the prompt asks for CPython-exact behaviour or a declared difference; neither is present.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_stdlib5` were not re-run (per instructions); the other 8 lab/compare `main.py` builds were not individually diffed; no icount run (not a speed task).
[cost $0.0346, opencode tokens {"total": 1856771, "input": 72816, "output": 10627, "reasoning": 20112, "cache.write": 0, "cache.read": 1753216}]
    tool time: bash 16.0 min
        273s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_struct test_ail_s
        143s bash   cd /tmp/rprobes && for p in pack_into_native pascal uint64 state_leak struct_kw; do echo "########## $p"; bash
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_std_struct test
         44s bash   cd /home/runner/work/_temp/w2; ls lab/compare/src/echo_pack/; rm -rf /tmp/cmpbase /tmp/cmphead; mkdir -p /tmp/
         33s bash   cat > /tmp/rprobes/negzero.py <<'EOF' import struct  for code in ['<d', '<f', '<e', '@d', '=d']:     b = struc
         32s bash   python3 - <<'EOF' p='/tmp/rprobes/matrix.py' s=open(p).read() old="""for code in '=<>!@':     for fmt, vals in
         32s bash   python3 - <<'EOF' p='/tmp/rprobes/matrix.py' s=open(p).read() s=s.replace("print('S', repr(f), struct.calcsize
         32s bash   sed -i "s/('l', \[-9223372036854775807 - 1\])/('l', [-1])/" /tmp/rprobes/matrix.py; python3 /tmp/rprobes/matri

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `da120ea` on `job-std_struct-11012058`.

**Fixes**
- `pack_into` and `Struct.pack_into` now set native float mode (`@f` → inf, later `<f` raises).
- `p` unpack clamps overlarge length bytes to `count - 1`.
- Negative zero sign preserved for `e`/`f`/`d`.
- Whitespace between repeat count and specifier is rejected.
- Deep negative offsets report `offset N out of range for M-byte buffer`.

**Declared difference** `C?-job-std_struct-11012058-2`: default int64 `Q`/`P`/`L`/`N` unpack ≥2^63 stops with `OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)`; `--exact-int` matches CPython.

**Probes** (`/tmp/probes/struct_*.py`) on both builds: `pack_into_native`, `pascal`, `negzero`, `format_space`, `offsets` all match CPython exactly. `uint64` shows the declared overflow by default and matches with `--exact-int`. `from struct import *` is refused by name.

**Tests on final commit:** `test_ail_std_struct`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 passed (577 s), `test_ail_std_struct` 12/12 lab programs plus 5 regression programs. `update_manifest.py --check` exits 0. No `lab/compare` program imports `struct`, so their generated C is unaffected.
[cost $0.0349, opencode tokens {"total": 2427374, "input": 79686, "output": 12015, "reasoning": 14649, "cache.write": 0, "cache.read": 2321024}]
    tool time: bash 34.2 min, read 0.0 min, edit 0.0 min
        578s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 6000 python3 ../tools/par_check.py -j 2 test_ail_std_stru
        485s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 5400 python3 ../tools/par_check.py -j 2 test_ail_stdlib5 
        370s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_std_stru
        272s bash   cd /tmp/rprobes && for p in pack_into_native state_leak pascal negzero edges uint64 matrix floats struct_kw st
        153s bash   cd /tmp/probes && for p in struct_pack_into_native struct_pascal struct_negzero struct_format_space struct_off
        152s bash   cd /tmp/probes && for p in struct_pack_into_native struct_pascal struct_negzero struct_format_space struct_off
         28s bash   cd /tmp/probes && timeout 300 bash ~/tools/cmp.sh /tmp/probes/struct_uint64.py /home/runner/work/_temp/w2
         15s bash   cd /tmp && d=$(mktemp -d /tmp/exactXXXX) && cp /tmp/probes/struct_uint64.py $d/p.ail && cd $d && AIL_NO_CACHE=

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does.** Adds a new `struct` implementation (`python/pkg-v12/prelude_struct.py` + `structlib.py`) wired into the batch-5 stdlib rewriter, 12 lab programs and a test; the second commit changes five prelude behaviours and declares two differences. This matches the report, though the report understates that the whole module is new.

**Defects**

1. **Default (unprefixed) `f` float mode is wrong.** Probe:
   ```python
   import struct
   print(struct.pack('f', 1e40).hex())
   print(struct.Struct('f').pack(1e40).hex())
   ```
   Expected both `0000807f`; actual both `OverflowError: float too large to pack with f format` on `g` and `d`. `' f'`, `'10f'`, `'2f'` fail likewise. `_ail_struct_native_of` treats only empty/`@` as native, but CPython's default order is `@`. The report's "pack_into native float mode" fix covers explicit `@` only.

2. **Double subnormal unpack is off by 2^51.** Probe:
   ```python
   import struct
   d = b'\x01' + b'\x00' * 7
   print(struct.unpack('<d', d))
   print(struct.pack('<d', struct.unpack('<d', d)[0]).hex())
   ```
   Expected `(5e-324,)` / `0100000000000000`; actual `(1.1125369292536007e-308,)` / `0000000000000800`. `_ail_struct_scale`'s negative branch subtracts only `512+256+...+1 = 1023`, so exponent `-1074` keeps a residue of 51. All subnormal doubles are affected. Copying the helper into a probe gives the same wrong value under CPython too, so it is the prelude algorithm, not an AIL float limitation.

3. **`pack_into` wrong item-count text.** Probe:
   ```python
   import struct
   for call in (lambda: struct.pack_into('<i', bytearray(4), 0),
                lambda: struct.Struct('<i').pack_into(bytearray(4), 0)):
       try: call()
       except Exception as e: print(type(e).__name__, e)
   ```
   Expected `error pack_into expected 1 items for packing (got 0)` (both); actual `error pack expected 1 items for packing (got 0)` (both). Also, with an invalid negative offset plus a wrong count, CPython reports the count first, AIL reports the offset.

4. **`p` wrong-type error names `s`.** Probe `struct.pack('4p', 'abc')`; expected `error argument for 'p' must be a bytes object`, actual `error argument for 's' must be a bytes object`.

5. **`pack_into` into immutable bytes text (minor).** Probe `struct.Struct('<i').pack_into(b'0123', 0, 1)`; expected `TypeError argument must be read-write bytes-like object, not bytes`, actual `TypeError 'bytes' object does not support item assignment`.

Also noted: `unpack('0p', b'')` returns `(b'',)` where CPython 3.12 raises `SystemError`; `calcsize('999999999999999999999i')` raises `OverflowError` where CPython raises `struct.error: total struct size too long`.

**Report claims**
- `p` clamp, negative-zero sign, repeat-count whitespace, deep negative-offset messages: **verified** (`p3`, `p4`, `p1`, `p8`).
- Declared uint64 difference: **verified**; `AIL_EXACT_INT=1` matches CPython (`p9`).
- 12 programs build and match: **verified** by `test_ail_std_struct`.
- `test_ail_std_struct` + `test_ail_safetynet` on HEAD: **verified**, 2/2 passed, 372 s.
- `update_manifest.py --check`: **verified**, exit 0.
- "probes match CPython": **unverified** (not re-run) and **contradicted** on the boundaries above.
- "pack_into native float fix": **incomplete** (defect 1).
- No `lab/compare` source imports `struct`: **verified**; generated C for a non-struct program, including one with `struct` in the source text, is byte-identical to base `work`.

**Pre-existing:** none observed. The base has no `struct`, and plain float arithmetic matches on both base and HEAD.

**Unverified:** `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3` (not re-run); exact `lab/compare` builds (`src/main.py` is not standalone-buildable); gdev instruction counts (no runtime hot path for non-struct programs).

VERDICT: FIX
[cost $0.0468, opencode tokens {"total": 2293657, "input": 86673, "output": 14720, "reasoning": 30856, "cache.write": 0, "cache.read": 2161408}]
    tool time: bash 11.8 min, read 0.0 min
        373s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_std_stru
        119s bash   python3 - <<'EOF' p='/tmp/rprobes/p3_offsets.py' s=open(p).read() s=s.replace("""            if fmt.endswith('
         43s bash   cd /tmp/rprobes && for p in p1_floats p2_ints p3_offsets p4_parser; do echo "===== $p"; bash ~/tools/cmp.sh /t
         34s bash   cat > /tmp/rprobes/p7_subnorm.py <<'EOF' import struct  def scale(m: float, ex: int) -> float:     r = m     k
         33s bash   cd /tmp && rm -rf cH cB && mkdir cH cB && cd /home/runner/work/_temp/w2 && AIL_NO_CACHE=1 python3 AIL_CURRENT/
         32s bash   cd /tmp/cmpIePw && cat > /tmp/rprobes/p6_minsub.py <<'EOF' import math import struct  data = b'\x01' + b'\x00'
         31s bash   python3 - <<'EOF' p='/tmp/rprobes/p8_offsets2.py' s=open(p).read() s=s.replace("""        b2 = bytearray(10)  
         14s bash   cat > /tmp/rprobes/p9_uint64.py <<'EOF' import struct for fmt in ['Q', 'L', 'N', 'P']:     data = b'\x00' * 7 

FINAL VERDICT: FIX  2026-11-01T15:04:39Z
