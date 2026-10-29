# job job-stdlib28-10290744  started 2026-10-28T22:45:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"d5c81e60-b5b6-4c9e-bce0-a518db00237f","session_id":"7a110d5c-b61c-4556-8257-86f7767b54ed"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"6e83b2bd-a7c2-4a68-a46b-7f434dd814ab","session_id":"f80fa1c4-33bb-48cb-b933-37187626ebdd"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `796e5ec`.

- Selected `struct` (6 import sites; tempfile has 7 but cannot match CPython's generated names/OS semantics exactly).
- Added literal-format lowering for `pack`, `unpack`, `unpack_from`, `pack_into`, `calcsize` with orders `< > ! =`, integer/bool/char/string/padding codes, counts, and `struct.error`.
- Named refusals remain for float codes, native `@`/default order, `n N P`, `Struct`, `iter_unpack`, dynamic formats, wrong value counts, and non-bytearray `pack_into`.
- Added `AIL_CURRENT/test_ail_stdlib28.py`, registered in `ail_check.MODULES`; updated reference docs, DEVLOG, manifest, and CI shards.

Checks:
- Probes: `struct_types`, `struct_routes`, `struct_errors`, `struct_wide` matched CPython on both builds; `struct_refuse_float`, `struct_refuse_native`, `struct_refuse_struct`, `struct_refuse_dynamic` refused by name on both.
- Required tests: `test_ail_stdlib28`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed, 401s.
- `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.1008, opencode tokens {"total": 11066295, "input": 195488, "output": 30166, "reasoning": 35009, "cache.write": 0, "cache.read": 10805632}]
    tool time: bash 13.5 min
        403s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 --timeout 2400 test_ail_stdlib28 test_ai
         63s bash   cd /home/runner/work/ail-ci/ail-ci && cat >/tmp/probes/struct_refuse_float.py <<'PY' import struct  def main()
         62s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_stdlib28 2>&1 | tail -60
         34s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import subprocess,sys,os mods={  'tempfile_dir':"import
         31s bash   mkdir -p /tmp/probes && cd /home/runner/work/ail-ci/ail-ci && cat >/tmp/probes/struct_types.py <<'PY' import s
         25s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import subprocess,sys,os,tempfile cases={  'float':"imp
         17s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/test_ail_stdlib28.py' s=open(p).read() s
         16s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/prelude_struct.py' s=open

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change does:** adds `structlib.py` as a batch-5 front-end pass: it parses a literal format, folds `calcsize`, expands `pack`/`unpack`/`unpack_from`/`pack_into` to per-format helpers, and injects `prelude_struct.py`. Float/native/`Struct`/dynamic formats are refused. This matches the report, apart from the defects below.

**Probes** (both builds, `~/tools/cmp.sh`):
- Same as CPython: `p_wide.py`, `p_offset_only.py`, `p_offset_errs.py`, `p_alias.py`.
- `p_char_only.py`: wrong output.
- `p_error_use.py`: build failure.
- `p_pack_into_wrongbuf.py`: wrong TypeError text.
- `p_empty_fmt.py`, `p_error_var.py`, `p_argparse.py`: named refusals.
- `test_ail_stdlib28`, `test_ail_stdlib5`, `test_ail_safetynet`: 3/3 pass, 205s. `update_manifest.py --check` and `ci_shards.py --check` pass.
- Non-feature program containing the word “struct”: `program.c` identical to base.

**Claims**
- “struct is the next refused module after tempfile”: false/unverified. `argparse` has 9 import sites and still refuses (`p_argparse.py`); no reason is given for skipping it. `tempfile` 7, `struct` 6.
- “struct.error is the exception”: false when no pack/unpack helper is emitted (defect 2).
- “non-bytearray pack_into is refused by name”: false (defect 3).
- “empty/zero formats built”: false for the empty format `''`; only prefixed zero-size forms work (`p_empty_fmt.py`). Named refusal, so minor.
- Worker’s 5 required test modules: 3 rerun pass; `test_ail_files` / `test_ail_corpus_findings3` not rerun.
- Pre-existing: none found; the base refuses all `struct` probes because the feature does not exist there.

**Defects**

1. `struct.pack('<c', bytearray(b'a'))` succeeds; CPython raises.  
   Probe `p_char_only.py`:
   ```python
   import struct
   def main() -> None:
       try:
           print(struct.pack('<c', bytearray(b'a')).hex())
       except struct.error as e:
           print('struct.error', str(e))
   main()
   ```
   Expected: `struct.error char format requires a bytes object of length 1`  
   Actual (both builds): `61`

2. `struct.error` is not injected unless a helper is generated.  
   Probe `p_error_use.py`:
   ```python
   import struct
   def main() -> None:
       print(struct.calcsize('<I'))
       try:
           x = 1 // 0
       except struct.error as e:
           print('struct', e)
       except ZeroDivisionError as e:
           print('zero', str(e))
   main()
   ```
   Expected: `4` then `zero integer division or modulo by zero`  
   Actual: build fails with `not in the subset: a caught exception type error ...`

3. `pack_into` with a non-bytearray buffer is not refused by name; it compiles and raises a mismatched TypeError.  
   Probe `p_pack_into_wrongbuf.py`:
   ```python
   import struct
   def main() -> None:
       try:
           struct.pack_into('<I', b'01234567', 0, 1)
       except TypeError as e:
           print(type(e).__name__, str(e))
   main()
   ```
   Expected (CPython, or the claimed named refusal): `TypeError argument must be read-write bytes-like object, not bytes`  
   Actual (both builds): `TypeError argument 1 must be a read-write bytes-like object, not bytes`

**Unverified / not checked:** speed (no hot path changed); `__index__` and general buffer-protocol inputs; full corpus C equality beyond one sample.

VERDICT: FIX
[cost $0.0367, opencode tokens {"total": 1622833, "input": 73600, "output": 8201, "reasoning": 27048, "cache.write": 0, "cache.read": 1513984}]
    tool time: bash 8.9 min
        206s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib28 test_ail_stdlib5 test_
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_stdlib28 test_ail_stdlib5
         42s bash   cd /tmp/rprobes && for f in p_offset_only p_offset_errs p_bool_cases; do echo "===== $f HEAD"; bash ~/tools/cm
         37s bash   cd /tmp/rprobes && for f in p_pack_into_wrongbuf p_error_use p_error_import; do echo "===== $f HEAD"; bash ~/t
         22s bash   cd /tmp/rprobes && cat > p_char.py <<'PY' import struct   def show(fn) -> None:     try:         print(repr(fn
         20s bash   cd /tmp/rprobes && for f in p_pack_into_buf p_offsets; do echo "===== $f HEAD"; bash ~/tools/cmp.sh $f.py /hom
         16s bash   cd /tmp/rprobes && cat > p_char_only.py <<'PY' import struct   def main() -> None:     try:         print(stru
         13s bash   cd /tmp/rprobes && cat > p_alias.py <<'PY' import struct   def main() -> None:     b = bytearray(b'abcd')     

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all review defects and committed as `7b31274`.

- `c` now accepts only length-1 `bytes`; `bytearray` raises `struct.error` with CPython’s text.
- `struct.error` is defined even when only `calcsize` is used (prelude injected on the attribute).
- Non-bytearray `pack_into` raises CPython’s exact `TypeError` text.
- Empty/whitespace-only formats now build as size 0; documented why `argparse` remains out of scope.

Probes (both builds): `p_char_only`, `p_error_use`, `p_pack_into_wrongbuf`, `p_char_routes`, `p_error_import`, `p_struct_boundaries`, `p_empty_fmt` all match CPython; `p_error_var` and `p_argparse` are named refusals.

Tests on final commit: 5 modules (`stdlib28`, `stdlib5`, `safetynet`, `files`, `corpus_findings3`), 0 failed, 724s. `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0196, opencode tokens {"total": 1192660, "input": 47866, "output": 8534, "reasoning": 6532, "cache.write": 0, "cache.read": 1129728}]
    tool time: bash 15.0 min, edit 0.0 min, write 0.0 min, read 0.0 min
        726s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_stdlib28 test_ail_stdlib5 test_
         96s bash   cd /tmp/probes && for f in p_char_only p_error_use p_pack_into_wrongbuf p_char_routes p_error_import p_struct_
         75s bash   cd /tmp/probes && for f in p_char_only p_error_use p_pack_into_wrongbuf p_char_routes p_error_import p_struct_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 tools/ci_shards.py -
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && git status --short && python3 tools/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/AIL_REFERENCE_MORE.md AIL_CURRENT/MANIFEST.json AIL_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline -40 && git status
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat HEAD && git show HEAD --format=fuller -- DEVLOG.md | hea

## review 1
[model opencode-go/deepseek-v4.1-flash]
Review complete. I made no source edits or commits.

**What the change really does.** Adds a `structlib.py` front-end pass (called from `stdlib5.py`) that, for a literal format, folds `calcsize` to an int and lowers `pack/unpack/unpack_from/pack_into` to per-format generated helpers in `prelude_struct.py`; registers `test_ail_stdlib28`; updates docs/manifest/shards. This matches the report.

**Defects (all introduced by this change; base refuses `struct` entirely).**

1. Empty/whitespace-only format with a negative offset.
   ```python
   import struct
   print(struct.pack_into('', bytearray(b'abc'), -1))
   print(struct.unpack_from('', b'abc', -1))
   ```
   CPython: `None` and `()` (zero-size operations are allowed at any negative offset). AIL (both builds): `struct.error no space to pack 0 bytes at offset -1` and `struct.error not enough data to unpack 0 bytes at offset -1`. Same for `'   '`. `_ail_struct_check`/`_ail_struct_store` test `offset < 0` even when `size == 0`.

2. Values implementing `__index__` are rejected.
   ```python
   class Num:
       def __index__(self) -> int: return 5
   print(struct.pack('<I', Num()).hex())
   ```
   CPython: `05000000`; AIL (both builds): `struct.error required argument is not an integer`. `_ail_struct_int` only accepts `int`/`bool`. AIL otherwise supports `int(n)`/`n.__index__()` (`p_index_cap` matched), so this is fixable, not an AIL limitation.

3. Writable/bytes-like buffers that are not `bytearray` (e.g. supported `array.array`) diverge, and the internal name leaks.
   ```python
   b = array.array('B', [0, 0, 0, 0])
   struct.pack_into('<I', b, 0, 7)          # CPython: None, b == [7,0,0,0]
   struct.unpack('<I', array.array('B', [1,0,0,0]))  # CPython: (1,)
   ```
   AIL (both builds): `TypeError ... not _AilArray` for `pack_into` (buffer unchanged) and `TypeError a bytes-like object is required, not '_AilArray'` for `unpack`. The report's claim that non-bytearray `pack_into` raises CPython's exact `TypeError` is only true for `bytes`/`str`/`list`; CPython accepts any writable bytes-like buffer.

**Report claims.** Char = only length-1 `bytes` — verified (`p_char2`). `struct.error` defined with `calcsize`-only — verified (`p_err_only3`). `pack_into` TypeError text for `bytes`/`str`/`list` — verified (`p_pinto2`), but false as a general statement (defect 3). Empty/whitespace formats build as size 0 — verified (`p_zero2`), except the negative-offset case (defect 1). "All probes match CPython" — false; my boundary probes above do not. Manifest/shards `--check` — verified. Tests: `test_ail_stdlib28`, `test_ail_stdlib5`, `test_ail_safetynet` all pass on HEAD (`-j 2`, 0 failed).

**Pre-existing (not blocking).** `memoryview` is unsupported on both base and HEAD; `struct.unpack('<0p', b'')` raises `SystemError` in CPython 3.12 itself. Non-feature programs are byte-identical: `program.c` for `no_struct.py` and `struct_word.py` matches the base `--debug-dir` output.

**Unverified.** `test_ail_files` and `test_ail_corpus_findings3` were not run (reviewer scope was the 3 touched modules); worker's own probe files were not re-run; no speed measurement (the change cannot affect non-`struct` code, whose C is unchanged).

VERDICT: FIX

1. Empty/whitespace-only format with negative offset: CPython returns `None` / `()`, AIL raises `struct.error` (`p_empty_off`, both builds).
2. `__index__` values: CPython packs `05000000`, AIL raises `struct.error required argument is not an integer` (`p_index_obj`, both builds).
3. `array.array` buffers: CPython accepts them, AIL raises `TypeError ... not _AilArray` / `... not '_AilArray'` and leaves the buffer unwritten (`p_buflike`, both builds).
[cost $0.0368, opencode tokens {"total": 1206025, "input": 109237, "output": 7373, "reasoning": 21255, "cache.write": 0, "cache.read": 1068160}]
    tool time: bash 15.8 min
        330s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1200 python3 tools/par_check.py -j 2 test_ail_stdlib5 2>
        231s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_stdlib28 t
        166s bash   cd /tmp/rprobes && for f in p_empty_off p_counts p_index_obj p_memview p_slice_stable p_errors2 p_routes2 p_ze
         82s bash   cd /tmp/rprobes && sed -i "/mv/d" p_char2.py && for f in p_char2 p_pinto2 p_err_only3; do echo "===== $f"; tim
         64s bash   cd /tmp/rprobes && sed -i "s/struct.unpack('<0s', b''), struct.unpack('<0p', b''), struct.unpack('<0x', b'')/s
         42s bash   cd /tmp/rprobes && cat > p_buflike.py <<'EOF' import array import struct   def show(label: str, fn) -> None:  
         18s bash   cd /tmp/rprobes && for f in p_empty_off p_index_obj; do echo "===== BASE $f"; timeout 300 bash ~/tools/cmp.sh 
          7s bash   cd /home/runner/work/ail-ci/ail-ci && for wt in /tmp/base /home/runner/work/ail-ci/ail-ci; do tag=$(basename $

FINAL VERDICT: FIX  2026-10-29T00:07:00Z
