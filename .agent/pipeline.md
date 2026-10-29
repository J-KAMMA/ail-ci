# job job-rbpre429-10290923  started 2026-10-29T00:24:28Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"12c01def-9e1a-45c2-84b6-1ca9480ce132","session_id":"4b9f4cf9-48f4-4290-b1ca-858b54165043"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"37064550-4859-4e37-8525-ca208c6ec4ff","session_id":"fe4c225e-d1b2-44e6-bbd1-9a8cc8563d11"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- Re-applied pre429 on `job-rbpre429-10290923`: kept the BIGINT arm exact (CPython match) and changed the `AIL_BIGINT=off` arm to raise catchable `OverflowError("integer overflow")` instead of the uncatchable `AIL_LIMIT` stop.
- Resolved conflicts by regenerating `tools/ci_shards.json` and adapting `test_ail_pre429.py` to cover both exact-int and int64 modes.
- Commits: `f7b0524` (code/test/records), `6565088` (DEVLOG probe-report correction).
- Probes: 9 in `/tmp/probes/pre429`; all 9 match CPython on both builds with exact ints. With `AIL_BIGINT=off`: 3 still match, 3 print the int64 catch text, 3 are the declared exit-1 `OverflowError: integer overflow` stop.
- Final-commit tests: 45 tests across pre429, fz2, pre54, pre104, safetynet, files, corpus_findings3 — all OK (1 skipped).
- `tools/update_manifest.py --check` and `tools/ci_shards.py --check` pass. `tools/diff_ids.py` does not exist in this tree or in `FETCH_HEAD`, so it could not be run.
- `.agent/pipeline.md` remains untracked and was not touched.
[cost $0.0000, opencode tokens {"total": 3533501, "input": 110974, "output": 10549, "reasoning": 11914, "cache.write": 0, "cache.read": 3400064}]
    tool time: bash 21.1 min, write 0.0 min
        742s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && printf '%s\n' test_ail_pre429 test_ail_fz2 test_ail_pre54 te
        394s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && printf '%s\n' test_ail_pre429 test_ail_fz2 test_ail_pre54 te
         67s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre429/*.py; do echo "==== $(basename "$p")"; bash 
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre429/q01_catch.py /tmp/probes/pre429/q02_except_v
         15s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre429/q04_boundaries.py /tmp/probes/pre429/q05_non
          3s bash   cd /home/runner/work/ail-ci/ail-ci && ls tools && git fetch https://github.com/J-KAMMA/ail-ci.git job-pre429-1
          0s write  /tmp/probes/pre429/q02_except_variants.py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py; echo update_rc=$?; python3 tools/updat

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** In `AIL_CURRENT/python/pkg-v12/cruntime.py:18531`, the non-BIGINT (`AIL_BIGINT=off`) arm of `ail_bi_round` now raises catchable `OverflowError("integer overflow")` via `ail_raise_c` instead of `ail_hit_limit`; the BIGINT arm still returns exact CPython integers. Tests, DIFFERENCES, DEVLOG, manifest and shard list are updated. This matches the report.

**Probes (mine, `/tmp/rprobes/p01`–`p15`):**
- Exact/default builds: all match CPython, including wide positives/negatives, `round(x,n)`, `round(x,None)`, NaN/Inf, boundaries, routes through argument/list/attribute/dict, alias mutation, and propagation through nested calls.
- `AIL_BIGINT=off`: `p06` ndigits, `p07` non-finite, `p08` in-range/-2^63, `p12` ints and `p15` alias match CPython; `p01`–`p05`, `p09`, `p13`, `p14` catch the wide value; `p04`/`p11` uncaught exit 1 with `OverflowError: integer overflow` (declared int64 stop). Base (`work`, e30e9d6) does not catch `p01`; the change is effective.
- No-feature `p10`: `--debug-dir` `program.c` is byte-identical to the base worktree; only `native_report.json` temp paths differ.
- Worker probes `q01`–`q09`: exact builds all match; int64 `q04/q05/q09` match, `q01`–`q03` catch, `q06`–`q08` declared exit-1 stop. Report classification verified.

**Tests:** `test_ail_pre429`, `test_ail_safetynet`, `test_ail_fz2`, `test_ail_pre54`, `test_ail_pre104`, `test_ail_files`, `test_ail_corpus_findings3` all pass on HEAD (45 tests, 1 skipped). `tools/update_manifest.py --check` and `tools/ci_shards.py --check` pass. `tools/diff_ids.py` is absent in HEAD and FETCH_HEAD, as reported.

**Claims:** All verified; none false. No defect found.

**Pre-existing:** int64 finite wide `round()` differs from CPython's exact big integer (declared C74/A1); base already stopped there. Not caused by this change.

**Unverified:** Full suite (not run by design); typed-path catchability beyond the existing pre54/pre104/fz2 tests; icount (change only touches the overflow path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1414429, "input": 86691, "output": 6091, "reasoning": 18991, "cache.write": 0, "cache.read": 1302656}]
    tool time: bash 26.9 min
        610s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test
        301s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre429 tes
        273s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fz2 test_a
         96s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre429/q*.py; do echo "===== $(basename $p)"; bash 
         90s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre429/q*.py; do echo "===== $(basename $p)"; AIL_B
         76s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p*.py; do echo "===== $(basename $p)"; bash ~/tool
         57s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p01_catch.py /tmp/rprobes/p02_exception.py /tmp/rp
         37s bash   cat > /tmp/rprobes/p13_propagation.py <<'EOF' def inner(v: float) -> int:     return round(v)  def middle(v: f

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T02:36:46Z
