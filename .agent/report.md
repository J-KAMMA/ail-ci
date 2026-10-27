# job job-pre321-10271546  started 2026-10-27T06:46:55Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"7150ef7a-f699-4d80-a3ed-87f16be46c21","session_id":"cfb0ee29-6024-4ab4-928d-5d06c29e4d16"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"aa08c490-2fd6-412e-90a1-2ae1f68fed19","session_id":"63441ead-7741-4968-a550-26537273e90d"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first pre-existing difference: default-build `b ** e` with a computed negative integer exponent now matches CPython (`2 ** -1` → `0.5`).

- Change: `pyfunc._etype` routes a `**` with a non-constant integer exponent to the general path, whose tagged values return int for non-negative exponents and float for negative ones. Constant exponents keep their old lowering.
- Reproduced before the fix: default build exited 1 with `negative exponent on an integer...`; general path printed `0.5`. Both match after.
- Probes `/tmp/probes/pre321/p01`–`p15`: variables, locals, arguments, list items, attributes, dict values, aliases, positive exponents, zero/underflow, bools, negative bases and float bases — all match CPython on both builds.
- Tests: `test_ail_pre321`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` = 4 modules, 342 s, 0 failed. Also `test_ail_pre265/pre273/pre305` = 0 failed.
- `update_manifest.py --check` passes; `ci_shards.py --check` reports only the pre-existing `test_ail_pre61` / `test_ail_pre126` duplicates.
- The review’s second pre-existing item, out-of-int64 integer powers, is unchanged.

Committed as `d8bba6a`; not pushed.
[cost $0.0000, opencode tokens {"total": 6160919, "input": 119804, "output": 10493, "reasoning": 18846, "cache.write": 0, "cache.read": 6011776}]
    tool time: bash 8.6 min
        345s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         60s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre2
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre321/p*.py; do echo "=== $(basename "$f") ==="; t
         40s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre321/p*.py; do echo "=== $(basename "$f") ==="; t
         22s bash   cd /tmp/probes/pre321 && cat > p11_positive_routes.py <<'EOF' class Box:     def __init__(self):         self.
          2s bash   timeout 60 git fetch --no-tags origin job-pre305-10271259 2>&1 | tail -3; git show FETCH_HEAD:.agent/report.md
          0s bash   find /home/runner -path /home/runner/work/ail-ci -prune -o -path /home/runner/.qoder -prune -o -path /home/run
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('DEVLOG.md') s = p.re

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** In `pyfunc._etype`, an `int ** int` power whose exponent is not a compile-time constant now raises `Unsupported`, so the whole program is rebuilt on the existing general path (tagged values). Constant exponents and float operands keep the old lowering. This matches the report.

**Probes** (`/tmp/rprobes`, both builds, HEAD vs `/tmp/base`):
- `r01_var_positive` — variable/variable positive exponents: matches CPython on both, base too.
- `r03_routes`, `r09_var_negative_only`, `r11_attr_dict_neg`, `r12_unary_exp`, `r14_huge_neg` — negative exponents via locals, arguments, aliases, list items, attributes, dict values, unary exponent, huge negative exponent: HEAD default now matches; base default exits 1.
- `r04_sizes`, `r05_bool_float_exp`, `r10_contexts`, `r13_zero`, `r15_const_and_float`, `r16_annotations`, `r17_globals` — sizes 0/62/−1074/−2000, bool and float exponents, zero division, expressions in list/dict/f-string/if/sum, annotations, module globals: match CPython.
- `r06_overflow` — out-of-int64 `10 ** 19`: both builds stop `integer overflow`; identical on base.
- `r02_var_negative` — includes constant base `10 ** e`; refused by name identically on base.
- `r07_nonfeature` — `--debug-dir` `program.c` byte-identical to base; `r15` constant/float-power C also identical.
- Worker's `p01`–`p15` rerun on HEAD: all 15 match CPython on both builds.

**Claims:** Fixed difference verified. Change description verified. Pre-fix reproduction verified (`2 ** -1`: base default exit 1, general prints `0.5`). Manifest `--check` passes; `ci_shards --check` only reports `test_ail_pre61`/`test_ail_pre126`. `test_ail_pre321` (5 s) and `test_ail_safetynet` (126 s) pass, 0 failed. Second pre-existing item (out-of-int64 powers) unchanged, verified.

**Speed:** `gdev/g02_034` now takes the general path (`built on the general path ... because a power whose integer exponent is not a constant...`), 0.01 s base → 0.06 s HEAD (6×, consistent over 5 runs); output identical. This is the unavoidable cost of the permitted whole-program fallback, not a correctness defect.

**Pre-existing:** out-of-int64 integer powers; constant-base variable-exponent refusal; general path accepting a CPython `SyntaxError` global-usage program.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3` and the worker's `test_ail_pre265/pre273/pre305` reruns (per review scope); instruction counts (`perf_event_paranoid=4`).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1656687, "input": 54046, "output": 8189, "reasoning": 13268, "cache.write": 0, "cache.read": 1581184}]
    tool time: bash 5.9 min, write 0.0 min
        128s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         65s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/pre321/p*.py; do out=$(bash ~/tools/cmp.sh "$f" "$P
         34s bash   for f in /tmp/rprobes/r09*.py /tmp/rprobes/r1*.py; do echo "===== HEAD $(basename $f) ====="; bash ~/tools/cmp
         34s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/r*.py; do echo "===== HEAD $(basename $f) ====="; 
         30s bash   cd /tmp/base && for f in /tmp/rprobes/r*.py; do echo "===== BASE $(basename $f) ====="; bash ~/tools/cmp.sh "$
         22s bash   for f in /tmp/rprobes/r13*.py /tmp/rprobes/r14*.py /tmp/rprobes/r15*.py; do echo "===== HEAD $(basename $f) ==
         16s bash   for f in /tmp/rprobes/r16*.py /tmp/rprobes/r17*.py; do echo "===== HEAD $(basename $f) ====="; bash ~/tools/cm
         12s bash   cd /tmp && rm -rf sp && mkdir sp && cd sp && for f in g02_034 g17_024; do cp ~/corpus/gdev/$f.py .; for w in h

## full suite
test_ail_dunders

## worker report (suite fix)
[model opencode/deepseek-v4.1-flash-free]
Fixed the regression and committed as `5eca65f`.

`test_ail_dunders` failed because the new computed-exponent fallback also rejected the annotated `-> int` `__pow__` method, which must build on the typed path alone. The power typing now keeps `ail_ipow` for functions explicitly returning `int`, while unannotated functions still fall back to the general path for CPython-compatible negative exponents.

Verified: `test_ail_dunders`, `test_ail_pre321`, `test_ail_pre273`, `test_ail_pre294`, and `test_ail_pre265` all pass. Manifest updated and checked.
[cost $0.0000, opencode tokens {"total": 2329736, "input": 80105, "output": 5589, "reasoning": 10826, "cache.write": 0, "cache.read": 2233216}]
    tool time: bash 4.0 min
         63s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre273 test_ail_pre294 test_ail_pre265 2>&1 | tail -30
         60s bash   cd AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('python/pkg-v12/pyfunc.py') s=p.read_text()
         54s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_dunders 2>&1 | tail -80
         53s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_dunders 2>&1 | tail -40
          5s bash   cd AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('python/pkg-v12/pyfunc.py') s=p.read_text()
          3s bash   cd AIL_CURRENT && cp python/pkg-v12/pyfunc.py /tmp/pyfunc.py.bak && python3 - <<'PY' from pathlib import Path 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/pyfunc.py D

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T09:48:26Z
