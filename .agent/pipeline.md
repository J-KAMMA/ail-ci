# job job-pre428-10281850  started 2026-10-28T09:50:49Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"78c1a8bc-499e-43fd-baea-3b40cb488fee","session_id":"e733c27f-91c3-4562-9920-ce7516bf897e"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"0aaf83fa-f442-4dec-a30d-8c2d7b3da5b3","session_id":"662189a0-350b-49be-afaf-1dda3d1d441f"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre-existing item from the pre416 review: `E() * F()` now names the classes, not `'exception'`.

- Commit: `84404f4` on `job-pre428-10281850`
- Runtime change: `ail_op_mul` formats both operand names via `ail__tname_c`, with separate buffers and CPython’s `%.100s` cap; updated the `dunderrt.py` patch anchor.
- Probes in `/tmp/probes/pre428` — `p1_direct`, `p2_routes`, `p3_mixed`, `p4_long_99/100/101/150/300`, `p5_instances`, `p6_controls`: all match CPython on both builds.
- Tests on final commit: `test_ail_pre428`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_left1` — 5 modules, 389s, 0 failed.
- `update_manifest.py --check` and `ci_shards.py --check` pass.

Remaining pre-existing items from that review are unchanged: `//`, `%`, `/`, `**` messages still omit operands, and ordering comparisons still say `'exception'`. Speed not measured; this is a cold error path.
[cost $0.0000, opencode tokens {"total": 6298556, "input": 131604, "output": 12782, "reasoning": 12602, "cache.write": 0, "cache.read": 6141568}]
    tool time: bash 11.1 min, edit 0.0 min
        391s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre428 test_ail_safetynet test_ail_files test_ai
         73s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre428 2>&1 | tail -80
         70s bash   for p in /tmp/probes/pre428/p*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep
         64s bash   for p in /tmp/probes/pre428/p*.py; do r=$(bash ~/tools/cmp.sh "$p" "$PWD" 2>&1); printf '%-18s ' "$(basename $
         33s bash   for p in /tmp/probes/pre428/p*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep
          9s bash   mkdir -p /tmp/probes/pre428 && cat > /tmp/probes/pre428/p0_pre_existing.py <<'PY' class E(Exception): pass cla
          6s bash   bash ~/tools/cmp.sh /tmp/probes/pre428/p0_pre_existing.py "$PWD" 2>&1 | sed -n '/g DIFF:/,/^d exit/p' | head -
          5s bash   bash ~/tools/cmp.sh /tmp/probes/pre428/p6_controls.py "$PWD" 2>&1 | tail -30

## review 0
[model opencode/deepseek-v4.1-flash-free]
Start 10:08 UTC, last probe 10:19 UTC.

**What the change really does.** In the general-path runtime, `ail_op_mul`'s fallback now formats each operand via `ail__tname_c` into separate 101-byte buffers with `%.100s` and a 256-byte message; the `dunderrt.py` patch anchor is moved to the new first line. Also adds `test_ail_pre428.py` and records. Diff matches the report.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds):
- `p_pre416`: the `*` line now matches CPython; `//`, `%`, `/`, `**` and `<` still differ exactly as on `/tmp/base`.
- `u_aliasing`, `u_longboth`, `u_bufreuse`, `u_types`, `u_seq`, `u_shortinst`: match CPython on both builds (aliasing, 100-char exception names both operands, static-buffer reuse after two raises, 32 builtin/function/class/collection cases, sequence `can't multiply` path).
- `u_longinst`: ordinary-instance names over 79 chars truncate at 79 (expected 244, actual 202) — identical on base.
- `u_mixinst`: `E()*A()` still says `'exception' and 'A'` — identical on base.

**Claims.** Target `E()*F()` fixed on both builds: verified. Long exception names (99/100/101/150/300 via the new test), mixed builtins, routes: verified (test module ran: 0 failed). Remaining `//`,`%`,`/`,`**`, ordering items unchanged: verified. `update_manifest.py --check` and `ci_shards.py --check`: verified. "Class names (including ordinary instances) were lost": **false** — base already names ordinary instances (dunderrt path), so only exceptions and non-INST values changed; DIFFERENCES/DEVLOG overstate this. Which item was first in the pre416 list: unverified (list not in repo). Worker's exact probes, the other three test modules, and speed: unverified (cold error path).

**Pre-existing (identical on base; not blocking).**
1. Ordinary-instance class names >79 chars truncate at 79 instead of CPython's 100 (`u_longinst`, expected 244 / actual 202).
2. Exception with an ordinary-instance operand still prints `'exception'` (`u_mixinst`, both builds equal to base).
3. `//`, `%`, `/`, `**` messages omit operands; ordering prints `'exception'`.

Default-build binary for a no-feature program is byte-identical to base; general-path C differs only in the intended runtime line.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2580973, "input": 312582, "output": 8857, "reasoning": 27086, "cache.write": 0, "cache.read": 2232448}]
    tool time: bash 4.6 min
        136s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre428 t
         24s bash   cd /tmp/rprobes && cat > u_unicode.py <<'PY' class Café(Exception):     pass   class Ünïcode(Exception):     p
         20s bash   cd /tmp/rprobes && cat > u_types.py <<'PY' from collections import Counter, defaultdict, deque class C:     pa
         19s bash   cd /tmp/rprobes && cat > u_unicode.py <<'PY' class Café(Exception):     pass   class Ünïcode(Exception):     p
         14s bash   cd /tmp/rprobes && cat > u_shortinst.py <<'PY' class A:     pass   class B:     pass   try:     print(A() * B(
         12s bash   cd /tmp/rprobes && cat > p_pre416.py <<'PY' class E(Exception):     pass   class F(Exception):     pass   for 
         11s bash   cd /tmp/rprobes && cat > u_mixinst.py <<'PY' class E(Exception):     pass   class A:     pass   for label, fn 
          9s bash   cd /tmp/rprobes && cat > u_views.py <<'PY' def main():     d = {'a': 1, 'b': 2}     vals = [('keys', d.keys())

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T11:34:05Z
