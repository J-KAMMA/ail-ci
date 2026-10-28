# job job-cov22-10290434  started 2026-10-28T19:41:10Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"b2172932-0b93-4ce2-bd16-21f901958610","session_id":"b646ece2-1656-47a4-a37c-964fec29d2fd"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"64d3649d-5a28-45ff-b7fd-ac6e727ee50f","session_id":"fa8f9465-57b0-495d-bcc8-511f534dc3cc"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `52d819e` on `job-cov22-10290434`.

- **Baseline:** `lab/profile/run.py` does not exist in this tree; I used the compile shape from `lab/corpus/check.py` over all 219 programs on both builds.
- **Construct:** with imports excluded, the most frequent refusal was the untyped JSON document (`glm/t176`, `glm/t184`). `json.load(sys.stdin)` now lowers to `json.loads(sys.stdin.read())` on the general path; other file arguments stay named refusals.
- **Counts:** default `24 -> 23`, unified `24 -> 23`; excluding the 7 import refusals, `17 -> 16`. `glm/t184` now matches CPython on all three inputs on both builds.
- **Probes:** `p_types`, `p_routes`, `p_json_alias`, `p_from_load` matched CPython on both builds over 13 inputs (objects, lists, ints, negatives, floats, 1e300, strings, true, null, duplicate keys, empty, invalid, extra data). `p_refuse_file`, `p_refuse_binary`, `p_refuse_filevar`, `p_refuse_sys_alias` were refused by name on both builds.
- **Tests:** passed `test_ail_cov22` (2), `test_ail_genlib` (30), `test_ail_check` (7), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skip), `test_ail_corpus_findings3` (2). Manifest and shard checks pass.
[cost $0.0000, opencode tokens {"total": 5645954, "input": 148889, "output": 18444, "reasoning": 24413, "cache.write": 0, "cache.read": 5454208}]
    tool time: bash 27.4 min, edit 0.0 min
        900s bash   cat > /tmp/compile_all.py <<'PY' import json, os, subprocess, sys, concurrent.futures, pathlib, re, time root=
        192s bash   (python3 test_ail_files.py > /tmp/t_files.log 2>&1; echo $? > /tmp/t_files.rc) & (python3 test_ail_corpus_find
         96s bash   (python3 test_ail_check.py > /tmp/t_check.log 2>&1; echo $? > /tmp/t_check.rc) & (python3 test_ail_safetynet.p
         57s bash   mkdir -p /tmp/probes/cov22 && cd /tmp/probes/cov22 && cat > p_types.py <<'PY' import json import sys  def main
         53s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 test_ail_genlib.py > /tmp/t_genlib.log 2>&1; echo $
         50s bash   cat > /tmp/full_reasons.py <<'PY' import json,os,subprocess,sys,pathlib,concurrent.futures,re root=pathlib.Pat
         43s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 test_ail_cov22.py > /tmp/t_cov22.log 2>&1; echo $? 
         39s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_cov22.py -v

## review 0
[model opencode/deepseek-v4.1-flash-free]
Report

**What the diff really does** — One source change (`genlib.py` `_Renamer.visit_Call`): exactly `json.load(sys.stdin)` (one positional arg, no keywords, literal `sys.stdin`) is lowered to the already-existing `_ail_json_loads(sys.stdin.read())`; every other `json.load` form raises a named `Unsupported`. The rest of the diff is the new test, docs/DIFFERENCES row, manifest and shard registration. This matches the report.

**My probes** (`/tmp/rprobes`, both builds via a cmp-equivalent harness feeding stdin; `cmp.sh` also run for `p_empty`):
- `p_routes` (dict/list/str/int/float/bool/null/dupes/empty/invalid/extra/BOM, routed through arg, list item, attribute, dict value), `p_alias` (`import json as j`, `from json import load`), `p_big` (huge ints, NaN/Infinity, 5e-324, 1e400, `-0`, NUL, invalid UTF-8, trailing newlines), `p_catch`/`p_catch2` (`except json.JSONDecodeError`, BOM, CRLF), `p_partial` (readline then load), `p_mut` (alias/slice mutation), `p_empty` — all match CPython.
- Worker's own `p_types`, `p_routes`, `p_json_alias`, `p_from_load` over all 13 `inputs/*.json`: all match on both builds.
- Refusal forms (`json.load(f|open(...)|sys.stdin.buffer)`, no args, 2 args, kwargs, `*args`, `**kw`, `json.load` as value, aliased `sys`): all exit 3 with a named refusal.
- `t184`: matches CPython on all 3 corpus inputs on both builds; base refuses.
- Non-feature C unchanged: `p_plain` and `p_lib` (json.dumps/loads, no json.load) `program.c` from `--debug-dir` are byte-identical to `/tmp/base` (same sha256).

**Tests** (`par_check.py -j 2` on HEAD): `test_ail_cov22`, `test_ail_genlib`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` both exit 0.

**Claims**
- `lab/profile/run.py` absent: verified (it does not exist).
- t184 now matches on both builds/all inputs: verified.
- Refusal probes named: verified (file/binary filevar are refused at `open()` but still named).
- "untyped JSON document (t176, t184)": **false for t176** — t176 is annotated `list[dict]` and is still refused on both builds due to `sys.stdout.reconfigure`, so only t184 is actually fixed.
- Counts `24 -> 23` (both builds): unverified (would require recompiling all 219 programs; not reproduced).
- "most frequent non-import refusal": unverified (not independently recounted).
- Manifest/shard checks: verified. Speed: not applicable (compile-time-only change; no runtime C change for non-users).

**Pre-existing (do not block)**
- Non-BMP stdin on the general path: raw astral chars fail with `stdin code point above U+FFFF` (same on base plain `sys.stdin.read()`); JSON `\uD83D\uDE00` escapes give `ValueError: a surrogate escape ...` both for `json.loads` on base (`/tmp/base`) and now for `json.load` on HEAD. Identical failure, inherited from the 16-bit runtime, not introduced by the helper forwarding.

**Unverified** — exact before/after corpus refusal counts; independent recount of "most frequent construct".

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2194253, "input": 70795, "output": 9632, "reasoning": 24354, "cache.write": 0, "cache.read": 2089472}]
    tool time: bash 9.4 min
        310s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_cov22 test_ail_gen
         45s bash   cd /tmp/rprobes && python3 - <<'PY' import sys, pathlib; sys.path.insert(0,'/tmp/rprobes') import harness D=pa
         37s bash   cd /tmp/rprobes && python3 - <<'PY' import re p='/tmp/rprobes/harness.py'; s=open(p).read() s=s.replace("src =
         28s bash   cd /tmp/rprobes && python3 - <<'PY' import sys, pathlib; sys.path.insert(0,'/tmp/rprobes') import harness root
         21s bash   cd /tmp/rprobes && cat > p_loads_ref.py <<'PY' import json import sys  data = json.loads(sys.stdin.read()) pri
         15s bash   cd /tmp/rprobes && date && python3 - <<'PY' import sys, pathlib; sys.path.insert(0,'/tmp/rprobes') import harn
         14s bash   cd /tmp/rprobes && cat > p_big.py <<'PY' import json import sys  data = json.load(sys.stdin) print(type(data).
         13s bash   cd /tmp/rprobes && cat > p_astral.py <<'PY' import json import sys  try:     data = json.load(sys.stdin) excep

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T21:43:17Z
