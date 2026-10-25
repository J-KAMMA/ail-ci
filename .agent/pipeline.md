# job job-pre203-10252345  started 2026-10-25T14:46:15Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":386,"duration_api_ms":267,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":388,"duration_api_ms":272,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `131ace0` on `job-pre203-10252345`.

**Fix:** The integration tree’s generic constant folder capped intermediates at 4096 bits, breaking both suites. `pyfunc.py` now ends with `_CONST_INT_BITS = max(_MAXSPLIT_BITS, 8192)` (shares pre200’s limit); larger values remain refused by name. Added an invariant test, DEVLOG entry, DIFFERENCES row, and refreshed `MANIFEST.json`.

**Verification**
- Final-commit tests: `test_ail_pre203`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 180s.
- Reproduced integration tree (`origin/integ` + pre200 + this commit): `test_ail_pre200` + `test_ail_pre203` — 6 tests, OK, 18.6s.
- Probes, both builds:
  - Local: `pre203fix_routes`, `pre203fix_boundary`, `pre203fix_plain` — same stdout as CPython.
  - Integration: `pre203fix_integration` — same stdout; `pre203fix_largepow`, `pre203fix_above_limit`, `pre203fix_above_limit2` — refused by name.
- `python3 tools/update_manifest.py --check` — rc 0.

`test_ail_pre200.py` is not in this branch, so it was verified on the temporary integration tree.
[cost $0.0000, opencode tokens {"total": 9997180, "input": 159559, "output": 16162, "reasoning": 54803, "cache.write": 0, "cache.read": 9766656}]
    tool time: bash 8.7 min, edit 0.0 min
        182s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre203 test_ail_safetynet test_
         45s bash   rm -rf /tmp/scen; git worktree add --detach /tmp/scen origin/job-pre204-10252054 >/dev/null 2>&1; cd /tmp/scen
         21s bash   rm -rf /tmp/oninteg_fix; git worktree add --detach /tmp/oninteg_fix origin/integ >/dev/null 2>&1; cd /tmp/onin
         21s bash   cd /tmp/oninteg && sed -i 's/^_CONST_INT_BITS = _MAXSPLIT_BITS$/_CONST_INT_BITS = 1 << 22/' AIL_CURRENT/python
         20s bash   cd /tmp/oninteg && printf '\n_CONST_INT_BITS = _MAXSPLIT_BITS\n' >> AIL_CURRENT/python/pkg-v12/pyfunc.py && cd
         20s bash   cd /tmp/oninteg && sed -i 's/^_CONST_INT_BITS = 1 << 22$/_CONST_INT_BITS = max(_MAXSPLIT_BITS, 8192)/' AIL_CUR
         20s bash   rm -rf /tmp/integ3; git worktree add --detach /tmp/integ3 6ea4722 >/dev/null 2>&1; cd /tmp/integ3; for b in jo
         19s bash   rm -rf /tmp/oninteg_final; git worktree add --detach /tmp/oninteg_final origin/integ >/dev/null 2>&1; cd /tmp/

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review complete. No source edits or commits made.

**What the diff really does:** appends `_CONST_INT_BITS = max(_MAXSPLIT_BITS, 8192)` at EOF of `pyfunc.py` (so it overrides the integration folder's 4096 when merged), plus an invariant test, DEVLOG entry, DIFFERENCES row and refreshed MANIFEST. Matches the report.

**Probes** (`~/tools/cmp.sh`, both builds; base = `origin/cand-1025225738`, fixed = cand + this commit):

| probe | result on cand+fix | cand base |
|---|---|---|
| `(1<<8000)>>7980`; `(1<<8191)>>8190`; `-((1<<8191)>>8128)` | same stdout as CPython | refused by name |
| 5000/8191-bit values via argument, list item, attribute, dict, local | same stdout, both builds | refused by name |
| `(1<<8192)>>8191`; `(1<<9000)>>8990`; out-of-int64 results | named compile refusal | same refusal |
| nested unary overflow, `-(-9223372036854775808)` | named refusal | same |
| plain program (no constants) | generated C byte-identical to cand | — |

On the branch itself, wide constants such as `(1<<8000)>>7980` still fail with runtime `integer overflow`, identical on base `work`: pre-existing.

**Tests**
- HEAD `test_ail_pre203` + `test_ail_safetynet`: OK; `test_ail_files` + `test_ail_corpus_findings3`: OK.
- cand base: `test_ail_pre200`+`test_ail_pre203` FAIL (3 failures).
- cand+fix: `test_ail_pre200`+`test_ail_pre203` 6 tests OK (21.2s); `test_ail_pre113`+`test_ail_pre172` OK.
- `tools/update_manifest.py --check` rc 0.

**Claims:** all report claims verified; worker's own probe files were not inspected, but the same behaviours were reproduced independently.

**Pre-existing:** branch-level wide-constant runtime overflow; generic folder's power-width overestimate refuses some ≤8192-bit expressions by name both before and after (e.g. `(2**5000)>>4999`); duplicate `_pow_within_maxsplit_bits` defs already present in cand. None caused by this change.

**Unverified:** runtime speed (change is compile-time only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1773535, "input": 58540, "output": 7978, "reasoning": 19337, "cache.write": 0, "cache.read": 1687680}]
    tool time: bash 5.1 min
        112s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_fin
         70s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre203 test_ail_safetynet
         21s bash   date; cd /tmp/rev_fix/AIL_CURRENT && python3 -m unittest -q test_ail_pre200 test_ail_pre203 2>&1 | tail -8
         19s bash   date; cd /tmp/oninteg/AIL_CURRENT && python3 -m unittest -q test_ail_pre200 test_ail_pre203 2>&1 | tail -20
         17s bash   date; cd /tmp/rev_cand/AIL_CURRENT && python3 -m unittest -q test_ail_pre200 test_ail_pre203 2>&1 | tail -25
         16s bash   date; for p in /tmp/rprobes/p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" /tmp/oninteg 2>&1 | sed -n '1,
         13s bash   date; for p in /tmp/rprobes/p*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ail-c
         12s bash   date; for p in /tmp/rprobes/p3_overcap.py /tmp/rprobes/p4_int64.py /tmp/rprobes/p6_types.py /tmp/rprobes/p7_sh

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T16:08:25Z
