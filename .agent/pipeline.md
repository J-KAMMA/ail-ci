# job job-pre411-10281301  started 2026-10-28T04:05:01Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"24b110ee-259f-4f2e-9433-0d5bc3053b4a","session_id":"013ecc14-dd83-4c7b-aba2-eb0616886a9d"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"0d8ecfe7-50fb-47c4-9e33-acfa34bc8db3","session_id":"77902e8d-b842-4a73-9dcd-067ac6304634"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `c66b323` on `job-pre411-10281301`.

Fixed the first remaining difference (r4): non-int `__index__` results on list/tuple/str subscripts now raise `TypeError: __index__ returned non-int (type ...)`. The same change fixes direct IntEnum/IntFlag keys with overridden `__index__` (r5) and one-level nested member results (r6) for indexing.

Probes (`cmp.sh`, both builds):
- `p_index_nonint.py`: 12 DIFF routes before, all match CPython after.
- `p_nested.py`: direct/arg/attr/item/str/member-chain now match; slice cases still DIFF.
- `p_slice.py`: still DIFF (separate slice-bound cause, unchanged).
- `p_pre411_testprog.py`: matches CPython.

Final-commit tests: `test_ail_pre411` (new, 2 tests), `test_ail_safetynet` (5), `test_ail_files` (18, 1 skipped), `test_ail_corpus_findings3` (2) — all OK. `update_manifest.py --check` passes. Full suite not run, per instructions.
[cost $0.0000, opencode tokens {"total": 3471113, "input": 207891, "output": 15388, "reasoning": 13658, "cache.write": 0, "cache.read": 3234176}]
    tool time: bash 14.4 min, write 0.0 min
        535s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && for m in test_ail_pre411 test_ail_safetynet test_ail_files t
        227s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && cd AIL_CURRENT && for m in t
         46s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_*.py; do echo "===== $p ====="; timeout 900 bash 
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_index_nonint.py /tmp/probes/p_nested.py /tmp/prob
         24s bash   cat > /tmp/probes/p_pre411_testprog.py <<'EOF' from enum import IntEnum, IntFlag   class BadStr:     def __ind
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/dunderrt.py 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pre411 (`c66b323`)

**What the change really does.** It adds two C helpers that detect an "IntEnum" by scanning the class base chain for the *name string* `_AilIntEnum`, and rewrites the general-path list/tuple/str instance-key subscript to use an IntEnum's `value` and to validate `__index__` results. Plus test/docs/manifest updates. This matches the report's description except that the "int-subclass fast path" is implemented as a class-name match — the source of the defect below.

**Claims checked**
- r4 non-int `__index__` → CPython TypeError on list/tuple/str: **verified** (p6/p8/p10, both builds).
- r5 direct IntEnum/IntFlag with overridden `__index__` uses the value: **verified** (p1/p6/p14).
- r6 nested member result: **verified** (p2/p6).
- Slice bounds still differ and are unchanged: **verified** (p12 identical on base/HEAD).
- `test_ail_pre411` + `test_ail_safetynet` on HEAD: **verified** (ok, 0 failed); `update_manifest.py --check` **verified** (exit 0).
- `test_ail_files` / `test_ail_corpus_findings3`: **not re-run** (reviewer rule).

**Probes (both builds unless noted)**
- p1, p6, p9, p10, p14, p15 (direct/arg/item/attr/dict/classattr/global/default, bounds, flags, composites, negatives): match CPython.
- p3: named refusal (`class … bases on int`) — acceptable.
- p5 (no feature): `--debug-dir` C differs only by the added helpers/branch; no lowering change.
- p2: matches except pre-existing wording (`not instance` vs `not Box`).
- p8: bytes/bytearray divergence — pre-existing (base same).
- p12: slice divergence — pre-existing (base same).
- p13/p17: **new regression** (below).

**Defect**
1. Name-based IntEnum detection hijacks any user class literally named `_AilIntEnum` (`AIL_CURRENT/python/pkg-v12/dunderrt.py:120`). This is legal in a program that does not import `enum`.
   - p13 `class _AilIntEnum: def __init__(self): self.value = 2` / `xs[_AilIntEnum()]`:
     expected `TypeError: list indices must be integers or slices, not _AilIntEnum` (CPython; base also raises), actual HEAD `plain 30`.
   - p17 `class _AilIntEnum: ... value=2` and `class X: __index__ -> _AilIntEnum()` / `xs[X()]`:
     expected `TypeError: __index__ returned non-int (type _AilIntEnum)`, actual HEAD `ret-spoof 30`.
   - p11 (`_AilIntEnum` with `__index__` but no int `value`): expected `30`, actual `TypeError … not instance`.
   Fix by identifying the real prelude class (flag/identity) or refusing a user redefinition of `_AilIntEnum`, not by matching the name string.

**Pre-existing (identical on base, not blocking)**
- p2/p13: `not instance` instead of the class name for an instance key with no `__index__`.
- p8: bytes/bytearray ignore `__index__` (and non-int results).
- p12: slice bounds ignore `__index__` entirely (r5/r12).
- p4: IntEnum member `.value` is mutable.
- Minor: `enumlib.py` docstring still says "a member is not usable as a list index", now stale.

**Unverified**
- `test_ail_files`, `test_ail_corpus_findings3` not re-run.
- Speed not measured (`perf_event_open` denied); the change only adds work inside the instance-key branch, so int-key indexing is unchanged.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2062676, "input": 37071, "output": 10971, "reasoning": 34986, "cache.write": 0, "cache.read": 1979648}]
    tool time: bash 7.4 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre4
         50s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p1_intenum_routes.py /tmp/rprobes/p2_chain_routes.
         42s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p2_chain_routes.py /tmp/rprobes/p4_mutate_value.py
         34s bash   cd /tmp/rprobes && cat > p8_more.py <<'PY' from enum import IntEnum  class Z(IntEnum):     ONE = 1     def __i
         32s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== HEAD ==="; timeout 500 bash ~/tools/cmp.sh /tmp/rprobes/p6_edg
         21s bash   cd /tmp/rprobes && cat > p12_slice.py <<'PY' from enum import IntEnum  class Z(IntEnum):     ONE = 1     def _
         21s bash   cd /tmp/rprobes && cat > p9_bounds.py <<'PY' from enum import IntEnum  class N(IntEnum):     FAR = -50  class 
         16s bash   cd /tmp/rprobes && cat > p14_flag_returns.py <<'PY' from enum import IntFlag, IntEnum  class F(IntFlag):     O

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `75043ee`.

**Defect fix:** a user class named `_AilIntEnum` is now refused by name at compile time in `ail_syntax.py`, before the enum prelude is inserted. The runtime name match can therefore only see the real prelude class.

**Probes (both builds, `cmp.sh`):**
- `p_reserved_direct.py` (p13), `p_reserved_index.py` (p11), `p_reserved_chain.py` (p17), `p_reserved_routes.py` (argument/list item/attribute/dict value), `p_reserved_nested.py`: **refused by name on both builds**.
- `p1`, `p6`, `p10`, `p14`, `p15`, `p_index_nonint`, `p_pre411_testprog`: **match CPython on both builds**.
- `p2`: still differs only by the pre-existing `not instance` wording.
- `p_nested` / `p_slice_bounds`: still differ only on the pre-existing slice-bound behavior.

**Tests on final commit:** `test_ail_pre411`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4 modules, 0 failed**. `update_manifest.py --check` passes. Full suite not run.
[cost $0.0000, opencode tokens {"total": 4242728, "input": 216579, "output": 9118, "reasoning": 20615, "cache.write": 0, "cache.read": 3996416}]
    tool time: bash 9.0 min
        385s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 3000 python3 tools/par_check.py -j 2 --timeout 1800 test_ail_pre
         83s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_reserved_direct.py /tmp/probes/p_reserved_index.p
         66s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_index_nonint.py /tmp/probes/p_nested.py /tmp/prob
          5s bash   mkdir -p /tmp/inspect && cd /tmp/inspect && cat > p.py <<'PY' from enum import IntEnum class E(IntEnum):     A
          0s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_reserved_direct.py <<'PY' class _AilIntEnum:     def __init_
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/ail_syntax.py AIL_CURRENT/
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/python/p

## review 1
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (two commits: `c66b323` primary `__index__`/IntEnum fix, `75043ee` reserved-name refusal).

**What the diff really does:** On list/tuple/str subscripts it validates `__index__` results (CPython's `__index__ returned non-int (type X)`), uses an IntEnum/IntFlag member's stored `value` directly (ignoring an overridden `__index__`, unwrapping one member result), and reserves the internal class name `_AilIntEnum` by refusing a user `class _AilIntEnum`.

**Probes (`cmp.sh`, HEAD, both builds):**
- Match CPython: `r1_over`, `r2_bad`, `r3_routes`, `r9_enum_smoke`, `r11_combo`, `p1_intenum_routes`, `p6_edges`, `p10_routes_bad`, `p14_flag_returns`, `p15_other_routes`, `p_index_nonint`, `p_pre411_testprog`.
- Refused by name on both builds (acceptable): `r5`–`r8`, `p16`, `p17`, `p_reserved_direct/index/chain/routes/nested`.
- `p5_nofeature`, `r4_plain`: same stdout/exit as CPython.

**Pre-existing (identical on `/tmp/base`, not blocking):**
- `p2`: `Box(Bad())` list/tuple error says `not instance` vs CPython `not Box`.
- `p4`: `z.value = 2` succeeds vs CPython `AttributeError` on the enum member.
- `p12_slice` / `p_nested`: slice bounds never call `__index__`.
- `r10`: bytes/bytearray indexing never calls `__index__`/uses an IntEnum value.

**C check:** a no-class program's `--debug-dir` C is byte-identical to base. A class-bearing program not using the feature differs only by the two new `static inline` helpers and the getitem prelude text; stdout/exit are identical.

**Claim check:**
- Reserved-name refusal before prelude inserted: verified (r5–r8, p16, p17; code sits before the stdlib5 prelude insertion).
- Listed probes refused / matching: verified on HEAD both builds.
- p2 wording and slice divergence pre-existing: verified.
- `update_manifest.py --check`: verified (rc 0).
- Tests: `test_ail_pre411` and `test_ail_safetynet` re-run on HEAD, both ok; `test_ail_files` and `test_ail_corpus_findings3` not re-run (per instruction) — unverified.
- “Fixed and committed as 75043ee”: incomplete; the primary `__index__`/IntEnum fix is `c66b323`, both are in the change.

**Unverified:** `test_ail_files` / `test_ail_corpus_findings3`; instruction-count speed (perf_event_open denied; hot path unchanged for non-instance keys, so no measurable impact expected).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3441487, "input": 93585, "output": 8786, "reasoning": 32620, "cache.write": 0, "cache.read": 3306496}]
    tool time: bash 8.9 min
        136s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
        109s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in p1_intenum_routes p2_chain_routes p4_mutate_value p5_nofeat
         73s bash   date; cd /tmp/base; for p in p1_intenum_routes p2_chain_routes p4_mutate_value p5_nofeature p6_edges p12_slice
         49s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r1_over.py /tmp/rprobes/r2_bad.py /tmp/rprobes
         43s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in p_index_nonint p_pre411_testprog p_reserved_routes p_nested
         35s bash   cd /tmp/rprobes && cat > r11_combo.py <<'PY' import re from enum import IntEnum from dataclasses import datacl
         34s bash   cd /tmp/rprobes && cat > r10_bytes.py <<'PY' from enum import IntEnum class E(IntEnum):     ONE = 1     def __
         17s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in r5_reserved_direct r6_reserved_index r7_reserved_return r8_

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T06:32:02Z
