# job job-pre237-10260353  started 2026-10-25T18:53:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":337,"duration_api_ms":212,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":327,"duration_api_ms":202,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing item, `p4_collide`.

- Cause: `pymix._escapes` ignored class-method bodies and `obj.method()` call sites, so a helper called from a method was selected as a typed clone and its `ValueError` bypassed the caller's boxed `try` on the default build.
- Fix: walk every method body separately (duplicate names and module-function name collisions preserved) and record attribute call sites.
- Commit: `483d6c4` on `job-pre237-10260353`; not pushed.

Probes (both builds vs CPython):
- `p4_collide2.py`: match — `caught ValueError 'negative shift count'`, `valid 8` (failed on base before fix).
- `pre237_forms.py`: match — literal/argument/list/attribute/dict/alias counts, zero/large/valid shifts, method chains, own `try`, duplicate method names, division/subscript traps.
- `pre237_uncaught.py`: match — exit 1, same stdout, `ValueError: negative shift count`.
- `r11_method_full.py`: match on both builds.
- `p5_dupname2.py`: match, but it did not reproduce the reviewer's `p5` on base, so no claim is made for that probe.

Tests on final commit: `test_ail_pre237` (2), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` exits 0. `p9_methodalias`/`p11_classval` still differ as recorded.
[cost $0.0000, opencode tokens {"total": 3261363, "input": 95256, "output": 11580, "reasoning": 18271, "cache.write": 0, "cache.read": 3136256}]
    tool time: bash 16.7 min
        328s bash   python3 tools/par_check.py -j 2 test_ail_pre237 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        252s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_pre237 test_ail_safetynet
        251s bash   python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 2 test_ail_pre237 test_ail_safetynet
         39s bash   mkdir -p /tmp/probes/p4v && cd /tmp/probes/p4v cat > a.py <<'EOF' def run(a, b):     return a << b  class C:  
         33s bash   for p in /tmp/probes/p4_collide.py /tmp/probes/p4_collide2.py /tmp/probes/p5_dupname.py /tmp/probes/p5_dupname
         26s bash   for p in /tmp/probes/p4_collide2.py /tmp/probes/p5_dupname2.py /tmp/probes/pre237_forms.py /tmp/probes/pre237_
         18s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p4_collide.py <<'EOF' def run(value):     return value + 1   class C
         15s bash   rm -rf /tmp/base237 && mkdir -p /tmp/base237 && git archive 3952feb | tar -x -C /tmp/base237 && for p in p5_du

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the diff really does:** `pymix._escapes` now walks every class-method body in addition to module functions and records `obj.method()` call sites. This only *adds* call edges, so it can only add escapes/protection — i.e. keep more functions on the boxed path. No runtime, I/O, buffer or ownership code is touched.

**Probes** (`bash ~/tools/cmp.sh`, both builds, HEAD vs base):

| probe | HEAD g/d | base g/d |
|---|---|---|
| `r1_chain` (method→method→shl under module try, dup method names) | match / match | match / **FAIL** (exit 1) |
| `r2_collisions` (methods `pop`/`append` shadow builtins + list mutation) | match / match | match / match |
| `r3_forms` (arg/list/dict/attribute/alias, zero/62/negative/-2/-3/-4) | match / match | match / **FAIL** (exit 1) |
| `r4_uncaught` (uncaught shift through method chain) | exit 1, same stdout/stderr | same |
| `r5_nofeature` | match / match | match / match |
| `r6_methodvalue` (p9/p11 bound-method values) | AttrError exit 1 | identical AttrError exit 1 |

Also ran worker probes: `p4_collide2` fails on base (exit 1, missing `caught ValueError`/`valid 8`) and matches on HEAD; `pre237_forms`, `pre237_uncaught`, `p5_dupname2`, `r11_method_full`, `p4_collide` all match on HEAD. `p5_dupname` matches on base too, as the report says.

**Unchanged C:** `--debug-dir/program.c` byte-identical base vs HEAD for `r5_nofeature`, gdev `g13_018`, `g12_036`, `g06_032`. `tools/icount.c` cannot run here (`perf_event_open: Permission denied`), but identical C means no instruction-count change for those programs.

**Tests:** `update_manifest.py --check` rc=0; `par_check.py -j 2 test_ail_pre237 test_ail_safetynet` → 2 modules, 0 failed, 121s.

**Claims:** cause/fix location, commit `483d6c4`, p4_collide2 base-failure→HEAD-fix, `pre237_forms`/`pre237_uncaught`/`p5_dupname2`/`r11_method_full`, p9/p11 still differing, and unchanged C for the three named gdev programs are **verified**. Worker's 4-module test run (`test_ail_files`, `test_ail_corpus_findings3`) is **unverified** (I re-ran only the added module + safetynet); their unchanged-C claims for `p10_nofeature`/`p12_classonly`/`p6_uncaught` are **unverified** (probes not present).

**Pre-existing:** bound-method-as-value (`p9`, `p11`) gives `AttributeError` and exit 1 on both base and HEAD — recorded difference, not introduced here.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 698827, "input": 42233, "output": 4713, "reasoning": 11625, "cache.write": 0, "cache.read": 640256}]
    tool time: bash 4.8 min
        123s bash   date; cd AIL_CURRENT && python3 ../tools/update_manifest.py --check; echo "manifest rc=$?"; python3 ../tools/p
         29s bash   date; for p in p4_collide p5_dupname p4_collide2 p5_dupname2 pre237_forms pre237_uncaught; do echo "######## $
         29s bash   date; for wt in "$PWD:HEAD" "/tmp/base:BASE"; do root=${wt%%:*}; tag=${wt##*:}; for p in /tmp/probes/r11_metho
         29s bash   date; for p in r1_chain r2_collisions r3_forms r4_uncaught r5_nofeature r6_methodvalue; do echo "######## $p B
         28s bash   date; T=/tmp/rprobes/cmpc; rm -rf $T; mkdir -p $T; for src in /tmp/rprobes/r5_nofeature.py ~/corpus/gdev/g13_0
         28s bash   date; for p in r1_chain r2_collisions r3_forms r4_uncaught r5_nofeature r6_methodvalue; do echo "######## $p H
         19s bash   date; for p in p4_collide p5_dupname p4_collide2 p5_dupname2; do echo "######## $p BASE"; bash ~/tools/cmp.sh 
          0s bash   git worktree list; git worktree add /tmp/base work 2>&1 | tail -3

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T20:37:50Z
