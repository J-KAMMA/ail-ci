# job job-ex35-10291432  started 2026-10-29T05:46:27Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"79d15a9e-a857-495e-a14f-f78a6313afe2","session_id":"2edd2aa9-0859-4833-b1f8-f94d795defaf"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"55de0873-bff6-417c-8d7a-f3ee7e0015ff","session_id":"0dc077a5-5fb5-42e9-9c56-7daf80f2c343"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `2cd3af1`.

**Refusal survey**
- 20 Python-syntax examples: 14 `.py` + 6 Python-parseable `.ail`.
- 6 `.ail` build (`use_math.ail` with `--module math.ail`); `c_headers_workflow/table_crc.py` builds.
- `c_export/geometry.py` was the only exactly supportable refusal: `not in the subset: the decorator on def add ...`.
- The other 12 `.py` files are host scripts refused for `__file__`, host-only imports (`pyfunc`, `benchmark_current_rows`, local `table_crc`), module-name collisions, `Path`/`os.environ`; not supportable exactly.

**Change**
`ail_ffi_lower.py` now strips a bare/`@export()`/`ail_ffi.export` decorator for an ordinary compile when CPython’s own decorator accepts the function, and refuses every other form by name. A called form with arguments (`@export(expr)`) is explicitly refused so CPython would not silently evaluate-and-drop the argument.

**Probes** (`/tmp/probes/ex35`, both builds via `cmp.sh`)
- Match CPython: `p01_geometry`, `p02_routes` (argument/list/dict), `p03_forms`, `p04_future_scalar`, `p_bare`, `p_call`, `p_dataclass_param`, `p_future`, `p_import_no_export`, `p_lru`, `p_module`, `p_none`, `p_routes_valid`, `p_star`, `p_types`.
- Refused by name: `p05_attr`/`p_attribute_route`/`p_routes` (attribute-held function), `p06_export_args`, `p07_export_undefined_arg`, `p_method`, and `bad01`–`bad11` (defaults, missing annotations/result, `list[str]`, positional-only, bad dataclass field, dataclass result, reversed `@lru_cache`, import alias, future dataclass, shadowed `int`). `bad09`/`bad11` are valid CPython but conservatively refused by existing import/shadow screens.
- `p_other_decorator`: general path refuses by name, default matches; pre-existing and unrelated.

**Tests on final commit**
- `test_ail_ex35`: 5/5 pass.
- Required set: 78 tests, 77 pass, 2 skipped, 1 environmental failure: `test_ail_c_export.test_rust_host_matches_cpython` because rustup has no default toolchain on this runner.
- `tools/update_manifest.py` run; `--check` clean.
[cost $0.0363, opencode tokens {"total": 2396821, "input": 102534, "output": 9823, "reasoning": 13616, "cache.write": 0, "cache.read": 2270848}]
    tool time: bash 17.7 min, edit 0.0 min
        617s bash   cd AIL_CURRENT && python3 -m unittest test_ail_ex35 test_ail_ffi test_ail_c_export test_ail_check test_ail_saf
        114s bash   cd /tmp/probes/ex35 && export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT && for p in p*.py bad*.py; do 
         95s bash   cd /tmp/probes/ex35 && export PYTHONPATH=/home/runner/work/_temp/w2/AIL_CURRENT && for p in p*.py bad*.py; do 
         45s bash   cd AIL_CURRENT && python3 -m unittest test_ail_ex35 -v 2>&1 | tail -30
         41s bash   cd AIL_CURRENT && python3 -m unittest test_ail_ex35 2>&1 | tail -8
         40s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('DEVLOG.md') s=p.read_text(
         39s bash   cd AIL_CURRENT && python3 -m unittest test_ail_ex35 -v 2>&1 | tail -60
         24s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' > /tmp/probes/ex35/buildlist.log 2>&1 import ast, pathlib, 

## review 0 skipped: only 19 minutes left

FINAL VERDICT: ERROR  2026-10-29T10:21:52Z
