# job job-pre137-10250031  started 2026-10-24T15:59:27Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":812,"duration_api_ms":687,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"success","duration_ms":2020,"duration_api_ms":1884,"is_error":false,"num_turns":1,"result":"pong","stop_reason":"end_turn","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_

## worker report 0
[model qoder/DeepSeek-Flash]
Done. Commit `3fae150` on `job-pre137-10250031`.

**Task interpretation.** The pre22 difference list was missing from the exported task text (only its "Speed"/"Unverified" notes survived). I reproduced the documented open rows in `DIFFERENCES.md` order; the first that still differed was `C?-job-fuzz8-10220554-1`: negative `r` for `itertools.permutations` / `combinations` / `combinations_with_replacement` returned `[]` on both builds vs CPython's `ValueError: r must be non-negative`.

**Fix.** Added `ail__it_reject_negative_r` in `cruntime.py` (OBJ2 runtime) raising `ail_raise_c(cx, AIL_B_VALUEERROR, "r must be non-negative")`; the pool is still materialized first, so a non-iterable argument raises TypeError first as in CPython. `r > n`, `r == 0` and the `product(repeat=-1)` path are unchanged. Added `test_ail_pre137.py` (4 tests) and registered it in `ail_check.MODULES`; updated the DIFFERENCES row to `fixed` and added a DEVLOG entry.

**Probes** (`bash ~/tools/cmp.sh`, both builds unless noted):
- `neg_r_perm`, `neg_r_comb`, `neg_r_cwr`: same as CPython (literal/var/list/dict/attr/argument, empty pool, zero, r>n).
- `neg_r_catch`: same (caught `ValueError`, `str(e)`, `e.args`, no-iterate call, nested helper).
- `neg_r_inputs`: same (generator consumed before the check, custom iterable, bool, r=n, tuple/range inputs).
- `typed_loop_neg`, `prod_neg_repeat`, `catch_order_exact`: same.
- `neg_r_uncaught`: general path same (exit 1, exact stderr); default build cannot compile the typed `list(permutations(...))` shape — a pre-existing C error that also occurs on the base with `r=1` (`toplevel_perm`).
- `neg_r_types`: differs for float/str/explicit-None `r` — byte-identical on the base, so pre-existing and recorded in DEVLOG, not fixed.

**Tests on committed tree:** `test_ail_pre137`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (24 s, 122 s, 129 s, 203 s). `update_manifest.py --check` exits 0. Working tree has no diff from HEAD (only untracked `.agent/pipeline.md`, left alone). Speed not measured; the change only adds a branch on the `r < 0` error path.

## review 0
[model qoder/DeepSeek-Flash]
All verification done. Writing the report.

## Review: pre137 — negative `r` in itertools choosers

**What the change really does.** In the general-path C runtime (`cruntime.py`, OBJ2) `ail_it_permutations`, `ail_it_combinations` and `ail_it_combinations_wr` now raise a catchable `ValueError("r must be non-negative")` when `r < 0`, after the pool is materialized; `r > n` still yields the empty iterator, and the `combinations_wr` check order is swapped harmlessly. This matches the report.

**Probes** (HEAD, both builds; `bash ~/tools/cmp.sh`, CPython oracle):

| probe | result |
|---|---|
| p01_basic (r=-1,-2; all 3) | general matches; default build compile fails (same on base, see below) |
| p02_order (call-time raise, generator consumed first, non-iterable/None → TypeError first) | both match |
| p03_empty (empty pool ±r, r=0, r>n, bool, range/tuple, `product(repeat=-1)`) | both match |
| p04/t_uncaught (uncaught, exit 1, exact stderr) | general matches; test's local-`r` variant matches on both builds |
| p05_channels (literal/arg/list item/attr/dict/sum) | both match |
| p10_order2 (generator raising before check; dict/str pool; r=INT64_MIN) | both match |
| p11_typed (statement/for-loop shapes) | both match (base: no error) |
| p07_rtypes (float/str/None `r`) | identical output on HEAD **and base** → pre-existing |
| p12_leak (100k caught ValueErrors) | RSS 10.5 MB, 0.03 s — no leak (frame roots are popped before raise) |
| p06_nofeature (no itertools) | output matches; default-build C byte-identical, general C differs only by the added helper |

**Pre-existing (identical on `/tmp/base`, does not block):**
- Default/typed build emits bad C (`ail_list_push` given `ail_list`) for `out = list(itertools.permutations(<literal>, r))` and `return list(...)`; reproduced on base with `r=1` and `r=5`.
- float/str/None `r` still disagree with CPython (byte-identical on base), including an `AIL internal error: out of memory` in that program.

**Claims:** task-list absent from `.agent/task.md` — verified; chosen difference `C?-job-fuzz8-10220554-1` fixed — verified; pool-first ordering — verified; tests/manifest/DEVLOG/DIFFERENCES updates — verified; `update_manifest.py --check` rc=0; commit message ends with the required trailer; worktree clean except untracked `.agent/pipeline.md`. `test_ail_pre137` (24 s) and `test_ail_safetynet` (121 s) pass on HEAD.

**Unverified:** `test_ail_files` / `test_ail_corpus_findings3` (worker reports pass; not re-run per review rules); gdev instruction counts (`perf_event_open: Permission denied` — logic shows the normal path's comparison count is unchanged, only an extra branch on the `<0` path).

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T17:33:32Z
