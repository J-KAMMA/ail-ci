# job job-pre254-10260535  started 2026-10-25T20:37:59Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":590,"duration_api_ms":455,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":573,"duration_api_ms":448,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining pre-existing difference.

- Cause: `module_bare_annotation` in `AIL_CURRENT/ail_syntax.py` silently returned for a starred subscript slice; the value-less annotation was then dropped.
- Fix: refuse it by name at compile time (exit 2) and detect stars inside nested tuple displays too.
- Added `AIL_CURRENT/test_ail_pre254.py` with 11 refused shapes and 10 valid CPython-parity cases; registered it in `ail_check.MODULES`.
- Updated `DIFFERENCES.md` (`C?-job-pre254-10260535-1`) and `DEVLOG.md`; `update_manifest.py --check` passes.

Probes on both builds:
- Refused by name: `pre254_direct`, `pre254_tuple_form`, `pre254_mixed`, `pre254_nested`, `pre254_future`; attribute/list-item/dict-value/call bases and empty-star cases.
- Match CPython: `pre254/valid_{list_star2,dict_star,call_star,nested_subscript_star2,ifexp_star,binop_star,nested_tuple_no_star,attr_star_load2,with_value_tuple,with_value_nested}.py`.
- `pre254_local.py` and `pre254_class.py` were already refused by name and remain so.

Final commit `fd5fb88`: `test_ail_pre254`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_pre124`, `test_ail_pre125` — 35 tests, OK (1 skipped).
[cost $0.0000, opencode tokens {"total": 3994749, "input": 123131, "output": 11968, "reasoning": 13634, "cache.write": 0, "cache.read": 3846016}]
    tool time: bash 16.3 min
        296s bash   cd AIL_CURRENT && python3 -m unittest test_ail_pre254 test_ail_safetynet test_ail_files test_ail_corpus_findin
        213s bash   cd AIL_CURRENT && python3 -m unittest test_ail_corpus_findings3 2>&1 | tail -25
        135s bash   cd AIL_CURRENT && python3 -m unittest test_ail_files 2>&1 | tail -25
        125s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_safetynet 2>&1 | tail -40
         52s bash   cd AIL_CURRENT && python3 -m unittest test_ail_pre124 test_ail_pre125 2>&1 | tail -20
         48s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_pre254
         41s bash   mkdir -p /tmp/probes/pre254 cat > /tmp/probes/pre254/valid_list_star.py <<'EOF' xs = {0: "zero"} a = [0] def a
         23s bash   cat > /tmp/probes/pre254/valid_list_star2.py <<'EOF' xs = {(0,): "zero"} a = [0] def ann():     print("ann") x

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review of job `pre254` (commit `fd5fb88`)

**What the diff really does:** in `module_bare_annotation` (AIL_CURRENT/ail_syntax.py:2692-2732), `_annotation_slice_parts` now recurses into tuple displays and `module_bare_annotation` raises `SyntaxErrorAIL` instead of silently returning when the slice contains a `Starred`. Adds `test_ail_pre254.py`, registers it, plus DIFFERENCES/DEVLOG/MANIFEST. Matches the report.

**Probes** (`/tmp/rprobes`, `cmp.sh` on HEAD and `/tmp/base`):

| probe | CPython | HEAD g/d | base g/d |
|---|---|---|---|
| `xs[*a]: ann()` | SyntaxError | exit 2, refused by name | exit 0, ran (DIFF) |
| `xs[*a,]:`, `xs[0,*a,*b]:` | SyntaxError | exit 2 refused | exit 0 ran |
| `xs[((*a,),)]: ann()` | SyntaxError | exit 2 refused | exit 0 ran (`ann`) |
| module `if`/`try` blocks, same form | SyntaxError | exit 2 refused | exit 0 ran |
| `xs[[*a]]:`, `xs[key(*a)]:`, `xs[([*a],)]:`, `xs[(1,2)]:`, `xs[(*a,):2]:` | ok | match both builds | match |
| `xs[*a]: ann = 3` (value form) | ok | matches | matches |
| function/class-level starred | SyntaxError | refused by name | refused by name (pre-existing) |

C for a non-star program (`plain.py`, incl. nested-tuple annotation) is identical between HEAD and base on both builds (`--debug-dir`, only temp paths in `native_report.json` differ).

**Tests:** `par_check -j 2 test_ail_pre254 test_ail_safetynet` → 2 modules, 0 failed. `tools/update_manifest.py --check` → rc 0. Test contains 11 refused / 10 valid cases, 2 test methods.

**Claims:** cause verified; refusal exit 2 on both builds verified; nested-tuple detection verified; test counts/registration verified; manifest/DIFFERENCES/DEVLOG verified. No claim found false.

**Pre-existing (not caused):** function/class-level starred targets refused by name on both base and HEAD; value-form `xs[*a] = ...` exits 1 on both.

**Not checked:** full suite (per instructions), speed (change is compile-time only, no hot code).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 456277, "input": 24388, "output": 4256, "reasoning": 7665, "cache.write": 0, "cache.read": 419968}]
    tool time: bash 3.9 min
        130s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && time python3 ../tools/par_check.py -j 2 test_ail_pre254 test
         36s bash   cd /tmp/rprobes && for p in p_direct.py p_trailing.py p_mixed.py p_nested.py p_func_level.py p_valid_list.py p
         32s bash   cd /tmp/rprobes && for p in p_*.py; do echo "=== $p HEAD"; bash ~/tools/cmp.sh $p /home/runner/work/ail-ci/ail
         11s bash   cd /tmp && cat > plain.py <<'EOF' xs = {(1, 2): "z"} a = 1 b = 2 def ann(): print("ann") xs[(a, b)]: ann() xs[
          9s bash   cd /tmp/rprobes && cat > p_if_block.py <<'EOF' xs = [1, 2] a = [0] def ann(): print("ann") if True:     xs[*a]
          8s bash   cd /tmp/rprobes && for m in g d; do if [ $m = g ]; then export AIL_UNIFIED_FORCE=1; else unset AIL_UNIFIED_FOR
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh p_class.py /home/runner/work/ail-ci/ail-ci 2>&1 | sed -n '1,20p'
          0s bash   git worktree add /tmp/base work >/dev/null 2>&1; ls /tmp/base/AIL_CURRENT | head -3; echo done

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T22:17:52Z
