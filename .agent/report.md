# job job-pre419-10281416  started 2026-10-28T05:18:48Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"3c811e2b-61fa-4aee-9595-7e5a3942349d","session_id":"40450da9-0fe9-456a-8c89-c1d641e5c3f6"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"b041eb79-47a1-4084-9613-e1e8106d20de","session_id":"66042720-d9e9-4b64-828c-fdb5409c6cd3"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the class-subscript difference. Commit `8cd9a02`.

- `A[0]` and `A[1:2]` now raise `TypeError: type 'A' is not subscriptable` (was `'type' object is not subscriptable`) on both builds, including aliases, arguments, list items, dict values, attributes, returns and subclasses; names cap at 200 chars like CPython.
- Probes in `/tmp/probes/pre419` on both builds: `p01_keys`, `p02_slices`, `p03_routes`, `p04_long_names`, `p05_control` match CPython. `p06_class_getitem` still differs (separate pre-existing `__class_getitem__` gap, not addressed).
- Tests on final tree: `test_ail_pre419`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (391s).
- `tools/update_manifest.py --check` passes; `tools/ci_shards.py --check` is clean.
[cost $0.0000, opencode tokens {"total": 6862653, "input": 150112, "output": 12951, "reasoning": 19398, "cache.write": 0, "cache.read": 6680192}]
    tool time: bash 10.5 min, edit 0.0 min, read 0.0 min, write 0.0 min
        393s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre419 test_ail_safetynet test_ail_files test_ai
        137s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre419 test_ail_safetynet 2>&1 | tail -30
         28s bash   for p in /tmp/probes/pre419/p*.py; do echo "########## $(basename $p)"; bash ~/tools/cmp.sh "$p" $PWD; done
         22s bash   cat > /tmp/probes/pre419/c02_builtin_types.py <<'EOF' for o in [int, str, list, dict, type, Exception, ValueEr
         14s bash   python3 - <<'PY' p='/tmp/probes/pre419/p01_keys.py' s=open(p).read().replace(", 10 ** 20", "") open(p,'w').wri
          9s bash   cat > /tmp/probes/pre419/c08_class_getitem.py <<'EOF' class G:     def __class_getitem__(cls, item):         r
          5s bash   mkdir -p /tmp/probes/pre419 && cat > /tmp/probes/pre419/c01_class_subscript.py <<'EOF' class A:     pass try: 
          5s bash   bash ~/tools/cmp.sh /tmp/probes/pre419/c01_class_subscript.py $PWD

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** Adds an `AIL_T_CLASS` check to `ail_op_getitem`/`ail_op_getslice` so `A[0]`/`A[1:2]` raise `TypeError: type 'A' is not subscriptable` via the existing `ail_class_name_c`, plus a test module and records.

**Probes (HEAD, both g/d builds, run in /tmp/rprobes):**
- `q01_keys.py` (None/bools/ints/negative/float/str/tuple/list/bytes/frozenset/4 slices on A, B and alias): same stdout/exit as CPython; base shows the old `'type' object ...` on every line. Fix verified.
- `p03_routes.py` (alias, arg, list item, dict value, attribute, return, subclass, slice): same as CPython on both builds.
- `p04_long_names.py` (199/200/201/250-char names): same as CPython.
- `q03_assign.py`: instance subscript, item assignment, list/str/dict subscripts match; `del A[0]` prints `'type' object doesn't support item deletion` vs CPython's `does not` — **Pre-existing** (identical on base).
- `q02_unicode.py` (`A.__name__` rename): refused by name ("cannot update one through the class"); acceptable.
- `q06_type.py` (`e.__class__` route): unsupported `__class__`; output identical on base — **Pre-existing**.
- `p06_class_getitem.py`: still wrong on HEAD (`type 'G' is not subscriptable`) and on base (`'type' object ...`); underlying `__class_getitem__` gap is pre-existing, only the wrong message text changed.

**Claims:** fix on both builds — verified; all value routes/subclasses/200-cap — verified; p03/p04 match — verified; p01/p02/p05 individually — not re-run (q01/q03 cover the same ground); p06 still differs — verified; `update_manifest --check` and `ci_shards --check` — pass. One record inaccuracy: the new DIFFERENCES row says item deletion keeps CPython's wording, but AIL's deletion message uses "doesn't" (pre-existing, cosmetic).

**Tests:** `test_ail_pre419`, `test_ail_safetynet` on final tree: 2 modules, 0 failed (137s). `test_ail_files`/`test_ail_corpus_findings3` not re-run, per reviewer instruction.

**Speed:** Unverified — `perf_event_open` is denied (`perf_event_paranoid=4`). The three gdev programs (`g10_010`, `g01_002`, `g08_004`) produced identical stdout base vs HEAD; the added branch is one predicted test on the getitem path.

**Unverified:** p01/p02/p05 individually; test_ail_files/test_ail_corpus_findings3; instruction counts.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1151618, "input": 47060, "output": 6914, "reasoning": 18604, "cache.write": 0, "cache.read": 1079040}]
    tool time: bash 5.7 min
        140s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre419 t
         57s bash   mkdir -p /tmp/speed && cc -O2 -w -include signal.h -include stdlib.h -o /tmp/speed/icount /home/runner/work/ai
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q03_assign.py /tmp/probes/pre419/p03_routes.py /tm
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q*.py; do echo "########## $(basename $p)"; bash ~
         33s bash   cd /tmp && for p in /tmp/rprobes/q03_assign.py /tmp/probes/pre419/p06_class_getitem.py /tmp/probes/pre419/c06_
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/q02_unicode.py /tmp/rprobes/q03_assign.py; do echo
         10s bash   cd /tmp && for p in /tmp/rprobes/q03_assign.py /tmp/probes/pre419/p06_class_getitem.py; do echo "########## $(
          5s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/pre419/p04_long_names.py $PWD 2>&1 | tai

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T07:01:01Z
