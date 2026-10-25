# job job-pre200-10252345  started 2026-10-25T14:46:05Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":302,"duration_api_ms":176,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":321,"duration_api_ms":194,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `0e38dea` on `job-pre200-10252345`.

**Fix:** the shared `pyfunc.fold_int_constant` added by rbrbpre121 still used a 4096-bit intermediate cap. It now uses pre200's 8192-bit width, so it no longer pre-empts the maxsplit folder (pre200) or the MIN unary fold (pre203). Changes: `pyfunc.py`, `MANIFEST.json`, `DEVLOG.md`.

**Tests**
- Branch: `test_ail_pre200`, `test_ail_pre97`, `test_ail_pre160`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all 6 pass. `test_ail_pre121`/`test_ail_pre203` do not exist on this branch.
- Integration simulation (`cand-1025225738` + this patch): `test_ail_pre200` + `test_ail_pre203` — 5/5 pass.
- Pre-existing, unchanged without the patch: `test_ail_pre121` has 2 message-expectation failures; `test_ail_pre195` is superseded by pre200.

**Probes** (`/tmp/probes`, both builds)
- `pre200fix_direct_8191.py`: branch + integration same stdout.
- `pre200fix_channels_4096.py`: branch + integration same stdout.
- `pre200fix_over_cap.py`: refused by name on both.
- `pre203fix_unary_channels.py`: integration same stdout (branch lacks pre203's fold, pre-existing).
- `pre203fix_over_int64.py`: refused by name on integration.

`tools/update_manifest.py --check` exits 0. No push.
[cost $0.0000, opencode tokens {"total": 7481580, "input": 103610, "output": 48946, "reasoning": 0, "cache.write": 0, "cache.read": 7329024}]
    tool time: bash 14.3 min
        387s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_pre200 test_ail_pr
         74s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre200fix_direct_8191.py /tmp/probes/pre200fix_chan
         73s bash   cd /tmp/integ2/AIL_CURRENT && timeout 1800 python3 -m unittest -q test_ail_pre121 test_ail_pre160 test_ail_pre
         47s bash   git worktree add --detach /tmp/i200 e95db66 >/tmp/wt3.log 2>&1; cat /tmp/wt3.log; git worktree add --detach /t
         29s bash   cd /tmp/integ2 && git checkout -- AIL_CURRENT/python/pkg-v12/pyfunc.py && printf '\n# pre200 accepts intermedi
         29s bash   cd /tmp/integ2 && sed -i 's/^_CONST_INT_BITS = 4096$/_CONST_INT_BITS = 8192/' AIL_CURRENT/python/pkg-v12/pyfun
         27s bash   cd /tmp/integfinal/AIL_CURRENT && timeout 1800 python3 -m unittest -q test_ail_pre200 test_ail_pre203 > /tmp/i
         26s bash   git worktree add --detach /tmp/integ2 refs/temp/cand25738 >/tmp/wt2.log 2>&1; cat /tmp/wt2.log; cd /tmp/integ2

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** appends `_CONST_INT_BITS = 8192` to `AIL_CURRENT/python/pkg-v12/pyfunc.py`. On this branch the name is unused; once merged with rbrbpre121 it overrides that module's `_CONST_INT_BITS = 4096`. MANIFEST hash and DEVLOG are updated. This matches the report's intended effect, though the constant is inert on the branch alone.

**Probes** (integration sim = cand-1025225738 + appended line; both builds via `cmp.sh`):
- `p1c_mid_channels` (`3**4096 >> 6440` via direct call, arg, list, attribute, dict, local; negative base): patched integration matches CPython on g and d; unpatched integration refuses by name, so the change is what enables it.
- `p3_exact_cap` (`2**8191 >> 8155`, `-((1<<8191)>>8128)`): patched matches CPython on both; unpatched refuses.
- `p2_over_cap` (`2**9000 >> 8964`, final value fits): refused by name on both builds, acceptable.
- `p4_unary_min` (`-((1<<5000)>>4937)` etc. via all channels): patched matches; base lacks the pre203 fold, pre-existing.
- `p5_unrelated`: generated `program.c` byte-identical patched vs unpatched for g and d.
- Worker probes `direct_8191`, `channels_4096`, `over_cap`, pre203 `unary_channels`/`over_int64`: all behave as reported.

**Tests:** HEAD `test_ail_pre200`, `test_ail_pre97`, `test_ail_pre160`, `test_ail_safetynet` pass; `update_manifest.py --check` exits 0. Patched integration: `test_ail_pre200` + `test_ail_pre203` 5/5 pass (unpatched both fail). `test_ail_pre121` has the same 2 message-expectation failures with and without the patch.

**Claims:** verified, apart from pre195 (not checked) and the extra branch modules/files below. **Pre-existing:** pre121 message failures; the shared fold's conservative `bit_length*right` Pow bound still refuses some in-cap intermediates (`2**8000>>7954` via list/attr/dict/local, and `((2**63*4)**63)>>4095` as a user-function argument) identically without the patch, as named refusals; base-branch p1/p3/p4 failures (no shared folder/pre203).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, pre195 claim, full suite; no icount run (compile-time-only change, unrelated C identical).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1491939, "input": 69943, "output": 9240, "reasoning": 25620, "cache.write": 0, "cache.read": 1387136}]
    tool time: bash 8.9 min
        135s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         61s bash   date; cd /tmp/rev_integ/AIL_CURRENT && timeout 1500 python3 -m unittest -q test_ail_pre97 test_ail_pre160 > /t
         55s bash   date; cd /tmp/rev_integ/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre97 test_ail_pre160 > /tm
         51s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre97 test
         33s bash   date; cd /tmp/rev_integ/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre200 test_ail
         29s bash   date; cd /tmp/rev_integ/AIL_CURRENT && timeout 1500 python3 -m unittest -q test_ail_pre200 test_ail_pre203 > /
         22s bash   cd /tmp/rev_integ && cp /tmp/rev_integ_pyfunc_orig.py AIL_CURRENT/python/pkg-v12/pyfunc.py && grep -n "_CONST_
         21s bash   date; cd /tmp/rev_integ/AIL_CURRENT && timeout 1500 python3 -m unittest -q test_ail_pre121 > /tmp/rev_patch_12

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T16:38:40Z
