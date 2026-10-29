# job job-pre440-10300211  started 2026-10-29T19:07:41Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"5cd8096e-405f-4d52-8bdb-154dd435fabf","context_usage_ratio":0.019625},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"e2d9b452-663e-4ea1-a54f-d02267df66f9","session_id":"c3ed209f-bfaf-49e9-a954-dd8cc29d392c"}

## worker report 0
[model qoder/DeepSeek-Flash]
Fixed the first still-differing item only.

**Cause:** `ail_dun_binop` in `AIL_CURRENT/python/pkg-v12/dunderrt.py` kept each operand's class name in `char na[80]`/`nb[80]`, so names were cut at 79. CPython caps `unsupported operand type(s)` names at 100 and concatenate/multiply names at 200. Operands now use 201-byte buffers, with `%.100s` in the unsupported-operand message.

**Verified on both builds** (`bash ~/tools/cmp.sh`, all 2/2 same stdout):
- `p_add_120`, `p_sub_120`, `p_mul_120` (two long instances)
- `p_add_79`, `p_add_80`, `p_add_99`, `p_add_100`, `p_add_101` (cap boundaries)
- `p_add_long_int`, `p_add_int_long`, `p_sub_100`, `p_subclass`
- `p_routes` (argument, alias, list item, attribute, dict value, instance+instance)
- `p_other_ops` (concat list/tuple/str, repeat, divmod, bitwise, shifts)
- `p_caps250` (250-char names: 100 for unsupported, 200 for concat/repeat)

**Untouched review items:** `p_case23` still shows the pre-existing `'exception'` operand text, `'exception'` ordering, and `**`'s missing `or pow()`; on this tree `//`, `%`, `/` already name operands.

**Tests:** `test_ail_pre440.py` (new), `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (362 s) on final HEAD. Manifest updated and `--check` passes.

**Commits:** `ada0a8a` (fix + test + records), `a77e041` (record wording correction). Not pushed.

## review 0
[model qoder/DeepSeek-Flash]
All probes match on HEAD; base reproduces the truncation. Final report:

## Review: pre440 (job-pre440-10300211)

**What the change really does:** in `AIL_CURRENT/python/pkg-v12/dunderrt.py:129-152`, `ail_dun_binop`'s operand-name buffers grow `na/nb[80]→[201]` and `buf[240]→[400]`, and the unsupported-operand format becomes `'%.100s' and '%.100s'`. That is exactly what the report says (fix of review item 1 only).

**Probes** (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, both builds g+d):

| probe | covers | HEAD |
|---|---|---|
| r1_bounds | `inst+int`, names 79/80/99/100/101/150/200/201/250 | 2/2 same |
| r2_concat | list/tuple/str `+` inst(150/250), `inst*str`, `list*inst` | 2/2 same |
| r3_routes | arg, alias, list item, attribute, dict value, both orders | 2/2 same |
| r4_ops | divmod(2 ways), `//`,`%`,`/`,`<<`,`>>`,`&`,`|`,`^` w/ 220-char name | 2/2 same |
| r5_two | two long operands 100/101/250 | 2/2 same |
| r6_sub | subclass of 120-char base; concat with 200/201-char names | 2/2 same |
| r9_modfmt | `"fmt"%o`, `"abc"%o`, `1%o` | 2/2 same |
| no-feature C | `--debug-dir` vs base | identical (g and d) |
| with-class C | `--debug-dir` vs base | d identical; g differs only in the two intended lines |

**Base comparison:** r1 fails on base for every name ≥80 (e.g. n=100: CPython 147 vs base 126; `inst+inst` = 244 vs 202); r9 `1%o` base 126 vs CPython 147. Both now correct on HEAD. r7 (exception operand prints `'exception'`) and r8 (`**` missing ` or pow()`) are **byte-identical to base** → pre-existing.

**Claims:** cause/implementation — verified. Probe list — verified via my equivalents. "Untouched items" — verified (r7/r8 match base; `//`,`%`,`/` name operands). Tests (4 modules, 0 failed) — I re-ran `test_ail_pre440` + `test_ail_safetynet`: **2 modules, 0 failed (154 s)**; `test_ail_files`/`test_ail_corpus_findings3` not re-run (per review rule). Manifest `--check` — verified exit 0.

**Speed:** `perf_event_open` is denied in this container, so no icount. Static check instead: `ail_dun_binop` disassembly of gdev `g14_014` is instruction-for-instruction identical head vs base; only the stack frame grows 0x1b8→0x348 (cold path, dunder miss). No hot-loop change.

**Pre-existing (block nothing):** `'exception'` for `+` with an exception operand (base-identical, r7); `**` omits ` or pow()` (base-identical, r8); non-ASCII class names still render as `?`.

**Note (not a defect):** `test_ail_pre440` is not added to `ail_check.MODULES`/`ci_shards.json`, so CI's shard discovery won't pick it up; the task did not ask for registration.

VERDICT: ACCEPT

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T21:00:47Z
