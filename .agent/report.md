# job job-pre70-10241829  started 2026-10-24T09:29:49Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"success","duration_ms":1938,"duration_api_ms":1798,"is_error":false,"num_turns":1,"result":"pong","stop_reason":"end_turn","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_

## worker report 0
[model qoder/DeepSeek-Flash]
**Report**

The attached task's list was blank, so I recovered the qtest2 reviewer's recorded list read-only from `origin/job-qtest2-10241617` (its `pipeline.md`, last fetch, no push). Its "Pre-existing" items:
1. run-time `sep=None` via variable/list/dict → `ValueError: empty separator` (first still differing).
2. maxsplit constant above int64 → `integer overflow` (not touched).

**Fix** (`a8955f5`): the emitter already accepted a run-time `None` (`sn` check); only the runtime helpers didn't. Four lines in `python/pkg-v12/cruntime.py`: `ail_meth_str_split`, `ail_meth_str_rsplit`, `ail_str_split_sep`, `ail_str_split_sep_into` now treat a None-tagged separator as whitespace mode (covers pooled `x = recv.split(sep)`). Added `AIL_CURRENT/test_ail_pre70.py`, registered it, DEVLOG + DIFFERENCES row (`C?-job-pre70-10241829-1`), manifest re-pinned.

**Probes** (`/tmp/probes`, both builds, all `same stdout` unless noted):
- `eq01_var`, `eq02_list`, `eq03_dict`, `eq04_arg`, `eq05_types`, `eq06_empty`, `eq07_typed`, `eq08_assign` (pooled), `eq09_typed`, `eq10_lit`, `eq12_max` (0/1/2/-1/-2/100), `eq13_empties`, `eq11b_nonstr` (3, 3.0, bytes, list → TypeError) — 13/13 match CPython on both builds.
- `eq11_nonstr` (includes `object()`): refused by name on both builds, acceptable.
- Manifest `--check` passes on the final commit.

**Tests** (final commit, `-j 2`): `test_ail_pre70`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 328s, 0 failed.

**Unverified:** full suite (per instructions); speed (compile/runtime path only, no hot code measured). Second pre-existing item left unchanged.

## review 0
[model qoder/DeepSeek-Flash]
All checks done. Final report:

**What the change really does.** Adds one `sepobj.tag == AIL_T_NONE` test to four boxed-runtime helpers (`ail_str_split_sep`, `ail_str_split_sep_into`, `ail_meth_str_split`, `ail_meth_str_rsplit`), routing a run-time `None` separator into the existing whitespace-mode helpers; plus a test module, DEVLOG/DIFFERENCES rows, `ail_check` registration and manifest repin. It matches the report.

**Probes** (`/tmp/rprobes`, `cmp.sh`, g + d builds):
| probe | HEAD | base |
|---|---|---|
| p1 None via var/list/dict/attr/arg, maxsplit 0/1/2/−1/−2/100, empty/ws receivers | same stdout both | exit 1 `ValueError: empty separator` |
| p2 split/rsplit assigned to names | same both | exit 1 |
| p3 non-str seps (int, float, bytes, list, dict, bool) + `sep=""` | same both | same both |
| p4 maxsplit matrix, unicode/control whitespace (`\xa0`, `\u2028`, `\x0b`, `\x1c`) | same both | exit 1 |
| p5 sep kind changes in one variable, list/dict mutation between calls | same both | exit 1 |
| p8 genuinely pooled `x = recv.split(sep)` (C confirms `ail_str_split_sep_into` is emitted; loop reuses the pool) | same both | exit 1 |
| p10 None from `dict.get` | same both | — |
| p11 receiver from list item/dict value/attribute + list mutation | same both | exit 1 |
| p12 `x = " a b ".split(x[0])` with `x = [None]` (pool aliasing) | same both | exit 1 |
| p9 `object()` sep, `*args` | named refusal, identical on base | identical |
| p6 no-feature program | same; default-build `program.c` byte-identical to base | — |

General build's C for p6 differs from base only by the 4 added runtime lines (the runtime is embedded; no codegen change).

**Claims.** Emitter's `sn` check / boxed `None` in `_m_split`: verified. "Four lines": verified exactly 4. Pooled `_into` fix: verified by probe (though the committed `ASSIGN_POOL` test forwards/returns its lists, so `_list_poolable` is false and it does not itself reach `_into` — coverage nit, not a defect). Non-str TypeError / empty-sep ValueError: verified, and identical to base. Manifest `--check`: verified rc 0. `test_ail_files`/`test_ail_corpus_findings3`: unverified (not re-run per reviewer rule).

**Tests (HEAD):** `test_ail_pre70` 28 s, `test_ail_safetynet` 124 s, 0 failed. `ci_shards.py --check` prints `unassigned: test_ail_pre70` (rc 0; missing modules still run per its docstring).

**Pre-existing:** p3 behavioural results are identical on base (correct TypeError/ValueError); `object()`/`*args` named refusal exists on base; the qtest2 item 2 (constant maxsplit > int64) was left alone, as the task scoped one cause.

**Unverified:** instruction counts — `perf_event_open` denied in this runner; the added cost is one predictable tag compare per split call, on programs whose split sites use literal separators.

VERDICT: ACCEPT

FINAL VERDICT: ACCEPT  2026-10-24T09:50:45Z
