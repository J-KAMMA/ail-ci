# job job-rbpre255-10261620  started 2026-10-26T07:21:07Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":660,"duration_api_ms":542,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":625,"duration_api_ms":507,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied pre255 on branch `job-rbpre255-10261620`, commit `7b13076`.

- Kept current exact class-level folding; added named refusal for class constants routed through list item / attribute / dict value, pruning deferred lambdas and attribute-call callees.
- Added `test_ail_pre255.py`, registered it, added DEVLOG entries and DIFFERENCES row `C?-job-rbpre255-10261620-1`.
- `tools/diff_ids.py` is absent on this tree (noted in DEVLOG); `tools/update_manifest.py --check` passes.

Probes (`/tmp/probes`, both builds), all matched CPython or refused by name:
- Refused: `pre255_list_out`, `pre255_dict_out`, `pre255_attr_out`, `pre255_list_in`, `pre255_neg_out`, `pre255_empty`, `pre255_nested_arg`, `pre255_call_arg`, `pre255_unary`, `pre255_tuple_route`, `pre255_nested_class`.
- Matched CPython: `pre255_outside`, `pre255_method`, `pre255_lambda_list`, `pre255_lambda_dict`, `pre255_str_method`, `pre255_list_receiver_method`, `pre255_plain`.

Final-commit tests: 9 modules, 51 tests, 0 failed, 1 skipped (`pre255`, `pre227`, `pre253`, `pre116`, `pre170`, `pre184`, `safetynet`, `files`, `corpus_findings3`).
[cost $0.0000, opencode tokens {"total": 1002287, "input": 50947, "output": 6607, "reasoning": 7133, "cache.write": 0, "cache.read": 937600}]
    tool time: bash 10.7 min, edit 0.0 min
        491s bash   python3 -m unittest AIL_CURRENT.test_ail_pre255 AIL_CURRENT.test_ail_pre227 AIL_CURRENT.test_ail_pre253 AIL_CU
        117s bash   python3 -m unittest AIL_CURRENT.test_ail_pre227 AIL_CURRENT.test_ail_pre253 AIL_CURRENT.test_ail_pre116 AIL_CU
         27s bash   for f in /tmp/probes/pre255_*.py; do echo "=== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD"; done > /tmp/p
          6s bash   python3 -m unittest -v AIL_CURRENT.test_ail_pre255 2>&1 | tail -30
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre255-10260535 2>&1 | tail -5
          0s bash   git add AIL_CURRENT/DEVLOG.md AIL_CURRENT/MANIFEST.json AIL_CURRENT/ail_check.py AIL_CURRENT/ail_syntax.py AIL
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "check rc=$?"; git status -
          0s bash   python3 tools/update_manifest.py --check && echo manifest-ok; git status --short; git show --stat --oneline HE

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. Time used ~13 min; no source edits or commits made.

## What the change really does
A faithful re-apply of accepted pre255: it adds a pre-fold AST scan in `ail_syntax.fold_constants` that refuses by name any class-body arithmetic routed through a list item, attribute or dict value (`SyntaxErrorAIL`), pruning methods, nested classes, lambdas and attribute-call callees; it keeps the current tree's exact class-level folding. The `ail_syntax.py` hunk and `test_ail_pre255.py` are byte-identical to the fetched pre255 change.

## Probes (own, `/tmp/rprobes`, both builds via `cmp.sh`)
- Matched CPython: `r_plain_item` (`X = xs[0]`, no arithmetic), `r_dict_call` (`d["s"].upper()*2`), `r_attr_chain`, `r_int_module`, `r_no_feature`, `r_exact_fold` (current exact class fold kept).
- Refused by name: `r_cond` (route inside class `if`), `r_comp`, `r_unary`.
- `r_aug` and `r_lambda_default`: refused by pre-existing unrelated messages, identical on `/tmp/base`.
- Non-feature C with `--debug-dir`: `program.c` byte-identical to `/tmp/base` on both builds (only JSON temp paths differ).

## Pre-existing (identical on `/tmp/base`, do not block)
1. `N=2**62; xs=[N]; T=xs[0]; class C: X=T*4` → runtime `integer overflow`; not caught by the class-body scan.
2. `class C: X = d.get("n")*4` → same overflow via a method call on a dict.
3. Class-body `X *= 4` refused as unsupported class statement; lambda-default method call refused as unknown static kind.

## Tests on HEAD `7b13076`
`par_check.py -j 2 test_ail_pre255 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` rc=0. `tools/diff_ids.py` absent from base, history and HEAD (claim verified).

## Report claims
- Verified: refusal + pruning behaviour, test registration, DEVLOG/DIFFERENCES row, manifest check, all 11 listed probes refused by name and all 7 listed probes matching CPython, current exact folding kept.
- Unverified: the 9-module/51-test tally (I ran the 4 required/key modules); no runtime speed check needed (change is compile-time only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 913338, "input": 46628, "output": 4798, "reasoning": 13400, "cache.write": 0, "cache.read": 848512}]
    tool time: bash 6.0 min, grep 0.0 min
        264s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1700 python3 ../tools/par_check.py -j 2 test
         27s bash   cd /tmp/rprobes && cat > r_indirect.py <<'EOF' N = 2**62 xs = [N] class C:     T = xs[0]     X = T * 4 print(C
         27s bash   cd /tmp/probes && date && for f in pre255_*.py; do printf '%s: ' "$f"; out=$(timeout 300 bash ~/tools/cmp.sh "
         24s bash   cd /tmp/rprobes && for f in r_*.py; do echo "######## $f"; timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/w
          8s bash   cd /tmp/rprobes && rm -rf dbg_head dbg_base && mkdir dbg_head dbg_base && for m in g d; do if [ "$m" = g ]; th
          7s bash   cd /tmp/base && for f in r_aug.py r_lambda_default.py; do echo "### $f"; timeout 300 bash ~/tools/cmp.sh /tmp/
          0s bash   cd /tmp/rprobes && for f in r_*.py; do echo "######## $f"; timeout 300 bash ~/tools/cmp.sh "$f" "$PWD/../.." 2
          0s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre255-10260535 2>&1 | tail -3; git diff 294cf1d60739461d0

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T08:47:53Z
