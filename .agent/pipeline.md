# job job-rbpre420-10290915  started 2026-10-29T00:35:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"bad18cc5-d0d2-4e27-b72e-a0a321258110","session_id":"a48a3f09-565e-4fa0-8992-88a741f85176"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"70d0fdd9-2cda-48fb-bd6b-dc6721f3f33d","session_id":"2ca28cdf-f424-4e8e-a2de-4bce7d860308"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied pre420 and committed as `6a7bee5`.

**Changes:**
- `cruntime.py`: list/tuple read index error now uses `ail__tname_c(key)` in a dynamically sized 200-char-capped buffer.
- `pyboxed2.py`: removed the now-redundant compile-time read-error rewrite; kept its write-side rewrite (both fixes retained).
- Added `test_ail_pre420.py`, registered in `ail_check.MODULES`.
- DEVLOG + DIFFERENCES records, manifest updated and `--check` passes.

**Probes (both builds, `cmp.sh`):**
- `pre420_types.py` — direct/arg/list-item/attribute/dict-value keys, list/tuple/empty, subclass, `__index__`, float/str/None/bool/negative: both builds same stdout as CPython.
- `pre420_long.py` — class names 200/201/210/500 chars: both builds same.
- `pre420_exc.py` — exception classes as keys: both builds same.

**Tests on final commit:** `test_ail_pre420`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 26 tests, OK (1 skipped: no zig for Windows target).

`tools/diff_ids.py` is not present on this tree; nothing was pushed.
[cost $0.0000, opencode tokens {"total": 1070082, "input": 43560, "output": 6624, "reasoning": 4730, "cache.write": 0, "cache.read": 1015168}]
    tool time: bash 9.3 min, edit 0.0 min
        370s bash   python3 -m unittest -v test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -40
        161s bash   python3 -m unittest -v test_ail_pre420 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail
         11s bash   for p in pre420_types pre420_long pre420_exc; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"
          7s bash   python3 -m unittest -v test_ail_pre420 2>&1 | tail -30
          7s bash   for p in pre420_types pre420_long pre420_exc; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py "$PWD"
          2s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre420-10281637 2>&1 | tail -5 && git diff ba60bdeb6ccafc1
          0s bash   git add AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/cruntime.py AIL_CURRENT/python/pkg-v12/pyboxed2.py
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "check=$?"

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** applies pre420's unconditional `cruntime.py` read-index fix (`ail__tname_c`, dynamically sized 200-capped message) and removes this tree's now-redundant compile-time read rewrite in `pyboxed2.py`, keeping its write-side rewrite. This matches the fetched `job-pre420` diff plus the necessary conflict resolution; nothing else changed.

**Probes (my own, `/tmp/rprobes`, `cmp.sh`, both builds, base comparison):**

| probe | covers | HEAD | base |
|---|---|---|---|
| p1_types | direct/arg/list-item/attr/dict-value, list/tuple/empty, subclass, exception, float/str/None/bytes/bool/negative/2**? | matches CPython | now differs (class names wrong: "instance") |
| p2_long | class names 199/200/201/210/500 | matches CPython (200-cap) | matches too (tree rewrite) |
| p3_dunder | `__index__` int/bool/non-int/raises | non-int case differs (pre-existing) | identical difference |
| p4_write | setitem/delitem bad keys, class/subclass/float/None | class names correct; tuple-del wording differs (pre-existing) | identical difference |
| p5_plain | no bad index, no feature use | matches CPython; default-build C unchanged | — |
| p6_unicode | non-ASCII class names | refused by name (ASCII-only) | same refusal |
| p7_args | error message/`.args` retained across repeated raises | matches CPython (copy/free safe) | matches |

**Pre-existing (identical on `/tmp/base`, non-blocking):**
- `__index__` returns non-int: `list indices ... not float` instead of `__index__ returned non-int (type float)` (report acknowledges).
- Tuple deletion wording: `'tuple' object doesn't support item deletion` vs CPython `does not support`.
- `10**20` index: both match CPython's `IndexError: cannot fit ...`; no defect.

**Report claims:** cruntime/pyboxed2 edits, test addition+registration, DEVLOG/DIFFERENCES, manifest `--check` all verified. Test file is byte-identical to fetched pre420. `tools/diff_ids.py` confirmed absent. Worker probe files exist. Tests on HEAD: `test_ail_pre420`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass (`-j 2`). Speed: not checked; change is on a cold error path only.

One note: general-path C for a program without the feature changes only inside the runtime helper; this is inherent to the accepted runtime change, and default-build C is unchanged.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1201909, "input": 46677, "output": 6414, "reasoning": 12690, "cache.write": 0, "cache.read": 1136128}]
    tool time: bash 6.7 min
        305s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre420 test_ail_
         25s bash   cd /tmp/base && for p in p1_types p2_long p3_dunder p4_write p5_plain; do echo "===== $p BASE"; bash ~/tools/c
         24s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_types p2_long p3_dunder p4_write p5_plain; do echo "===== $p
         22s bash   cd /tmp/rprobes && for spec in "head /home/runner/work/ail-ci/ail-ci d" "base /tmp/base d" "head /home/runner/
          8s bash   cd /tmp/rprobes && cat > p7_args.py <<'PY' class C:     pass class D(C):     pass  a = [1, 2] keep = [] for i 
          6s bash   cd /tmp/rprobes && python3 - <<'PY' s = '''class Caf\u00e9:     pass class \u03a9mega:     pass a = [1, 2] for
          6s bash   cd /tmp/rprobes && for m in g d; do  for tree in head base; do   wt=/home/runner/work/ail-ci/ail-ci; [ $tree =
          3s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh /tmp/rprobes/p6_unicode.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-29T02:12:59Z
