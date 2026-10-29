# job job-stdlib44-10291920  started 2026-10-29T10:58:02Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"9130915a-e10d-4845-8df1-a53d9486acfb","session_id":"f560f262-e3cd-4635-a234-8669d1531e2a"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"31eccac5-bc56-4950-b818-3a14f54a0493","session_id":"4e6493d9-baea-4dd6-88d2-967a7046690a"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed on `job-stdlib44-10291920` as `87a5329` (no push).

**Chosen module:** `struct` — 6 corpus/example imports, the most-imported still-refused module (higher counts were already modelled or out of scope). Supports `pack/unpack/unpack_from/pack_into/calcsize/error` for literal integer (`b B h H i I l L q Q n N P`), bool, `c`, `s`, `p` and `x` formats, with native alignment and `< > = !`. Fixed the staged candidate's failures: native-only `n/N/P`, CPython negative-offset semantics, `'b'` error text, `struct.error(...)`, and zero-width `p`.

**Probes** (`cmp.sh`, both builds):
- Same stdout/status as CPython: `p_int`, `p_align`, `p_bytes`, `p_bool`, `p_into`, `p_routes` (argument/list item/attribute/dict value), `p_imports`, `p_errors`.
- Refused by name on both builds: `r_float`, `r_nonliteral`, `r_struct`, `r_keyword`, `r_star`, `r_badchar`, `r_repeat`, `r_native`, `r_zerop`, `r_binderror`.
- Declared difference (`p_highq`): unpacking a `Q/N/P` value above int64 stops with the documented int64 error where CPython returns a bignum.

**Tests:** `test_ail_stdlib44`, `test_ail_stdlib5`, `stdlib_batch1/3/4` — 57 passed; `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 25 passed, 1 skipped. `update_manifest.py --check` rc=0. DEVLOG + DIFFERENCES (`C?-job-stdlib44-10291920-1`) added. Only untracked `.agent/pipeline.md` remains uncommitted.
[cost $0.0540, opencode tokens {"total": 3999907, "input": 99204, "output": 18983, "reasoning": 27000, "cache.write": 0, "cache.read": 3854720}]
    tool time: bash 36.1 min, write 0.0 min
        892s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 -B -m unittest test_ail_stdlib44 test_ail_stdlib5 t
        524s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest test_ail_safetynet test_ail_files tes
        161s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/stdlib44/p_*.py; do echo "===== $(basename $f)"; ba
        136s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/stdlib44/p_*.py; do echo "===== $(basename $f)"; ba
         94s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 -B -m unittest test_ail_stdlib44 -v 2>&
         87s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/stdlib44/p_into.py /tmp/probes/stdlib44/p_imports.p
         61s bash   cd AIL_CURRENT && timeout 1800 python3 -B -m unittest test_ail_stdlib44 -v 2>&1 | tail -40
         50s bash   cd /home/runner/work/ail-ci/ail-ci && R=$PWD && for f in /tmp/probes/stdlib44/r_*.py; do echo "===== $(basenam

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds a source-to-source lowerer (`structlib.py` + `prelude_struct.py`) that rewrites literal `struct.pack/unpack/unpack_from/pack_into/calcsize/error` calls into helper calls for integer, bool, `c`, `s`, `p`, `x` formats, with `@` alignment and `<>=!` orders; other uses are refused by name. That matches the report.

**Verified claims**
- 6 `import struct` sites in corpus/examples (2 corpus + 4 `language_examples`).
- `update_manifest.py --check` rc=0.
- `test_ail_stdlib44`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD: 4 modules, 0 failed (~447s).
- Non-`struct` program: `--debug-dir` `program.c` byte-identical between HEAD and `/tmp/base`; only the report path differs.
- Negative offsets, short buffers, native alignment for non-zero counts, error text for range/short buffers match my probes (`p_negoff2`, `p_intoerr2`, `p_routes`).
- Declared `Q/N/P` > int64 stop is present.

**Pre-existing.** None found; base refuses `struct` at compile time, so the failures below are introduced by this change.

**Unverified.** Speed/icount; the worker’s own `/tmp/probes/stdlib44` results; the “staged candidate” history; modules beyond the required rerun.

VERDICT: FIX

1. **`p` count is not capped at 255 (valid input crashes).** Probe `/tmp/rprobes/p_pascal.py`: `struct.pack('300p', b'y'*260)` then `unpack`. CPython: `300 255 b'yyy' 255`; AIL both builds: `ERR ValueError bytes must be in range(0, 256)`. CPython stores `min(len, size-1, 255)`; the helper stores `size-1` (e.g. 299/256) into `bytes([n])`.

2. **Zero repeat count loses native alignment padding in `@` mode.** Probe `/tmp/rprobes/p_zerocount2.py`: `calcsize('@b0i')`, `pack('@b0i',1)`, `calcsize('@c0lx')`, `pack('@c0lx',b'z')`, `calcsize('@b0h'/'@b0l'/'@b0q')`. CPython: `4`, `b'\x01\x00\x00\x00'`, `9`, `b'z\x00\x00\x00\x00\x00\x00\x00\x00'`, `2`, `8`, `8`; AIL: `1`, `b'\x01'`, `2`, `b'z\x00'`, `1`, `1`, `1`. CPython pads for the type even when the repeat count is 0; `_layout`/`_ail_struct_total` only pad inside the `while k < n` loop.

3. **Whitespace between a repeat count and its format character is accepted.** Probe `/tmp/rprobes/p_ws2.py`: `calcsize("3 i")`, `pack("3 i",1,2,3)`, `calcsize("3\tI")`, `calcsize("2\nh")`. CPython: four `error: bad char in struct format`; AIL: `12`, 12 packed bytes, `12`, `4`. (CPython permits whitespace before a format unit, as in `" 3i"` -> 12, which AIL also gets right.)

4. **Buffer arguments are not type-checked like CPython.** Probe `/tmp/rprobes/p_types.py` / `p_strinput.py`: `struct.unpack('<I', [1,2,3,4])` -> CPython `TypeError: a bytes-like object is required, not 'list'`; AIL returns `(67305985,)`. `struct.unpack('<3s', 'abc')` -> CPython `TypeError: a bytes-like object is required, not 'str'`; AIL `TypeError: string argument without an encoding`. `struct.pack_into('<I', b'abcde', 0, 1)` -> CPython `TypeError: argument must be read-write bytes-like object, not bytes`; AIL `TypeError: 'bytes' object does not support item assignment`. The helpers index whatever object they are given (`len`/`[]`) instead of rejecting non-buffer inputs.
[cost $0.0345, opencode tokens {"total": 1545424, "input": 64892, "output": 9667, "reasoning": 24337, "cache.write": 0, "cache.read": 1446528}]
    tool time: bash 11.0 min
        450s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib44 test_ail_safetynet tes
         51s bash   cd /tmp/rprobes && for p in p_ws p_intoerr p_negoff p_strinput p_routes; do echo "===== $p"; bash ~/tools/cmp.
         50s bash   cd /tmp/rprobes cat > p_ws2.py <<'EOF' import struct for f in ("3 i", "3\tI", "2\nh", " 3i", "3 i"):     pass 
         37s bash   cd /tmp/rprobes cat > p_pascal.py <<'EOF' import struct v = b'y' * 260 try:     b = struct.pack('300p', v)    
         23s bash   cd /tmp/rprobes cat > p_zerocount2.py <<'EOF' import struct print(struct.calcsize('@b0i')) print(struct.pack('
         22s bash   cd /tmp/rprobes cat > p_types.py <<'EOF' import struct print(struct.pack('<3s', bytearray(b'ab')), struct.unpa
         13s bash   cd /tmp/rprobes && echo "CPY p_zerocount2:"; python3 p_zerocount2.py; echo "---AIL:"; d=$(mktemp -d); cp p_zer
          6s bash   cd /tmp/base && git log --oneline -1; git status --short | head -3; echo ---; cd /tmp/rprobes && bash ~/tools/

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `6ea4f12`.

- `p` length byte now capped at `min(len, size-1, 255)`.
- Zero repeat counts now apply `@` alignment padding (`@b0i`=4, `@c0lx`=9, `@b0h/@b0l/@b0q`=2/8/8).
- Whitespace between count and format char is refused (`bad char in struct format`); whitespace before the count still works.
- `unpack`/`unpack_from` reject non-buffers and `pack_into` rejects non-writeable buffers with CPython 3.12 TypeError text.

Probes in `/tmp/probes/review44`, both builds via `cmp.sh`:
- `p_pascal` — same stdout; cap via value, argument, list item, attribute, dict value.
- `p_zerocount` — same stdout; sizes and packed output through the same routes.
- `p_types` — same stdout; list/str/int/None/float plus valid bytearray.
- `p_ws` — refused by name (`bad char in struct format`).

Added regression cases to `test_ail_stdlib44.py`. Final required run: `test_ail_stdlib44`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (330s). `update_manifest.py --check` rc 0.
[cost $0.0271, opencode tokens {"total": 1647521, "input": 76655, "output": 9619, "reasoning": 8607, "cache.write": 0, "cache.read": 1552640}]
    tool time: bash 17.0 min, edit 0.0 min, read 0.0 min
        436s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib44 test_ail_safetynet tes
        332s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib44 test_ail_safetynet tes
        100s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         65s bash   cd /tmp/probes/review44 && for p in p_pascal p_zerocount p_types p_ws; do echo "===== $p"; bash ~/tools/cmp.sh
         64s bash   cd /tmp/probes/review44 && for p in p_pascal p_zerocount p_types p_ws; do echo "===== $p"; bash ~/tools/cmp.sh
         20s bash   cd /tmp/probes/review44 && sed -i 's/for b in (b"abcde", \[0, 0, 0, 0\], "abcd", 7):/for b in (b"abcde", [0, 0
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib44 2>&1 | tail -40
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of `work..HEAD` (job-stdlib44)**

What the change really does: adds a `struct` lowerer (`python/pkg-v12/structlib.py` + `prelude_struct.py`) for literal `pack`/`unpack`/`unpack_from`/`pack_into`/`calcsize` over integer/bool/`c`/`s`/`p`/`x` formats with `@` alignment and `<>=!` orders; commit `6ea4f12` fixes the four previously reported defects. That matches the report.

Claims checked:
- `p` length cap `min(len,size-1,255)` — verified (sizes 1/2/5/255/256/257/300, values 0..600, routes arg/list/attr/dict).
- zero-count `@` padding (`@b0i`=4, `@c0lx`=9, `@b0h/l/q`=2/8/8) — verified; also fuzzed 5122 formats for `calcsize` and 3000 for pack/unpack, plus 6000 offset cases: no mismatch.
- whitespace between count and char refused, before count allowed — verified on both builds (`bad char in struct format`).
- non-buffer `unpack`/`unpack_from`, non-writable `pack_into` TypeError text — verified (list/str/None/int/float, bytearray accepted).
- worker probes `p_pascal`, `p_zerocount`, `p_types`, `p_ws` — re-ran, all match/refuse as reported.
- `test_ail_stdlib44` + `test_ail_safetynet` — pass (124s); `update_manifest.py --check` rc 0.
- non-struct programs: `program.c` identical to base (only temp paths differ).
- `test_ail_files`, `test_ail_corpus_findings3` — **unverified** (not re-run per reviewer scope).

Defects:

1. Integer formats accept wrong-typed values instead of `struct.error`. Probe:
```python
import struct
for v in (b"5", [5], (5,), {"a": 5}):
    try: print(repr(v), struct.pack("<i", v))
    except Exception as e: print(repr(v), type(e).__name__, str(e))
```
CPython: `b'5' error required argument is not an integer` (same for list/tuple/dict).
Actual (both builds): `b'5' b'\x05\x00\x00\x00'`; `[5] TypeError int() argument must be a string or a number, not 'list'`. Reproduced through an argument, list item, attribute and dict value (`p_badint2.py`). Root: `_ail_struct_check_int` rejects only float/str/None, then calls `int(value)` without rejecting bytes or catching `TypeError`.

2. Native `P` rejects negative values. Probe:
```python
import struct
print(struct.pack("@P", -1).hex())
```
CPython: `ffffffffffffffff`. Actual: `struct.error: 'P' format requires 0 <= number <= 18446744073709551615` (exit 1). `P` is treated like `Q`/`N`, but CPython masks negative pointer values. Also reproduced via list/dict routes (`p_pneg.py`).

3. Large literal repeat count hangs the compiler. Probe:
```python
import struct
print(struct.calcsize("1000000000000i"))
```
CPython: prints `4000000000000`, exit 0. Actual: compile does not finish within 30s (`rc=124`); `structlib._layout` materializes one value per repetition even for `calcsize` (`_layout('1000000000000i')` times out directly).

Pre-existing: none applicable (base `work` has no `struct` support).

Unverified: `test_ail_files` and `test_ail_corpus_findings3` (worker claim); instruction-count speed (no existing hot path is changed; the pass is gated on `"struct" in source`).

VERDICT: FIX

1. `_ail_struct_check_int`: reject bytes/bytearray/tuple/list/dict and other non-int types with `struct.error: required argument is not an integer`; catch `int()` `TypeError`. Probe `p_badint.py` / `p_badint2.py`; expected CPython `error required argument is not an integer`, actual packing or `TypeError`.
2. `_ail_struct_check_int` for `P`: accept negative values and mask to 64 bits (`struct.pack("@P", -1) == b"\xff"*8`), not the unsigned-range error. Probe `p_pneg.py`.
3. `_layout`: compute `calcsize`/sizes without materializing every repeated element, or refuse an oversized count by name; `calcsize("1000000000000i")` must not hang. Probe `p_bigcount.py`; expected `4000000000000`, actual compile timeout.
[cost $0.0508, opencode tokens {"total": 2497188, "input": 127358, "output": 14114, "reasoning": 27012, "cache.write": 0, "cache.read": 2328704}]
    tool time: bash 7.4 min
        126s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         63s bash   cd /tmp/probes/review44 && for p in p_pascal p_zerocount p_types p_ws; do echo "===== $p"; bash ~/tools/cmp.sh
         60s bash   cd /tmp/rprobes && sed -i 's/print(struct.pack("@b0p", 1, b"abc"), struct.unpack("@b0p", b"\\x01"))/print(stru
         53s bash   cd /tmp/rprobes && for p in p1_pascal p2_zero p3_ws p4_types p5_alias; do echo "===== $p"; bash ~/tools/cmp.sh
         30s bash   cd /tmp/rprobes && cat > p_bigcount.py <<'PY' import struct print(struct.calcsize("1000000000000i")) PY cd /tm
         17s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p_intoerr2.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail 
         16s bash   cd /tmp/rprobes && cat > p_pneg.py <<'PY' import struct  def pk(v):     try:         print(repr(v), struct.pac
         16s bash   cd /tmp/rprobes && cat > p_memview.py <<'PY' m = memoryview(b"abcd") print(m[0], len(m), bytes(m)) n = memoryv

FINAL VERDICT: FIX  2026-10-29T12:47:52Z
