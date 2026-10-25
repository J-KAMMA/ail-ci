# job job-pre201-10260354  started 2026-10-25T18:54:22Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":393,"duration_api_ms":275,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":416,"duration_api_ms":298,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Merged current integration (`f40ac27`) so `test_ail_pre190` was reproducible, then fixed the clash.

**Fix (commit `90b60f0`)**
- Added `_const_fold_int` in `ail_chatgpt.py`, mirroring the pre190 folder: zero/base 0/1/-1 shortcuts, 2**20-bit budget (2**24 for such exponents).
- Used it for the pre201 constant-shift/power value and parent climb. Out-of-int64 shifts are still refused by name; pre190 reductions now fold.
- `((10**64)**64) >> 100001` now folds to CPython's `0`, so `test_ail_pre201` records it as in-range.
- Updated DEVLOG/DIFFERENCES; manifest and CI-shard `--check` pass.

**Tests on final commit**
- Pass: `test_ail_pre190`, `test_ail_pre201`, `test_ail_pre184`, `test_ail_pre113`, `test_ail_pre177`, `test_ail_pre97`, `test_ail_pre172`, `test_ail_pre214`, `test_ail_pre205`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (12/13).
- `test_ail_pre195` fails, but identically on unmodified `origin/integ` (verified in a separate worktree): its `2**4096 // 2**4050` maxsplit expectation predates the pre190 2**20 budget. Not caused by this change.

**Probes** (`/tmp/probes`, both builds)
- `p201_{direct,arg,list,attr,dict,assign}_refuse.py`: refused by name `int64 constant out of range: 18446744073709551616`.
- `p201_inrange.py`, `p201_pre190_reduce.py`, `p201_pre190_flows.py`, `p201_pre190_maxsplit.py`, `p201_nestedpow.py`: match CPython on both builds.
- `p201_module_reduce.py`: module-level `(1 << 5000) >> 5000` is refused by name (pre-existing 4096-bit module/class folder), so allowed by the probe rule.
[cost $0.0000, opencode tokens {"total": 4891485, "input": 124815, "output": 12102, "reasoning": 28296, "cache.write": 0, "cache.read": 4726272}]
    tool time: bash 5.5 min, write 0.0 min, edit 0.0 min
        238s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 test_ail_pre190.py test_ail
         27s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_pre190.py test_ail
         26s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_pre190 2>&1 | t
         13s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add --detach /tmp/integwt origin/integ >/tmp/wt.log 2>&1 &&
          9s bash   cd /tmp/probes && for p in p201_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "/tmp/probes/$p" /home/runner/wo
          7s bash   mkdir -p /tmp/probes && cd /tmp/probes && for n in 15 16 17 18; do python3 - <<PY lines = '''class Box:     de
          2s bash   cd /tmp/probes && for p in p201_pre190_flows.py p201_module_reduce.py; do echo "===== $p"; bash ~/tools/cmp.sh
          2s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 git fetch --no-tags origin integ refs/heads/job-pre190-10252

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** merges integration `f40ac27`, then replaces the pre201 constant check's old evaluator/4096-bit climb with `_const_fold_int` (zero/0/1/-1 shortcuts, 2**20-bit budget, 2**24 for special exponents) shared with the pre190 folder, and moves `((10**64)**64) >> 100001` from refused to in-range. This matches the report.

**Probes** (`/tmp/rprobes`, both builds, `~/tools/cmp.sh`):
- `p190_core`, `p190_maxsplit`, `p190_edges`, `p190_e01..e17`: match CPython on HEAD. On `/tmp/base` (work) `p190_core` and `p190_maxsplit` fail (large-int refusal/`integer overflow`), reproducing the reported regression.
- `p201_inrange`, `p201_refuse`, `p_big_inrange`, `p_bound_under`: match CPython both builds.
- `p_big_over`, `p_big_maxsplit`, `p_bound_at`, `p_bound_max_at`, `p_idx_big`, `p_idx64`, `p_ret_shift`: named compile-time refusals (acceptable).
- `p_module_reduce` (module-level `(1<<5000)>>5000`): named refusal on both HEAD and f40 → pre-existing.
- Non-feature program: `program.c` identical to base work and to f40 (only `native_report.json` paths differ).
- Fuzzed `_const_fold_int` against Python on 18,753 generated constant expressions: 0 wrong values.

**Tests (HEAD, `-j 2`):** pass `test_ail_pre190`, `test_ail_pre201`, `test_ail_pre184`, `test_ail_pre113`, `test_ail_pre177`, `test_ail_pre97`, `test_ail_pre172`, `test_ail_pre214`, `test_ail_pre205`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. `test_ail_pre195` fails exactly as reported; it also fails identically on f40 `origin/integ` (verified in `/tmp/integ`), so pre-existing. `update_manifest.py --check` and `ci_shards.py --check` pass.

**Claims:** all verified. No defect found.

**Pre-existing (non-blocking):** `test_ail_pre195` expects the old 4096-bit maxsplit cap; module-level large-intermediate reductions are still refused by name on f40.

**Unverified:** full suite (not run per instructions); instruction counts (change is front-end checking only, no runtime/hot path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3887234, "input": 114283, "output": 10042, "reasoning": 31837, "cache.write": 0, "cache.read": 3731072}]
    tool time: bash 6.6 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci && date; timeout 900 python3 tools/par_check.py -j 2 test_ail_files.py test
         83s bash   cd /home/runner/work/ail-ci/ail-ci && date; timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre190.py te
         42s bash   cd /tmp/integ && date; timeout 500 python3 tools/par_check.py -j 1 test_ail_pre190.py 2>&1 | tail -8; date
         33s bash   cd /tmp/rprobes && date; for p in p190_core.py p190_edges.py p190_e*.py; do echo "===== $p"; timeout 300 bash 
         15s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/integ f40ac27 >/tmp/wti.log 2>&1; tail -2 /tmp/wti
         15s bash   cd /home/runner/work/ail-ci/ail-ci && date; timeout 900 python3 tools/par_check.py -j 2 test_ail_pre184.py tes
         13s bash   cd /home/runner/work/ail-ci/ail-ci && date; timeout 900 python3 tools/par_check.py -j 2 test_ail_pre113.py tes
         12s bash   git show work:AIL_CURRENT/ail_chatgpt.py | grep -nE '_check_int64_constants|_constant_int_exact|_CONST_INT_BIT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T20:15:34Z
