# job job-pre200-10252051  started 2026-10-25T11:57:56Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":525,"duration_api_ms":405,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":514,"duration_api_ms":399,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre195 item: `"a b c".split(" ", 2**4096 // 2**4050)` and `2**4096 >> 4096`.

Changed `_maxsplit_const` to measure powers by exact width under an 8192-bit limit, and raised the shared int constant folder limit to 8192 bits so the same value folds through arguments, list items, attributes, dict values and locals. Final values outside int64 and intermediates above 8192 bits remain named compile-time refusals.

Commit: `373064e`

Probes (`/tmp/probes`, both g/d builds vs CPython):
- `p_pre200_div`, `p_pre200_shift`, `p_pre200_100`, `p_pre200_bound`, `p_pre200_routes`, `p_pre200_neg`, `p_pre200_bases`, `p_pre200_dynamic` — all matched CPython.
- `p_pre200_bound_over`, `p_pre200_over`, `p_pre200_literal_over` — refused by name on both builds.

Tests on final commit: `test_ail_pre200`, `test_ail_pre97`, `test_ail_pre113`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed (232s). Manifest `--check` passes.

Unverified: wider suite (per instructions); instruction-count speed (compile-time folding only).
[cost $0.0000, opencode tokens {"total": 3020819, "input": 95586, "output": 11737, "reasoning": 22104, "cache.write": 0, "cache.read": 2891392}]
    tool time: bash 5.8 min
        234s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre200 tes
         30s bash   cd /tmp/probes cat > p_pre200_bound.py <<'EOF' print("a b c".split(" ", 2**8191 // 2**8180)) EOF cat > p_pre20
         29s bash   cd /tmp/probes cat > p_pre200_div.py <<'EOF' print("a b c".split(" ", 2**4096 // 2**4050)) print("a b c".rspli
         24s bash   cd /tmp/probes cat > p_route_arg.py <<'EOF' def cut(s, sep, n):     return s.split(sep, n), s.rsplit(sep, n) p
         15s bash   grep -o '.\{0,80\}recorded these.\{0,1500\}' /home/runner/work/_temp/work0.jsonl | head -5
         12s bash   cd /tmp/probes; WT=/home/runner/work/ail-ci/ail-ci; for p in p_4096_div p_4096_shift p_direct_over p_100_div; 
          2s bash   git fetch --quiet origin refs/heads/job-pre195-10251916:refs/remotes/origin/job-pre195-10251916 && git log --o
          1s bash   grep -o '.\{0,200\}pre195.\{0,300\}' /home/runner/work/_temp/work0.jsonl | head -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed the diff (`373064e`), ran probes on HEAD and base (`/tmp/base` worktree), and re-ran the targeted modules.

**What the change really does:** raises the maxsplit power-fold limit to 8192 bits with an exact capped square-and-multiply width test, and raises the shared `int_constant` fold limit from 4096 to 8192 bits. Adds `test_ail_pre200.py`, registers it, and records the difference. Matches the report.

**Probes (HEAD, both builds):**
- `r_claim_1..4` (`2**4096 // 2**4050`, `2**4096 >> 4096`, split/rsplit): all base builds refused by name; HEAD matches CPython.
- `r_routes`, `r_neg`, `r_bound`, `r_pow65`, `r_shiftbig`, `r_zero`: HEAD matches CPython; base refused or trapped (e.g. `r_routes` base runtime `integer overflow`, HEAD matches).
- `r_over`, `r_finalover`: named maxsplit refusal (acceptable).
- Worker's `/tmp/probes/p_pre200_*`: all 10 match CPython or are named refusals on both builds, as reported.
- Plain program debug-dir build: generated `program.c` byte-identical to base; only report paths differ.

**Tests:** `test_ail_pre200` + `test_ail_safetynet`, 2 modules, 0 failed (81s). `update_manifest.py --check` passes. Did not run files/corpus modules (outside reviewer scope).

**Pre-existing (identical on base, non-blocking):**
- `r_arg_over`: an over-limit intermediate reaching split through a function argument still traps at run time with `integer overflow` on both HEAD and base, not a named refusal.
- `r_collateral`, `r_collateral2`, `r_index`: unchanged runtime `integer overflow` on both.

**Claim check:** all verified except "intermediates above 8192 bits remain named compile-time refusals", which is overbroad: true for a direct maxsplit expression, but false when the over-limit expression reaches split through an argument/value (it stays a runtime trap). This is pre-existing and not introduced by the change. Speed not measured (compile-time-only change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1321650, "input": 48293, "output": 5310, "reasoning": 17871, "cache.write": 0, "cache.read": 1250176}]
    tool time: bash 3.5 min
         83s bash   date; cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_pre200 test_ail_safetynet 2>&
         34s bash   cd /tmp/probes; for p in p_pre200_*.py; do n=${p%.py}; out=$(bash ~/tools/cmp.sh /tmp/probes/$p /home/runner/w
         20s bash   cd /tmp/rprobes; for p in r_claim r_bound r_over r_finalover r_neg r_routes r_no_feature; do echo "===== BASE 
         19s bash   cd /tmp/rprobes; for p in r_claim r_bound r_over r_finalover r_neg r_routes r_no_feature; do echo "===== HEAD 
         15s bash   cat /home/runner/work/_temp/work0.md; echo ====; grep -o '.\{0,120\}pre195.\{0,1500\}' /home/runner/work/_temp
         11s bash   cd /tmp/rprobes; for p in r_claim_1 r_claim_2 r_claim_3 r_claim_4; do echo "===== BASE $p"; bash ~/tools/cmp.s
         10s bash   cd /tmp/rprobes; for p in r_pow65 r_zero r_arg_over; do echo "===== HEAD $p"; bash ~/tools/cmp.sh /tmp/rprobes
          5s bash   cd /tmp/rprobes; cat > r_index.py <<'EOF' def main():     xs = [10, 20, 30]     print(xs[(2**5000) >> 5000])  

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:05:58Z
