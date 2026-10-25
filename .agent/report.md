# job job-rbpre204-10252303  started 2026-10-25T14:05:26Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":535,"duration_api_ms":417,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":406,"duration_api_ms":288,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `cdf41c3` on `job-rbpre204-10252303`.

Applied the pre204 fix on the current tree:
- Raised exact constant-fold limits to `1 << 22` in `pyfront.int_constant` and `pyfunc._const_int_expr`.
- Added the missing unary fold to `pyboxed.expr_UnaryOp`; the other emitters already fold via the tree's broader `fold_int_constant` path.
- Added `test_ail_pre204.py`, registered it in `ail_check.py` and `ci_shards.json`, plus DEVLOG/DIFFERENCES/manifest updates.

Tests on final commit:
- `test_ail_pre204` 4 OK; `test_ail_pre177` 4 OK; `test_ail_pre192` 1 OK
- `test_ail_safetynet` 5 OK; `test_ail_files` 18 OK (1 skipped); `test_ail_corpus_findings3` 2 OK

Probes (`/tmp/probes/`, `cmp.sh`, default + general builds): `p204_negmin`, `p204_boundary`, `p204_flows`, `p204_reductions`, `p204_dynamic` — all matched CPython stdout and exit 0 on both builds.

`tools/update_manifest.py` and `--check` pass. `tools/diff_ids.py` does not exist in this tree, so it could not be run.
[cost $0.0000, opencode tokens {"total": 1018712, "input": 45496, "output": 7913, "reasoning": 8375, "cache.write": 0, "cache.read": 956928}]
    tool time: bash 6.6 min, edit 0.0 min, write 0.0 min
        363s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && export AIL_NO_CACHE=1 && for m in test_ail_pre204 test_ail_p
         18s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_pre204.py 2>&1 | tail -40
         13s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p204_negmin.py <<'EOF' def main():     print(-(1 << 63))     print(-
          2s bash   cd /home/runner/work/ail-ci/ail-ci && git fetch https://github.com/J-KAMMA/ail-ci.git job-pre204-10252054 2>&1
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/pyboxed.py A
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo manifest_check=$? && git 
          0s edit   /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12/pyfunc.py
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** raises exact integer constant folding to `1 << 22` bits in `pyfront.int_constant` and `pyfunc._const_int_expr`, and adds whole-unary constant folding to the general legacy `pyboxed.expr_UnaryOp`; the other emitters already fold unary constants through `fold_int_constant` (`ir/lower._expr`, `pyfunc._expr`, `pyboxed2.expr`, `unified.nexpr`). Plus the accepted test/doc/manifest edits. Report matches the diff.

**Probes** (created in `/tmp/rprobes`, `cmp.sh`, default + general builds; base = `/tmp/base` worktree):
- `p1` negated INT64_MIN spellings, nested unaries, invert, negative shift: HEAD both builds match CPython exit 0; base refuses at the 5000-bit spelling.
- `p2` large-intermediate reductions (`0 >> (1<<5000)`, `2**((1<<2000000)-(1<<2000000))`, `(1<<2000000)>>2000000`): both builds match.
- `p3` flows through argument, list item, attribute, dict value, alias and return: both builds match.
- `p4`, `p8` dynamic operands and assignment/container flows: both builds match.
- `p7` 5000-bit and 4194303-bit shift boundaries: HEAD matches; base refuses.
- `p9` negative large intermediates through `>>`, `//`, `%`: both builds match.
- `p6` no-feature program: default and general `--debug-dir` `program.c` byte-identical to base.
- Re-ran the worker's five `/tmp/probes/p204_*.py`: all match on both builds (claim verified).

**Tests on HEAD:** `test_ail_pre204`, `test_ail_pre177`, `test_ail_pre192`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all `ok` (`-j 2`). `update_manifest.py --check` = 0. `tools/diff_ids.py` is genuinely absent.

**Claims:** all verified. The extra `_CONST_INT_BITS` bump is a conflict resolution needed because this tree routes these folds through `fold_int_constant`; it only widens exact folding (out-of-int64 results keep the same refusal), and pre177 still passes.

**Pre-existing (identical on base, not blocking):** dynamic negation that leaves int64 (`b = -(1<<63); -b`) still exits 1 with `integer overflow`; out-of-int64 constant results are refused by name or trap as before.

**Unverified:** instruction-count speed — no runtime/hot path is touched, so not measured; wider suite not run per instructions.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1388092, "input": 51298, "output": 6056, "reasoning": 20274, "cache.write": 0, "cache.read": 1310464}]
    tool time: bash 4.9 min
        215s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         17s bash   cd /tmp/rprobes && for p in p1 p2 p3 p4 p5 p6; do echo "===== HEAD $p ====="; timeout 600 bash ~/tools/cmp.sh 
         17s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
         12s bash   for f in /tmp/probes/p204_*.py; do echo "===== $(basename $f) ====="; timeout 600 bash ~/tools/cmp.sh $f /home
         10s bash   cd /tmp/rprobes && python3 - <<'EOF' p='/tmp/rprobes/p1.py' s=open(p).read().replace('print(-(-(1 << 63)))','p
          5s bash   cd /tmp/rprobes && cat > p7.py <<'EOF' def main():     print((1 << 5000) >> 4937)     print((1 << 5000) >> 500
          5s bash   cd /tmp/rprobes && python3 - <<'EOF' p='/tmp/rprobes/p7.py' s=open(p).read().replace('print((1 << 5000) >> 493
          3s bash   cd /tmp && rm -rf dbg_head_g dbg_base_g && for m in head base; do d=/tmp/dbg_${m}_g; mkdir -p $d; cp /tmp/p6.a

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T15:10:36Z
