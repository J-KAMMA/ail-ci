# job job-rbrbrbpre204-10261336  started 2026-10-26T04:37:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":426,"duration_api_ms":299,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":326,"duration_api_ms":200,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done.

- Re-applied pre204: exact unary constant folding in general legacy `pyboxed`, fold limit raised to `1<<22` in `pyfront`/`pyfunc`; added `test_ail_pre204.py`, registered it in `ail_check` and both `ci_shards` lists.
- Reconciled later fold-limit tests in `test_ail_pre190`/`test_ail_pre236` to the new 2^22 boundary.
- Added DEVLOG entry and DIFFERENCES row `C?-job-rbrbrbpre204-10261336-1`.
- Commits: `3ddca55`, `49ffebe`.
- `tools/update_manifest.py` ran, `--check` exits 0. `python3 tools/diff_ids.py` does not exist in this tree, so it could not be run.
- Final-commit tests: 44 run, 43 passed, 1 skipped (`windows` target, no zig); includes pre204, pre177, pre190, pre236, pre241, safetynet, files, corpus_findings3.
- Probes: `p204_direct`, `p204_flows`, `p204_reductions`, `p204_dynamic`, `p204_types` match CPython on both builds; `p204_out_of_range` is refused by name on both builds.
- Untracked `.agent/pipeline.md` left untouched.
[cost $0.0000, opencode tokens {"total": 1868976, "input": 65514, "output": 8591, "reasoning": 10679, "cache.write": 0, "cache.read": 1784192}]
    tool time: bash 19.3 min, edit 0.0 min, write 0.0 min
        671s bash   python3 -B -m unittest -v test_ail_pre204 test_ail_pre177 test_ail_pre190 test_ail_pre236 test_ail_pre241 test
        385s bash   python3 -B -m unittest -v test_ail_pre204 test_ail_pre177 test_ail_pre190 test_ail_pre236 test_ail_pre241 test
         28s bash   python3 -B -m unittest -v test_ail_pre204 2>&1 | tail -60
         25s bash   for p in /tmp/probes/p204_direct.py /tmp/probes/p204_flows.py /tmp/probes/p204_reductions.py /tmp/probes/p204_
         23s bash   for p in /tmp/probes/p204_direct.py /tmp/probes/p204_flows.py /tmp/probes/p204_reductions.py /tmp/probes/p204_
         14s bash   python3 -B -m unittest -v test_ail_pre190.Pre190Tests.test_fold_limit_is_shared_with_maxsplit test_ail_pre236.
          8s bash   for p in /tmp/probes/p204_flows.py /tmp/probes/p204_types.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$P
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-rbrbpre204-10260121 2>&1 | tail -5; echo "---"; git diff -

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** Re-applies pre204. The only functional compiler edit is in `pyboxed.py:1411` (general-legacy unary `+`/`-` of an all-constant int expression now emits an exact `ail_box_int` literal), plus raising the generic constant-fold limit from `1<<20` to `1<<22` in `pyfront.py:141` and both `pyfunc.py` `_CONST_INT_BITS` assignments (747, 37985). Everything else is the new test, pre190/pre236 boundary reconciliation, DEVLOG, DIFFERENCES, manifest, shard registration. This matches the report.

**Probes** (`/tmp/rprobes`, CPython oracle):
- `p1_min`: INT64_MIN spellings/reductions, in-range boundaries, `~`, `-0`, unary plus — match on general+default.
- `p2_flows`: arg, list item, attribute, dict value, alias, return — match.
- `p3_reductions`: `0 >> (1<<5000)`, large power differences, `(1<<2000000)>>2000000`, 2^22−1 boundary — match.
- `p4_out`: results outside int64 (`-(1<<63)-1`, `-(1<<64)`) — named refusal, acceptable.
- `p5_dynamic`: variable operands keep runtime path — match.
- `p7_boundary`: `(1<<4194303)>>4194303`, ±2^22 boundaries — match.
- `p8_nofeature`: non-feature program — `program.c` byte-identical to `/tmp/base` in both default and general-legacy builds.
- `p9_wide_shift`/`p10_huge_neg`: refusal identical on HEAD and base.
- `p1/p3/p7` also re-run in legacy (`AIL_IR=0`) and general-legacy (`AIL_UNIFIED_FORCE=1 AIL_UNIFIED=0`): match.

**Tests on HEAD:** `test_ail_pre204 test_ail_pre190 test_ail_pre236 test_ail_pre177 test_ail_pre241 test_ail_safetynet test_ail_files test_ail_corpus_findings3` — 8/8 modules pass. `tools/update_manifest.py --check` = 0. `tools/diff_ids.py` does not exist.

**Report claims:** all verified except the exact “44 run / 43 pass / 1 skip” count, which I did not reproduce individually (module-level results agree).

**Pre-existing:** `test_ail_pre195.test_intermediate_above_fold_limit_refused` fails on HEAD *and identically on base* (`2**4096 // 2**4050` folds to a valid maxsplit); not caused by this change.

**Unverified:** full suite (deliberately not run), benchmark speed (change is compile-time only), per-test count 44/43/1.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2031850, "input": 55273, "output": 7004, "reasoning": 11557, "cache.write": 0, "cache.read": 1958016}]
    tool time: bash 8.9 min
        429s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         23s bash   date; cd /tmp/rprobes && for p in p1_min p2_flows p3_reductions p4_out p5_dynamic p7_boundary; do echo "=====>
         21s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         18s bash   date; cd /tmp/base/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 1 test_ail_pre195 2>&1 | tail 
         17s bash   cd /tmp/rprobes && printf 'def main():\n    print((1 << 4194304) >> 4194304)\n\nmain()\n' > p9_wide_shift.py &
         10s bash   date; cd /tmp && rm -rf lmodes && mkdir lmodes && cd lmodes; for p in p1_min p7_boundary p3_reductions; do cp 
          6s bash   cd /tmp/rprobes && cat > p8_nofeature.py <<'EOF' def f(a, b):     s = a + b     t = [a, b, s]     d = {"k": s}
          6s bash   date; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$(basename $wt); rm -rf /tmp/dbgd_$tag; env 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T06:27:50Z
