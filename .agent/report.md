# job job-stdlib21-10290508  started 2026-10-28T20:15:10Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"c028a291-04fa-4dce-bd65-19b603bc4ffa","session_id":"46fb1e3b-a34c-4c72-9096-0a4100a63f02"}
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"7172a746-6fd8-49f3-b768-acfe9c23e59a","session_id":"e9aaf859-1348-467c-bba4-4841fc1de1a2"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `2b24090` on `job-stdlib21-10290508`.

**Scan (compile refusals):** `decimal` 2, `textwrap.shorten` 1, one `re` use 1, `datetime` 1 (actually compiles on the general path). `decimal` stays refused by name because exact context arithmetic/rounding is not a small lowering; the next supportable refusal was `textwrap.shorten`.

**Change:** added `_ail_tw_shorten`, CPython 3.12's default `TextWrapper(max_lines=1)` behavior (whitespace collapse, hyphen/em-dash chunking, `_handle_long_word`, `" [...]"` placeholder) for `shorten(text, width)` and `shorten(text, width=...)`. Missing width, `placeholder=`, and other options remain named compile-time refusals. `test_ail_stdlib21.py` already existed from the prior unicodedata commit, so I extended it with shorten cases, a 500-case fuzz, and two refusal cases.

**Probes (all via `cmp.sh`, both builds):**
- `tw_shorten_basic`, `tw_shorten_routes`, `tw_shorten_ws`, `tw_shorten_types`, `tw_shorten_floatlong`, `tw_shorten_fuzz` (4000 LCG cases) — match CPython.
- `tw_shorten_nonstr`, `tw_shorten_bytes` — match CPython's exact `AttributeError`/`TypeError`.
- `tw_shorten_refuse_onearg`, `tw_shorten_refuse_placeholder` — refused by name.

**Final state:** `tools/update_manifest.py --check` passes. Tests on final commit: `test_ail_stdlib21`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre360`, `test_ail_python_syntax` — 6 modules, 0 failed.
[cost $0.0703, opencode tokens {"total": 6938281, "input": 148111, "output": 18917, "reasoning": 27445, "cache.write": 0, "cache.read": 6743808}]
    tool time: bash 27.4 min, edit 0.0 min
        496s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && echo MANIFEST_OK && cd AIL_C
        448s bash   cd /home/runner/work/ail-ci/ail-ci && ls AIL_CURRENT/test_ail_pre360.py AIL_CURRENT/test_ail_python_syntax.py 
        177s bash   mkdir -p /tmp/probes && cat > /tmp/scan_imports.py <<'PY' import json, re, subprocess, sys from pathlib import
        172s bash   cat > /tmp/scan2.py <<'PY' import json, re, subprocess, sys from pathlib import Path from concurrent.futures i
        115s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_stdlib21 2>&1 | 
         45s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/tw_shorten_basic.py /tmp/probes/tw_shorten_ws.py /t
         38s bash   mkdir -p /tmp/probes && cat > /tmp/probes/tw_shorten_basic.py <<'PY' import textwrap   def show(t: str, w: int
         31s bash   cat > /tmp/probes/tw_shorten_bytes.py <<'PY' import textwrap  print(textwrap.shorten(b"one two three", 10)) PY

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review

**What the change does (one line):** Adds a `tw_shorten` helper and lowers `textwrap.shorten(text, width)` / `shorten(text, width=...)` to `_ail_tw_shorten`, which re-implements CPython 3.12's default `TextWrapper(width, max_lines=1)`; the branch in `work..HEAD` also contains the earlier `unicodedata.category` commit that the report describes as prior work.

**Independent probes** (`cmp.sh`, HEAD `/home/runner/work/ail-ci/ail-ci`, both builds):

| probe | covers | result |
|---|---|---|
| r1_emdash | em-dash runs, punctuation prefixes, unicode neighbours, widths 5–18 | match |
| r2_hyph | hyphenated words, digit-letter mixes, long hyphen words, widths 5–21 | match |
| r3_width | -9..1e6, bool, float, width via arg/list/attr/dict | match |
| r4_types | int/bytes/None/float/list/bool/bytearray text; str/None/list width | match |
| r5_ws_long | empty, whitespace, long words, VT/FF, NBSP, CJK/é | match |
| r6_refuse | `placeholder=` | named refusal (both builds) |
| r7_uniws | 31 Unicode whitespace/non-whitespace chars | match |
| r8_uniletters | accents, CJK, Arabic-Indic digits, superscripts, Roman numerals | match |
| r9/r10_unicode | non-BMP/surrogate literals and dynamic `chr` | named compile refusal; dynamic non-BMP crash identical on base (see Pre-existing) |
| r13_bigfuzz | 20 000 LCG cases, broad alphabet, widths -2..30 | match |
| r14_dashfuzz | 20 000 LCG cases dense in `-`, `_`, spaces, widths -2..25 | match |

Also: corpus `t116.py` (the motivating program) matches CPython on both builds; a non-textwrap program's `program.c` is byte-identical to base on both the default and general paths.

**Claims vs observations**
- Lowering/helper and refusal spellings: verified in diff and probes.
- `test_ail_stdlib21.py` extension: verified; 6 claimed modules rerun on HEAD — all pass (`test_ail_stdlib21`, `safetynet`, `files`, `corpus_findings3`, `pre360`, `python_syntax`).
- `tools/update_manifest.py --check`: passes.
- `decimal` still refused by name: verified.
- Worker's probe list: independently corroborated by r1–r14 (not their exact files).

**Pre-existing (not counted against this change)**
1. Non-BMP handling: `chr()`/stdin non-BMP stops with the 16-bit runtime error identically on base for the general path; a non-BMP `unicodedata.category(chr(cp))` is refused at compile for constants. DEVLOG honestly notes the 16-bit limit.
2. Module-name shadowing: `textwrap = B(); textwrap.shorten(...)` is mis-lowered (`a b c` vs CPython `custom`). The same resolution bug exists on base for already-supported `textwrap.wrap` and `math.sqrt`; the `shorten` spelling alone was refused on base, so the root cause is pre-existing and orthogonal.

**Unverified**
- Instruction counts (not run: feature is not hot and the helper is emitted only when used).
- Full suite (per instructions).

VERDICT: ACCEPT
[cost $0.0581, opencode tokens {"total": 4732835, "input": 113163, "output": 14220, "reasoning": 31500, "cache.write": 0, "cache.read": 4573952}]
    tool time: bash 12.2 min
        256s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        173s bash   cat /tmp/rprobes/p_no_feature.py 2>/dev/null | head -30; echo ---; cd /home/runner/work/ail-ci/ail-ci/AIL_CURR
         25s bash   cat > /tmp/rprobes/r10_unicode.py <<'PY' import unicodedata  def main() -> None:     print(unicodedata.categor
         22s bash   cat > /tmp/rprobes/r11a.py <<'PY' import sys import unicodedata  def main() -> None:     s = sys.stdin.read().
         21s bash   cat > /tmp/rprobes/r12_wrap_shadow.py <<'PY' import textwrap  class B:     def wrap(self, t: str, w: int) -> s
         21s bash   cat > /tmp/rprobes/r4_types.py <<'PY' import textwrap  def show(t: object, w: object) -> None:     try:       
         15s bash   date; bash ~/tools/cmp.sh /home/runner/work/ail-ci/ail-ci/lab/corpus/programs/deepseek-v4.1-flash-free/t116.py
         14s bash   date; bash ~/tools/cmp.sh /tmp/rprobes/r1_emdash.py $PWD 2>&1 | tail -30

## full suite
test_ail_modconst
test_ail_reference_examples

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `7737264`.

- Root cause: `AIL_REFERENCE.md` was 3523 chars (limit 3500), and its MORE index was stale after the unicodedata addition.
- Trimmed prose to 3497 chars, regenerated the MORE index, refreshed `MANIFEST.json`.
- Passing: `test_ail_modconst`, `test_ail_reference_examples`, `test_ail_stdlib21`; `update_manifest.py --check` is clean.
[cost $0.0145, opencode tokens {"total": 775462, "input": 39315, "output": 3656, "reasoning": 7115, "cache.write": 0, "cache.read": 725376}]
    tool time: bash 4.9 min
        138s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_modconst 2>&1 | tail -60
         59s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_modconst 2>&1 | tail -30
         44s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_stdlib21 2>&1 | 
         43s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_reference_examples 2>&1 | tail -80
          9s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_reference_examples 2>&1 | tail -30
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' from pathlib import Path p = Path('AIL_REFE
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/ref_index.py && python3 tools/ref_index.py --check && wc -

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T00:21:03Z
