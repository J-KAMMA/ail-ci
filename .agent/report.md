# job job-pre115-10251611  started 2026-10-25T07:46:38Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":534,"duration_api_ms":412,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":524,"duration_api_ms":407,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed.

- Root cause: typed `pydiv`/`pymod` raised `AIL_EXC_ZERODIV` from parallel workers, corrupting the exception stack; `test_ail_typed_tuples` intermittently SIGSEGV'd. The helpers now use `ail_par_trap` on workers and PAR re-raises the recorded message/code on the calling thread.
- Merged current `origin/integ` so `test_ail_pre166` is present; no conflict markers remain.
- Final commit: `852ad78` (plus merge `8fd24b0`), no push.

Probes in `/tmp/probes` via `cmp.sh`, all matched CPython on both builds:
`p1_par_int_map`, `p2_par_float_map`, `p3_routes`, `p4_par_tuple_map`, `p5_widths` (p5 omits the pre-existing `INT64_MIN // -1` overflow).

Final commit tests: 48 tests, OK (1 skipped), including `test_ail_pre115`, `test_ail_typed_tuples`, `test_ail_pre166`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. Also passed earlier on the same code: `test_ail_parallel_for` (6), `test_ail_typed_parallel` (14). Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 8131118, "input": 154058, "output": 18506, "reasoning": 24730, "cache.write": 0, "cache.read": 7933824}]
    tool time: bash 14.6 min
        363s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_safetynet test_ail_files tes
        184s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_pre115 test_ail_typed_tuples
        107s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 -m unittest -q test_ail_pre115 test_ail_typed_tuple
         46s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre166 2>&1 | tail -50
         44s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 -m unittest -q test_ail_parallel_for > /tmp/t3.log 
         31s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -60
         30s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_typed_tuples 2>&1 | tail -40
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/p1_par_int_map.py /tmp/probes/p2_par_float_map.py /

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does.** The substantive worker delta (vs the integrated base `ffeb623`) is the pre‑115 typed zero‑division fix: int/float `//`, `%`, `/` by zero now raise catchable `ZeroDivisionError` with CPython's messages; on a typed parallel worker the typed `//`/`%` helper traps via `ail_par_trap`, and `ail_par_go_wide` re‑raises the recorded message/code on the calling thread. The merge `8fd24b0` brings the current integration branch (including `test_ail_pre166`) and `852ad78` only edits the DEVLOG. This matches the report's description.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD vs base `/tmp/base` at `work`):

| probe | HEAD result |
|---|---|
| `p1_par_int_div` (//,%,/ by 0 in map, w=1/4, caught) | matches CPython both builds |
| `p2_par_float_div` (//,%,/ incl. -0.0 in map, w=1/4, caught) | matches both |
| `p3_widths` (int/float/bool/mixed, list/dict/attr/arg, caught) | general okay; default = same failure as base (see below) |
| `p4_par_uncaught` (float `/` in map, uncaught) | `g` matches; `d` differs, **identical on base** |
| `p5_no_feature` (lists/dicts/loops, no division) | matches both |
| `p6_lambda_list` (lambda in list called via parameter, caught) | `d` differs, **identical on base and on integ** |
| `p7_int_true_uncaught` (int `/` in map, uncaught) | matches both |
| `p8_float_floor_uncaught` (float `//` in map, uncaught) | `g` matches; `d` differs, **identical on base** |

**Pre-existing (base and HEAD identical; not blocking):**
- `p4`/`p8` default build: when the failure happens in a real worker, `ail_fdiv_f`/`ail_ffloormod` reach `ail_die(..., code 0)`, so after the join the new `msg && code` branch is skipped: stdout loses already-computed results (`-50.0`, `-100.0`) and stderr is a bare `float division by zero` / `float floor division by zero` instead of `ZeroDivisionError: ...` (exit still 1). This contradicts the DEVLOG claim that uncaught float map cases match on both builds, but it is identical on `/tmp/base`, so it predates this job.
- `p3`/`p6`: default build does not catch `ZeroDivisionError` for a lambda stored in a list and invoked through a function parameter; identical on `/tmp/base` and on integ.

**Claims:** root cause/PAR trap+re-raise — verified by code and passing `test_ail_typed_tuples`; merge/pre166/no conflict markers — verified; commits `8fd24b0`+`852ad78` — verified; manifest `--check` — verified; final tests — verified (`pre115`, `typed_tuples`, `pre166`, `safetynet`, `files`, `corpus_findings3`, `parallel_for`, `typed_parallel`, 0 failed); "probes covered uncaught float `/`/`//` and matched" — **false** (p4/p8; pre-existing); exact "48 tests" count — not recounted; `INT64_MIN // -1` omission — unverified.

**Unverified:** worker's own `/tmp/probes` (not available); byte-for-byte C comparison of no-feature programs against `/tmp/base` (the merge legitimately changes unrelated C); speed (no hot-path change: the added check is inside the zero-divisor branch only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3017844, "input": 100546, "output": 9827, "reasoning": 30287, "cache.write": 0, "cache.read": 2877184}]
    tool time: bash 6.0 min, write 0.0 min
        129s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_files test_ai
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre166 test_a
         44s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_parallel_for 
         16s bash   date; for wt in /tmp/base /tmp/integ; do echo "########## $wt"; for p in /tmp/rprobes/p4_par_uncaught.py /tmp/
         15s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p*.py; do echo "##### $(basename $p)"; bash ~/
         12s bash   date; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "########## $wt"; for p in /tmp/rprobes/p7_
         10s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p1_par_int_div.py /tmp/rprobes/p2_par_float_di
          9s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p1_par_int_div.py /tmp/rprobes/p2_par_float_di

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T09:12:04Z
