# job job-pre432-10281950  started 2026-10-28T10:59:09Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"86cf55f5-309e-48c5-9039-2c2e79ee7880","session_id":"6bd90842-2e80-478c-bc9b-e8bea6a8b732"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"2567bd10-7b57-4977-bee2-a2fd8c53022f","session_id":"67939b56-b901-432b-9278-fa55da14c8e7"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing rbpre395 item: `del A[0]` on a class object now says CPython's `'type' object does not support item deletion` (E()[0] was already fixed by pre414).

- Commit: `c1f472c`
- Change: class-object branch in `ail_op_delitem` (`AIL_CURRENT/python/pkg-v12/cruntime.py:16135`)
- Added `AIL_CURRENT/test_ail_pre432.py` (3 tests); registered in `ail_check.MODULES` and `ci_shards.json`
- Probes (both builds): `pre432_del_class_stmt2`, `pre432_del_class_routes`, `pre432_dunder_delete` match CPython; `pre432_del_types` class/subclass match, int/None remain the pre-existing `doesn't` wording; `pre432_slice_args` still differs only on `A[slice('a','b')]`, the next pre-existing item
- Tests: `test_ail_pre432`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 233 s, 0 failed
- `update_manifest.py --check` rc 0; `ci_shards.py --check` rc 0
[cost $0.0000, opencode tokens {"total": 3505525, "input": 101070, "output": 9919, "reasoning": 20328, "cache.write": 0, "cache.read": 3374208}]
    tool time: bash 4.9 min, edit 0.0 min
        234s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre432 test_ail_safetynet test_ail_files test_ai
         22s bash   for p in /tmp/probes/pre432_*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail -30; done
         11s bash   for p in /tmp/probes/pre432_del_class_stmt2.py /tmp/probes/pre432_del_class_routes.py /tmp/probes/pre432_del_t
          8s bash   cat > /tmp/probes/pre432_del_class_routes.py <<'PY' class A:     pass  class B(A):     pass  class Holder:    
          7s bash   cat > /tmp/probes/pre432_exc_read.py <<'PY' class E(Exception):     pass  class F(E):     pass  def show(label
          6s bash   cat > /tmp/probes/pre432_exc_item2.py <<'PY' class E(Exception):     pass  class F(E):     pass  def show(labe
          3s bash   cat > /tmp/probes/pre432_dunder_delete.py <<'PY' class D:     def __delitem__(self, k):         print('deleted
          2s bash   timeout 120 git fetch origin refs/heads/job-rbpre395-10281537:refs/remotes/origin/job-rbpre395-10281537 refs/h

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `c1f472c` vs `work` (base `/tmp/base` at `940dad0`).

**What the diff really does:** adds one cold branch in `ail_op_delitem` (`AIL_CURRENT/python/pkg-v12/cruntime.py:16135`): a class receiver now raises `TypeError: 'type' object does not support item deletion` instead of the generic `doesn't` text. Plus `test_ail_pre432.py`, registrations, DEVLOG/DIFFERENCES. Matches the report.

**Probes** (`/tmp/rprobes`, both builds, head vs base):
- `p1_direct`: subclass, negative/bool/wide/str/None/float/empty keys, slices, alias/arg/list-item/dict-value/attribute/return, direct statement — base differs, head matches CPython.
- `p2_nonclass`: instance/exception/str/tuple match; int/None/bool/float still say `doesn't` — identical on base (pre-existing).
- `p3_meta` (metaclass `__delitem__`): refused by name on both.
- `p4_nofeature`: same stdout on both; debug-dir C deltas only the one embedded runtime line (runtime is embedded in every program).
- `p5_empty`, `p8_slice` (incl. slice(`'a'`,`'b'`), step 0, long class name): head matches CPython.
- `p6_builtin_class` (Exception subclass E/F): base differs, head matches.
- `p7_exc_inst`: `E()[0]` already matches base and head, so `del A[0]` is indeed the first still-differing rbpre395 item.
- `p9_sliceargs`: `A[slice('a','b')]` still differs, identically on base and head (next pre-existing item).

**Tests:** `test_ail_pre432 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4 modules, 168 s, 0 failed. `update_manifest.py --check` rc 0; `ci_shards.py --check` rc 0.

**Claims:** verified — first differing item, wording on class/subclass/exception-class/builtin-int class, all routes, int/None (and bool/float) remaining pre-existing, slice-args next item, commit, registrations, manifest/shard checks. Unverified — full suite, speed (error-only path; no hot code).

**Pre-existing:** int/None/bool/float item-deletion wording (`doesn't` vs `does not`); metaclass `__delitem__` refusal; `A[slice('a','b')]` slice-index error. All identical on base.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 772202, "input": 32700, "output": 6404, "reasoning": 8234, "cache.write": 0, "cache.read": 724864}]
    tool time: bash 4.5 min
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre4
         28s bash   cd /tmp/rprobes && cat > p6_builtin_class.py <<'PY' class E(Exception): pass class F(E): pass def drop(label,x
         17s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > p1_direct.py <<'PY' class A: pass class B(A): pass class Hol
          8s bash   cd /tmp/rprobes && cat > p7_exc_inst.py <<'PY' class E(Exception): pass class F(E): pass def show(label, f):  
          8s bash   cd /tmp/rprobes && cat > p9_sliceargs.py <<'PY' class A: pass def show(f):     try:         print(f())     exc
          8s bash   cd /tmp/rprobes && cat > p8_slice.py <<'PY' class A: pass def drop(k):     try:         del A[k]     except Ex
          6s bash   cd /tmp/rprobes && cat > p6_builtin_class.py <<'PY' class E(Exception): pass class F(E): pass def drop(label,x
          6s bash   cd /tmp/rprobes && cat > p1_direct.py <<'PY' class A: pass class B(A): pass class Holder: pass  def drop(x,k):

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T12:29:13Z
