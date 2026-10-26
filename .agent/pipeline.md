# job job-rbpre201-10261355  started 2026-10-26T04:56:33Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":552,"duration_api_ms":435,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":526,"duration_api_ms":407,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `fecf613` on `job-rbpre201-10261355`.

**Applied:** pre201's shared 2**20-bit constant-fold budget (2**24 special) in `_check_constant_power`, via `_const_fold_int`. Kept this tree's existing generic out-of-int64 shift refusal (pre236/pre241 wording) instead of duplicating pre201's refusal path.

**Changed:** `AIL_CURRENT/ail_chatgpt.py`, `ail_check.py`, new `test_ail_pre201.py`, `MANIFEST.json`, `DEVLOG.md`, `DIFFERENCES.md`, `tools/ci_shards.json` (7 files).

**Tests (final commit, `-j 2`):** 10/10 passed — `pre201`, `pre190`, `pre205`, `pre191`, `pre236`, `pre241`, `pre121`, `safetynet`, `files`, `corpus_findings3` (239s). `pre195` was run but fails `over_fold_limit`; I confirmed the identical failure on clean HEAD, so it is pre-existing.

**Probes (`~/tools/cmp.sh`, both builds):**
- Out-of-range shifts (bool/int/negative/argument/list/class attr/dict/assignment): refused by name, no overflow — 1/1.
- `((10**64)**64) >> 100001`: now matches CPython (0) — direct, argument, list, dict, nested argument/list.
- Attribute assignment/module/class/default forms of that wide fold: refused by name, same as the accepted `FETCH_HEAD` tree.
- Boundaries `(1<<1048575)>>1048575` match; `(1<<1048576)>>1048576` refused by name; negative counts match.
- `True/False/0` shift widths and `True<<62` match.

`python3 tools/diff_ids.py` could not run: that file does not exist in this tree. `update_manifest.py --check` passes. Nothing pushed.
[cost $0.0000, opencode tokens {"total": 5617970, "input": 123591, "output": 12582, "reasoning": 20165, "cache.write": 0, "cache.read": 5461632}]
    tool time: bash 11.0 min, edit 0.0 min, read 0.0 min
        302s bash   python3 tools/par_check.py -j 2 test_ail_pre201 test_ail_pre190 test_ail_pre195 test_ail_pre205 test_ail_pre19
        241s bash   python3 tools/par_check.py -j 2 test_ail_pre201 test_ail_pre190 test_ail_pre205 test_ail_pre191 test_ail_pre23
         36s bash   cd /tmp/probes && cat > p201_in_module.py <<'EOF' X = ((10 ** 64) ** 64) >> 100001 print(X) EOF cat > p201_in_
         24s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && python3 tools/par_check.py -j 
         20s bash   cd /tmp/probes && for p in p201_*.py; do echo "======== $p"; bash ~/tools/cmp.sh /tmp/probes/$p "$PWD/../../ho
         13s bash   git worktree add --detach /tmp/headbase HEAD >/tmp/wt2.log 2>&1; echo rc=$?; cd /tmp/headbase && python3 tools
         10s bash   cd /tmp/probes && cat > p201_wide_arg.py <<'EOF' def take(v):     print(v) take(((10 ** 64) ** 64) >> 100001) 
          8s bash   cd /tmp/probes && for p in p201_in_range.py p201_out_bool.py p201_out_pow_wider.py p201_out_int.py; do echo "=

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `rbpre201` (HEAD `fecf613`)

**What the diff really does:** adds `_const_fold_int` with the pre190 2**20-bit budget (2**24 for a 0/1/-1 exponent) and rewires `_check_constant_power`/`_check_constant_out_of_range` to it; it does *not* add pre201's separate shift-refusal path, because the tree's generic constant folder already refuses out-of-int64 shifts. This matches the report.

**Probes** (`bash ~/tools/cmp.sh`, both builds; base `/tmp/headbase`):

| probe | HEAD vs CPython | base |
|---|---|---|
| `r1a` direct `((10**64)**64)>>100001` → `0` | same (both) | refused (fix) |
| `r1b` argument, `r1c` list+dict item | same (both) | refused (fix) |
| `r1d` class attr / `r1e` module assign | refused by name, same as FETCH_HEAD | refused (pre-existing) |
| `r2` `(1<<1048575)>>1048575`, `>>1048576`, `(10**64)>>100000`, negative count | same (both) | line 5 refused (fix) |
| `r3` hidden power `((10**64)**64 << 1) >> 1` | refused by name | same refusal |
| `r4` bool/boundary/zero (`True<<62`, `False<<64`, `0<<1000000`, huge `& 0`) | same (both) | same |
| `r5` out-of-range shifts via argument/list/dict/attr | refused by name, no overflow | same refusal |
| `r6` no-feature program | same; generated `program.c` identical to base (only report paths differ) | — |

Boundaries around the 2**20 budget and the 4096-bit module/class check behave exactly as FETCH_HEAD.

**Tests:** `python3 tools/par_check.py -j 2 test_ail_pre201 test_ail_safetynet` → 2/2 ok (83s). `update_manifest.py --check` → rc 0. `tools/diff_ids.py` is absent (verified), as reported.

**Claims:** commit/branch, files changed, fold-budget application, kept generic refusal, boundaries, missing `diff_ids.py`, manifest check: verified. Worker's other module results (pre190/205/191/236/241/121/files/corpus_findings3) and the pre195 pre-existing failure: unverified (not rerun, per the targeted-test rule).

**Pre-existing:** `r1d`/`r1e`/`r3` named refusals and the `r5` refusal are identical on base; they are acceptable named refusals, not caused by this change. No new difference versus CPython, no wrong output or crash. Speed not checked: the change is compile-time-only.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1726010, "input": 87742, "output": 5844, "reasoning": 22696, "cache.write": 0, "cache.read": 1609728}]
    tool time: bash 2.1 min
         84s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre201 test_ail_safetynet
         16s bash   date; cd /tmp/rprobes && for p in r1a_direct r1b_arg r1c_list_dict r1d_attr r1e_assign r2_bounds r3_hidden r4_
          8s bash   cd /tmp/rprobes && cat > r1a_direct.py <<'EOF' print(((10 ** 64) ** 64) >> 100001) EOF cat > r1b_arg.py <<'EOF
          8s bash   date; cd /tmp/rprobes && for p in r1_paths r2_bounds r3_hidden r4_zero_and_bools r5_refuse_paths r6_no_feature
          6s bash   date; cd /tmp/rprobes && for p in r1a_direct r1b_arg r1c_list_dict r1d_attr r1e_assign r2_bounds r3_hidden r4_
          2s bash   set -e; rm -rf /tmp/cmpc_head /tmp/cmpc_base; mkdir -p /tmp/cmpc_head /tmp/cmpc_base; cd /tmp/cmpc_head; cp /t
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git fetch https://github.com/J-KAMMA/ail-ci.git job-pre201-10260354 2>&1
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/ail_chatgpt.py compile --help 2>&1 | grep -i -A2 deb

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T06:10:39Z
