# job job-pre131-10250027  started 2026-10-24T15:28:05Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":573,"duration_api_ms":443,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":578,"duration_api_ms":452,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Report**

The task file's list after "recorded these as already present" was empty, so I used the first still-open row in `DIFFERENCES.md`: `C?-job-fuzz8-10220554-1` (negative `r` for `permutations` / `combinations` / `combinations_with_replacement`). It still differed on both builds.

**Change:** the three general-path runtime iterators in `cruntime.py` now raise `ValueError("r must be non-negative")` after materializing the pool, so a non-iterable pool still raises `TypeError` first. `r=0`, `r > n`, and positive `r` are unchanged. Added `AIL_CURRENT/test_ail_pre131.py`, registered it in `ail_check.MODULES`, updated `DIFFERENCES.md`, `DEVLOG.md`, and the manifest. Commit `fa779e2`.

**Probes** (both builds unless noted, `cmp.sh`):
- `p_pre131_main.py` — literals, args, list/attribute/dict values, empty pool, 0, `r>n`: both match CPython.
- `p_pre131_order.py` — non-iterable pool raises `TypeError` first, generator consumed before `ValueError`, aliasing: both match (exit 1).
- `p_pre131_product.py` — `product(repeat=...)` and positive cases unaffected: both match.
- `p_pre131_qual.py` — module-qualified calls: general path now matches; default build C-compile failure is identical on the base worktree (pre-existing).
- `p_pre131_types_small.py` / `p_pre131_width.py` — non-int `r` and `10**20` still differ, identically on base (pre-existing, not caused by this change).
- `p1d.py` — positive from-import regression: both match.

**Tests on final commit:** `test_ail_pre131`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 pass, 334 s; `update_manifest.py --check` rc=0. Full suite and speed/icount not run by design. Nothing pushed.
[cost $0.0351, opencode tokens {"total": 2159665, "input": 104661, "output": 13086, "reasoning": 9022, "cache.write": 0, "cache.read": 2032896}]
    tool time: bash 8.5 min, edit 0.0 min, read 0.0 min, write 0.0 min
        337s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "manifest rc=$?"; cd AIL_
         30s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_pre131_main p_pre131_order p_pre131_product p_pre131_qual p1d
         28s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p1_perm_neg p2_enum_start p3_reversed p5_nesting; do echo "====
         27s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_pre131_main.py <<'EOF' from itertools import permutations, c
         15s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/pre131base HEAD >/tmp/wt.log 2>&1; cat /tmp/wt.log
         12s bash   cd /tmp/probes && cat > p_pre131_main.py <<'EOF' from itertools import permutations, combinations, combination
         10s bash   cd /tmp/probes && cat > p_pre131_types_small.py <<'EOF' from itertools import permutations, combinations, comb
          9s bash   cd /tmp/probes && cat > p1b.py <<'EOF' import itertools print(list(itertools.permutations([1,2,3], -1))) print

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does:** In the general-path C runtime, `ail_it_permutations`, `ail_it_combinations` and `ail_it_combinations_wr` now raise `ValueError("r must be non-negative")` after materializing the pool, instead of silently returning an empty iterator; the `r > n` and positive-`r` paths are unchanged.

**Probes** (all via `bash ~/tools/cmp.sh`, HEAD and `/tmp/base`; `g`=general, `d`=default):
- `r1_values.py` — all three functions, `r` = `-2**62,-100,-1,False,True,0,1,3,4` and via attribute/list-item/dict/expression: HEAD g+d match CPython; base g+d differ (return `[]`).
- `r2_order.py` — generator consumption and a pool whose `__iter__` raises: generator is consumed, its error propagates before `ValueError`; non-iterable `Bad` raises `RuntimeError` first. HEAD g+d match; same on base.
- `r3_create.py` — iterator creation raises eagerly, caught 3× in a loop, `e.args` correct: HEAD g+d match.
- `r4_qualified.py`, `r6_keyword.py` — module-qualified and keyword `r=-1`: HEAD general matches; default build C-compile failure identical on base.
- `r5_controls.py` — empty pool, `r=0`, `r>n`, `r` omitted, `product(repeat=-1/-3)`, list mutation after building the iterator: HEAD g+d match.
- `r7_width.py` — `10**20`, `2**63`, `-(2**63)`: compile-time `integer overflow` refusal, identical on base.
- `r8_types.py` — float/str/None/list `r`: outputs identical on HEAD and base.
- `nofeature.py` — no itertools: user C (`program_mix0.c`) byte-identical to base; `program.c` differs only in the three embedded runtime helper branches; behavior matches CPython on both builds.
- Regression test itself: copied to `/tmp/base/AIL_CURRENT`, `test_ail_pre131` fails on base (`FAILED (failures=1)`) and passes on HEAD, so it does guard the fix.

**Report claims:** all verified — empty task list → first open row used; difference on both builds; change description; TypeError/consumption order; `r=0`/`r>n`/positive unchanged; product unaffected; module-qualified fix and pre-existing default-build failure; non-int/out-of-int64 `r` identical on base; `test_ail_pre131`/`test_ail_safetynet`/`test_ail_files`/`test_ail_corpus_findings3` 4/4 pass in 257 s; `update_manifest.py --check` rc=0; commit `fa779e2` contains the stated files.

**Pre-existing (not blocking):**
- Default-build C compile failure for module-qualified/keyword `itertools` calls (`ail_list` vs `int64_t` at `ail_list_push`), identical on base.
- Non-int `r` and out-of-int64 `r` produce the same wrong/refused output on base and HEAD.
- AIL subset refusals I hit in first-draft probes (function values, `getattr` on modules) are unrelated compiler limits.

**Unverified:** speed/icount — `tools/icount.c` builds but `perf_event_open` returns `Permission denied` in this container; the changed code is a cold refusal path with one extra branch per call. Full suite not run by design.

No defect attributable to the change. No source edits or commits made.

VERDICT: ACCEPT
[cost $0.0257, opencode tokens {"total": 1053642, "input": 70519, "output": 8372, "reasoning": 12063, "cache.write": 0, "cache.read": 962688}]
    tool time: bash 6.5 min
        259s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre131 t
         30s bash   date; cd /tmp/rprobes && for f in r1_values r2_order r3_create r4_qualified r5_controls; do echo "============
         22s bash   cd /tmp/rprobes && cat > r6_keyword.py <<'EOF' from itertools import permutations, combinations, combinations_
         21s bash   date; cd /tmp/rprobes && for f in r1_values r2_order r3_create r4_qualified r5_controls; do echo "============
         12s bash   cd /tmp/rprobes && echo "=== nofeature head"; bash ~/tools/cmp.sh nofeature.py /home/runner/work/ail-ci/ail-ci
         12s bash   cd /tmp/rprobes && rm -rf /tmp/dbg_head_g /tmp/dbg_base_g /tmp/dbg_head_d /tmp/dbg_base_d && for tag in head b
         11s bash   cd /tmp/rprobes && cat > r8_types.py <<'EOF' from itertools import permutations, combinations, combinations_wi
          6s bash   cd /tmp/rprobes && echo "=== r1 BASE"; bash ~/tools/cmp.sh r1_values.py /tmp/base 2>&1 | sed -n '1,35p'

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T17:04:24Z
