# job job-stdlib47-10292150  started 2026-10-29T13:49:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"1d85149c-d2ea-4710-bebf-285dd89f4772","session_id":"270c7fda-0ffa-4d0d-bd39-37afc0fbb809"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"acfd7247-463a-41af-a27b-a4dadc07d7f0","session_id":"1f1196cc-a611-4147-9174-196fa6ed77f4"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `5270977` on `job-stdlib47-10292150`.

**What changed**
- Added `python/pkg-v12/structlib.py`: lowers `struct.pack`, `struct.unpack`, `struct.calcsize`, `struct.error` with literal formats onto bytes / `int.to_bytes` / `int.from_bytes`.
- Built prefixes `< > ! =`; fields `x c b B ? h H i I l L q Q s p`, counts and inter-field whitespace.
- Refused by name: native `@`/no prefix, `e f d n N P u w`, `Struct`, `pack_into`, `unpack_from`, `iter_unpack`, dynamic formats, zero-length `s`/`p`, count/format whitespace, leading whitespace.
- `struct` was the next used still-refused module (6 compiled imports). The 7 `tempfile` imports are CPython-side test-harness code; `hashlib` is crypto/out of scope.
- Added `test_ail_stdlib47.py` (2 tests, both builds), registered in `ail_check.MODULES`; added DEVLOG and DIFFERENCES rows; refreshed manifest.

**Tests on final commit**
- `test_ail_stdlib47`, `test_ail_python_syntax`, `test_ail_modules`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet`: **103 tests OK, 1 skipped**.
- `python3 tools/update_manifest.py --check`: **passes**.

**Probes** (all on both builds)
- Matched CPython: `s47_ints`, `s47_orders`, `s47_strings`, `s47_unpack`, `s47_values`, `s47_bytearray`, `s47_strbytes`, `s47_bool`, `s47_floatarg`, `s47_errorclass`, `s47_layout`, `s47_unpackroutes`, `s47_unpackbuf`, `s47_unpackstr`, `s47_whitespace`.
- Refused by name: `r_badchar`, `r_count`, `r_dynamic`, `r_float`, `r_from_import`, `r_iter_unpack`, `r_leadspace`, `r_module_value`, `r_native_at`, `r_native_none`, `r_pack_into`, `r_struct_class`, `r_unpack_from`, `r_whitespace`, `r_zero_s`.
[cost $0.0723, opencode tokens {"total": 6945579, "input": 143725, "output": 23627, "reasoning": 27123, "cache.write": 0, "cache.read": 6751104}]
    tool time: bash 35.2 min, edit 0.0 min, read 0.0 min
        820s bash   time python3 -m unittest AIL_CURRENT.test_ail_stdlib47 AIL_CURRENT.test_ail_python_syntax AIL_CURRENT.test_ail
        314s bash   for p in /tmp/probes/s47_ints.py /tmp/probes/s47_orders.py /tmp/probes/s47_strings.py /tmp/probes/s47_unpack.p
        275s bash   time python3 -m unittest AIL_CURRENT.test_ail_stdlib47 AIL_CURRENT.test_ail_python_syntax AIL_CURRENT.test_ail
         99s bash   for p in /tmp/probes/s47_ints.py /tmp/probes/s47_orders.py /tmp/probes/s47_strings.py /tmp/probes/s47_unpack.p
         82s bash   for p in /tmp/probes/s47ref/r_*.py; do printf '%-22s ' "$(basename $p)"; out=$(bash ~/tools/cmp.sh "$p" "$PWD"
         82s bash   for p in /tmp/probes/s47_unpackbuf.py /tmp/probes/s47_unpackstr.py /tmp/probes/s47_bytearray.py /tmp/probes/s4
         70s bash   cat > /tmp/probes/s47_errorclass.py <<'PY' import struct from struct import error as E  try:     raise struct.
         62s bash   cat > /tmp/probes/s47_bool.py <<'PY' import struct  print("b", struct.pack("<b", True), struct.pack("<b", Fals

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: `job-stdlib47` (`5270977`)

**What the change really does:** adds `AIL_CURRENT/python/pkg-v12/structlib.py`, called from `ail_syntax.python_surface`, rewriting literal-format `struct.pack` / `unpack` / `calcsize` / `error` into bytes, `int.to_bytes/from_bytes`, and helper functions, plus a new test module and manifest/devlog updates.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD; base = worktree at `work`):
- `a_ovf` — **DIFF on both builds**: 8-byte `q`/`Q` overflow raises `OverflowError` instead of `struct.error`.
- `c2_forms` — same stdout/status as CPython on both builds (`=`, `!`, `<`, `?`, `c`, `s`, `p`, counts, `x` padding, bytearray inputs, truncation, bad `c`, long buffer).
- `d_none`, `d2_str` — compiled C byte-identical to the `work` base via `--debug-dir`.
- `e_dyn` — named compile-time refusal (dynamic format), acceptable.
- `b_fromerr` — `from struct import error` is *refused* (`struct.error used here is not built`), even though `from struct import pack` works; named refusal, so not blocking, but it contradicts the broad `struct.error` claim.

**Tests:** `test_ail_stdlib47` and `test_ail_safetynet` pass (`2 modules, 0 failed`); `tools/update_manifest.py --check` passes.

**Report claims:** built prefixes/fields, counts, inter-field whitespace, named refusals, test registration, manifest — verified. “Range errors and messages match CPython” — **false** for `q`/`Q` (8-byte). Import count (6) and the full 30-probe list — unverified.

**Pre-existing:** none observed.

**Unverified:** import-count method; probe claims for forms I did not re-run; wider suite (not run by design).

### Defect
1. `structlib.py:170-182` omits the 8-byte range checks (signed branch returns `[]`; unsigned branch only checks `< 0`), so out-of-range `q`/`Q` values reach `int.to_bytes` and raise the wrong exception.
   Probe `/tmp/rprobes/a_ovf.py`:
   ```python
   import struct
   for f, v in [("q", 9223372036854775808), ("q", -9223372036854775809),
                ("Q", 18446744073709551616), ("Q", -1)]:
       try: print(f, v, struct.pack(">" + f, v).hex())
       except struct.error as e: print(f, v, "struct.error", e)
       except Exception as e: print(f, v, type(e).__name__, e)
   ```
   Expected: `q 9223372036854775808 struct.error 'q' format requires -9223372036854775808 <= number <= 9223372036854775807` (same for the other `q` case; `Q` variants use `0 <= number <= 18446744073709551615`).
   Actual (both builds): `q 9223372036854775808 OverflowError int too big to convert`, likewise for `qmin-1` and `Qmax+1`. `Q` with `-1`, and `i`/`B` bounds, match.

VERDICT: FIX
1. `struct.pack` with format `q`/`Q` and an out-of-range 8-byte value raises `OverflowError: int too big to convert` where CPython raises `struct.error` with the format's range message (`/tmp/rprobes/a_ovf.py`, lines `qmax+1`, `qmin-1`, `Qmax+1`).
[cost $0.0193, opencode tokens {"total": 803119, "input": 51628, "output": 5020, "reasoning": 10599, "cache.write": 0, "cache.read": 735872}]
    tool time: bash 5.2 min, read 0.0 min
        175s bash   cd AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_stdlib47 test_ail_safetynet 2>&1 | tail -30
         53s bash   cat > /tmp/rprobes/b_fromerr.py <<'PY' import struct from struct import error  try:     raise error("boom") ex
         26s bash   cat > /tmp/rprobes/c2_forms.py <<'PY' import struct  class Box:     def __init__(self, v):         self.v = v 
         25s bash   sed -i 's/print(struct.pack(">1p", b"").hex(), struct.unpack(">1p", b"\\x07").hex())/print(struct.pack(">1p", 
         24s bash   sed -i 's/b"\\x00xyz"/b"\\x00xyzw"/' /tmp/rprobes/c2_forms.py; grep -n '4s' /tmp/rprobes/c2_forms.py; cd /tmp 
          6s bash   cat > /tmp/rprobes/d2_str.py <<'PY' label: str = "struct" print(label, len(label)) PY rm -rf /tmp/dbg_head /tm
          3s bash   cd /tmp && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/a_ovf.py /tmp/base47 2>&1 | tail -12; date
          0s bash   grep -rn "debug-dir" AIL_CURRENT/*.py | head -5; git worktree add /tmp/base47 work 2>&1 | tail -3; date

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed the 8-byte `q`/`Q` range checks in `AIL_CURRENT/python/pkg-v12/structlib.py`; out-of-range values now raise `struct.error` with CPython 3.12's exact text.

Probes (both builds, all match CPython):
- `p1_qrange` — `q`/`Q` min, max, ±1 past, huge, both endiannesses
- `p2_smallrange` — `b B h H i I l L` bounds/over/under
- `p3_paths` — values via argument, list item, attribute, dict value
- `p4_types` — bool, float, str, None, bytes for 8-byte fields
- `p5_layout` — calcsize, counts, padding, endianness, unpack round trips, bytearray

Committed `04233c0`. Required tests on final commit: `test_ail_stdlib47`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes. The `from struct import error` named refusal was left unchanged (non-blocking per review).
[cost $0.0095, opencode tokens {"total": 354530, "input": 24200, "output": 5241, "reasoning": 2913, "cache.write": 0, "cache.read": 322176}]
    tool time: bash 8.5 min, edit 0.0 min
        423s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_stdlib47 te
         61s bash   cat > /tmp/probes/p1_qrange.py <<'PY' import struct   def qb(v):     try:         return struct.pack(">q", v).
         27s bash   cd /tmp && for p in /tmp/probes/p1_qrange.py /tmp/probes/p2_smallrange.py /tmp/probes/p3_paths.py /tmp/probes/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/DEVLOG.md AIL_CURRENT/MANIFEST.json AIL_CURRENT/pyth
          0s bash   git log --oneline -10 && git status --short && pwd
          0s bash   sed -n '1,240p' AIL_CURRENT/python/pkg-v12/structlib.py
          0s bash   python3 - <<'PY' import struct,sys print(sys.version) for f,v in [("q",9223372036854775808),("q",-922337203685

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: job-stdlib47 (struct support)

**What the change actually does.** `work..HEAD` adds a whole `struct` library batch (`AIL_CURRENT/python/pkg-v12/structlib.py`, wired into `ail_syntax.python_surface`) that lowers literal-format `struct.pack/unpack/calcsize/error` onto bytes and `int.to_bytes/from_bytes`, plus a follow-up commit range-checking `q`/`Q`. The worker report describes only the `q`/`Q` range fix, not the module addition.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, both builds unless noted):

| probe | covers | result |
|---|---|---|
| p1_qrange | q/Q min/max/±1/both endians/`=` | matches CPython |
| p16_smallrange | b B h H i I l L bounds±1 | matches |
| p4_paths | value via argument, list item, attribute, dict | matches |
| p5_types | float/str/None/bytes/bool into int fields; `?` | matches |
| p6_layout | calcsize, empty, 0i/0x/0c, pads, counts, round trips | matches |
| p7_alias_error | aliases, `from` imports, `struct.error` raise/catch | matches |
| p9_mutation | bytearray mutated after pack/unpack | matches (copies) |
| p11_fromerr | `from struct import error` | named refusal |
| p12_sideeffect | argument evaluation order | matches |
| p10/p13 | no `struct` (one contains "structure") | C identical to base via `--debug-dir` |
| **p2_pwidth / p14_pmin** | `p` counts ≥257 with value >255 bytes | **FAILS** |

**Claims.** q/Q range text: verified (p1). Worker probe families p1–p4 equivalents: verified. "p5_layout … every built field / truncation" is **false** for `p` counts ≥257. Commit `04233c0`, `test_ail_stdlib47`+`test_ail_safetynet` (2 modules, 0 failed), and `update_manifest.py --check`: verified. "`from struct import error` refusal left unchanged": verified (p11).

**Pre-existing:** none found; the `p` failure is introduced (base refuses all of `struct`).

**Unverified:** did not rerun the worker's exact `/tmp/probes/*`; did not run `test_ail_files`/`test_ail_corpus_findings3`; `memoryview` semantics (the language has no `memoryview`).

**Defect**

1. `AIL_CURRENT/python/pkg-v12/structlib.py:62` `_ail_struct_pascal` computes `n = min(len(v), width-1)` then `n.to_bytes(1, "big")`. For `p` counts ≥257 with a value longer than 255 bytes, `n` exceeds 255 and raises `OverflowError`; CPython 3.12 packs the length byte as `n & 0xff` (`\xff`) and the truncated field.
   Probe `/tmp/rprobes/p14_pmin.py`:
   ```python
   import struct
   print(struct.pack(">257p", b"a" * 256).hex())
   ```
   Expected: `ff` followed by `61`×256 (257-byte result, exit 0).
   Actual (both builds): no stdout, stderr `OverflowError: int too big to convert`, exit 1. Same for `>300p` with 299/305-byte values in `/tmp/rprobes/p2_pwidth.py`.

VERDICT: FIX
1. `struct.pack` with a `p` count ≥257 and argument length >255 raises `OverflowError` instead of packing the length byte modulo 256 like CPython (probe `/tmp/rprobes/p14_pmin.py`).
[cost $0.0275, opencode tokens {"total": 1205917, "input": 62787, "output": 9776, "reasoning": 14762, "cache.write": 0, "cache.read": 1118592}]
    tool time: bash 5.9 min
        134s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         45s bash   date; cd /tmp && for p in p5_types p4_paths p6_layout; do echo "===== $p ====="; timeout 400 bash ~/tools/cmp.
         40s bash   date; cd /tmp && for p in p7_alias_error p8_zerofields p9_mutation; do echo "===== $p ====="; timeout 400 bash
         33s bash   date; cd /tmp && for p in p2_pwidth p1_qrange; do echo "===== $p ====="; timeout 400 bash ~/tools/cmp.sh /tmp/
         19s bash   cat > /tmp/rprobes/p16_smallrange.py <<'PY' import struct def chk(tag, v):     try:         print(tag, struct.
         19s bash   cat > /tmp/rprobes/p15_badtypes.py <<'PY' import struct try:     print(struct.pack(">4s", "abcd").hex()) excep
         15s bash   cd /tmp && for p in p2_pwidth p1_qrange p5_types; do echo "===== $p ====="; timeout 400 bash ~/tools/cmp.sh /t
         14s bash   date; cd /tmp && for p in p11_fromerr p12_sideeffect; do echo "===== $p ====="; timeout 400 bash ~/tools/cmp.s

FINAL VERDICT: FIX  2026-10-29T15:22:45Z
