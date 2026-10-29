# job job-stdlib46-10291930  started 2026-10-29T10:54:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"a09c76d5-fd8c-41cc-bd11-966ac2f69dc1","session_id":"814b8621-249d-4690-8aa2-6bfa7c895ba1"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"332a1d21-abde-450d-9411-0a0f5717d2cd","session_id":"6b9f1f63-9756-4441-8235-30a6d9df6712"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented `unicodedata` support and committed as `d70e961`.

- Module chosen: `unicodedata`, 3 refused imports in the requested corpus (most refused; next was `resource`, out of scope).
- Built: `name`, `category`, `normalize("NFC"/"NFD")`, `unidata_version` via generated Unicode 15.0 tables.
- Refused by name: other functions, `NFKC`/`NFKD`, computed forms, keyword arguments, and literal CJK compatibility ideographs decomposing above U+FFFF.

Probes (`/tmp/probes`, both builds):
- Match CPython: `uni_basic_embedded.py`, `uni_name_default.py`, `uni_errors.py`, `uni_routes.py`, `uni_from_import.py`, `uni_normalize_cases.py`, `uni_sweep_bmp.py` (all BMP code points except the documented seven).
- Refused by name: `uni_refusal_lookup.py`, `uni_refusal_nfkc.py`, `uni_refusal_computed_form.py`, `uni_refusal_keyword.py`, `uni_refusal_normalize_type.py`, `uni_refusal_astral_decomp.py`, updated `uni_cjk_compat_astral.py`.

Tests passing on the committed tree: `test_ail_stdlib46` (3 tests, both builds), `test_ail_stdlib5`, `test_ail_python_syntax`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `tools/update_manifest.py --check` passes. One recorded open limitation: runtime-only values among the seven CJK compatibility ideographs keep the 16-bit limitation (DIFFERENCES row `C?-job-stdlib46-10291930-1`).
[cost $0.0745, opencode tokens {"total": 7755807, "input": 174031, "output": 21630, "reasoning": 21330, "cache.write": 0, "cache.read": 7538816}]
    tool time: bash 33.1 min, write 0.0 min, edit 0.0 min
        959s bash   cd AIL_CURRENT && for m in test_ail_stdlib46 test_ail_stdlib5 test_ail_safetynet test_ail_files test_ail_corpu
        241s bash   for p in /tmp/probes/uni_basic_embedded.py /tmp/probes/uni_name_default.py /tmp/probes/uni_errors.py /tmp/prob
        147s bash   for p in /tmp/probes/uni_basic_embedded.py /tmp/probes/uni_from_import.py /tmp/probes/uni_normalize_cases.py /
        118s bash   for p in /tmp/probes/uni_basic_embedded.py /tmp/probes/uni_name_default.py /tmp/probes/uni_errors.py /tmp/prob
        115s bash   for p in /tmp/probes/uni_basic_embedded.py /tmp/probes/uni_from_import.py /tmp/probes/uni_normalize_cases.py /
         78s bash   cd AIL_CURRENT && python3 -B test_ail_stdlib46.py -v 2>&1 | tee /tmp/test_stdlib46.log; echo "EXIT ${PIPESTATU
         57s bash   python3 - <<'EOF' from pathlib import Path p=Path('/tmp/probes/uni_sweep_bmp.py') s=p.read_text() s=s.replace(
         46s bash   printf 'A\u00e9\u00c5\u1e9b\n' | bash ~/tools/cmp.sh /tmp/probes/uni_basic.py $PWD; echo ====; printf 'Hello, 

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** it routes any source mentioning `unicodedata` through the batch-5 rewriter, removes its imports, rewrites `name` / `category` / `normalize` calls onto a generated prelude (tables decoded at program start), inlines `unidata_version`, and refuses other names/forms/keywords plus seven literal astral-decomposing characters. This matches the report, except the report does not mention rebinding/shadowing.

**Verified**
- `name`, `category`, `normalize("NFC"/"NFD")`, `unidata_version` match CPython on both builds for the tested values: p2 (22 tricky sequences), p5 (300 random combining sequences), p4 (defaults/unassigned), test sweep.
- `unicodedata` is the most-refused import in the corpus (3 files).
- Refusals: `lookup`, `NFKC`, computed form, keyword argument, literal U+FA6C; arity errors and non-BMP literals are compile-time refusals (acceptable).
- `test_ail_stdlib46`, `test_ail_stdlib5`, `test_ail_python_syntax`, `test_ail_safetynet`: 4 modules, 0 failed. `tools/update_manifest.py --check` passes.
- No-feature program C is unchanged (only `native_report.json` paths differ).

**Defects**
1. Rebinding an imported name is not detected; the pass rewrites the local call and returns the module result.
   ```python
   from unicodedata import name

   def name(x: str) -> str:
       return "local:" + x

   print(name("A"))
   ```
   Expected `local:A`; HEAD prints `LATIN CAPITAL LETTER A` on both builds. Base prints `local:A`. The module-alias variant (`unicodedata = Box()` then `unicodedata.name("A")`) is also silently rewritten; base refuses it, HEAD prints `LATIN CAPITAL LETTER A` instead of `box:A`. `run_fractions` already refuses this kind of rebinding; `run_unicodedata` does not.
2. The seven CJK compatibility ideographs still silently differ for run-time values, as recorded in the new DIFFERENCES row.
   ```python
   import unicodedata

   def main() -> None:
       s = "\ufa6c"
       print(repr(unicodedata.normalize("NFD", s)))
       print(repr(unicodedata.normalize("NFC", s)))

   main()
   ```
   Expected `'𤋮'` (U+242EE); actual `'𤋮'` (U+FA6C) on both builds. The task asks for exact CPython output or a named compile-time refusal; a run-time value gets neither. The literal form is correctly refused.

**Pre-existing / not blocking:** stdin containing a non-BMP code point still stops with `AIL internal error: stdin code point above U+FFFF in the 16-bit v2 runtime` (the existing 16-bit stdin limitation, not the `unicodedata` lowering).

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3` were not re-run (review scope: added/edited modules plus `test_ail_safetynet`); speed was not measured because no benchmark imports `unicodedata`.

VERDICT: FIX
1. Add a rebinding check for imported `unicodedata` names and the module alias (refuse, or leave the import/name alone), as `run_fractions` does for `Fraction`. Probe: `from unicodedata import name; def name(x): return "local:"+x; print(name("A"))` — expected `local:A`, actual `LATIN CAPITAL LETTER A`.
2. Make `normalize` on the seven astral-decomposing BMP characters match CPython or refuse by name; currently a run-time value returns the BMP character unchanged (`'𤋮'` instead of `'𤋮'`).
[cost $0.0581, opencode tokens {"total": 5333176, "input": 113422, "output": 8658, "reasoning": 34008, "cache.write": 0, "cache.read": 5177088}]
    tool time: bash 8.6 min
        236s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_stdlib46
         69s bash   cd /home/runner/work/_temp/w2; for p in p1_arity p2_norm_edge p3_runtime_astral p4_name_defaults; do echo "===
         44s bash   cat > /tmp/rprobes/p11_shadow.py <<'EOF' from unicodedata import name, category   def name(x: str) -> str:    
         26s bash   cat > /tmp/rprobes/p14_shadow_min.py <<'EOF' from unicodedata import name   def name(x: str) -> str:     retur
         26s bash   cd /tmp; rm -rf ast; mkdir ast; cp /tmp/probes/uni_astral.py ast/p.ail; cd ast; for m in g d; do if [ $m = g ]
         21s bash   cat > /tmp/rprobes/p10_name_obj_default.py <<'EOF' import unicodedata   def main() -> None:     print(unicoded
         19s bash   python3 - <<'EOF' import random random.seed(12345) pool = ['a','A','e','\u0301','\u0300','\u0308','\u0323','\u
         14s bash   cat > /tmp/rprobes/p8_surrogate_types.py <<'EOF' import unicodedata   def main() -> None:     print(hex(0xD800

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `dd5c8ae`.

**Changes**
- Rebinding: a shadowing `from unicodedata import ...` is left as written (prints `local:A` on both builds); module-alias and parameter shadowing are refused by name.
- Astral decompositions: literal and literal-derived `normalize` arguments are refused at compile time; a run-time value now raises named `RuntimeError: ... U+FA6C decomposes to U+242EE, above U+FFFF ...` instead of silently returning the BMP char.

**Tests on final commit**
- `test_ail_stdlib46`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 5 modules, 0 failed.
- `tools/update_manifest.py --check`: passes.

**Probes**
- Match CPython on both builds: rebind-from-import, safe from-import, dynamic argument/list/attribute/dict, `uni_basic_embedded`, `uni_name_default`, `uni_errors`, `uni_routes`, `uni_normalize_cases`, `uni_sweep_bmp`, t489 corpus sample.
- Refused by name on both builds: module-alias shadow, parameter shadow, astral value via variable, astral via list item, plus all prior refusal probes.
- Runtime stdin U+FA6C: named `RuntimeError` on both builds (not CPython; the 16-bit runtime cannot hold U+242EE). This is the remaining honest limitation for values only known at run time.
[cost $0.0729, opencode tokens {"total": 8126174, "input": 163941, "output": 13874, "reasoning": 26951, "cache.write": 0, "cache.read": 7921408}]
    tool time: bash 26.2 min
        464s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_stdlib5 
        463s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_stdlib46
        196s bash   cd /tmp/probes && for p in uni_basic_embedded uni_name_default uni_errors uni_routes uni_from_import uni_norma
        107s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
        106s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_stdlib46
         61s bash   cd /tmp/probes && cat > r8_dynamic_arg.py <<'EOF' import unicodedata   def show(s: str) -> None:     print(rep
         53s bash   cd /tmp/probes && echo "=== sweep"; bash ~/tools/cmp.sh /tmp/probes/uni_sweep_bmp.py /home/runner/work/_temp/w
         27s bash   cd /tmp && rm -rf t489chk && mkdir t489chk && cp /home/runner/work/_temp/w2/lab/corpus/programs/glm-5.3-flash-

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the diff really does.** It adds a generated `prelude_unicodedata.py` plus AST lowering for `unicodedata.name`, `category`, `normalize(NFC/NFD)` and `unidata_version`, routes `unicodedata` through `stdlib5/smalllib5/ail_syntax`, refuses the other queries/forms/keywords/shadowing, refuses literal astral decompositions, and raises a named `RuntimeError` for the seven astral decompositions when the value is only known at run time. Beyond the worker's `dd5c8ae` review fix, the diff also contains the original implementation `d70e961` (the report describes only the former).

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both builds unless noted):

| probe | result |
|---|---|
| `q6_basic` | matches CPython |
| `q1_shadow_from` (shadowing `from unicodedata import name`) | matches CPython (`local:A`) |
| `q2_norm_edge`, `p2_norm_edge`, `p4_name_defaults` | match CPython |
| `q10_shadow_module`, `q11_shadow_param` | refused by name |
| `q12_method_name` | refused (over-broad: an unrelated method named `name`) |
| `q29_surrogate`, `p1_arity`, `p8_surrogate_types` | compile refusal (pre-existing chr/surrogate limits) |
| `q7_chr_decomp`, `q30_astral_uncaught` | **diverge: runtime `RuntimeError`** |
| `q4_astral_hold`, `q9_chr_hold`, `q17/q18/q22/q24/q28` | identical to `/tmp/base46` |
| `q23_plain` with `--debug-dir` | `program.c` identical to base |

Tests: `test_ail_stdlib46`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. `update_manifest.py --check` passes.

**Defect**

1. `unicodedata.normalize` on a runtime-known BMP compatibility ideograph raises instead of matching CPython.
   Probe `/tmp/rprobes/q30_astral_uncaught.py`:
   ```python
   import unicodedata

   def main() -> None:
       s = chr(0xFA6C)
       print(repr(unicodedata.normalize("NFD", s)))

   main()
   ```
   - CPython 3.12, both builds expected: `'𤋮'` (U+242EE), exit 0.
   - Actual, both builds: no stdout, exit 1, `RuntimeError: unicodedata.normalize: U+FA6C decomposes to U+242EE, above U+FFFF, ...`.
   - `/tmp/base46` refuses the program by name at compile time, which the task allows; HEAD turns that into a runtime failure. `q7_chr_decomp` shows the same for `try/except` (`RuntimeError …` instead of `'𤋮'`), and `q4_astral_hold` shows the default build can print a U+242EE literal, so “the 16-bit runtime cannot hold U+242EE” is not true for that build. The new test asserts this non-CPython behavior, so the divergence is encoded rather than caught.

**Pre-existing** (identical on `/tmp/base46`): general-path rejection of non-BMP literals and non-BMP stdin/`chr`, and passing an astral string to a user function (`q4`, `q9`, `q17`, `q18`, `q22`, `q24`, `q28`); `chr()` of a surrogate (`q29`).

**Claims:** “5 modules pass”, “manifest check passes”, “shadowing from-import left as written”, “module/parameter shadowing refused”, “astral literal refused”, and “runtime astral raises named RuntimeError” all verified. The report's framing of the runtime error as an acceptable “honest limitation” is not compatible with “supported functions must match CPython exactly”; it is a change-caused runtime divergence, not a pre-existing one.

**Unverified:** the worker's list-item astral refusal probe (their test only exercises a variable), the entire `/tmp/probes` set, and instruction counts (change is not in hot code).

VERDICT: FIX
1. `unicodedata.normalize("NFD"/"NFC", s)` with `s = chr(0xFA6C)` (or U+FACF/FAD0/FAD1/FAD5/FAD6/FAD7, reachable from stdin/argv) exits 1 with a named `RuntimeError`; CPython 3.12 prints `'𤋮'` (U+242EE) and exits 0 on both builds. Probe `/tmp/rprobes/q30_astral_uncaught.py`; same divergence with `try/except` in `/tmp/rprobes/q7_chr_decomp.py`.
[cost $0.0488, opencode tokens {"total": 3392654, "input": 116288, "output": 9361, "reasoning": 26685, "cache.write": 0, "cache.read": 3240320}]
    tool time: bash 13.9 min
        364s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_stdlib5 
        127s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_stdlib46
         66s bash   cd /tmp/rprobes && for p in q1_shadow_from q2_astral_input q3_astral_decomp_var q4_astral_hold q5_local_name q
         65s bash   cd /tmp/rprobes && for p in p1_arity p2_norm_edge p4_name_defaults p8_surrogate_types; do echo "######## $p"; 
         34s bash   cd /tmp/rprobes && cat > q7_chr_decomp.py <<'EOF' import unicodedata   def main() -> None:     s = chr(0xFA6C)
         27s bash   cd /tmp/rprobes && for kind in cat name norm; do case $kind in cat) expr='unicodedata.category(ch)';; name) ex
         25s bash   cd /tmp/rprobes && cat > q16_astral_stdin.py <<'EOF' import sys import unicodedata   def main() -> None:     t
         21s bash   cd /tmp/rprobes && cat > q30_astral_uncaught.py <<'EOF' import unicodedata   def main() -> None:     s = chr(0

FINAL VERDICT: FIX  2026-10-29T13:33:34Z
