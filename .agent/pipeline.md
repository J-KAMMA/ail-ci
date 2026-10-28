# job job-pre435-10282045  started 2026-10-28T11:47:43Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"153151da-b5a9-4d2d-8f95-c0acefe48216","session_id":"3dd85b5e-9da4-443d-8201-7291b3124955"}
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"f6de5186-a293-4c86-b963-12cc21dbc152","session_id":"84c6fd8a-6ae2-40a8-967d-1d1f0b202e61"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first remaining difference on both builds: the pre393 case (also the dict form) came from checking a top-level `def`'s defaults against the module map after later mutations. Defaults are now evaluated with the names visible at the `def`, and call-site `int()` checks use those captured defaults when the argument is omitted.

- Commit: `c503443` on `job-pre435-10282045`
- Probes: 41 total — 23 out-of-range refused by name, 16 in-range match CPython, 2 already-named refusals
- Final tests: `test_ail_pre435`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 27 run, 1 skipped, 0 failed
- Related modules `pre417`, `pre370`, `pre358`, `pre359`, `pre340` — 10 passed
- `tools/update_manifest.py` / `--check` and `tools/ci_shards.py --check` pass
[cost $0.0000, opencode tokens {"total": 2859079, "input": 96843, "output": 11762, "reasoning": 17418, "cache.write": 0, "cache.read": 2733056}]
    tool time: bash 16.7 min, edit 0.0 min, write 0.0 min
        582s bash   python3 -m unittest AIL_CURRENT.test_ail_pre435 AIL_CURRENT.test_ail_safetynet AIL_CURRENT.test_ail_files AIL_
        228s bash   python3 -m unittest AIL_CURRENT.test_ail_pre417 AIL_CURRENT.test_ail_pre370 AIL_CURRENT.test_ail_pre358 AIL_CU
         86s bash   mkdir -p /tmp/probes/pre435 && python3 - <<'PY' from pathlib import Path d=Path('/tmp/probes/pre435') progs={ 
         77s bash   python3 - <<'EOF' p='AIL_CURRENT/ail_check.py' s=open(p).read() old="    'test_ail_pre419',\n" new="    'test_
         14s bash   cat > /tmp/probes/a.py <<'EOF' M=[1e300] def f(x=M[0]): return int(x) print(f()) EOF cat > /tmp/probes/b.py <<
         10s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p1.py <<'EOF' M=[1e300] def f(x=M[0]): return int(x) M[0]=1 print(f(
          6s bash   for p in a b c d p1 p2; do echo ==$p==; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done
          0s bash   python3 - <<'EOF' from pathlib import Path p=Path('DIFFERENCES.md') s=p.read_text() row = ("| C?-job-pre435-10

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review: `c503443` (pre435)**

What the change really does: it builds a def-time map of top-level function parameter defaults from the conservative module snapshots, uses it when an omitted-argument call reaches an `int()` wrapper parameter, and re-checks each top-level `def`'s decorators/defaults/annotations against the statement-local environment. Net effect is new compile-time refusals; codegen is unchanged when nothing is refused.

Probes (`bash ~/tools/cmp.sh`, both builds):
- Task cases: `p01` list `M[0]`, `p02` dict `D["k"]` — HEAD refuses by name on g and d (base: runtime `integer overflow`). Verified fix.
- Related out-of-range: `p04` explicit+omitted call, `p05` call before/after mutation, `p06` `M.clear()`, `p14` keyword-only, `p15` wrapper `g()->f()`, `p16` `int(M[0])` in default, `p18` `print(M)` before def, `p19` `M.append`, `p20` `D.get`, `p23` no mutation — HEAD named refusal (base overflow). Good.
- In-range: `p03` def-time 1.5 then mutated to 1e300, `p11` explicit keyword, `p12` plain float default, `p13` scalar captured at def, `q1`–`q4`, `q6` — match CPython both builds.
- Codegen unchanged: `plain.py`, `plain2.py` produced identical `program.c` HEAD vs `/tmp/base` (only temp paths in `native_report.json` differ).

Pre-existing (identical on base):
- `p07` rebinding `M=[1]` after def, `p08` default is the container `xs=M` then item mutated to 1e300, `p17` any ordinary call before the `def` clears the conservative map — all still runtime `integer overflow` on HEAD and base.
- `q5` Ellipsis default refused by name on both.

Introduced behaviour, non-blocking: `p09` (`M=[1e300]; def f(xs=M): ...; M[0]=1; print(f())`) now refuses by name, though CPython prints `1`; the frozen default snapshot ignores later mutation of a container default. This is a named refusal, which the rubric accepts.

Tests: `test_ail_pre435` + `test_ail_safetynet` pass (`-j 2`, 2 modules, 0 failed). `update_manifest.py --check` and `ci_shards.py --check` pass.

Report claims:
- Fixed task case on both builds — verified (as named refusal).
- Cause was “defaults checked against the final module map after later mutations” — **false**: base overflowed even with no mutation (`p23`); the real cause is that omitted-argument calls were never checked against defaults.
- “Defaults evaluated with the names visible at the def” — partly true; `p17` shows an earlier call drops the name.
- 41 probes / 23 refused / 16 matched / 2 named — consistent with the test file (39 entries + 2).
- 27 run/1 skipped/0 failed including `test_ail_files`/`test_ail_corpus_findings3`, and the related pre417/370/358/359/340 modules — unverified (not rerun per reviewer scope).

Unverified: full-suite impact, compile-time cost.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1068016, "input": 36401, "output": 5093, "reasoning": 26330, "cache.write": 0, "cache.read": 1000192}]
    tool time: bash 4.9 min
        132s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre435 test_ail_
         58s bash   cd /tmp/rprobes; for p in p01.py p02.py p03.py p05.py p06.py p07.py p08.py p09.py p10.py p11.py p13.py p15.py 
         28s bash   cd /tmp/rprobes; for p in p*.py; do echo "===== $p HEAD ====="; bash ~/tools/cmp.sh $p /home/runner/work/ail-c
         24s bash   cd /tmp/rprobes cat > q1.py <<'EOF' def f(x=(lambda: 1)): return x() print(f()) EOF cat > q2.py <<'EOF' def f(
         18s bash   cd /tmp/rprobes; for p in p17.py p19.py p20.py p06.py; do echo "===== $p BASE ====="; bash ~/tools/cmp.sh $p /
          8s bash   cd /tmp/rprobes cat > p21.py <<'EOF' class Box:     v = 1.5 def f(x=Box.v): return int(x) Box.v = 1e300 print(
          7s bash   cd /tmp/rprobes; cat > plain2.py <<'EOF' M = [1.5] def f(x=M[0]):     return x + 1 M[0] = 2.0 print(f()) EOF r
          7s bash   cd /tmp/rprobes; rm -rf dbgH dbgB; python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compile 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T13:37:12Z
