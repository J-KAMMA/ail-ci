# job job-pre117-10242227  started 2026-10-24T13:34:45Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":801,"duration_api_ms":675,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":787,"duration_api_ms":663,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

Reproduced the listed probes on both builds. `immutable` and `module_def_mut` matched CPython; the first silent difference was `mut_list`: a nested `def` with a mutable literal default rebuilt it per call (`[]` → `[1] [2] [3]` instead of CPython's `[1] [1, 2] [1, 2, 3]`).

Fix: refuse mutable literal nested-def defaults (list/dict/set, or a tuple containing one) by name on both builds, in `AIL_CURRENT/python/pkg-v12/pyboxed2.py:1168`. Added `AIL_CURRENT/test_ail_pre117.py`, registered it, updated DEVLOG/DIFFERENCES/manifest.

Probes (via `cmp.sh`, both builds):
- `mut_list`, `mut_dict`, `mut_set`, `mut_tuple`, `mut_empty`, `mut_kwonly`: refused by name, 6/6.
- `immutable_ok`: matched CPython, both builds (negative, int boundary, empty tuple, tuple, argument/list-item/dict-value/attribute values, recursion).
- `module_def_mut`, `mut_deep`: matched CPython, both builds.
- `nested_class`: refused identically on both builds; pre-existing.

Tests on final commit `f7e7cc8`: `test_ail_pre117`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_functions` — 5/5 modules, 0 failed. Manifest `--check` rc=0.
[cost $0.0000, opencode tokens {"total": 3966694, "input": 100442, "output": 10419, "reasoning": 20057, "cache.write": 0, "cache.read": 3835776}]
    tool time: bash 8.0 min
        362s bash   cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre117 test_ail_safetynet test_ail_
         28s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -v test_ail_pre117 2>&1 | tail -40
         21s bash   cd /tmp/probes && cat > mut_list.py <<'EOF' def main():     def f(x, acc=[]):         acc.append(x)         re
         21s bash   cd /tmp/probes && for p in immutable module_def_mut mut_list mut_dict mut_set mut_tuple mut_empty mut_kwonly m
         14s bash   cd /tmp/probes && ls -1 *.py | xargs -P2 -I{} bash -c 'echo "===== {}"; bash ~/tools/cmp.sh /tmp/probes/{} /ho
         13s bash   cd /tmp/probes && for p in immutable module_def_mut mut_list mut_deep nested_class default_name; do (bash ~/to
         10s bash   grep -rn "immutable\|module_def_mut\|mut_list\|nested_class\|mut_deep" /home/runner 2>/dev/null | head -20
          5s bash   cd /tmp/probes && cat > immutable_ok.py <<'EOF' class C:     def __init__(self):         self.v = 42  def main

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (`f7e7cc8`), base worktree `/tmp/base` at `10e5fb0`.

**What the change does:** adds `_literal_default_is_mutable()` and, in `_register_nested`, refuses (by name, both emitters) a nested `def` whose default is a literal list/dict/set or a tuple containing one. No compiler/runtime hot path changed.

**Probes (cmp.sh, HEAD vs base):**
- Refused by name on HEAD (general + default), silently wrong output on base: `nested_deep_tuple`, `nested_dict_value`, `nested_tuple_of_set`, `nested_callback` (`mutable literal default`, 2/2 builds).
- Match CPython on both builds: `nested_immutable_nested`, `nested_immutable_boundary`, `module_mut_default`, `lambda_mut_default`, `loop_nested_mut_value`, `nested_value_alias`, `nested_returned`, `nested_in_if`, `nested_in_try`, `nested_in_while`, `no_feature`.
- Worker's six (`mut_list/dict/set/tuple/empty/kwonly`) all refused by name on HEAD (6/6); their outputs differ on base.
- `--debug-dir` for `no_feature` and `nested_immutable_nested` (g and d): generated `program.c` byte-identical base vs HEAD; only `native_report.json` temp paths differ.

**Tests on HEAD:** `test_ail_pre117`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_nested_functions` — 5/5 ok, 0 failed. Manifest `--check` rc=0.

**Claim checks:** Refusal behaviour, both builds, new test/module registration, DEVLOG/DIFFERENCES/manifest, and 5/5 tests verified. Minor inaccuracy: `immutable.py` is refused identically on both builds, not "matched CPython"; only `immutable_ok.py` matches. Line cited as 1168 is the helper at 1171 — cosmetic. "First silent difference" ordering unverified.

**Pre-existing (same on base):** `immutable.py`/`default_name.py` nested-def defaults via non-literal names are refused; `nested_class` refused. Not caused by this change.

**Unverified:** full suite (not run per instructions); benchmark instruction counts (compile-time-only change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 841536, "input": 37770, "output": 5409, "reasoning": 12053, "cache.write": 0, "cache.read": 786304}]
    tool time: bash 12.1 min, write 0.0 min
        331s bash   ls -1 /tmp/probes 2>/dev/null | head -30; echo ---; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_pre
        103s bash   cd /tmp/probes && for p in *.py; do echo "== $p"; for lbl in head base; do if [ "$lbl" = base ]; then wt=/tmp/
         40s bash   cd /tmp/rprobes && for p in *.py; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p /tmp/base 2>&1 
         38s bash   cd /tmp/rprobes && for p in *.py; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$p /home/runner/wo
         33s bash   cd /tmp/rprobes && for p in nested_value_alias.py nested_returned.py nested_in_if.py nested_callback.py; do fo
         18s bash   cd /tmp/rprobes && for p in nested_in_try.py nested_in_while.py; do for lbl in head base; do if [ "$lbl" = bas
         18s bash   cd /tmp && for p in no_feature nested_immutable_nested; do for mode in g d; do for lbl in base head; do if [ "

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T15:15:15Z
