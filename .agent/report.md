# job job-perf4-10270016  started 2026-10-26T15:17:34Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":380,"duration_api_ms":252,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":377,"duration_api_ms":252,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `35eb44f` on `job-perf4-10270016`.

**Cause:** `utf8_stream.ail` gained `_utf8_tail_complete`, but `STANDARD_SOURCE_API.json` still pinned the old SHA, so `export_sdk` refused all exports (`stale or missing standard API dependency`). Updated both catalog hashes; no compiler/runtime behavior changed.

**Tests**
- 9 named task modules present on this branch + `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_utf8_stream_fuzz`: **13/13 pass** (429 s).
- `test_ail_pre110` is absent from this branch. On an `origin/integ` worktree with the two perf4 code changes + this catalog fix applied: **10/10 named modules pass** (231 s), including `test_ail_pre110`.
- `tools/update_manifest.py --check`: clean.

**Probes**
- `leaf_inline_int.py`: both builds match CPython.
- `leaf_inline_float.py`: both builds match CPython.
- `utf8_chunk_boundaries.py`: refused by name in both builds (`codecs` not in subset).
- UTF-8 change covered by passing `test_ail_utf8_stream_fuzz` (600 randomized chunk streams).
[cost $0.0326, opencode tokens {"total": 2708830, "input": 73112, "output": 8990, "reasoning": 13992, "cache.write": 0, "cache.read": 2612736}]
    tool time: bash 12.2 min, edit 0.0 min
        431s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_grid_return test_a
        234s bash   cd /tmp/ail-integ && timeout 1800 python3 tools/par_check.py -j 2 test_ail_grid_return test_ail_numeric_bindin
         35s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_grid_return test_a
         17s bash   mkdir -p /tmp/probes && cat > /tmp/probes/leaf_inline_int.py <<'PY' def leaf(values, bias):     total = bias  
          5s bash   cd AIL_CURRENT && timeout 300 python3 -m unittest -q test_ail_grid_return 2>&1 | tail -60
          3s bash   mkdir -p /tmp/probes && printf 'print(1 + 2)\nfor i in range(3):\n    print(i)\n' > /tmp/probes/simple.py && b
          2s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 git fetch --no-tags https://github.com/J-KAMMA/ail-ci integ:
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add --detach /tmp/ail-integ origin/integ 2>&1 | tail -5 && 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: job-perf4-10270016 (commit 35eb44f)

**What the change really does:** updates the `utf8_stream` SHA-256 in `STANDARD_SOURCE_API.json` (module row + `dependency_pins`), the same catalog hash twice in `MANIFEST.json`, and adds a DEVLOG entry. No compiler/runtime/lib source changed. This matches the report.

**Verified**
- Actual `language_examples/utf8_stream.ail` hash is `24bc7059...`; catalog row and pin both equal it. A scan of every catalog pin/module hash vs. file contents found **0 mismatches**; the old `e1625b...` appears nowhere.
- `tools/update_manifest.py --check` exits 0.
- HEAD: 13 modules pass (`test_ail_sdk`, `test_ail_grid_return`, `test_ail_safetynet`, `test_ail_numeric_bindings`, `test_ail_numeric_profiles`, `test_ail_numeric_profiles_native`, `test_ail_record_initializers`, `test_ail_sdk_environment`, `test_ail_tcp_json_deadlines`, `test_ail_tcp_json_lines_poll_resources`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_utf8_stream_fuzz`).
- Base (`/tmp/base` = `work`): `test_ail_sdk` and `test_ail_grid_return` fail with `stale or missing standard API dependency: language_examples/utf8_stream.ail`; `test_ail_safetynet` passes. This confirms the cause and the fix.
- `test_ail_pre110` is absent from this branch, as claimed.
- Worker probes rerun: `leaf_inline_int`/`leaf_inline_float` match CPython in both builds; `utf8_chunk_boundaries` is refused by name in both.
- My probes (`simple.py` with args/list item/attribute/dict/negative, `emptyish.py`, `mutation.py`, `b64.py`): both builds match CPython. `program.c` for `simple.py` is byte-identical between HEAD and base (only temp/debug paths differ in `native_report.json`).

**Unverified**
- The report's `origin/integ` experiment (10/10 including `test_ail_pre110`). Note: `origin/integ` here still carries the old `utf8_stream.ail` (`e1625b...`); the pin update is only consistent together with the branch's earlier UTF-8 source change, which `origin/job-perf4-10270016` does contain.

**Pre-existing:** none observed.

VERDICT: ACCEPT
[cost $0.0157, opencode tokens {"total": 658462, "input": 30760, "output": 4529, "reasoning": 10821, "cache.write": 0, "cache.read": 612352}]
    tool time: bash 10.0 min
        224s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_sdk test_ail_grid_r
        211s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_numeric_bindings t
        123s bash   cd /tmp/base && timeout 900 python3 tools/par_check.py -j 2 test_ail_sdk test_ail_grid_return test_ail_safetyn
         20s bash   cd /tmp/rprobes && for p in simple emptyish mutation b64; do echo "=== $p HEAD"; bash ~/tools/cmp.sh /tmp/rpro
         17s bash   cd /tmp/probes && for p in leaf_inline_int leaf_inline_float utf8_chunk_boundaries; do echo "=== $p"; bash ~/t
          3s bash   cd /tmp/rprobes && rm -rf /tmp/dbgH /tmp/dbgB && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add --detach /tmp/base work 2>&1 | tail -3; ls /tmp/base/AI
          0s bash   git branch -a | head -30; echo ---; git rev-parse work 2>/dev/null || echo "no work ref"; echo ---; git log --

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T16:53:57Z
