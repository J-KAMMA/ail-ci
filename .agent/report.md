# job job-pre397-10281018  started 2026-10-28T01:24:13Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"0732d0eb-4c7c-43e2-aecc-cdf94d5decfb","session_id":"f23aa664-a03c-48b7-982f-5315f16a4a41"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"53cc8179-f8b9-4c6c-9b36-0e494bc61b1c","session_id":"4f825a6c-9821-4dd0-9b97-b9e8c69f0808"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing pre397 case, `p6_enumret`: an `__index__` result that is an IntEnum/IntFlag member is now unwrapped through its own `__index__` instead of being rejected as an instance.

**Changes**
- `dunderrt.py`: new `ail__intenum_index` helper; applied to list/tuple/str subscription and `round()` ndigits.
- `pyboxed2.py`: applied to `range()` arguments and sequence index bounds.
- `safetyrt.py`: applied to str/bytes search bounds.
- Added `AIL_CURRENT/test_ail_pre397.py`, registered it, added DIFFERENCES/DEVLOG records, updated manifest and CI shard weight.

**Probes (both builds, all matched CPython)**
- `/tmp/probes/p6_enumret.py` — original p6 case.
- `/tmp/probes/p6_boundaries.py` — direct/returned IntEnum and IntFlag, empty, negative, out-of-range, argument/list-item/attribute/dict-value routes, non-int returns.
- `/tmp/probes/p6_other_contexts.py` — range, round, str/bytes find, list.index.
- Exploratory `p6_enum_contexts.py` still shows pre-existing differences in contexts not changed here: slicing, bytes subscript, `int()`, `hex()/oct()/bin()`, `format()` and `%d`. The other pre379 items (`E.A *= [1,2]`, list/deque `*= IntEnum`, `d.keys() * 2` / genexpr `* 2`) are unchanged.

**Tests on final code**
8 modules, 48 tests, 0 failed (1 skipped): `test_ail_pre397`, `test_ail_safetynet`, `test_ail_pre160`, `test_ail_pre173`, `test_ail_pre258`, `test_ail_c169`, `test_ail_files`, `test_ail_corpus_findings3`.

`update_manifest.py --check` passes. Committed as `9da5ba8`; not pushed.
[cost $0.0000, opencode tokens {"total": 7009913, "input": 155932, "output": 16681, "reasoning": 23092, "cache.write": 0, "cache.read": 6814208}]
    tool time: bash 9.1 min
        246s bash   printf '%s\n' test_ail_files test_ail_corpus_findings3 | xargs -P2 -I{} sh -c 'cd AIL_CURRENT && python3 -B -m
        135s bash   printf '%s\n' test_ail_safetynet test_ail_pre173 test_ail_pre160 test_ail_pre258 test_ail_c169 | xargs -P2 -I{
         38s bash   python3 -B AIL_CURRENT/test_ail_pre397.py 2>&1 | tail -40
         37s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p6_enumret.py <<'EOF' import enum  class E(enum.IntEnum):     A = 3 
         29s bash   cp /tmp/probes/cpython_enum_contexts.py /tmp/probes/p6_enum_contexts.py bash ~/tools/cmp.sh /tmp/probes/p6_enu
         21s bash   python3 -B -m unittest -q test_ail_pre160 2>&1 | tail -20
         19s bash   cat > /tmp/probes/p6_other_contexts.py <<'EOF' import enum  class E(enum.IntEnum):     ZERO = 0     ONE = 1   
         19s bash   cat > /tmp/probes/p6_boundaries.py <<'EOF' import enum  class E(enum.IntEnum):     ZERO = 0     A = 3     NEG 

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — job pre397 (commit `9da5ba8`)

**What the change really does:** adds a runtime helper `ail__intenum_index` (dunderrt.py:104) that detects an `_AilIntEnum` descendant instance and "unwraps" it by calling **the member's own `__index__`**, then applies it at five `__index__`-result sites (list/tuple/str getitem, `range`, seq index bounds, `round` ndigits, str/bytes bounds). That matches the report except the report never says the unwrap calls the member's `__index__` rather than reading its int value.

**Probes (HEAD, both builds; base compared):**
- `r1_orig`, `r2_routes`, `r3_intflag`, `r5b_contexts`, `r7_outofrange`, `r8_unrelated` — match CPython. Original p6 case is fixed; IntFlag (inherits `_AilIntEnum`) works; arg/list-item/attr/dict routes work.
- `r9_override_diff`, `r10_override_raise` — **new divergence** (see defect).
- `r11/r12` direct override, `r4_nonint` messages, `r5` slicing, `r6` chained enum return — identical on base, listed as pre-existing.

**Pre-existing (base identical, not blocking):**
- `__index__` returning a non-int raises the wrong TypeError text (`list indices...` vs `__index__ returned non-int`) — r4.
- Slice bounds and direct IntEnum with an overridden `__index__` still diverge — r5, r12.
- Nested chain: member's `__index__` returning another IntEnum member still raises `TypeError` — r6 (one-level unwrap only).

**Tests:** `test_ail_pre397` (ok) and `test_ail_safetynet` (ok) on HEAD; `update_manifest.py --check` passes. Report's "8 modules" claim not re-run (only required modules per instructions).

**Claim check:** "All probes matched CPython" is **false** at the overridden-`__index__` boundary; this boundary is not mentioned in the report or test module. Registered/manifest/commit claims verified.

VERDICT: FIX

1. `ail__intenum_index` (dunderrt.py:104-111) calls the returned member's `__index__` instead of using the member's integer value. CPython accepts an IntEnum/IntFlag member returned from `__index__` as a plain int subclass and never calls its overridden `__index__`. This yields silently wrong results (and a spurious exception) that did not occur on base.
   Probe `/tmp/rprobes/r9_override_diff.py`:
   ```
   import enum
   class E(enum.IntEnum):
       A = 5
       def __index__(self):
           return 999
   class C:
       def __index__(self):
           return E.A
   data = list(range(2000))
   print(data[C()])
   ```
   Expected `5`; HEAD prints `999` (base raised `TypeError`, so this is change-caused).
   Probe `/tmp/rprobes/r10_override_raise.py` (same `E` but `__index__` raises `ValueError("boom")`, list of 7):
   Expected `60`; HEAD prints `ValueError boom` on both builds.
[cost $0.0000, opencode tokens {"total": 613504, "input": 44923, "output": 4223, "reasoning": 14726, "cache.write": 0, "cache.read": 549632}]
    tool time: bash 5.9 min
        131s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/par_check.py -j 2 test_ail_pre397 test_ail_safetynet 2
         90s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$
         37s bash   cd /tmp/base; for p in /tmp/rprobes/r4_nonint.py /tmp/rprobes/r5_contexts.py /tmp/rprobes/r6_chain.py; do echo
         29s bash   cd /tmp/base; for p in /tmp/rprobes/r9_override_diff.py /tmp/rprobes/r10_override_raise.py /tmp/rprobes/r11_ov
         29s bash   cat > /tmp/rprobes/r9_override_diff.py <<'EOF' import enum class E(enum.IntEnum):     A = 5     def __index__(
         20s bash   cat > /tmp/rprobes/r12_direct_override.py <<'EOF' import enum class E(enum.IntEnum):     A = 2     def __index
         17s bash   cat > /tmp/rprobes/r5b_contexts.py <<'EOF' import enum class E(enum.IntEnum):     A = 2     NEG = -1 class C: 
          0s bash   mkdir -p /tmp/rprobes; rm -rf /tmp/base; git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base >/dev/nu

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed `ail__intenum_index` in `AIL_CURRENT/python/pkg-v12/dunderrt.py`: it now reads the returned member's integer `value` instead of dispatching its overridden `__index__`.

Commit `2aa5492`.

Verification on final commit:
- Probes, both builds vs CPython: `r9_override_diff`, `r10_override_raise`, `v1_getitem_override`, `v2_contexts_override`, `v3_raise_override`, `v4_intflag_override`, `v5_big_override`, `v6_nested_override` — all identical.
- Tests: `test_ail_pre397`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 1418552, "input": 59383, "output": 7794, "reasoning": 7631, "cache.write": 0, "cache.read": 1343744}]
    tool time: bash 9.7 min
        378s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre397 test_ail_safetynet test_
         84s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && for p in r9_override_diff r1
         82s bash   cd /tmp/probes && cat > v1_getitem_override.py <<'EOF' import enum class E(enum.IntEnum):     ZERO = 0     A =
         29s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > r9_override_diff.py <<'EOF' import enum class E(enum.IntEnum):
         10s bash   cd /tmp/probes && cat > v6_nested_override.py <<'EOF' import enum class F(enum.IntEnum):     B = 2 class E(enu
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git status && git log --oneline -5 && ls
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -n "ail__intenum_index" -r . --include=*.py | head -50

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed both commits (`9da5ba8`, `2aa5492`). The change adds `ail__intenum_index` (dunderrt) and calls it at `__index__` result sites: list/tuple/str subscription, `range()` args, sequence-index bounds, `round()` ndigits, bytes/str search bounds; the second commit makes it read the member's `value` attribute instead of calling its `__index__`.

**Verified**
- `p6_enumret`, `r9_override_diff`, `r10_override_raise`, `v1`–`v6`: identical stdout on both builds vs CPython (re-ran).
- `test_ail_pre397`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass on HEAD (0 failed); `update_manifest.py --check` passes.
- No-feature program (`z_plain.py`) generates byte-identical C on HEAD vs `/tmp/base` (only `native_report.json` temp paths differ).
- IntFlag composites, zero/negative/bool values through getitem, find, list.index, round, range match CPython.

**Defect (caused by the change)**
1. The helper identifies an IntEnum member by the private class name `_AilIntEnum` anywhere in the chain, without requiring it to be a *base* or checking the member shape. A user class with that (internal) name is therefore silently accepted as an IntEnum when returned from `__index__`, where CPython raises `TypeError`:
```python
class _AilIntEnum:
    def __init__(self, v): self.value = v
    def __index__(self): return 5
class C:
    def __init__(self, v): self.v = v
    def __index__(self): return self.v
try:
    print([10,20,30,40][C(_AilIntEnum(2))])
except Exception as e:
    print(type(e).__name__, str(e))
```
Expected (CPython): `TypeError __index__ returned non-int (type _AilIntEnum)`; HEAD: `30`. Base also raises `TypeError` (different message). Fix: require `_AilIntEnum` only as a base of the member's own class, or check the `cname`/`name`/`value`/`_idx` member shape.

**Pre-existing (same on base, not blocking)**
- IntEnum members whose declared value is a float/str/nested member (`A=1.5`, `A="5"`, `A=F.B`) still give `TypeError` where CPython indexes by the normalized int; `E.A.value` itself already differs on base.
- Direct IntEnum/IntFlag subscription with an overridden `__index__` uses the override (CPython uses the int value); `r6_chain_value` fails at class creation with `AttributeError: type object 'F' has no attribute 'B'`.
- Slice bounds (`[0,1,2,3][C(E.ONE):]`), bytes/bytearray/deque indexing, sequence repeat and `pop(i)` still do not normalize a returned member.
- `list(range(2**62))` aborts with `AIL internal error: out of memory` on base and HEAD for plain ints; the change merely lets an IntEnum value reach that pre-existing path.

Unverified: instruction-count/speed check (the added code runs only on the instance-key `__index__` path; C for non-feature programs is unchanged).

VERDICT: FIX
1. Name-based IntEnum detection accepts a user class named `_AilIntEnum` returned from `__index__`; expected `TypeError`, actual `30`.
[cost $0.0000, opencode tokens {"total": 2993719, "input": 88055, "output": 8606, "reasoning": 31778, "cache.write": 0, "cache.read": 2865280}]
    tool time: bash 14.6 min
        263s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1200 python3 tools/par_check.py -j 2 test_ail_files test
        139s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre397 tes
        121s bash   cd /tmp/rprobes && cat > x_rangehuge.py <<'EOF' def show(t,f):     try: print(t,repr(f()))     except Exceptio
         84s bash   cd /tmp/rprobes && python3 - <<'EOF' s=open('x_contexts.py').read() s=s.replace('class G(enum.IntEnum):\n    V
         67s bash   cd /tmp/probes && for p in v1_getitem_override v2_contexts_override v3_raise_override v4_intflag_override v5_b
         47s bash   cd /tmp/rprobes && cat > x_contexts.py <<'EOF' import enum class E(enum.IntEnum):     ZERO=0     ONE=1     TWO
         41s bash   cd /tmp/probes && for p in p6_enumret r9_override_diff r10_override_raise v6_nested_override; do echo "=== $p 
         32s bash   cd /tmp/rprobes && for p in x_floatval x_strval y_override; do echo "=== $p BASE ==="; bash ~/tools/cmp.sh /tm

FINAL VERDICT: FIX  2026-10-28T02:21:13Z
