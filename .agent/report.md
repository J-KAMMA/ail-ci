# job job-pre317-10271455  started 2026-10-27T05:55:49Z  worker=oc reviewer=oc (GitHub)
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
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"e5e8c89d-718c-4b17-8816-b95a02a86084","session_id":"b9354fbc-b286-4db2-afe2-579d985a2776"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"575e4fc5-07a6-4ade-8fbf-3de66b48b519","session_id":"002e3850-a38b-46a0-aa12-bf69941caa97"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Completed and committed on `job-pre317-10271455`.

**What was fixed**
- Selected the first still-differing reviewer item: `e.args[0] = ...` ran on both builds with matching stdout/exit but a different stderr traceback.
- Added `exctext.refuse_args_item_store` and wired it into both the typed front end (`pyfunc`) and general emitter (`pyboxed2`).
- Refused by name on both builds:
  - literal, negative, computed, augmented, annotated, deleted, destructuring, `for`, and `with` targets
  - values arriving through an argument, list item, attribute, or dict value
  - simple aliases of the exception through a name, list item, attribute, or dict value
- Left unchanged: reading `e.args[0]`, whole `e.args` stores, non-exception objects' `args` lists, stores inside the argument object, and handler-name rebinding.
- Passing the exception to a function that stores into its parameter's `args` remains the pre-existing traceback-only difference; `cmp.sh` still matches stdout, exit, and the last stderr line.

**Records/tests**
- Added `AIL_CURRENT/test_ail_pre317.py`, registered it in `ail_check.MODULES`, added DIFFERENCES row `C?-job-pre317-10271455-1`, DEVLOG entry, and refreshed/validated `MANIFEST.json`.
- Final commit: `e9b47f5` (follow-up to `20033ae`).
- Required tests on final commit: `test_ail_pre317`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all passed, 0 failed.
- Additional exception coverage: `test_ail_pre298`, `test_ail_exc_str`, `test_ail_exception_context`, `test_ail_exception_values_core` — all passed.
- Not pushed. Untracked `.agent/pipeline.md` was left untouched.
[cost $0.0000, opencode tokens {"total": 6775675, "input": 377216, "output": 21960, "reasoning": 44595, "cache.write": 0, "cache.read": 6331904}]
    tool time: bash 14.1 min
        170s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre317 test_ail_safetynet test_ail_files test_ai
        135s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre317 test_ail_safetynet test_ail_files test_ai
         90s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre317.py') s = p.read_text() old = '
         80s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre298 test_ail_exc_str test_ail_exception_conte
         66s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre317.py') s = p.read_text() old = '
         66s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre317.py') s = p.read_text() old = '
         66s bash   python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail_pre317.py') s = p.read_text() old = '
         65s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre317 test_ail_safetynet 2>&1 | tail -50

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** Adds `exctext.refuse_args_item_store`, an AST pass that raises the named `Unsupported` refusal for a store/delete into a caught exception's `e.args[...]` (with simple name/list/attribute/dict alias taint), called from `pyfunc._to_c_once` and `pyboxed2.Compiler.compile`; no code generation changes.

**Report claims**
- Selected first still-differing item: **verified for `e.args[0]`** — base runs it and differs only in stderr traceback; HEAD refuses by name on both builds. The other listed item (multi-argument `raise` on the forced general path) is already a named refusal (`p2`).
- Wired into typed and general builds: **verified** in the diff; `p1` refused by name on both.
- Listed refused forms / value and alias routes: **verified** by `test_ail_pre317` (23.7 s), plus my `p1`, `p8`, `p9`, `p10`.
- Reading `e.args[i]`, whole `e.args` store, nested argument object store, non-exception `args` and handler rebinding: **verified** (`p2`, `p12`, `p3`, `p11`, `p9`, `p10`, `p5`).
- Parameter-store case remains pre-existing traceback-only difference: **verified** (`p13`: HEAD and base identical).
- Tests/records/manifest: **verified** — `test_ail_pre317`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` and the four extra exception modules all pass; `update_manifest.py --check` passes; commits carry the required trailer.
- Feature-free program C unchanged: **verified** — `plain.py` `program.c` is byte-identical to base on both the typed and forced-general builds.
- "Non-exception objects' `args` lists left unchanged": **mostly verified**; false for one mutation boundary — `p4` (`xs=[e]; xs.pop(); xs.append(Box()); xs[0].args[0]=9`) compiled and matched on base but is newly refused by name because list mutation via methods is not tracked. This is a named refusal, acceptable under the review rules, but the claim is not exhaustive.

**Probes (`/tmp/rprobes`, HEAD vs base where relevant)**
`p1` refused both; `p2/p12` read-only match; `p3` whole-`args` store matches; `p4` HEAD refuses where base matched (named, acceptable); `p5` nested-function shadowing matches; `p6` nested-handler store matches stdout/exit but stderr traceback differs (same on base); `p7` nested-class named refusal (pre-existing); `p8` slice store refused; `p9/p10` attribute/dict rebinding matches; `p11` store inside argument object matches; `p13` parameter store matches base.

**Pre-existing**
- `e.args[i]` store inside a nested handler reaching the outer `e` still has only the last stderr line equal (`p6`, identical on base).
- Forced-general multi-argument `raise` refusal (`p2`) and nested-class refusal (`p7`).

**Unverified:** full suite, exact “82 tests / 1 skipped” count, icount speed (change is compile-time only, not hot code).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1896310, "input": 69421, "output": 7729, "reasoning": 20888, "cache.write": 0, "cache.read": 1798272}]
    tool time: bash 4.9 min
        106s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings
         80s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre298 test_ail_exc_str test_a
         67s bash   date; cd AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_pre317 test_ail_safetynet 2>&1
         18s bash   date; for p in /tmp/rprobes/p*.py; do echo "===== $p"; timeout 240 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail
          6s bash   date; for p in p4_rebind_list p6_nested_handler; do echo "===== $p base"; timeout 240 bash ~/tools/cmp.sh /tmp
          5s bash   cat > /tmp/rprobes/p13_param_store.py <<'EOF' def setit(x) -> None:     x.args[0] = "z"   def main() -> None: 
          4s bash   date; for p in p11_nested_item p12_read_one; do echo "===== $p"; timeout 240 bash ~/tools/cmp.sh /tmp/rprobes/
          3s bash   date; timeout 240 bash ~/tools/cmp.sh /tmp/rprobes/p1_basic.py /tmp/base 2>&1 | tail -12

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T07:19:02Z
