# job job-stdlib29-10290853  started 2026-10-29T00:18:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"8d5945a6-3049-4aaa-b79f-42ed8ea38fd9","session_id":"acd0d787-0efc-4755-b68c-8f037b246324"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"8e8f3825-c623-4ab2-a247-c30c008147b6","session_id":"a365f2c5-45e8-4138-ae85-54076842c9f9"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done and committed on `job-stdlib29-10290853`.

- Supported `unicodedata.category()` for one BMP character via 4007 generated Unicode 15.0 ranges (60,104 bytes), with exact CPython `TypeError` messages. `name()`, `normalize()`, and the rest remain named refusals.
- Added `test_ail_stdlib29.py` (77 code points, 29 categories, 6 refusal cases), registered it in `ail_check.py` and CI shards, and updated DEVLOG, DIFFERENCES, reference docs, and the manifest.
- Probes: 7 match CPython on both builds; 4 are refused by name. Targeted tests: 10 modules + `test_ail_python_syntax`, 0 failed. `update_manifest --check` and `ci_shards --check` pass.
- Commit: `0a47575`. Not pushed.
[cost $0.0000, opencode tokens {"total": 13329020, "input": 363786, "output": 31970, "reasoning": 39952, "cache.write": 0, "cache.read": 12893312}]
    tool time: bash 45.3 min
        863s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 --timeout 1800 test_ail_stdlib29 test_ail_std
        687s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 --timeout 1800 test_ail_stdlib29 test_ail_std
        600s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/census.py <<'PY' import glob,subprocess,sys,os,re,collections,conc
        147s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/census2.py <<'PY' import glob,subprocess,sys,os,re,collections,con
         55s bash   cat > /tmp/probes/udcat_empty.py <<'PY' import unicodedata   def main() -> None:     try:         print(unicod
         47s bash   cd /home/runner/work/_temp/w2 && git add AIL_CURRENT/ail_syntax.py && python3 tools/update_manifest.py && git 
         45s bash   cd /home/runner/work/_temp/w2 && cat > /tmp/census3.py <<'PY' import subprocess,sys,os,tempfile,re,json rows=[
         39s bash   cd /home/runner/work/_temp/w2 && git add AIL_CURRENT/MANIFEST.json && python3 tools/par_check.py -j 2 --timeou

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change does (one line):** Adds `unicodedata.category()` for one BMP char to `ail_syntax._SMALL_MODULES`/`_DROPPED`, lowered to `_ail_ud_category`, a binary search over a generated 4007-row Unicode 15.0 range table (`python/pkg-v12/unicodecat.py`, 60,104 bytes), plus the new test, docs and manifest. This matches the report.

**Verified (probes, both builds, `cmp.sh`):**
- Table correctness: exec'd the generated helper against `unicodedata.category` over all 1,114,112 code points — 0 mismatches; 4007 ranges / 60,104 bytes.
- Routes: import, alias, `from ... import category` (aliased and plain), function arg, list item, dict value, instance attribute, reassigned char local, local import, `chr(n)`, result used as key/compared/concatenated — all match CPython.
- Multi-byte BMP (é, €, 一, combining, soft hyphen, NEL, hiragana) and BMP ranges (U+E000, U+FFFD, U+FFFF, U+D7FF) match.
- `TypeError` messages match exactly for `""`, `"ab"`, `None`, `1`, `1.5`, `b"a"`, `True`, `bytearray`, `list`.
- Aliasing/mutation: taking a char from a list/dict/attribute, then mutating the source, still gives CPython's value.
- `name/normalize/lookup/bidirectional/decimal` and extra/keyword/star/value forms are refused by name.
- Non-BMP literal is refused by name (pre-existing 16-bit runtime limit); non-BMP/surrogate `chr()` hits the pre-existing `chr()` refusal — not caused by this change.
- No-feature program: `--debug-dir` `program.c` byte-identical to the base (only temp paths in `native_report.json` differ).
- `update_manifest.py --check` and `ci_shards.py --check` exit 0.
- Targeted tests: `test_ail_stdlib29` ok 41.8s, `test_ail_safetynet` ok 131.5s (0 failed).

**Defects**
1. Shadowing/rebinding the module name is ignored by the rewrite, so a program that must raise `AttributeError` compiles and prints a category (wrong stdout, wrong exit status). Base refused the whole module, so this is new.
   ```python
   import unicodedata
   def f(unicodedata: int) -> str:
       return unicodedata.category("A")
   print(f(5))
   ```
   Expected: CPython exit 1, stderr `AttributeError: 'int' object has no attribute 'category'`, no stdout.
   Actual: both builds exit 0, stdout `Lu`.
   Same wrong `Lu` with a module-level `unicodedata = 5` (`p12`), a local assignment (`p22`) and a loop target (`p23`).
2. Rebinding a from-imported name is also ignored:
   ```python
   from unicodedata import category as cat
   cat = 5
   print(cat("A"))
   ```
   Expected: CPython `TypeError: 'int' object is not callable`; actual: both builds print `Lu`, exit 0.
   Likely fix: add `unicodedata` to `shadowing._STRUCTURAL` (as `math`/`os` already are) and/or make the `modules`/`names` mapping respect a rebinding.

**Notes / pre-existing (not blocking):** `textwrap = 5; textwrap.dedent(...)` shows the same shadowing bug on the base; `class S(str)`, complex constants and non-BMP `chr()` are pre-existing refusals. Adding `unicodedata` to `_DROPPED` degrades the bare-module refusal from "the module unicodedata used as a plain value" to "name 'unicodedata' is not defined" (still a compile-time refusal).

**Claims:** all report claims verified except: worker's own 11 probes are not all present (`/tmp/probes` has only `udcat_basic.py`), and its 10-module run was not re-run (only the two required modules). Speed not measured (new feature, no hot-path change).

Unverified: worker's `test_ail_python_syntax` and the other 8 claimed modules.

VERDICT: FIX
1. `import unicodedata` then a parameter/local/loop/constant rebinding of `unicodedata` still rewrites `unicodedata.category("A")` to the helper: CPython raises `AttributeError` (exit 1), both builds print `Lu` (exit 0).
2. `from unicodedata import category as cat; cat = 5; cat("A")`: CPython raises `TypeError: 'int' object is not callable`, both builds print `Lu` (exit 0).
[cost $0.0000, opencode tokens {"total": 2101288, "input": 72597, "output": 8478, "reasoning": 18805, "cache.write": 0, "cache.read": 2001408}]
    tool time: bash 4.7 min
        133s bash   date; cd /home/runner/work/_temp/w2 && timeout 1700 python3 tools/par_check.py -j 2 --timeout 1500 test_ail_st
         23s bash   cat > /tmp/rprobes/p12_shadowmod.py <<'PY' import unicodedata unicodedata = 5 print(unicodedata) try:     prin
         21s bash   date; cd /home/runner/work/_temp/w2 && for n in p5b_types p9_nonbmplit p10_bmp p11_shadow; do p=/tmp/rprobes/$
         19s bash   date; cd /home/runner/work/_temp/w2 && for p in /tmp/rprobes/p*.py; do n=$(basename $p .py); (bash ~/tools/cmp
         16s bash   cat > /tmp/rprobes/p5c_types.py <<'PY' import unicodedata  for v in [True, bytearray(b"a"), ["a"], b"a", 1.5, 
         15s bash   date; cd /tmp/base && for p in /tmp/rprobes/p*.py; do n=$(basename $p .py); (bash ~/tools/cmp.sh $p $PWD > /tm
         14s bash   cat > /tmp/rprobes/p21_paramshadow.py <<'PY' import unicodedata  def f(unicodedata: int) -> str:     return un
         12s bash   cat > /tmp/rprobes/p17_localimport.py <<'PY' def cat(ch: str) -> str:     import unicodedata     return unicod

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `93ff1ed`.

- Rebound `unicodedata`/from-import names now produce a named compile-time refusal instead of wrong output: module constant, alias, parameter, local, loop/with/except target, nested parameter, and from-import alias/plain rebinding.
- Probes (`/tmp/probes`, both builds): `ud_const`, `ud_fromrebind`, `ud_local`, `ud_loop`, `ud_param`, `ud_shadow_modalias`, `ud_shadow_fromplain`, `ud_shadow_except`, `ud_shadow_nestedparam`, `ud_shadow_with`, `ud_shadow_other_scope` refused by name; all existing `udcat_*` probes still match CPython or are refused as before.
- Added regression cases to `test_ail_stdlib29.py`.
- Tests: `test_ail_stdlib29`, `test_ail_builtin_shadowing`, `test_ail_python_syntax`, `test_ail_refusal_messages`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_stdlib_batch4`, `test_ail_modules`, `test_ail_check`: 10 modules, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` exit 0.
[cost $0.0342, opencode tokens {"total": 1546981, "input": 107719, "output": 8282, "reasoning": 14788, "cache.write": 0, "cache.read": 1416192}]
    tool time: bash 15.4 min
        405s bash   date; python3 tools/par_check.py -j 2 --timeout 1500 test_ail_stdlib_batch4 test_ail_modules test_ail_check; e
        350s bash   date; python3 tools/par_check.py -j 2 --timeout 1500 test_ail_stdlib29 test_ail_builtin_shadowing test_ail_pyt
         71s bash   date; for p in /tmp/probes/ud*.py; do echo ==== $(basename $p); bash ~/tools/cmp.sh $p $PWD | grep -E "cpython
         66s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_syntax.py') s=p.read_text() old="""         
         24s bash   date; for p in /tmp/probes/ud_*.py; do echo ==== $(basename $p); bash ~/tools/cmp.sh $p $PWD | tail -12; done
          2s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_syntax.py') s=p.read_text() old="""         
          2s bash   for p in /tmp/probes/ud_shadow_except.py /tmp/probes/ud_shadow_fromplain.py /tmp/probes/ud_shadow_modalias.py 
          1s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_syntax.py') s=p.read_text() s=s.replace("els

## review 1 skipped: only 45 minutes left

FINAL VERDICT: FIX  2026-10-29T04:27:49Z
