# job job-pre52-10270755  started 2026-10-26T22:56:06Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":589,"duration_api_ms":472,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":551,"duration_api_ms":438,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done on branch `job-pre52-10270755`, commit `ffa6595` (not pushed).

- Cause: current `integ` already contains the pre27 form of this refusal, which scans the whole `try` and does not set a column. When the branch was applied, integration's version won, so `test_ail_pre52` failed 6 subtests (`handler`/`else`/`finally` imports were treated as guarded).
- Fix: updated the branch onto current `integ`, preserving pre52's narrower semantics — scan only the `try` body, report the first guarded import's `line:column`, and keep an import only in a handler/`else`/`finally` at the generic caught-type refusal located at the `try`. Kept `test_ail_pre52`, registered it, added DEVLOG/DIFFERENCES rows, refreshed `ci_shards.json`, and regenerated `MANIFEST.json` (`--check` passes).
- Tests on the final tree: `test_ail_pre52`, `test_ail_pre27`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 237 s, 0 failed. `test_ail_safetynet` was already passing; only `test_ail_pre52` reproduced the reported failure.
- Probes: 18 in `/tmp/probes/pre52_*.py`, both builds — 3 accepted programs match CPython exactly; 15 refusals are by name (11 guarded-import refusals, 4 located caught-type refusals, including the shadowed-`ImportError` pre-existing refusal).
[cost $0.0540, opencode tokens {"total": 5854107, "input": 126994, "output": 10178, "reasoning": 19527, "cache.write": 0, "cache.read": 5697408}]
    tool time: bash 7.9 min
        238s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_pre52 test_ail_pre
         81s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_safetynet 2>&1 | tail -80
         54s bash   cd /tmp/merge/AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_pre52 2>&1 | tail -100
         52s bash   cd AIL_CURRENT && timeout 600 python3 -m unittest -q test_ail_pre52 2>&1 | tail -60
         44s bash   mkdir -p /tmp/probes && cd /tmp/probes && python3 - <<'PY' from pathlib import Path cases = { 'pre52_body_impo
          2s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 git fetch --no-tags origin integ:refs/remotes/origin/integ j
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree remove --force /tmp/merge >/dev/null 2>&1; git worktree add
          0s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/merge && git worktree add --detach /tmp/merge origin/integ >

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Relative to current `integ` (8346862) the authored delta is only: add/register `test_ail_pre52.py`; narrow `stmt_Try`'s guarded-import scan from `ast.walk(node)` to `node.body`; set `source_column` on the guarded-import and caught-type refusals; DEVLOG/DIFFERENCES/ci_shards/MANIFEST rows. The rest of `work..HEAD` is the merge bringing `integ` in (35k lines) plus branch `.agent`/`corpus/gdev`. That matches the report.

**Probes** (`/tmp/rprobes`, cmp.sh, both builds):
- r1 body import → refused `p.ail:2:5` guarded-import; same on integ.
- r2/r3/r4 import only in handler/else/finally → HEAD `p.ail:1:1: a caught exception type ImportError`; integ `p.ail:4:5`/`6:5` guarded-import. Intended narrowing; both are named refusals.
- r5 `except Exception` with import in body → both builds match CPython.
- r6 plain try/except IndexError → both builds match CPython; `program.c` identical to integ.
- r7 nested `if` import, tuple handler → refused `p.ail:4:13`, both builds.
- r8 import after `s = "é";` on one line → refused but no `path:line:col`; **identical on integ**, so pre-existing multi-statement-line source-map loss.
- Re-ran all 18 worker `pre52_*` probes: 3 accepted match CPython, 15 refused by name, consistent with the report.

**C unchanged.** `--debug-dir/program.c` for r6 and `corpus/gdev/g00_000.py`, `g00_002.py` is byte-identical between HEAD and clean integ 8346862. Against `work` (23a82d7) it differs only by the integrated runtime changes, not this change.

**Tests.** `par_check.py -j 2 test_ail_pre52 test_ail_safetynet`: 2/2 ok (48s, 76s). Also `test_ail_pre27`: ok (26s). `update_manifest.py --check`: exit 0. Per instructions I did not run `test_ail_files` or `test_ail_corpus_findings3`.

**Report claim check.** Cause (integ wide scan → 3 handler/else/finally cases × 2 builds = 6 subtests) verified from integ source and base probes. Fix semantics, registration, DEVLOG/DIFFERENCES row, ci_shards entry and MANIFEST check verified. Test-list claim partly verified (pre52/safetynet/pre27 yes; files/corpus_findings3 unverified). Probe claims verified. Minor nit: the printed column comes from the loader's source map, not the newly added `source_column`; harmless here.

**Pre-existing.** (1) r8 loses the location when the guarded import shares a line with another statement — same on integ. (2) C differences vs `work` come from the integration merge, not this change.

**Defects:** none.

VERDICT: ACCEPT
[cost $0.0479, opencode tokens {"total": 3685770, "input": 113403, "output": 9408, "reasoning": 24399, "cache.write": 0, "cache.read": 3538560}]
    tool time: bash 3.6 min
         77s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1000 python3 tools/par_check.py -j 2 test_ail_pre52 test
         28s bash   cd /tmp/rprobes && for p in pre52_alias_from pre52_alias_handler pre52_body_import pre52_else_only pre52_final
         27s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/par_check.py -j 1 test_ail_pre27 2>&1 | tail -
         20s bash   cd /tmp/rprobes && for p in r1_body_import r2_handler_import r3_else_import r4_finally_import r5_exception_ok 
         15s bash   cd /tmp/rprobes && for p in pre52_body_and_handler pre52_nested_function pre52_shadow_exc_name pre52_plain_imp
         13s bash   cd /tmp/rprobes && for p in r1_body_import r2_handler_import r3_else_import r4_finally_import r8_unicode_col; 
          9s bash   set -e cmp_c() {   src=$1; name=$2   for wt in /home/runner/work/ail-ci/ail-ci /tmp/intbase /tmp/base; do     
          8s bash   rm -f /tmp/r6.*.c /tmp/g00000.*.c /tmp/g00036.*.c cmp_c() {   src=$1; name=$2   for wt in /home/runner/work/ai

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T00:09:48Z
