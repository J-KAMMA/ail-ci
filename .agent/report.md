# job job-stdlib26-10290642  started 2026-10-28T21:43:57Z  worker=oc reviewer=oc (GitHub)
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
Failed to fetch model list: catalog init completed without available models
DeepSeek-Flash -> fetch_requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your authentication has expired. Please sign in again."],"error_code":105,"fast_mode_state":"off","uuid":"a2a79f38-1e59-4f26-994a-fcdbae43d391","session_id":"2cb4f5c2-3ddf-44fc-bc00-7f569cae0ecf"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `70afafc` on `job-stdlib26-10290642` (not pushed).

**Module:** `struct` (6 refused imports, plus corpus `t475.py`). Added `structlib.py` lowering, bundled `stdlib/struct.py` + C glue, and `test_ail_stdlib26.py` registered in `ail_check.MODULES`.

**Supported:** literal `pack` / `calcsize` / tuple-assignment `unpack` / `unpack_from`; codes `x c b B ? h H i I l L q Q e f d s p P`; `@ = < > !`, native alignment, zero repeats, exact unpack size, negative offsets, bytes-like input, float/half overflow errors, `struct.error`. Computed formats, `Struct`, `pack_into`, `iter_unpack`, unpack-as-value and wrong arity/names are compile-time refusals naming the use.

**Probes** (`/tmp/probes/stdlib26c`, both `cmp.sh` builds):
- Match CPython: `ints`, `order`, `float`, `float_over`, `str`, `bool_pad`, `fixed_mixed`, `unpack_from_ok`, `unpack_error`, `pack_error`, `calc`, `routes`, `alias`, `bytearray`, `empty`, `field_route`.
- Refused by name: `computed`, `struct`, `pack_into`, `iter_unpack`, `unpack_value`, `bad`, `count`, `names`.
- Corpus `t475.py` matches on both builds for `4 0 1 255 65535`.

**Final-commit tests:** `test_ail_stdlib26` 2, `test_ail_modules` 66, `test_ail_zlib` 10, `test_ail_stdlib5` 10, `test_ail_files` 18 (1 skipped), `test_ail_corpus_findings3` 2, `test_ail_safetynet` 5 — all 0 failed.

`tools/update_manifest.py` and `--check` pass. DEVLOG entry added; DIFFERENCES row records the declared int64 limit for high-bit `Q`/`P` unpack values.
[cost $0.1433, opencode tokens {"total": 13860276, "input": 343887, "output": 44363, "reasoning": 41370, "cache.write": 0, "cache.read": 13430656}]
    tool time: bash 62.5 min, write 0.0 min, edit 0.0 min
        393s bash   (python3 -B test_ail_zlib.py > /tmp/t_zlib.log 2>&1; echo $? > /tmp/t_zlib.code) & (python3 -B test_ail_stdlib
        338s bash   (python3 -B test_ail_files.py > /tmp/t_files.log 2>&1; echo $? > /tmp/t_files.code) & (python3 -B test_ail_cor
        289s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/stdlib26c/*.py; do echo "===== $(basename $f) ====="; ba
        276s bash   cd /home/runner/work/_temp/w2 && python3 /tmp/probes/gen3.py && for f in /tmp/probes/stdlib26c/*.py; do echo "
        257s bash   cd /home/runner/work/_temp/w2 && python3 /tmp/probes/gen2.py && for f in /tmp/probes/stdlib26b/*.py; do echo "
        232s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 -B test_ail_modules.py > /tmp/t_modules.log 2>&1; echo $
        214s bash   cd /home/runner/work/_temp/w2 && python3 /tmp/probes/gen.py && for f in /tmp/probes/stdlib26/*.py; do echo "==
        212s bash   cd /home/runner/work/_temp/w2 && for f in /tmp/probes/stdlib26c/*.py; do echo "===== $(basename $f) ====="; ba

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review report

**What the change really does.** Adds a `struct` lowering pass (`AIL_CURRENT/python/pkg-v12/structlib.py`, wired into `ail_syntax.py:3424`) that rewrites literal-format `struct.pack` / `calcsize` / tuple-assignment `unpack` / `unpack_from` onto byte/int/list code, plus a bundled `stdlib/struct.py` with C glue for IEEE-754 bit conversions, `BUNDLED_NAMES[('struct','error')]`, a bundled stdlib pin, and a new 2-test module. This matches the report, except the report omits the packaging side.

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh ... $PWD`, both builds):
- Match CPython: `p1_p`, `p2_float` (e/f/d boundaries, inf/nan/-0.0, overflows), `p3_unpack` (all unpack/unpack_from sizes and negative/too-large offsets), `p4_native` (native alignment `@bqi @?q @cq @ld @bhq @ehl @xq @q x i @ 2h i @l0i @2q @d c`), `p7_routes` (data via arg, attribute, bytearray mutation after unpack), `p9_types` (int into `e/f/d`), `p12_zero` (empty/zero formats, 0s, 255/256-byte pascal).
- `p11_structword`: a program containing "struct" in identifiers produces byte-identical `program.c` on base vs HEAD (`--debug-dir`).
- Defect: `p8_pascal`, `p10_pascal` (below).

**Defects**

1. `struct.pack` with a Pascal-string count > 256 crashes. Probe `/tmp/rprobes/p10_pascal.py`:
   ```python
   p = struct.pack("<257p", b"c" * 257)
   print(len(p), p[0], p[1:4].hex(), p[-1])
   ```
   Expected (CPython): `257 255 636363 99`, exit 0. Actual: both builds exit 1, empty stdout, stderr `bytes must be in range(0, 256)`. Cause: `structlib.py:254-258` clamps `n` only to `count-1`, so for `count >= 257` the value appended as the length byte is 256+; CPython stores length `min(len,255)` but copies `min(len,count-1)` bytes. Same failure for `<300p`, `<1000p`.

2. The new bundled files were never added to `MANIFEST.json` `"sdk_files"`. `python/pkg-v12/structlib.py`, `stdlib/struct.py`, `stdlib/struct_glue.c`, `stdlib/struct_glue.h` are pinned in `sha256` but absent from `sdk_files` (only `stdlib/zlib*` are listed there). Since a declared `sdk_files` exports exactly that list, the exported SDK has no struct support: `find /tmp/sdkcheck -name '*struct*'` is empty, and compiling `/tmp/rprobes/p1_p.py` with the exported compiler dies with `ModuleNotFoundError: No module named 'structlib'`. The repository test `test_ail_sdk.SdkTests.test_sdk_files_cover_every_compiler_module_import` fails: `[('ail_syntax.py', 'structlib')] != []`. Expected: those four files in `sdk_files` and that test passing.

**Report claims.** Verified: supported-code list (except the `p` boundary above), zero repeats, exact unpack size, negative offsets/messages, float/half overflow, `struct.error`→`RuntimeError`, refusals, `update_manifest --check`, `test_ail_stdlib26` (2 tests, pass) and `test_ail_safetynet` (pass). False/omitted: `p`-string support is broken for count > 256; the packaging claim is incomplete — `--check` passes only because `update_manifest.py` does not add `sdk_files` membership.

Non-blocking limitations: pack `s`/`c` with `bytearray`/`memoryview` and `pack('<i', True)` are compile-time refusals (CPython accepts them); allowed as named refusals.

**Pre-existing:** none observed.

**Unverified:** `test_ail_modules`, `test_ail_zlib`, `test_ail_stdlib5`, `test_ail_files`, `test_ail_corpus_findings3`, and the claimed `t475.py` run (only the new module's embedded corpus test was exercised); no speed measurement (not a speed task).

VERDICT: FIX
1. `struct.pack("<257p", b"c"*257)` (and any Pascal count > 256): expected `257 255 636363 99`/exit 0, actual exit 1 with `bytes must be in range(0, 256)`.
2. Add `python/pkg-v12/structlib.py`, `stdlib/struct.py`, `stdlib/struct_glue.c`, `stdlib/struct_glue.h` to `MANIFEST.json` `"sdk_files"`; expected exported SDK compiles struct programs and `test_ail_sdk` passes, actual `ModuleNotFoundError: No module named 'structlib'` and the SDK test fails.
[cost $0.0642, opencode tokens {"total": 3824794, "input": 159562, "output": 18309, "reasoning": 30667, "cache.write": 0, "cache.read": 3616256}]
    tool time: bash 8.4 min
        181s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_s
         32s bash   cd /tmp/rprobes && cat > p4_native.py <<'EOF' import struct   def main() -> None:     p1 = struct.pack("@bqi",
         31s bash   cd /tmp/rprobes && python3 - <<'PY' s=open('p3_unpack.py').read() s=s.replace('        print("uf-neg5", str(er
         26s bash   cd /tmp/rprobes && cat > p7_routes.py <<'EOF' import struct   class Box:     def __init__(self, v: int, off: i
         26s bash   cd /tmp/rprobes && cat > p5c1.py <<'EOF' import struct   def main() -> None:     print("q-nan", struct.pack("<
         23s bash   cd /tmp/rprobes && python3 - <<'PY' s=open('p7_routes.py').read() s=s.replace('    print(i, struct.unpack("<I"
         23s bash   cd /home/runner/work/_temp/w2 && date; for p in p3_unpack p4_native; do echo "########## $p"; bash ~/tools/cmp
         20s bash   cd /home/runner/work/_temp/w2 && for p in p1_p p2_float; do echo "########## $p"; bash ~/tools/cmp.sh /tmp/rpr

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `7b39927`.

**Changes**
- `structlib.py`: Pascal length byte now `min(len, count-1, 255)` while data copies `min(len, count-1)` bytes. `<257p`/`<300p`/`<1000p` now match CPython.
- `MANIFEST.json`: added `python/pkg-v12/structlib.py`, `stdlib/struct.py`, `stdlib/struct_glue.c`, `stdlib/struct_glue.h` to `sdk_files`; pins refreshed.
- `test_ail_stdlib26.py`: added Pascal boundary regressions (255/256/257/300, `>`/`@`, short value in wide field).
- `DEVLOG.md`: dated review entry.

**Probes** (`bash ~/tools/cmp.sh`, both builds)
- `p_pascal` — boundaries 1/2/4/255/256/257/300/1000, `>` `@`, short data: same stdout.
- `p_pascal_routes` — argument, alias, list item, dict value, attribute, short: same stdout.
- `p_pascal_unpack` — unpack at 4/256/257/300: same stdout.
- Isolation probes `pr_arg`, `pr_list`, `pr_dict`, `pr_attr`, `pr_alias`: same stdout. (Dict route needed a typed `dict[str, bytes]`; untyped literal inference is a pre-existing AIL limitation, unrelated to struct.)

**Tests** (`par_check.py -j 2`)
`test_ail_stdlib26`, `test_ail_sdk`, `test_ail_files`, `test_ail_safetynet`, `test_ail_corpus_findings3` — 5 modules, 0 failed. `update_manifest.py --check` passes.
[cost $0.0192, opencode tokens {"total": 1150603, "input": 53301, "output": 6218, "reasoning": 7052, "cache.write": 0, "cache.read": 1084032}]
    tool time: bash 11.7 min, edit 0.0 min
        614s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_stdlib26 test_ail_sdk t
         34s bash   cat > /tmp/probes/pr_arg.py <<'EOF' import struct def main() -> None:     data = b"c" * 300     print(len(stru
         25s bash   cd /home/runner/work/_temp/w2 && for p in p_pascal p_pascal_routes p_pascal_unpack; do echo "########## $p"; b
         23s bash   cd /tmp/probes && python3 - <<'PY' p='p_pascal_routes.py' s=open(p).read().replace('    d = {"k": b"c" * 300}'
          7s bash   cat > /tmp/probes/pr_dict.py <<'EOF' import struct def main() -> None:     d: dict[str, bytes] = {"k": b"c" * 
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check;
          0s bash   cd /home/runner/work/_temp/w2 && timeout 2400 python3 tools/par_check.py -j 2 test_ail_stdlib26 test_ail_sdk t

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds a compile-time `struct` lowering pass (`python/pkg-v12/structlib.py`) for literal-format `pack`/`calcsize`/tuple `unpack`/`unpack_from`, a bundled `stdlib/struct.py` + C IEEE-754 bit glue, module registration, `test_ail_stdlib26.py`, MANIFEST/DIFFERENCES/DEVLOG. Commit `7b39927` corrects the Pascal length byte to `min(len,count-1,255)` (data still `min(len,count-1)`) and exports the four new files in `sdk_files`.

**Defect (change-caused, not a named refusal)** — `structlib.py:378` wraps the unpack data in `bytes(...)`, so AIL silently converts an `int` or `list[int]` into bytes where CPython raises `TypeError`:
`/tmp/rprobes/p_bufbad.py`:
```python
import struct
def main() -> None:
    xs = [1, 2, 3, 4]
    a, = struct.unpack("<I", xs); print("list", a)
    b, = struct.unpack("<I", 4);  print("int", b)
    c, = struct.unpack_from("<H", xs, 0); print("from-list", c)
main()
```
Expected (CPython 3.12): exit 1, stdout empty, `TypeError: a bytes-like object is required, not 'list'`.
Actual (both builds): exit 0, stdout `list 67305985`, `int 0`, `from-list 513`. Base (/tmp/base26) refuses `struct` outright, so this is new. Same coercion also forced a misleading type error when the data was a list item inside a helper (p_unpack_routes).

**Probes (all `bash ~/tools/cmp.sh`, both builds)**
- `p_pascal2` (1/2/255/256/257/300/1000, `<,>,@`, `p/s`): same stdout.
- `p_ints2`, `p_floats2`, `p_round`, `p_nan`, `p_native3`, `p_extra`, `p_mutate4`, `p_nonstruct`: same stdout; `p_nonstruct`'s `program.c` is byte-identical to the base.
- `p_bufbad`: **differs** (defect above).
- Named refusals observed and OK: `=P`, computed format, unpack-as-value, pack wrong argument count.

**Report claims**
- Pascal fix `min(len,count-1,255)` verified — true.
- MANIFEST `sdk_files`/pins — true (`update_manifest.py --check` exit 0; diff shows all four files; `test_ail_sdk` passes).
- New Pascal regression cases / dated DEVLOG entry — true.
- “5 modules, 0 failed” — verified: `test_ail_stdlib26, test_ail_sdk, test_ail_files, test_ail_safetynet, test_ail_corpus_findings3` = 5/5 pass on HEAD.
- “p_pascal_routes / pr_* same stdout” — plausible and consistent with my route probes; not re-run verbatim.

**Pre-existing:** untyped-dict inference, `bytearray` item assignment, no `TypeError` catch, tuple→bytes are general AIL limitations, not caused here. No gdev program imports `struct`, and the change adds no runtime path to existing programs, so instruction-count comparison does not apply.

**Unverified:** fresh exported-SDK build beyond `test_ail_sdk`; untyped-dict `unpack` route.

VERDICT: FIX

1. `struct.unpack` / `unpack_from` accept `int` and `list[int]` data because the lowering calls `bytes(data)` (`python/pkg-v12/structlib.py:378`), printing values and exit 0 where CPython raises `TypeError`. Probe `/tmp/rprobes/p_bufbad.py`; expected CPython: exit 1, empty stdout, `TypeError: a bytes-like object is required, not 'list'`; actual both builds: exit 0, stdout `list 67305985` / `int 0` / `from-list 513`. Restrict the data operand to `bytes`/`bytearray` (or emit a named compile-time refusal) instead of a general `bytes()` coercion.
[cost $0.0460, opencode tokens {"total": 2890691, "input": 91440, "output": 12770, "reasoning": 27185, "cache.write": 0, "cache.read": 2759296}]
    tool time: bash 16.1 min
        571s bash   date; cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check 2>&1 | tail -3; cd AIL_CURRENT
         99s bash   date; cd /tmp/rprobes && for p in p_pascal2 p_ints2 p_floats2 p_native2 p_mutate2 p_refusals; do echo "#######
         81s bash   cd /tmp/rprobes && for p in p_pascal p_unpack_from p_routes p_types p_floats p_ints p_native p_mutate p_nonstr
         36s bash   cd /tmp/rprobes && python3 - <<'PY' import struct def emit(name, lines):     open(name,'w').write('import stru
         14s bash   cd /tmp/rprobes && cat > p_buflist2.py <<'EOF' import struct   def main() -> None:     xs = [1, 2, 3, 4]     b
         13s bash   cd /tmp/rprobes && cat > p_min1.py <<'EOF' import struct   def take(payload: bytes) -> int:     a, = struct.un
         11s bash   cd /tmp/rprobes && python3 - <<'PY' s=open('p_extra.py').read() s=s.replace('    print(struct.pack("<3 i", 1, 
         11s bash   cd /tmp/rprobes && cat > p_bufkind.py <<'EOF' import struct   def main() -> None:     try:         a, = struct

FINAL VERDICT: FIX  2026-10-29T00:44:53Z
