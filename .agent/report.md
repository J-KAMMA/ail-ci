# job job-stdlib24-10290512  started 2026-10-28T20:18:38Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"a4958a3d-d9f9-4a61-a3ac-3692ff7d03bd","session_id":"156b4417-64c1-4788-807d-d6f991557764"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"f44319e9-a5ea-445c-a9d9-1e2a79f9bfc0","session_id":"60d601fb-2d4c-431e-bb75-62b55584b9e1"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Committed as `1a35394` on `job-stdlib24-10290512`.

- `struct` was the most-imported still-refused module (6; the 6 `heapq` imports were already built).
- Added `structlib.py` + `prelude_struct.py`: literal-format `pack`, `unpack`, `unpack_from`, `pack_into`, `calcsize` over integer, bool, char, pad, `s` and `p` codes, counts, native alignment and standard layouts.
- Added `test_ail_stdlib24.py`, registered in `ail_check.py`; updated `MANIFEST.json`, `ci_shards.json`, `DEVLOG.md`, `DIFFERENCES.md`.
- Probes: 14 behaviour probes (`basic`, `pack_all`, `routes`, `routes2`, `buffers`, `alias`, `fromimport`, `errors`, `errtuple`, `qneg`, `boolint`, `empties`, `calc_float`, `customerr`) match CPython on both builds; 11 refusal probes (`nonliteral`, `floatfmt`, `ref_0p`, `ref_empty_unpack`, `ref_value`, `ref_wildcard`, `ref_badfmt`, `ref_nonliteral_calc`, `ref_float_unpack`, `ref_collision`, `ref_error_value`) are refused by name.
- Final tests: 5 modules (`test_ail_stdlib24`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) — 36 tests, 0 failed, 1 skipped. `update_manifest.py --check` and `ci_shards.py --check` pass.
- Known limits documented: float formats refused; `struct.error` in `except` is `ValueError`; int64 caps Q/N/P; `0p` refused. Untracked `.agent/pipeline.md` was left untouched.
[cost $0.0656, opencode tokens {"total": 5265038, "input": 118930, "output": 26575, "reasoning": 27565, "cache.write": 0, "cache.read": 5091968}]
    tool time: bash 20.7 min, write 0.0 min
        509s bash   python3 -m unittest -v test_ail_stdlib24 test_ail_check test_ail_safetynet test_ail_files test_ail_corpus_find
        120s bash   pwd; ls test_ail_safetynet.py >/dev/null && echo exists; python3 -c "import sys; print(sys.path[:3])"; python3
         89s bash   python3 -m unittest -v test_ail_stdlib24
         87s bash   for p in pack_all routes fromimport errors qneg boolint empties nonliteral floatfmt; do echo "=== $p"; bash ~/
         76s bash   for p in fromimport errors alias ref_error_value; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/probes/stdlib24/$
         73s bash   cd /tmp/probes/stdlib24 && python3 - <<'EOF' from pathlib import Path codes = ["b", "B", "h", "H", "i", "I", "
         53s bash   cd /tmp/probes/stdlib24 && python3 - <<'EOF' from pathlib import Path codes = ["b", "B", "h", "H", "i", "I", "
         39s bash   cd /tmp/probes/stdlib24 && cat > ref_empty_unpack.py <<'EOF' import struct  print(struct.unpack("", b"")) EOF 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `struct` batch 24

**What the change really does:** `python_surface` now calls a new `structlib.rewrite_text` whenever the source contains `"struct"`; it reads the literal format with CPython's `calcsize` at compile time and rewrites `pack`/`unpack`/`unpack_from`/`pack_into`/`calcsize` onto helpers in `prelude_struct.py` built on `int.to_bytes`/`from_bytes`. This matches the report.

**Verified**
- Counts: `struct` 6, `heapq` 6 in `lab/corpus/programs` + `AIL_CURRENT/language_examples`; `heapq` is already supported.
- Files/registration/manifest/DEVLOG/DIFFERENCES present; `update_manifest.py --check` and `ci_shards.py --check` are silent (pass).
- Required modules on HEAD: 5 modules, 0 failed in 367s (`test_ail_stdlib24`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- A non-`struct` program and one with `struct` only in a comment: generated `program.c` identical to `/tmp/base` (only `native_report.json` differs), so unrelated C is unchanged.
- Float, non-literal format, wildcard, keyword `offset`, literal negative offset, and `0p` cases are named compile-time refusals. `struct.error`→`ValueError` and int64 Q/N/P are documented differences.

**Report claims that are false**
- "Both builds match CPython for the built fields… and the raised errors": false; see defects 1–3.
- `pack('0p', b'x')` is `b''` in CPython 3.12, not a `SystemError`; only `unpack('0p')` raises. The refusal is named so acceptable, but the test/doc rationale is wrong.

**Defects**

1. **Negative offsets are not handled.** `/tmp/rprobes/neg_off_var.py`:
```python
import struct
buf = b"abcdefgh"
off = -4
print(struct.unpack_from(">i", buf, off))
off2 = -2
print(struct.unpack_from(">h", buf, off2))
b = bytearray(8)
struct.pack_into(">i", b, off, 0x01020304)
print(bytes(b).hex())
```
Expected (CPython): `(1701209960,)`, `(26472,)`, `0000000001020304`. Actual both builds: no stdout, `ValueError: not enough data to unpack 4 bytes at offset -4`, exit 1 (`pack_into` likewise `ValueError: no space to pack 2 bytes at offset -2`). `_ail_struct_check` rejects every `base < 0` (`prelude_struct.py:61`) and `_ail_struct_pack_into` rejects `offset < 0` (`:99`); CPython 3.12 interprets in-range negative offsets from the end.

2. **Unpack does not normalize the buffer type.** `/tmp/rprobes/bytearray_unpack3.py`:
```python
import struct
b = bytearray(b"abcd")
print(struct.unpack("4s", b))
pb = bytearray(b"\x02ab\x00")
print(struct.unpack("4p", pb))
cb = bytearray(b"Z")
print(struct.unpack("c", cb))
buf = bytearray(struct.pack(">3h", 1, 2, 3))
print(struct.unpack_from("2s", buf, 1))
```
Expected CPython: `(b'abcd',)`, `(b'ab',)`, `(b'Z',)`, `(b'\x01\x00',)`. Actual both builds: the same tuples but with `bytearray(...)` elements. The `s`/`p`/`c` helpers return a slice of the input (`prelude_struct.py:78-92`). A `str` buffer is also wrongly accepted: `/tmp/rprobes/unpack_str_s.py`, `s = "abcd"; print(struct.unpack("4s", s))` prints `('abcd',)` and exits 0 where CPython raises `TypeError: a bytes-like object is required, not 'str'` and exits 1.

3. **Wrong-type values for `c`/`s`/`p` crash instead of raising the documented `struct.error`/`ValueError`.** `/tmp/rprobes/pack_char_int.py`:
```python
import struct
try:
    print(struct.pack("c", 65))
except struct.error as e:
    print("err", e)
```
Expected CPython: `err char format requires a bytes object of length 1`, exit 0. Actual both builds: no stdout, `TypeError: object of type 'int' has no len()`, exit 1; the `except struct.error` (aliased to `ValueError`) does not catch it. Same for `pack("s", 5)` and `pack("p", 5)`.

**Unverified:** the worker's full 14/11 probe list was not re-run individually (the test module covers equivalents and passes); full suite; no icount run because the change is compile-time only and runtime C for non-`struct` programs is unchanged.

VERDICT: FIX
[cost $0.0312, opencode tokens {"total": 1397647, "input": 60320, "output": 6904, "reasoning": 23415, "cache.write": 0, "cache.read": 1307008}]
    tool time: bash 10.6 min
        369s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_stdlib24 test_ail_che
         44s bash   mkdir -p /tmp/rprobes cat > /tmp/rprobes/neg_off.py <<'EOF' import struct  buf = b"abcdefgh" print(struct.unpa
         42s bash   cat > /tmp/rprobes/pack_into_immutable.py <<'EOF' import struct  b = b"abcd" struct.pack_into(">h", b, 0, 7) p
         37s bash   cat > /tmp/rprobes/unpack_str_s.py <<'EOF' import struct  s = "abcd" print(struct.unpack("4s", s)) EOF cat > /
         36s bash   cat > /tmp/rprobes/pack_s_int.py <<'EOF' import struct  try:     print(struct.pack("s", 5).hex()) except struc
         35s bash   cat > /tmp/rprobes/neg_off_var.py <<'EOF' import struct  buf = b"abcdefgh" off = -4 print(struct.unpack_from("
         34s bash   date; cat > /tmp/rprobes/mutate_after.py <<'EOF' import struct  b = bytearray(b"abcd") t = struct.unpack("4s",
         31s bash   cat > /tmp/rprobes/bytearray_unpack3.py <<'EOF' import struct  b = bytearray(b"abcd") print(struct.unpack("4s"

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `3613648` on `job-stdlib24-10290512`. Manifest and ci_shards checks pass.

Fixed all three review defects:
1. Negative `unpack_from`/`pack_into` offsets now normalize against the buffer, including literal `-N` and CPython's out-of-range/no-space boundaries.
2. `unpack` snapshots `bytearray` to `bytes`; `str` buffers raise `TypeError: a bytes-like object is required, not 'str'`.
3. Wrong-type `c`/`s`/`p` values raise `struct.error`/`ValueError`; `s`/`p` accept `bytearray`, `c` does not.
Also: `pack('0p')` now returns `b''` (only unpack `'0p'` stays refused), and `pack_into` on immutable data raises CPython's read-write `TypeError`.

Probes (both builds, `cmp.sh`):
- Match CPython: `neg_off`, `neg_off_var`, `pack_neg_var`, `bytearray_unpack3`, `mutate_after`, `unpack_str_s`, `pack_char_int`, `pack_s_int`, `pack_p_int`, `pack_into_immutable`, `pack0p`, `packempty`, `unpack_str_i`, plus `/tmp/probes/stdlib24_review/{neg_offsets,pack_into_offsets,pack_types,unpack_types,regression}.py`.
- Refused by name: `kw_offset`, `memview`, `unpack_empty_zero`.
- Direct differential over 20k random `unpack_from` cases and all `pack_into` sizes/offsets: 0 mismatches.

Tests on final tree: `test_ail_stdlib24` (127s, pass); `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (218s, 0 failed).
[cost $0.0546, opencode tokens {"total": 3938640, "input": 112550, "output": 20536, "reasoning": 23410, "cache.write": 0, "cache.read": 3782144}]
    tool time: bash 16.5 min
        265s bash   cd /tmp && : > /tmp/probe_results.txt; for p in /tmp/probes/stdlib24_review/*.py /tmp/rprobes/neg_off_var.py /
        231s bash   cd /tmp && for p in neg_off_var bytearray_unpack3 pack_char_int pack_s_int pack_p_int unpack_str_s mutate_afte
        219s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_check test_ail_safety
        129s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_stdlib24 2>&1 | tail 
         94s bash   cd /tmp && : > /tmp/probe_results2.txt; for p in /tmp/probes/stdlib24_review/*.py /tmp/rprobes/pack_into_immut
         32s bash   cd /tmp && for p in /tmp/probes/stdlib24_review/neg_offsets.py /tmp/probes/stdlib24_review/unpack_types.py /tm
         15s bash   cd /tmp/probes/stdlib24_review && python3 - <<'PYEOF' from pathlib import Path p=Path('unpack_types.py'); s=p.
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check && python3 tools/ci_shards.py --chec

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds a compile-time `struct` pass (`structlib.py`) that parses literal format strings and lowers `pack`/`unpack`/`unpack_from`/`pack_into`/`calcsize` onto `prelude_struct.py` helpers for integer/bool/char/`s`/`p`/`x` fields, plus the review commit's negative-offset, bytes-copy and wrong-type fixes; `test_ail_stdlib24` and manifest/devlog/differences entries are registered.

**Claims checked**
- Commit `3613648`, branch state, manifest `--check` (0) and `ci_shards --check` (0): verified.
- Fix 1 (negative `unpack_from`/`pack_into`, literal + variable, out-of-range/no-space boundaries): verified (`negzero.py`, `neg_var.py`, and the committed `negatives` program all match CPython on both builds).
- Fix 2 (`unpack` snapshots `bytearray`, `str` -> `TypeError`): verified (`mut_types.py`).
- Fix 3 (wrong-type `c`/`s`/`p`, `s`/`p` accept `bytearray`, `c` does not, `pack_into` immutable `TypeError`): verified (`errmsgs.py`, `mut_types.py`).
- `pack('0p', value)` returns `b''`; `unpack('0p', ...)` stays a named refusal: verified. (The report's `pack('0p')` wording omits that CPython still requires the single argument; the built form matches.)
- Tests on HEAD: `test_ail_stdlib24`, `test_ail_safetynet`, `test_ail_check`, `test_ail_files`, `test_ail_corpus_findings3` all pass (389 s, 0 failed; `test_ail_stdlib24` 187.9 s).
- Non-`struct` program: generated `program.c` is byte-identical to `/tmp/base` (14052 lines).
- Unverified: the "20k random `unpack_from` differential" (no artifact); the worker's `/tmp/probes/stdlib24_review` list is not fully present here. Speed: the pass only runs for `struct` programs, no hot path; not measured.

**Pre-existing:** none observed; base refuses every `struct` import, so both defects below are introduced by this change.

**VERDICT: FIX**

1. `p` (pascal string) with a repeat count >= 257 and a value longer than 255 bytes crashes where CPython clamps the length byte to 255. Probe `/tmp/rprobes/p_bigcount.py`:
```python
import struct
d = struct.pack("257p", b"a" * 400)
print(len(d), d[0], d[1:4].hex(), len(struct.unpack("257p", d)[0]))
d = struct.pack("300p", b"a" * 400)
print(len(d), d[0], d[1:4].hex(), len(struct.unpack("300p", d)[0]))
```
Expected (CPython, exit 0): `257 255 616161 255` then `300 255 616161 255`.
Actual (both builds): exits 1 with `ValueError: bytes must be in range(0, 256)` after the 255p/256p lines (prelude writes `bytes([n])` with `n = size - 1` unchecked against 255). A named refusal for `p` counts > 256 would also be acceptable; silently crashing is not.

2. A format containing `\x1c`-`\x1f` is accepted as whitespace, but CPython rejects it. Probe `/tmp/rprobes/control_ws.py`:
```python
import struct
print(struct.calcsize("\x1ci"))
```
Expected (CPython, exit 1): no stdout, `struct.error: bad char in struct format`.
Actual (both builds): prints `4`, exit 0. `_format` uses `str.isspace()`, which is true for `\x1c`-`\x1f`, while CPython's parser skips only C whitespace. (`pack`/`unpack` are affected the same way, and the committed `FormatLayout` test only uses counts 0-3 and ordinary formats, so neither boundary is covered.)
[cost $0.0335, opencode tokens {"total": 1175147, "input": 67057, "output": 8209, "reasoning": 25449, "cache.write": 0, "cache.read": 1074432}]
    tool time: bash 10.3 min
        391s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_stdlib24
         37s bash   cd /tmp/rprobes && for p in p_bigcount unpack_wide align0 negzero; do echo "===== $p"; bash ~/tools/cmp.sh /tm
         33s bash   cd /tmp/rprobes && cat > mixed.py <<'PY' import struct  print(struct.calcsize("@b2s3pi"), struct.calcsize("@b3
         31s bash   cd /tmp/rprobes && cat > unpack_wide.py <<'PY' import struct  r = b"\xff" * 8 print("Q", struct.unpack("Q", r)
         30s bash   cd /tmp/rprobes && cat > p_bigcount.py <<'PY' import struct  d = struct.pack("255p", b"a" * 400) print(len(d),
         23s bash   cd /tmp/rprobes && cat > neg_var.py <<'PY' import struct  class Box:     def __init__(self, v):         self.v
         21s bash   cd /tmp/rprobes && cat > errmsgs.py <<'PY' import struct  for bad in ("c", "s", "p"):     if bad == "c":      
         20s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('mut_types.py'); s=p.read_text() s=s.repla

FINAL VERDICT: FIX  2026-10-28T22:09:21Z
