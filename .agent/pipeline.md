# job job-rbpre190-10252302  started 2026-10-25T14:06:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":336,"duration_api_ms":212,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":313,"duration_api_ms":189,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied pre190 onto the current tree, preserving the existing exact `_pow_within_maxsplit_bits` guard while adding the zero/base reductions and shared fold cap.

- Commit: `d3ab969`
- Manifest: updated; `--check` rc 0
- Probes (`bash ~/tools/cmp.sh ... $PWD`, all matched CPython on both builds):
  - `/tmp/probes/p190_int64.py`
  - `/tmp/probes/p190_maxsplit.py`
  - `/tmp/probes/p190_nonint.py`
  - `/tmp/probes/p190_boundaries.py`
- Tests on final commit: `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass (4/4).
- Also ran `test_ail_pre113`, `test_ail_pre160`, `test_ail_pre177` — pass. `test_ail_pre121` has 2 failures, reproduced identically on base `44cb4c6`, so pre-existing.
- `tools/diff_ids.py` does not exist in this tree or the fetched ref, so it could not be run.
[cost $0.0000, opencode tokens {"total": 1759427, "input": 53248, "output": 9132, "reasoning": 9239, "cache.write": 0, "cache.read": 1687808}]
    tool time: bash 8.4 min, edit 0.0 min, read 0.0 min, write 0.0 min
        245s bash   time python3 tools/par_check.py -j 2 test_ail_pre190 test_ail_pre121 test_ail_pre160 test_ail_pre113 test_ail_
        210s bash   time python3 tools/par_check.py -j 2 test_ail_pre190 test_ail_safetynet test_ail_files test_ail_corpus_finding
         23s bash   python3 tools/par_check.py -j 2 test_ail_pre121 2>&1 | tail -25
         17s bash   for p in /tmp/probes/p190_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tee /tmp/prob
          2s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p190_boundaries.py') s=p.read_text().replace("  
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre190-10252047 2>&1 | tail -5; echo "---"; git rev-parse 
          1s bash   python3 -m py_compile AIL_CURRENT/python/pkg-v12/pyfront.py AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/t
          1s bash   python3 tools/update_manifest.py --check; echo "manifest rc=$?"; git status --short; git worktree remove /tmp/

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** Re-applies the accepted pre190 constant-folder change (`pyfront.int_constant`, `pyfunc._maxsplit_const`, `_CONST_INT_BITS = _MAXSPLIT_BITS`) on top of `44cb4c6`. `pyfront.py` and `test_ail_pre190.py` are byte-identical to the fetched pre190 versions; `pyfunc.py` differs from the original only by keeping the current tree's exact `_pow_within_maxsplit_bits` guard (the requested "keep both sides' fixes"). No runtime or I/O code changed.

**Probes** (own, `/tmp/rprobes/`, `bash ~/tools/cmp.sh ... $PWD`, both builds):
- `r1_types.py` (bool/float/negative-exponent/non-int zero cases) — both builds same stdout as CPython, exit 0.
- `r2_alias.py` (zero/base reductions via argument, list item, attribute, dict value, and maxsplit routes) — same.
- `r3_effects.py` (calls and side-effect ordering around `0*x`, `0**f()`, split maxsplit) — same.
- `r4_boundary.py` (near-cap shifts/pow/div/mod/xor, `2**524287`) — same.
- `r9_maxsplit_neg.py` (negative/zero maxsplit from `(-1)**odd/even`, routes, empty string) — same.
- `r10_maxsplit_cap.py` (cap-sized intermediate reduced for split) — same.
- `r5_nonfeature.py` (ordinary program, small constants only) — C generated with `--debug-dir` is byte-identical between `/tmp/base` and HEAD; native report differs only in temp paths/cwd.
- Beyond-cap probes (`r6`, `r7`, `r8`, `r11`) are refused by name, identically on base; acceptable.

**Tests on HEAD (`d3ab969`):** `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_pre121` has the same 2 failures on HEAD and `/tmp/base` (pre-existing).

**Claims:** commit/manifest `--check` rc 0 — verified. Probes match CPython on both builds — verified. Required tests pass — verified. `test_ail_pre121` pre-existing — verified. `tools/diff_ids.py` absent in this tree and fetched ref — verified. "pre113/pre160/pre177 pass" — unverified (not rerun).

**Pre-existing:** `test_ail_pre121` two `int64 constant out of range` expectation failures, and the >2^20/>16M-bit constant refusals, are identical on base.

**Not checked:** instruction counts; the diff only changes compile-time constant folding and the generated C for non-feature programs is identical, so no runtime hot path changed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2218803, "input": 68817, "output": 9521, "reasoning": 23345, "cache.write": 0, "cache.read": 2117120}]
    tool time: bash 6.2 min
        168s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1500 python3 ../tools/par_check.py -j 2 test_ail
        107s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; timeout 1500 python3 ../tools/par_check.py -j 2 test_ail
         21s bash   cd /tmp/base/AIL_CURRENT; date; timeout 600 python3 ../tools/par_check.py -j 2 test_ail_pre121 2>&1 | tail -18
         15s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/p190_int64.py /tmp/probes/p190_maxsplit.py /tmp/probe
         12s bash   cd /tmp/base; for p in /tmp/rprobes/r6_over_cap.py /tmp/rprobes/r7_over_special.py /tmp/rprobes/r11_maxsplit_t
         10s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r1_types.py /tmp/rprobes/r2_alias.py /tmp/rprobes/r3
          7s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r1_types.py /tmp/rprobes/r2_alias.py /tmp/rprobes/r3
          7s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && cp /tmp/rprobes/r5_nonfeature.py /tmp/dbg_he

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T15:42:49Z
