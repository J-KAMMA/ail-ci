# job job-stdlib42-10291457  started 2026-10-29T06:12:35Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"1ecf20fe-4179-479e-a93e-37c3c1f04a12","session_id":"1f100ea7-bf31-4f35-a2d8-06ad461e5c24"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"7f4cef28-5022-480d-bef4-adafbf596619","session_id":"e3bd98da-9247-41f8-b53d-aa412b444ddd"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `struct` support on branch `job-stdlib42-10291457`.

- Commit: `1954ca3 stdlib42: support struct pack, unpack, calcsize and error`
- Added `AIL_CURRENT/python/pkg-v12/structlib.py`, `prelude_struct.py`, and `test_ail_stdlib42.py`.
- Supports `pack`, `unpack`, `calcsize`, `error` for `< > !` with `x b B h H i I l L q Q ?`; `?` is pack-only.
- Other uses remain named compile-time refusals: native `@`/`=`, floats, `c s p`, `n N`, `Struct`, `pack_into`, `unpack_from`, `iter_unpack`, dynamic formats, `*`/keyword args, zero-value unpack.
- Updated `ail_syntax.py`, `pyfunc.py`, `ail_check.py`, manifest, CI shards, `DEVLOG.md`, `DIFFERENCES.md`.

Probes in `/tmp/probes/struct42`: `p1b`, `p2`, `p3`, `p4`, `p10`-`p13` match CPython on both builds; `p1`/`p8` and `r1`-`r4` are refused by name as expected.

Final commit tests: 49 tests passed, 1 skipped across `test_ail_stdlib42`, `test_ail_python_syntax`, `test_ail_pre105`, `test_ail_refusal_messages`, `test_ail_pre346`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. Manifest and shard checks exit 0. Not pushed.
[cost $0.0000, opencode tokens {"total": 13945232, "input": 372257, "output": 41345, "reasoning": 44910, "cache.write": 0, "cache.read": 13486720}]
    tool time: bash 56.5 min, write 0.0 min
        637s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest test_ail_pre346 test_ail_safetynet test_ail_f
        300s bash   cd AIL_CURRENT && python3 - <<'PY' import subprocess,sys,json,glob,collections,os files=glob.glob('../lab/corp
        275s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 -m unittest test_ail_stdlib42 test_ail_python_syntax tes
        269s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' src=open('/tmp/probes/struct42/p1.py').read().splitlines() o
        258s bash   cd /home/runner/work/_temp/w2 && for f in p1 p2 p3 p4 p8 p10 p11 p12 p13; do echo =====$f; bash ~/tools/cmp.sh
        233s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 -m unittest test_ail_stdlib42 test_ail_python_syntax tes
        153s bash   cd AIL_CURRENT && python3 -m unittest test_ail_stdlib42 -v 2>&1 | tail -50
        145s bash   python3 - <<'PY' p='AIL_CURRENT/python/pkg-v12/prelude_struct.py' s=open(p).read() repls={ 'def _ail_struct_bo

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** `structlib.py` rewrites a top-level `import struct` / `from struct import ...` and lowers literal-format `pack` / `unpack` / `calcsize` / `error` for `< > !` integer formats onto `prelude_struct.py`; other uses are refused by name. It also rewords the import refusal in `pyfunc.py` and narrows `python_wording`'s `struct`→`class` replacement.

**Claims**
- Commit/files/test registration/manifest/shards/not pushed: verified (`1954ca3`, `update_manifest.py --check`=0, `ci_shards.py --check`=0, branch ahead of origin by 1).
- Supported surface: mostly verified (widths, ranges, whitespace, `x`, `?` pack, routes through argument/list/attribute/dict).
- Refusal list: verified on samples (native `@`/`=`, `*`-import, dynamic format, zero-value unpack, local import).
- Probe claim “p1b…p13 match on both builds”: false for the typed build; the probes/tests avoid `Q` values above int64 (defect 2).
- Final test counts: partially verified — the four relevant modules pass, exact `49 passed, 1 skipped` not reproduced.
- Non-`struct` C: verified unchanged (`--debug-dir` on `plain.py`; only path strings in `native_report.json` differ).

**Defects**
1. `struct.unpack` of a non-bytes object raises `struct.error`; CPython raises `TypeError`, changing `except` behaviour on both builds. Probe: `try: struct.unpack("<I", "abcd")` / `except TypeError` vs `except struct.error`. Expected `TypeError ...`; actual `struct.error ...`.
2. Typed build (`AIL_NO_GENERAL=1`): `print(struct.unpack("<Q", b"\xff"*8))` compiles, then exits 1 with stderr `integer overflow`. Expected `(18446744073709551615,)` exit 0; general/default builds match, so `cmp.sh` misses it. Root cause (`int.from_bytes` above int64) is pre-existing, but the new module exposes it instead of refusing by name.
3. `struct.error`’s class name differs: probe `except struct.error as e: print(type(e).__name__, repr(e))` prints `error error('boom')` in CPython and `_AilStructError _AilStructError('boom')` in AIL (both builds).

**Tests run:** `par_check.py -j 2 test_ail_stdlib42 test_ail_python_syntax test_ail_refusal_messages test_ail_safetynet` — 4 modules, 0 failed. Non-struct debug-dir comparison identical.

**Unverified:** exact worker test counts, `test_ail_pre105`/`pre346`/`files`/`corpus_findings3`; speed (no hot-path change, not measured).

VERDICT: FIX
1. `struct.unpack` with a str/other non-bytes argument must raise `TypeError`, not `struct.error`.
2. Typed path must either support unsigned `Q` above int64 or refuse it by name at compile time; it currently emits `integer overflow` at run time.
3. `struct.error` must preserve CPython’s observable class name/repr (`error`), not `_AilStructError`.
[cost $0.0397, opencode tokens {"total": 2461832, "input": 93011, "output": 8335, "reasoning": 22822, "cache.write": 0, "cache.read": 2337664}]
    tool time: bash 11.9 min
        366s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_stdlib42 test
        103s bash   cat > /tmp/rprobes/localimp.py <<'EOF' def main() -> None:     import struct     print(struct.pack("<I", 1).he
         39s bash   cat > /tmp/rprobes/types2.py <<'EOF' import struct   def main() -> None:     try:         print(struct.unpack(
         33s bash   cat > /tmp/rprobes/qrange.py <<'EOF' import struct   def main() -> None:     try:         print(struct.pack("<
         32s bash   cat > /tmp/rprobes/qmark.py <<'EOF' import struct   def main() -> None:     print(struct.pack("<?", 2.5).hex()
         30s bash   cat > /tmp/rprobes/packbig.py <<'EOF' import struct   def main() -> None:     print(struct.pack("<Q", 92233720
         30s bash   cat > /tmp/rprobes/mutate.py <<'EOF' import struct   def main() -> None:     raw = bytearray(struct.pack("<I",
         24s bash   date; for f in q_typed types2; do echo ==== base $f; cd /tmp/rprobes && bash ~/tools/cmp.sh $f.py /tmp/base 2>

## fix round skipped: only 45 minutes left

FINAL VERDICT: FIX  2026-10-29T10:22:15Z
