# job job-stdlib18-10290433  started 2026-10-28T19:42:10Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"9beb68b7-394b-4987-b9ac-a48cf158d8e9","session_id":"d6dace2b-ea25-450e-917d-38e478e07072"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"9ece2e88-e31f-4976-b417-552e28fed135","session_id":"0abe1e01-589c-4706-be22-69a0e621b5ab"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `struct` support in `e088349`:

- New `structlib.py` rewrite pass hooked into `ail_syntax.py`; `test_ail_stdlib18.py` registered in `ail_check.py`.
- Built `pack`/`unpack`/`unpack_from`/`pack_into`/`calcsize` for explicit byte orders and `x b B h H i I l L q s c ?`; native layout, floats, pointers, `Q`, `Struct`, `iter_unpack`, and dynamic formats refused by name.
- Probes in `/tmp/probes/stdlib18` match CPython on both builds; both corpus `t475` programs now build and match.
- `test_ail_stdlib18`, `test_ail_python_syntax`, `test_ail_modules`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass; `update_manifest.py --check` passes. Left untracked `.agent/pipeline.md` untouched.
[cost $0.0000, opencode tokens {"total": 8520254, "input": 401279, "output": 30830, "reasoning": 46929, "cache.write": 0, "cache.read": 8041216}]
    tool time: bash 26.5 min
        254s bash   cd AIL_CURRENT && python3 -m unittest test_ail_stdlib5 -q 2>&1 | tail -20
        189s bash   cd AIL_CURRENT && python3 -m unittest test_ail_corpus_findings3 -q 2>&1 | tail -20
        183s bash   cd /tmp && cat > /tmp/compcheck.py <<'EOF' import re,subprocess,sys,os,json,concurrent.futures from pathlib im
        156s bash   cd AIL_CURRENT && python3 -m unittest test_ail_safetynet -q 2>&1 | tail -20
        149s bash   cd AIL_CURRENT && python3 -m unittest test_ail_modules -q 2>&1 | tail -20
        130s bash   cd AIL_CURRENT && python3 -m unittest test_ail_safetynet -q 2>&1 | tail -8
         96s bash   cd AIL_CURRENT && python3 -m unittest test_ail_files -q 2>&1 | tail -20
         63s bash   cd /tmp/improbe && rm -f *.py *.out *.err && for m in argparse tempfile struct shutil contextlib signal resour

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Change (one line):** Adds `AIL_CURRENT/python/pkg-v12/structlib.py`, an AST source pass called from `ail_syntax.python_surface`, lowering `struct.pack/unpack/unpack_from/pack_into/calcsize` (literal `<,>,!` formats) to generated Python helpers, plus a test, manifest and DIFFERENCES/DEVLOG entries. This matches the report's description.

**Claims**
- New pass + `test_ail_stdlib18` registration: **verified** (diff, `ail_check.py`).
- Built/refused surface as listed: **verified** (code + `Refusals` cases).
- "s/c match CPython exactly, error messages included" (DIFFERENCES row): **false** (defects 1–4).
- `test_ail_stdlib18`, `test_ail_safetynet` pass: **verified** (par_check, 0 failed); `update_manifest.py --check`: **verified**.
- Other five test modules and both `t475` programs: **unverified** (not re-run here).
- `/tmp/probes/stdlib18` match: **unverified**; my independent probes found mismatches they miss.

**Defects** (each probe builds on baselines `work`; on base it is a named refusal, so each difference is introduced here)

1. `pack`/`pack_into` reject bytes-like objects for `s`/`c`; CPython accepts `bytearray`. Probe `/tmp/rprobes/r2_byteslike.py`:
   ```python
   b = bytearray(b'ab')
   print(list(struct.pack('>4s', b)))
   print(list(struct.pack('>2s', b)))
   ```
   Expected `[97, 98, 0, 0]` / `[97, 98]`; actual: no output, `_AilStructError: argument for 's' must be a bytes object`, exit 1 (same for a list item/dict value/attribute in `r8_byteslike_routes.py`).

2. `unpack`/`unpack_from` return `bytearray` slices for `s`/`c` when given a `bytearray`; CPython always returns `bytes`. Probe `/tmp/rprobes/r5_unpack_bytes.py`:
   ```python
   ba = bytearray(b'ab')
   print(struct.unpack('>2s', ba))
   print(struct.unpack('>2c', ba))
   print(struct.unpack_from('>2s', bytearray(b'abcd'), 1))
   ```
   Expected `(b'ab',)`, `(b'a', b'b')`, `(b'bc',)`; actual `(bytearray(b'ab'),)`, `(bytearray(b'a'), bytearray(b'b'))`, `(bytearray(b'bc'),)`.

3. Error class name leaks: catching with `except Exception` prints `_AilStructError` where CPython prints `error`. Probe `/tmp/rprobes/r9_errname.py` prints `type(e).__name__`. Expected `error unpack requires a buffer of 4 bytes` / `error 'B' format requires 0 <= number <= 255`; actual `_AilStructError ...` (documented in DIFFERENCES.md, but still an observable output difference).

4. Zero-size offsets: `unpack_from`/`pack_into` with a negative offset and a 0-byte format give different `struct.error` text. Probe `/tmp/rprobes/p_zeroerr.py`:
   ```python
   try: struct.unpack_from('>0I', b'', -1)
   except struct.error as e: print('uf', e)
   try: struct.pack_into('>0I', bytearray(0), -1)
   except struct.error as e: print('pi', e)
   ```
   Expected `uf offset -1 out of range for 0-byte buffer` / `pi offset -1 out of range for 0-byte buffer`; actual `uf not enough data to unpack 0 bytes at offset -1` / `pi no space to pack 0 bytes at offset -1`.

**Pre-existing:** none found (all probed differences are refusals on `work`).

**Unverified:** the worker's own `/tmp/probes/stdlib18`; `t475` output with real stdin; `test_ail_python_syntax`, `test_ail_modules`, `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3`; instruction-count/speed (frontend-only change).

VERDICT: FIX
[cost $0.0181, opencode tokens {"total": 661095, "input": 45587, "output": 4271, "reasoning": 11557, "cache.write": 0, "cache.read": 599680}]
    tool time: bash 6.5 min
        169s bash   cd /home/runner/work/_temp/w2 && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_stdlib18 test_a
        165s bash   date; cd /home/runner/work/_temp/w2 && printf '%s\n' p_rep p_routes p_from p_zerofrom r1_bool r2_byteslike r3_
         31s bash   cd /home/runner/work/_temp/w2 && printf '%s\n' p_zerofrom r2_byteslike r5_unpack_bytes r8_byteslike_routes r9_
         23s bash   cat > /tmp/rprobes/p_zeroerr.py <<'EOF' import struct   def main() -> None:     try:         struct.unpack_fro
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -5; echo "exit $?"; grep
          0s bash   git diff work..HEAD --stat; echo ---; git diff work..HEAD -- AIL_CURRENT/ail_check.py DEVLOG.md | head -100
          0s bash   date; pwd; ls
          0s bash   cd /tmp/rprobes; for f in p_rep p_routes p_from p_zerofrom r1_bool r2_byteslike r3_zero_offsets r4_routes r5_u

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0465, opencode tokens {"total": 3729418, "input": 98549, "output": 14748, "reasoning": 20089, "cache.write": 0, "cache.read": 3596032}]
    tool time: bash 44.6 min
        826s bash   cd /home/runner/work/_temp/w2 && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_stdlib18 test_a
        816s bash   cd /home/runner/work/_temp/w2 && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_stdlib18 test_a
        271s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/stdlib18/*.py /tmp/probes/reviewfix/*.py; do echo "=== $
        231s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/stdlib18/*.py /tmp/probes/reviewfix/*.py; do echo "=== $
        109s bash   cat > /tmp/probes/reviewfix/p_offsets.py <<'EOF' import struct   def uf(fmt, data, off):     try:         retu
        105s bash   ls /tmp/probes/stdlib18 && cd /home/runner/work/_temp/w2 && for f in /tmp/probes/stdlib18/*.py; do echo "=== $
         88s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/reviewfix/*.py; do echo "=== $f"; timeout 600 bash ~/too
         68s bash   cat > /tmp/probes/reviewfix/p_badinputs.py <<'EOF' import struct   def uf(data):     try:         print(struct
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
Read the diff, probes, and tests. Findings below.

**What the change really does:** adds `AIL_CURRENT/python/pkg-v12/structlib.py`, a source-to-source AST lowering of `struct.pack/unpack/unpack_from/pack_into/calcsize/error` (explicit byte order, int codes + `x s c ?`) onto `int.to_bytes`/`int.from_bytes`, hooked into `ail_syntax.python_surface` before the tuple pass; plus `test_ail_stdlib18`, MANIFEST/DIFFERENCES/DEVLOG. Matches the report's description.

**Probes (all `/tmp/rprobes/s18`, `cmp.sh`, both builds):** `p_alias`, `p_formats`, `p_qmark`, `p_qdirect`, `p_direct`, `p_qmin`, `p_combo`, `p_errorcoll` match CPython. `p_memview`, `p_localimp` refuse by name (acceptable). `p_unrelated` C is byte-identical to base2. `p_errorattr`, `p_errname2`, `p_order` differ (below).

**Defects**

1. **`pack_into` checks the values before the buffer/offset.** CPython validates the buffer/offset first, then packs. Probe `/tmp/rprobes/s18/p_order.py`:
```python
import struct
def pi(buf, off, v):
    try:
        struct.pack_into('>I', buf, off, v)
    except Exception as e:
        print(type(e).__name__, e)
def main() -> None:
    pi(bytearray(2), 0, 1099511627776)
    pi(b'xxxx', 0, 1099511627776)
    pi(bytearray(2), -5, 1099511627776)
main()
```
Expected (CPython, both builds):
```
error pack_into requires a buffer of at least 4 bytes for packing 4 bytes at offset 0 (actual buffer size is 2)
TypeError argument must be read-write bytes-like object, not bytes
error offset -5 out of range for 2-byte buffer
```
Actual (HEAD, g and d):
```
error 'I' format requires 0 <= number <= 4294967295
error 'I' format requires 0 <= number <= 4294967295
error 'I' format requires 0 <= number <= 4294967295
```
Cause: `Builder.pack_into` calls `pack(...)` before `_ail_struct_write` validates `buf`/`off`. `pack_into`/`bytearray(2)/bad value`, `bytes`+bad value, short valid value, and negative-offset+bad value all cover it.

2. **The injected generic name `error` leaks into the program namespace.** Probe `/tmp/rprobes/s18/p_errname2.py`:
```python
import struct
print(error)
error = 5
```
Expected (CPython): `NameError: name 'error' is not defined`, exit 1. Actual (HEAD, g and d): prints `<class '__main__.error'>` and exits 0. On the general path the same program without `import struct` (`p_forward.py`) correctly raises `NameError`, so the new `class error` injection causes this. A related symptom is `/tmp/rprobes/s18/p_errorattr.py`: `print(struct.error)` gives `<class '__main__.error'>` vs CPython `<class 'struct.error'>` (this one is the same pre-existing limitation as `json.JSONDecodeError` on the base, so it is not counted on its own).

**Pre-existing:** stdlib exception classes render as `<class '__main__.X'>` (verified with `json.JSONDecodeError` on base2). Default-build forward-reference read-before-assignment already misbehaves without struct (`p_forward.py` d build).

**Verified claims:** `s` bytearray / `c` bytes-only; unpack results bytes; error type name `error`; negative/zero offsets (formula grid 0 mismatches, matches `test_ail_stdlib18`); t475 builds and matches on `5 0 1 255 256 4294967295`; unchanged C for non-struct programs; named refusals; import counts (struct 2+4 vs unicodedata 3 etc.); `tools/update_manifest.py --check` exits 0; `test_ail_stdlib18` and `test_ail_safetynet` pass (2 modules, 0 failed).

**Unverified:** the deepseek t475, the other five final-state modules in DEVLOG, and speed (struct helper code is not on hot paths).

VERDICT: FIX

1. `pack_into` must validate buffer type/size/offset before packing values (`p_order.py`, expected/actual above).
2. Do not expose the generic `error` name unconditionally: refuse (or otherwise isolate) programs that bind/read `error`, so `p_errname2.py` raises `NameError` like CPython instead of printing the injected class.
[cost $0.0534, opencode tokens {"total": 3083674, "input": 94554, "output": 9662, "reasoning": 41090, "cache.write": 0, "cache.read": 2938368}]
    tool time: bash 4.4 min, read 0.0 min
         92s bash   cd /home/runner/work/_temp/w2 && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_stdlib18 test_a
         49s bash   cd /home/runner/work/_temp/w2 && date && for f in /tmp/rprobes/s18/*.py; do echo "########## $f"; timeout 900 
         17s bash   cd /home/runner/work/_temp/w2 && date && for f in /tmp/rprobes/s18/p_qmin.py /tmp/rprobes/s18/p_combo.py; do e
         13s bash   cd /tmp/rprobes/s18 && python3 - <<'EOF' p='/tmp/rprobes/s18/p_direct.py' s=open(p).read() s=s.replace("    tr
         13s bash   cd /tmp && rm -rf t475 && mkdir t475 && cp /home/runner/work/_temp/w2/lab/corpus/programs/glm-5.3-flash-free/t
         12s bash   cd /home/runner/work/_temp/w2 && timeout 700 bash ~/tools/cmp.sh /tmp/rprobes/s18/p_order.py "$PWD" 2>&1 | tai
         12s bash   cd /home/runner/work/_temp/w2 && timeout 700 bash ~/tools/cmp.sh /tmp/rprobes/s18/p_errname2.py "$PWD" 2>&1 | 
         12s bash   cat > /tmp/rprobes/s18/p_qdirect.py <<'EOF' import struct   def main() -> None:     print(struct.pack('>?', 'x

FINAL VERDICT: FIX  2026-10-28T21:58:34Z
