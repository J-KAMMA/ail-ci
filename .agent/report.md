# job job-pre251-10260446  started 2026-10-25T20:03:26Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":388,"duration_api_ms":270,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":376,"duration_api_ms":258,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case: `(True << 64) >> 64` (and wider bool shifts) now match CPython on both builds.

- Commit: `3020a4e` — constant int folder accepts `True`/`False` as 0/1; bool-only results such as `True & True` remain runtime bools; out-of-range `True << 64` is refused by name.
- Probes: `pre251_accept`, `pre251_contexts`, `pre251_boolops`, `pre251_module_const`, `pre251_maxsplit` all matched CPython on both builds; `pre251_refuse_true` refused by name; `pre251_refuse_pow` (`True ** 64`) matched CPython; `p1b`, `p3a`, `p3b`, `p4` unchanged/refused by name; `p2` non-constant still overflows as before.
- Final-commit tests: `test_ail_pre251`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 31 tests, OK (1 skipped). `test_ail_pre190` passes; `test_ail_pre121` has 2 failures reproduced on the base commit.
- `tools/update_manifest.py --check` passes. Only untracked `.agent/pipeline.md` remains.
[cost $0.0000, opencode tokens {"total": 3093514, "input": 100247, "output": 12480, "reasoning": 15155, "cache.write": 0, "cache.read": 2965632}]
    tool time: bash 7.3 min
        313s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest test_ail_pre251 test_ail_safetynet te
         39s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest test_ail_pre121 test_ail_pre190 2>&1 
         21s bash   cd /tmp/probes && cat > pre251_accept.py <<'EOF' def main():     print((True << 64) >> 64)     print((True << 
         19s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B test_ail_pre251.py 2>&1 | tail -30
         13s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p1a.py <<'EOF' def main():     print((True << 64) >> 64)   mai
         12s bash   cd /tmp/probes && for f in p1a boolops p_extra p_extra2 p1b; do echo "=== $f ==="; bash /home/runner/tools/cmp
          9s bash   rm -rf /tmp/pre251base && mkdir -p /tmp/pre251base && cd /home/runner/work/ail-ci/ail-ci && git archive HEAD^ 
          3s bash   cd /tmp && d=$(mktemp -d /tmp/pre251checkXXXX) && cp /tmp/probes/pre251_refuse_true.py $d/p.py && cd $d && for

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job pre251 (commit `3020a4e`)

**What the change really does:** extends the constant int folder (`_const_int_expr`) and the maxsplit folder (`_maxsplit_const`) to accept `bool` constants as 0/1, and refuses an out-of-int64 result by name; a final *bool*-typed result (`True & True`, `+True`) is deliberately left unfolded so its type is preserved. This matches the report (it additionally touches the maxsplit folder, which the report's one-line summary omits but DEVLOG/DIFFERENCES mention).

**Probes** (`bash ~/tools/cmp.sh`, both builds, against `/tmp/base` = `work`):

| probe | HEAD | base |
|---|---|---|
| r1 wide bool shifts `(True/False/-True/~True << 64/100000) >> ...` | matches CPython | overflow |
| r3 `True << 64` | refused by name | runtime overflow |
| r4/r7/r12 bool ops, types, pow, `//`,`%`,`**` | matches | overflow/matches |
| r5 contexts: attr, arg, list, dict, tuple | matches | overflow |
| r8 containers + bool maxsplit | matches | overflow |
| r11 index/dict/range/slice with folded bool shift | matches | overflow |
| r13/r14 maxsplit bool forms (incl. keyword/literal) | matches | partly matches, overflow |
| r2a/b int `(1<<100000)>>100000`, `(1<<64)>>64` | matches | already matched |
| r2c/d/e out-of-int64 int shifts/pow | named refusal | identical refusal |
| r6/r9 non-constant `n=True; n<<64` / via arg | runtime overflow | identical (pre-existing) |
| r10 plain bool program, plain.py `--debug-dir` | unchanged; `program.c` byte-identical | — |

**Claims:** 1) bool folder acceptance / bool-only results / `True<<64` refusal — verified. 2) both builds match — verified. 3) `True ** 64` matches — verified. 4) non-constant still overflows — verified, identical to base. 5) `update_manifest.py --check` and only `.agent/pipeline.md` untracked — verified. 6) Targeted tests `test_ail_pre251`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass (215s). Exact "31 tests/1 skipped" count and the `test_ail_pre190`/`pre121` claims — not re-verified.

**Pre-existing (identical on base, do not block):** non-constant `n=True; n << 64` still traps; `False ** -1` error text differs (`division by zero` vs CPython's message); `(1<<100001)>0`, `(-1<<100001)<0`, `(-(10**64))>>100000` are named refusals on both trees.

No source edits or commits made by me. Time used ~8 min.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 561766, "input": 33992, "output": 4903, "reasoning": 12279, "cache.write": 0, "cache.read": 510592}]
    tool time: bash 5.2 min
        216s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre251 test_ail_
         13s bash   cd /tmp/rprobes && for f in r1 r2 r3 r4 r5; do echo "===== HEAD $f ====="; bash /home/runner/tools/cmp.sh /tmp
         13s bash   cd /tmp/rprobes && cat > r2.py <<'EOF' def main():     print((1 << 100000) >> 100000)     print((1 << 64) >> 6
         12s bash   cd /tmp/rprobes && for f in r7 r8 r9 r10; do echo "===== BASE $f ====="; bash /home/runner/tools/cmp.sh /tmp/r
         12s bash   cd /tmp/rprobes && cat > r7.py <<'EOF' def main():     print((False << 100000) >> 100000)     print((-False <<
         10s bash   cd /tmp/rprobes && for i in a b c d e; do :; done cat > r2a.py <<'EOF' def main():     print((1 << 100000) >> 
         10s bash   cd /tmp/rprobes && for f in r2a r2b r2c r2d r2e; do echo "===== BASE $f ====="; bash /home/runner/tools/cmp.sh
          6s bash   cd /tmp/rprobes && cat > r11.py <<'EOF' def main():     xs = [10, 20, 30]     print(xs[(True << 64) >> 64])   

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T21:10:56Z
