# job job-rbpre183-10252048  started 2026-10-25T11:48:58Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":444,"duration_api_ms":324,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":374,"duration_api_ms":255,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Re-applied pre183 on branch `job-rbpre183-10252048`; commits `27521a7` (change) and `31f54d1` (manifest pin). The bytes/bytearray membership text was already fixed on this tree (`_ail_bcontains`, pre114), so the new work is the builtin/type tuple-member naming plus tests.

Probes in `/tmp/probes/` (all matched CPython on both `cmp.sh` builds):
- `pre183_builtin_member.py` — `len`/`abs`/`ord`/`bool` via literals, variables, args, list items, dict values, attributes, scalar form, both methods, early match, invalid/negative windows, empty tuple, user function.
- `pre183_bytes_contains.py` — str/float/None/list/tuple plus bytes/bytearray/int/bool/out-of-range ints on both receivers through args, list items, dict values, attributes, and methods.
- `pre183_misc.py` — `abs`/`repr`/`chr`, variable `bool`, normal searches, and other tuple member types.

Tests on final commit: `test_ail_pre183`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 27 tests, OK (1 skipped: no zig for Windows target). Manifest `--check` passes. Note: `tools/diff_ids.py` does not exist in this tree, so that command could not be run.

Untracked `.agent/pipeline.md` was left untouched.
[cost $0.0217, opencode tokens {"total": 1842936, "input": 56845, "output": 8712, "reasoning": 4451, "cache.write": 0, "cache.read": 1772928}]
    tool time: bash 11.0 min
        411s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre183 test_ail_safetynet te
        183s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_pre183 test_ail_safetynet test_
         41s bash   cd /tmp/probes && for p in pre183_builtin_member.py pre183_bytes_contains.py pre183_misc.py; do echo "##### $p
         22s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre183 2>&1 | tail -30
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre183-10251542 2>&1 | tail -5 && git diff --stat 6ffad059
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py | tail -5 && python3 tools/update_manif
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status --short && git diff --stat HEAD~2..HEAD && python3 tools/upda
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/ail_chec

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds a `builtin_fn` byte to `ail_funcobj`, tags synthetic builtin-value lambdas (`1` = builtin, `2` = `bool`/type), and makes `ail__tname_c` return `builtin_function_or_method` / `type`. It also re-adds `test_ail_pre183.py`, registers it in `ail_check.py`, and adds a DIFFERENCES row. The bytes-membership prelude hunk from pre183 is correctly omitted: `_ail_bcontains` (pre114 row, DIFFERENCES.md:44) already matches CPython.

**Report claims**
- Commits `27521a7` + `31f54d1` — verified.
- Bytes/bytearray membership already fixed, no prelude edit — verified: p3 matches CPython identically on base and HEAD; `_ail_bcontains` is present.
- Worker probes (`/tmp/probes/pre183_*`) matched on both `cmp.sh` builds — verified by re-running all three.
- Tests on final commit (`test_ail_pre183`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`) — verified: `par_check.py -j 2` reports 4 modules, 0 failed (exact 27/1-skip count not recounted).
- `update_manifest.py --check` passes — verified (rc 0).
- `tools/diff_ids.py` absent — verified.
- `.agent/pipeline.md` untouched — verified.
- Minor omission: report does not mention the `ail_check.py` module registration; benign (needed for CI to run the test).

**Probes (in /tmp/rprobes)**
- `p5` (len/abs via literal, list, dict, attr, return; empty/invalid/negative window, early hit) and `p7` (bool, mixed `len`/`bool`, bool via list/dict/attr): match CPython on HEAD; base prints `function` — feature verified.
- `p2` (user function, shadowed `len`, class, instance): HEAD and base match CPython.
- `p3` (str/float/None/int/bool/bytes/bytearray on both receivers via arg/list/dict/attr): HEAD and base match CPython.
- `p4` (unrelated program): generated user-code C identical base vs HEAD; only the embedded runtime typedef/helper/`mc_key` init differ, expected for this runtime change.

**Pre-existing** (identical on `/tmp/base`): named compile-time refusals in `p1`, `p1b`, `p6`, `p8` for builtins outside `_BUILTIN_VALUE_ARITY`, tuple members through untyped wrapper arguments, and module-level rebinding of builtin names. No defect.

**Unverified:** exact test count/skip; speed (change is error-path-only, so hot-code impact not applicable).

VERDICT: ACCEPT
[cost $0.0319, opencode tokens {"total": 2372719, "input": 76011, "output": 9205, "reasoning": 13583, "cache.write": 0, "cache.read": 2273920}]
    tool time: bash 6.7 min
        276s bash   cd /home/runner/work/ail-ci/ail-ci && ls tools/par_check.py && date && cd AIL_CURRENT && timeout 1500 python3 
         37s bash   cat /tmp/probes/results.log; echo "=== rerun ==="; cd /tmp/probes && date && for p in pre183_builtin_member pr
         20s bash   cd /tmp/rprobes && date && for p in p2 p3 p5; do echo "######## $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.
         19s bash   cd /tmp/rprobes && date && for p in p1 p2 p3; do echo "######## $p HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$p.
         14s bash   cat > /tmp/rprobes/p7.py <<'PY' class Box:     pass  def probe(tag: str, f) -> None:     try:         print(ta
          8s bash   cat > /tmp/rprobes/p1b.py <<'PY' def probe(tag: str, f) -> None:     try:         print(tag, f())     except T
          7s bash   cd /tmp/rprobes && for p in p1 p1b; do echo "### $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /tmp/base 2>
          7s bash   cat > /tmp/rprobes/p6.py <<'PY' def probe(tag: str, f) -> None:     try:         print(tag, f())     except Ex

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:12:04Z
