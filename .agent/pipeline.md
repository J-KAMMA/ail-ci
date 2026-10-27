# job job-rbpre322-10271910  started 2026-10-27T10:15:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"b81eadcf-3f55-4994-b93c-ccb38932bb81","session_id":"3f53c738-1480-4eb7-849d-ef2f22fcf6e1"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"3cc11d55-b2ca-4b31-b250-0edb48cce2a5","session_id":"b42a9ded-1f24-4b37-a01f-9ac449e4711d"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied pre322 and committed on `job-rbpre322-10271910` as `f5678ad`.

- Merge kept both fixes: pre322's alias-aware `_scope_constant_map`/`program_bound` and pre319's class-attribute map (`attributes`) in `_Int64CallChecker` and `_check_int64_literals`.
- Registered `test_ail_pre322` in `ail_check.py`, `ci_shards.json`, and `MANIFEST.json`; added DIFFERENCES row and DEVLOG entry.
- `tools/diff_ids.py` is absent on this tree, so it could not be run. `tools/update_manifest.py` and `--check` pass.

Probes: 20 in `/tmp/probes`, both builds via `cmp.sh`.
- `p01`-`p10`: refused by name (`int() of a float outside int64 ... big integer`) for module/function/chain/tuple/dict/negative/boundary/inline/builtin-`len` aliases.
- `p11`-`p20`: matched CPython (in-range boundaries, mutated/rebound/empty aliases, `len`/`repr` shadows, argument/list-item/attribute/dict-value routes).

Final-commit tests: `test_ail_pre322`, `test_ail_pre319`, `test_ail_pre39`, `test_ail_pre290` — 7 tests OK; `test_ail_pre302`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 29 tests OK, 1 skipped.
[cost $0.0000, opencode tokens {"total": 1989976, "input": 63382, "output": 8505, "reasoning": 7433, "cache.write": 0, "cache.read": 1910656}]
    tool time: bash 20.1 min, write 0.0 min, edit 0.0 min
        520s bash   python3 -m unittest -v test_ail_pre302 test_ail_safetynet test_ail_files test_ail_corpus_findings3 > /tmp/test
        222s bash   python3 -m unittest -v test_ail_pre302 test_ail_safetynet test_ail_files test_ail_corpus_findings3 > /tmp/fina
        198s bash   python3 -m unittest -v test_ail_pre322 test_ail_pre319 test_ail_pre39 test_ail_pre290 > /tmp/final_a.log 2>&1;
        156s bash   python3 -m unittest -v test_ail_pre319 test_ail_pre39 test_ail_pre290 > /tmp/tests_a.log 2>&1; rc=$?; tail -12
         52s bash   python3 -m unittest -v test_ail_pre322 > /tmp/pre322_test.log 2>&1; rc=$?; tail -25 /tmp/pre322_test.log; echo
         49s bash   for p in /tmp/probes/p*.py; do echo "=== $(basename "$p")"; bash ~/tools/cmp.sh "$p" "$PWD"; done > /tmp/probe
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre322-10271547 2>&1 | tail -5 && git rev-parse FETCH_HEAD
          1s bash   pwd && git status --short && git branch --show-current && git log --oneline -3

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: re-apply pre322

**What the change really does:** Adds `_all_bound_names`, `_escaped_constant_names`, `_scope_constant_map` and a per-scope `value_scopes` stack to `_Int64CallChecker`, so flat list/tuple/dict literals and their aliases are folded for the `int(float)` int64 check only when the name does not escape; scales the same folding to function/class/comprehension scopes; wires pre319's `attributes` map alongside the new `program_bound`. Test/registrations/DEVLOG/DIFFERENCES/manifest updated. Matches the reported intent.

**Probes (both builds, `cmp.sh`; base compared where relevant):**
- `r01` alias mutated before `int` → both match CPython.
- `r02` dict mutation through alias → match.
- `r05` in-range tuple alias → match.
- `r06` alias-chain mutation → match.
- `r08` augmented/subscript mutation → match.
- `r10` alias via dict item then mutation → match.
- `r11`/`r12` module mutation observed by a closure → match.
- `r13` in-range values via list item / dict value / alias → match.
- `r14` mutation after call → match.
- `r17` ±0.0 → match.
- `r03` local scalar `1e300` → named refusal (acceptable; base hit runtime overflow).
- `r07`, `hello.ail`: `--debug-dir` `program.c` byte-identical to base → non-feature codegen unchanged.
- Pre-existing (identical on base, not blocking): `r04` non-mutating call escape and `r09` attribute-held value still hit runtime `integer overflow`; `r15`/`r16` default-build stderr wording differs from CPython (`inf`/`nan`), same on base. Exit/stdout match.

**Tests on HEAD:** `test_ail_pre322`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (349 s). `update_manifest.py --check` rc=0.

**Claim check:** commit `f5678ad`/message/Co-Authored-By verified; both-side merge verified; registrations in `ail_check.py`, `ci_shards.json`, `MANIFEST.json`, DIFFERENCES and DEVLOG verified; `tools/diff_ids.py` genuinely absent (not in `work`, HEAD or `FETCH_HEAD`); test file blob identical to pre322's. Speed check not applicable — the diff changes only compile-time analysis, not emitted C.

Unverified: did not re-run all 20 worker probes individually; relied on their results file plus my own probes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1483344, "input": 51072, "output": 5520, "reasoning": 12352, "cache.write": 0, "cache.read": 1414400}]
    tool time: bash 7.5 min
        351s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre322 test_ail_safetyn
         41s bash   cd /tmp/rprobes && for p in r*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-ci 
         18s bash   cd /tmp/rprobes && cat > r11_closure_mut_before.py <<'EOF' items = [1e300] def f():     alias = items     retu
         13s bash   cd /tmp/rprobes && for p in r04_call_escape.py r09_dict_attr_route.py r03_local_scalar.py; do echo "=== BASE $
         13s bash   cd /tmp/rprobes && cat > r15_inf_alias.py <<'EOF' items = [float('inf')] alias = items print(int(alias[0])) EO
          7s bash   cd /tmp/rprobes && for p in r15_inf_alias.py r16_nan_alias.py; do echo "=== BASE $p"; bash ~/tools/cmp.sh "$p"
          6s bash   cd /tmp && rm -rf dbg && mkdir -p dbg/base dbg/head && cd /home/runner/work/ail-ci/ail-ci && cp /tmp/rprobes/r
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree list; git worktree add /tmp/base work 2>&1 | tail -3; ls /t

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T11:59:30Z
