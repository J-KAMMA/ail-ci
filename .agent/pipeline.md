# job job-stdlib48-10292234  started 2026-10-29T14:35:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"9ff1e915-6bde-4425-ade1-cf3fe25cca73","session_id":"3369676e-7394-4a05-b534-f81de724e712"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"6a78ca1e-84f1-4688-96d7-3b8b383aa58a","session_id":"fe4cc8e1-d16b-4c9a-85a0-d6b534278960"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Committed as `2f9441b` on `job-stdlib48-10292234` (not pushed).

**Support added:** `struct` for literal `<`, `>`, `!` formats with `x c b B ? h H i I l L q Q s p` (repeat counts, whitespace between codes). `calcsize`, `pack`, `unpack`, `unpack_from`. Everything else is a named compile-time refusal.

**Fixes found by self-check and applied:** float/string values for integer codes no longer silently truncate (now `ValueError`); `unpack` now requires the exact buffer length while `unpack_from` allows trailing bytes; zero-count `p` unpack is refused by name (CPython 3.12 raises `SystemError`).

**Probes (both builds via `cmp.sh`):** `s1`, `struct_int`, `struct_bytes`, `struct_values`, `struct_codes`, `struct_imports`, `struct_space`, `bool_int`, `bytearray_fields`, `q_max`, `offsets`, `zero_counts`, `unpack_length`, `pascal_lit` match CPython. `refuse_float`, `refuse_native`, `refuse_native_code`, `refuse_nonliteral`, `refuse_struct`, `refuse_pack_into`, `refuse_empty`, `refuse_space`, `refuse_zero_p` are refused by name. Invalid values/buffers stop on both builds (`str_float`, `str_num`, `neg_unsigned`).

**Tests:** `test_ail_stdlib48` 6/6, `test_ail_stdlib_batch4` 19/19, `test_ail_source_check` 33/33, `test_ail_check` 7/7, `test_ail_corpus_findings3` 2/2, `test_ail_files` 18/18 (1 skip), `test_ail_safetynet` 5/5. `tools/update_manifest.py --check` passes.
[cost $0.0232, opencode tokens {"total": 1334439, "input": 55472, "output": 7418, "reasoning": 11133, "cache.write": 0, "cache.read": 1260416}]
    tool time: bash 30.7 min
        896s bash   cd AIL_CURRENT && for t in test_ail_stdlib48 test_ail_stdlib_batch4 test_ail_source_check test_ail_check test_
        253s bash   cat > /tmp/probes2/refuse_zero_p.py <<'EOF' import struct print(struct.unpack('<0p', b'')) EOF for p in s1 str
        228s bash   cat > /tmp/probes2/unpack_length.py <<'EOF' import struct print(struct.unpack('<3s2p', b'abcxy')) print(struct
        221s bash   for p in s1 struct_int struct_bytes struct_values struct_codes struct_imports struct_space refuse_float refuse
        199s bash   mkdir -p /tmp/probes2; cat > /tmp/probes2/str_float.py <<'EOF' import struct print(struct.pack('<i', 3.9).hex(
         36s bash   cd AIL_CURRENT && timeout 1500 python3 test_ail_stdlib48.py 2>&1 | tail -60
         10s bash   cd AIL_CURRENT && timeout 1500 python3 test_ail_stdlib48.py 2>&1 | tail -40
          0s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('DEVLOG.md') s=p.read_text(

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change does (one line):** adds `structlib.py` (plus `prelude_struct.py`) that lowers literal `<`/`>`/`!` formats for `calcsize`/`pack`/`unpack`/`unpack_from` over `x c b B ? h H i I l L q Q s p`, folds `calcsize`, rewrites `pack` to a `b''.join`, generates one fixed-type unpack helper per format, and refuses the rest by name; also narrows `python_wording` for `struct.`.

**Claims checked**
- `calcsize`/`pack`/`unpack`/`unpack_from` data paths: verified (matrix of 19 formats incl. padding, `s`/`p`, `0s`, `x`, big/little/`!`, boundaries).
- Float/string int values and short/long buffers stop: verified.
- `unpack` exact length vs `unpack_from` trailing bytes: verified.
- Zero-count `p` unpack refused: verified (build fails; named note present).
- Refusals name the use: verified for float/native/zero-p/empty, though the headline is the generic `not in the subset: struct.pack ...` and the specific reason is in the `note:` line.
- Int64 `Q` limit: only true on the typed path (`AIL_NO_GENERAL=1` stops with `integer overflow`); on the general/default builds `Q` = 2^64−1 prints and computes correctly. Declared row is typed-path-specific.
- Aliases (`from struct import pack as pk`, `import struct as st`) and import-only programs: verified.
- Tests: `test_ail_stdlib48`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_source_check`, `test_ail_stdlib_batch4`, `test_ail_check` all pass; `update_manifest.py --check` passes.

**Pre-existing:** none for `struct` (base refuses all `struct` calls); both defects below are new.

**Unverified:** instruction counts (new feature, no hot path); the worker's `/tmp/probes*` set itself (not present).

## Defects

1. **Starred `pack` arguments are evaluated repeatedly.** `_pack` deep-copies the starred expression once for `len(...)` and again for every field, so side effects run N+1 times.
   Probe `/tmp/rprobes/star_call.py`:
   ```python
   import struct
   def vals():
       print('called')
       return [1, 2]
   print(struct.pack('<2i', *vals()).hex())
   ```
   Expected (CPython):
   ```
   called
   0100000002000000
   ```
   Actual (general, default and typed builds):
   ```
   called
   called
   called
   0100000002000000
   ```
   Same for `*[f(), g()]` (`/tmp/rprobes/star_list_side.py`): `f`/`g` each print once expected, twice extra in AIL.

2. **`unpack`/`unpack_from` accept non-buffer sequences as the buffer.** The generated helper indexes the value directly, so a list of ints is silently decoded; CPython raises `TypeError`.
   Probe `/tmp/rprobes/unpack_type.py`:
   ```python
   import struct
   print(struct.unpack('<i', [1, 2, 3, 4]))
   ```
   Expected (CPython): exit 1, no stdout, `TypeError: a bytes-like object is required, not 'list'`.
   Actual (general and default builds): exit 0, prints `(67305985,)`. Also `/tmp/rprobes/unpack_list_c.py` prints `41`, `True`, `6869` for `c`/`?`/`2s` instead of raising. The typed path does refuse this at compile time, so the hole is the general/default builds.

VERDICT: FIX
[cost $0.0243, opencode tokens {"total": 824768, "input": 55963, "output": 6295, "reasoning": 16526, "cache.write": 0, "cache.read": 745984}]
    tool time: bash 20.7 min
        400s bash   cd /home/runner/work/_temp/w2; date; cd AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ai
        391s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_stdlib_ba
        122s bash   cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/*.py; do echo "===== $p"; timeout 300 bash ~/tools/cmp.sh
         57s bash   cat > /tmp/rprobes/mutation.py <<'EOF' import struct ba = bytearray(b'abcd') s, = struct.unpack('<4s', ba) ba[
         53s bash   cat > /tmp/rprobes/unpack_list_c.py <<'EOF' import struct print(struct.unpack('<c', [65])[0].hex()) print(stru
         41s bash   cat > /tmp/rprobes/star_gen.py <<'EOF' import struct print(struct.pack('<2i', *[x * 2 for x in (1, 2)]).hex())
         29s bash   cat > /tmp/rprobes/import_only.py <<'EOF' import struct print('hi') EOF cat > /tmp/rprobes/alias.py <<'EOF' fr
         25s bash   python3 - <<'EOF' cases = [  ("<i",[-5]),(">i",[123456]),("<I",[4294967295]),("<h",[-32768]),(">H",[65535]),  

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed on `job-stdlib48-10292234` (final commit `25943c5`).

- Starred `struct.pack` now evaluates its sequence once: literal lists/tuples index elements directly; names/constants keep direct indexing; other expressions use one generated pack helper.
- `unpack`/`unpack_from` now validate the buffer on general/default builds and raise CPython’s `TypeError` instead of decoding lists. The typed path still refuses non-buffers at compile time.

Probes (`/tmp/probes/defects`, 17 programs): all match CPython on general/default builds for stdout and exit status, including `star_call`, `star_list_side`, `star_tuple_side`, `star_gen`, `star_gen_range`, `star_variable`, `star_bytes_pack`, `star_bytes`, `star_tuple_call`, `star_mixed_literal`, `star_empty`, `unpack_bytearray`, `unpack_list`, `unpack_list_c`, `unpack_str`, `unpack_from_list`, `star_bytes_unpack`. Typed build: 6 match; 9 refused by name, including the documented tuple-returning starred call and pre-existing typed limits (bytearray buffer, two consecutive `s` fields, generator expressions).

Tests on final commit: `test_ail_stdlib48` (7 tests), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_source_check`, `test_ail_check` — 6 modules, 0 failed. `tools/update_manifest.py --check` passes.
[cost $0.0701, opencode tokens {"total": 7207829, "input": 106381, "output": 19814, "reasoning": 35234, "cache.write": 0, "cache.read": 7046400}]
    tool time: bash 35.1 min
        420s bash   cd /tmp/probes/defects && for p in *.py; do out=$(bash ~/tools/cmp.sh "/tmp/probes/defects/$p" /home/runner/wo
        370s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_stdlib48
        367s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_stdlib48
        315s bash   cd /tmp/probes/defects && cat > star_gen_range.py <<'EOF' import struct  print(struct.pack('<2i', *[x * 2 for 
        161s bash   mkdir -p /tmp/probes/defects && cd /tmp/probes/defects && cat > star_call.py <<'EOF' import struct   def vals(
         96s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/pkg-v1
         83s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
         27s bash   cd /tmp/probes/defects && for p in star_call.py star_list_side.py star_tuple_side.py star_gen_range.py star_va

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change really does:** adds `struct.calcsize/pack/unpack/unpack_from` lowering for literal `< > !` formats (`x c b B ? h H i I l L q Q s p`), with `calcsize` folded, `pack` emitted as a byte join or a generated helper, generated unpack helpers, a general-path buffer `TypeError` check, and named refusals for the rest. It also narrows `python_wording` so `struct.` is not rewritten to `class.`.

### Defects

1. **Starred `pack` crashes on non-indexable/sizeless iterables instead of matching CPython or refusing by name.**
   `_pack` only wraps `ListComp`/`GeneratorExp`/`Subscript` (`structlib.py:202-203`); a call returning a generator, or a set literal, reaches the helper, which calls `len()`/subscript. On general and default builds this compiles and exits 1 with no output.
   Probe `/tmp/rprobes/p8_gen_call.py`:
   ```python
   import struct
   def gen():
       for x in (1, 2):
           yield x
   print(struct.pack('<2i', *gen()).hex())
   ```
   Expected (CPython): `0100000002000000`, exit 0. Actual: no stdout, exit 1, `TypeError: object of type 'instance' has no len()`.
   Also `/tmp/rprobes/p9_set_star.py` (`*{5}`): expected `05000000`; actual exit 1, `TypeError: 'set' object is not subscriptable`. Base refuses these by name (`a starred (*args) call argument`), so the regression is caused by this change. The typed build does refuse them.

2. **`pack` of a `p` field with count >= 257 raises `ValueError` where CPython returns bytes.**
   `_ail_struct_pack_p` builds the length prefix with `bytes([len(data)])` (`prelude_struct.py:26-33`); when `count-1 > 255` and the value is long, CPython caps the prefix at 255 and still emits the payload, while this code crashes.
   Probe `/tmp/rprobes/p15_p_wide.py`:
   ```python
   import struct
   print(struct.pack('<257p', b'y' * 256).hex())
   ```
   Expected (CPython): 257 bytes (`ff` + 256 `y`s), exit 0. Actual: no stdout, exit 1, `ValueError: bytes must be in range(0, 256)`. Same for `<300p`. Base refuses `struct` by name, so this is new. (`unpack` of the same format is fine.)

### Pre-existing
- Base `/tmp/base` refuses every `struct` program by name (module unsupported); p8/p9 refusals there are acceptable.
- A non-`struct` program containing the word “struct” produces byte-identical generated C on base and HEAD (`--debug-dir` diff only temp paths), so unaffected programs are unchanged.

### Report claims
- “Starred `pack` evaluates its sequence once” — verified for literal lists/tuples, names, list slices, comprehensions and list-returning calls (`/tmp/rprobes/p7_star_once.py`), but the helper assumption is wrong for generator calls/sets (defect 1).
- “`unpack`/`unpack_from` reject non-buffers with CPython’s `TypeError`; typed path refuses” — verified (`p13_nonbuffer.py`, `p14_unpack_from_list.py`; typed compile refusal observed).
- “17 probes all match” — false as a general claim; the probes above differ.
- “test_ail_stdlib48 + safetynet pass, manifest `--check` passes” — verified (`test_ail_stdlib48`, `test_ail_safetynet`, 0 failed; `update_manifest.py --check` rc 0). The other four test modules were not rerun.
- DIFFERENCES row 1 (`Q` > int64): verified on the typed build (`integer overflow`); general/default prints the exact value, so the wording is only accurate for the typed path.

### Unverified
- Worker’s other 4 test modules; typed-build status of all 17 worker probes; speed (change is not on a hot path).

VERDICT: FIX
1. Starred `pack` of a generator-returning call or set literal compiles then crashes (`p8_gen_call.py`, `p9_set_star.py`); match CPython by materialising the sequence once, or refuse by name.
2. `struct.pack('<257p', b'y'*256)` and larger `p` counts raise `ValueError: bytes must be in range(0, 256)` (`p15_p_wide.py`); emit CPython’s 255-capped length prefix (or refuse such counts by name).
[cost $0.0344, opencode tokens {"total": 1570970, "input": 75711, "output": 8495, "reasoning": 22572, "cache.write": 0, "cache.read": 1464192}]
    tool time: bash 8.1 min
        128s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_
         91s bash   cd /tmp/rprobes && cat > p10_mixed_call.py <<'EOF' import struct  def vals():     return [1, b'ab']  print(str
         54s bash   cd /tmp/rprobes && cat > p13_nonbuffer.py <<'EOF' import struct print(struct.unpack('<i', [1, 2, 3, 4])) EOF c
         44s bash   cd /tmp/rprobes && cat > p3_offsets.py <<'EOF' import struct  data = b'zz' + struct.pack('<i', 123456) + b'qq'
         43s bash   cd /tmp/rprobes && cat > p6b_widths.py <<'EOF' import struct  print(struct.calcsize('<b'), struct.calcsize('<B
         39s bash   cd /tmp/rprobes && date && for p in p2_alias.py p3_offsets.py; do echo "=== $p"; bash ~/tools/cmp.sh /tmp/rpro
         22s bash   cd /tmp/rprobes && date && echo "=== p9"; bash ~/tools/cmp.sh /tmp/rprobes/p9_set_star.py /home/runner/work/_t
         19s bash   cd /tmp/rprobes && cat > p15_p_wide.py <<'EOF' import struct  print(struct.pack('<257p', b'y' * 256).hex()) pr

FINAL VERDICT: FIX  2026-10-29T17:11:59Z
