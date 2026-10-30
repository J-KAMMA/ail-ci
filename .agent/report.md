# job job-fz204-10300805  started 2026-10-29T23:34:15Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> _requests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard","request_id":"2b62db3a-a47a-40ba-a94f-3cfb8cd49589","context_usage_ratio":0.01963},"modelUsage":{"dfmodel":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0,"credits":0}},"permission_denials":[],"fast_mode_state":"off","uuid":"82f3a97e-4d40-4bd8-8e08-94c2dd3561dd","session_id":"863bd229-d56e-4558-aba9-1b94b1208847"}

## worker report 0
[model qoder/DeepSeek-Flash]
## Report — fz204 (seed 2075520147): does not reproduce

**Result: the difference does not show on this tree; nothing changed, nothing committed.**

### 1. Reproducer check
Generated the program with `python3 lab/fuzz/gen.py 2075520147 -o …` and diffed it against the report text: **byte-identical**. Ran it every way the job specifies:

| run | CPython 3.12 | default build | unified (`g`) | `AIL_IR=0` | `AIL_IR=1` |
|---|---|---|---|---|---|
| `bash ~/tools/cmp.sh /tmp/probes/fz204.py $PWD` | exit 0 | exit 0, same stdout | exit 0, same stdout | — | — |
| direct compile + run | exit 0 | — | — | exit 0, same | exit 0, same |
| `lab/fuzz/run.py --start 2075520147 --count 1` | — | mode `default`: same | — | — | mode `ir`: same |

The reported `TypeError: '<' not supported between instances of 'object' and 'int'` at `v9.sort(key=lambda q: (-q, q))` (stdout line 39) no longer occurs; all 43 output lines match CPython. The whole-seed run reports `DIFF 0, crash 0` in both modes.

### 2. Cause note (no fix made)
The offending construct is a **`list.sort`/`sorted` key that returns a tuple compared element-wise**. It is already handled, and already pinned by `test_ail_fuzz_findings.py` (`alias_eq_sortkey`, which contains the identical `v9.sort(key=lambda q: (-q, q))` line); that module passes (23 tests, OK).

### 3. Probes run (all `bash ~/tools/cmp.sh`, g + d, plus `AIL_IR=1`) — all match CPython, no refusal
- `fz204.py` — exact reproducer
- `v1_tuplekey_ints.py` — int tuple key, negatives/duplicates, `sorted`
- `v2_tuplekey_items.py` — key from list items (`r[0], r[1]`), `-p[1]`
- `v3_tuplekey_attr.py` — dataclass attribute tuple key, `min`/`max`
- `v4_tuplekey_str.py` — `(len, w)` / `(w[0], w[1:])` keys, `sorted(dict)`
- `v5_print_line.py` — `"<%5d>" % 91`, `café`, `'AbCd' * 1`, `%d` of a float
- `v6_tuplekey_mixed.py` — int vs str tuple element: same `TypeError` text as CPython

Boundaries covered: empty/negative/duplicate keys, str/float/attr/list-item sources, comparison-error parity.

### 4. Other differences seen
None — the seed's run showed 0 DIFF, 0 crash, 0 timeout in both modes.

No files were modified (`git status` shows only the pre-existing untracked `.agent/pipeline.md`), so there was no code change to commit or test.

FINAL VERDICT: NOCHANGE  2026-10-29T23:44:46Z  (the worker changed nothing; no review was run)
