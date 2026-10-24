# job job-pre134-10250029  started 2026-10-24T15:30:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":517,"duration_api_ms":397,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":475,"duration_api_ms":356,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre24 item: `del C` for a class-only name crashed both builds with compiler `KeyError: 'C'`. It is now refused by name at compile time, including module rebinding and `global C` forms; local/parameter shadow deletion still matches CPython.

Commits: `67e8b2d`, `88e0f38`, `7796e27` (final).

Probes via `cmp.sh`, both builds:
- `p13_del_class_use`, `p18_del_class_only`, `p19_del_two_classes`: refused by name
- `p16_del_rebound_class`, `p17_del_class_global_func`: refused by name
- `p14_del_local`, `p15_del_global_plain`, `p21_del_local_shadow_clean`, `p22_del_param_shadow_clean`: same stdout/exit as CPython
- `p1_del_attr`: unchanged named refusal

Added `test_ail_pre134.py` (7 tests) and registered it. Final tests: `test_ail_pre134`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed (218s). `update_manifest.py --check` exits 0. Not verified: speed/`icount` (`perf_event_open` denied). Later pre-existing items (`getattr(C, "__name__")`, `C.__name__ = "X"`, nested/local classes, `int.__name__`) remain untouched.
[cost $0.0000, opencode tokens {"total": 4043959, "input": 107880, "output": 11316, "reasoning": 20891, "cache.write": 0, "cache.read": 3903872}]
    tool time: bash 11.3 min, edit 0.0 min, write 0.0 min
        280s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre134 test_ail_sa
        220s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre134 test_ail_ch
         36s bash   cd /tmp/probes && WT=/home/runner/work/ail-ci/ail-ci; for p in p*.py; do echo "##### $p"; timeout 180 bash ~/t
         30s bash   cd /tmp/probes && cat > p21_del_local_shadow_clean.py <<'EOF' class C:     pass def local():     C = 3     del
         24s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p
         22s bash   cd /tmp/probes && cat > p13_del_class_use.py <<'EOF' class C:     pass del C try:     print(C) except NameErro
         19s bash   cd /tmp/probes && WT=/home/runner/work/ail-ci/ail-ci; for p in p13_del_class_use.py p18_del_class_only.py p19_
         16s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_p

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: job pre134 (`del` of a class name)

**Start:** 15:47 UTC. **What the diff really does:** adds one compile-time guard in `stmt_Delete` (`pyboxed2.py:10011`): a `del <name>` whose name is a known user class is refused with `Unsupported('del on the class name ...')` unless the name has a local slot, pointer or closure cell. That matches the report; codegen and generated C are untouched.

**Probes** (`cmp.sh`, HEAD vs `/tmp/base`):

| probe | HEAD | base | judgement |
| --- | --- | --- | --- |
| p1 `class C; del C; print(C)` | refused by name, both builds | compiler `KeyError: 'C'` | fixed |
| p7 `del C` in function, class at module | refused by name | `KeyError: 'C'` | fixed |
| p5 parameter + list item named C, `del` | matches CPython | — | ok |
| p6 no class feature: local/global/item/slice del | matches CPython | — | ok |
| p11 `import math as C; del C` | refused by name | `KeyError: 'C'` | fixed |
| p4 `class C; C=5; del C` | refused by name | worked | named refusal (allowed) |
| p12 `for C in range(3); del C` | refused by name | worked | named refusal (allowed) |
| p13 `except ... as C; del C` | refused by name | wrong output ("ok") | named refusal (allowed) |
| p8 `del h.attr` | refused by name | same refusal | pre-existing |
| p2 p3 p9 nested class / class-body `del` | refused | same refusal | pre-existing |
| p10 local shadow read after `del C` | prints `<object>` (CPython `NE`) | identical | pre-existing |

**No-feature C:** `--debug-dir` on p6 gives byte-identical `program.c` on HEAD and base (only temp paths in `native_report.json` differ). Confirms report.

**Tests:** `test_ail_pre134` + `test_ail_safetynet` on HEAD, `-j 2`: 2 modules, 0 failed (102 s). `update_manifest.py --check` exit 0. Registration in `ail_check.py`/manifest verified.

**Speed:** not checked; the change is compile-time-only and does not touch emitted code or runtime (report's `perf_event_open` note plausible).

**Claim check:** commits `67e8b2d`/`88e0f38`/`7796e27`, refusal of basic/global/rebound class deletes, local/parameter shadow matching, unchanged attr refusal, test addition, registration, manifest — verified. The 5-module 218 s test run and the worker's `/tmp/probes` p13–p22 themselves — unverified (I re-ran only the required modules and equivalent probes). The over-broad refusal of module-scope rebindings (`for C`, import alias) is not called out separately, but is covered by "including module rebinding"; it yields a named refusal, which the review rules permit.

**Unverified:** wider suite; worker's exact probe files; speed/icount.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 498159, "input": 63148, "output": 3798, "reasoning": 10861, "cache.write": 0, "cache.read": 420352}]
    tool time: bash 3.1 min
        104s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_pre134 test_
         29s bash   date; cd /tmp/rprobes && WT=/home/runner/work/ail-ci/ail-ci; for p in p*.py; do echo "##### $p"; timeout 300 b
         20s bash   date; cd /tmp/rprobes && WT=/tmp/base; for p in p1_basic.py p2_local_class.py p3_classbody.py p4_shadow_global
         13s bash   cd /tmp/rprobes && cat > p10_local_shadow_read.py <<'EOF' class C:     pass def f():     C = 3     del C     t
         12s bash   date; cd /tmp/rprobes && WT=/tmp/base; for p in p10_local_shadow_read.py p11_import_rebind.py p12_for_target.p
          5s bash   cd /tmp && rm -rf dbg_head dbg_base && mkdir -p dbg_head dbg_base && cp /tmp/rprobes/p6_nofeature.py dbg_head/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && (git worktree list | grep -q /tmp/base || git worktree add /tmp/base wor
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/ail_chatgpt.py compile --help 2>&1 | grep -i -A2 deb

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T16:50:10Z
