# job job-pre309-10271313  started 2026-10-27T04:14:45Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"2eb06849-0ab2-4ece-8106-0aa9981e0da3","session_id":"f29d3596-15c8-4690-bd9e-f9ab859c6d7b"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"e42d89ba-0eb5-494c-93da-4f337d3767b2","session_id":"b5482f7a-9f0a-4f6e-a1de-a35fae123c91"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the only pre-existing difference from the rbrbpre245 review: `hash(frozenset([1, 2]))` now matches CPython (`-1826646154956904602`) on both builds. `ail_pyhash` now uses CPython's frozenset mix over the elements' Python hashes; frozensets of tuples stay on the general path so they are not identity-hashed through a tuple table.

Commit: `d7ee69b` (no push). Added `AIL_CURRENT/test_ail_pre309.py`, DIFFERENCES row, DEVLOG entry, and registered the module.

Probes (15/15 match CPython on both builds): `pre309_hash_frozenset`, `pre309_hash_int`, `pre309_fs_basic`, `pre309_fs_types`, `pre309_fs_routes`, `pre309_fs_semantics`, `pre309_fs_strings`, `pre309_fs_setdiff`, `pre309_fs_tuple`, `pre309_fs_repr`, `pre309_fs_diag1/2/3`, `pre309_fs_seq1/2`.

Tests: `test_ail_pre309` 24 s; `test_ail_safetynet` 124 s, `test_ail_files` 131 s, `test_ail_corpus_findings3` 208 s — 4 modules, 356 s, 0 failed. `tools/update_manifest.py --check` passes. `.agent/pipeline.md` left untouched.
[cost $0.0000, opencode tokens {"total": 7608212, "input": 143430, "output": 13349, "reasoning": 21545, "cache.write": 0, "cache.read": 7429888}]
    tool time: bash 9.5 min, edit 0.0 min
        334s bash   cd AIL_CURRENT && date && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files te
         67s bash   for p in /tmp/probes/pre309_*.py; do out=$(bash ~/tools/cmp.sh "$p" $PWD 2>&1); if echo "$out" | grep -q "same
         32s bash   for p in /tmp/probes/pre309_fs_diag2.py /tmp/probes/pre309_fs_types.py /tmp/probes/pre309_fs_basic.py /tmp/pro
         27s bash   cat > /tmp/probes/pre309_fs_basic.py <<'PY' print(hash(frozenset())) print(hash(frozenset([1]))) print(hash(fr
         27s bash   git add AIL_CURRENT/test_ail_pre309.py AIL_CURRENT/ail_check.py AIL_CURRENT/python/pkg-v12/cruntime.py AIL_CUR
         21s bash   cat > /tmp/probes/pre309_fs_diag1.py <<'PY' fs = frozenset([(1, 2)]) for x in fs:     print(hash(x)) print(has
         17s bash   for i in 1 2 3; do :; done cat > /tmp/probes/pre309_fs_seq1.py <<'PY' print(hash(frozenset([None]))) print(has
          8s bash   bash ~/tools/cmp.sh /tmp/probes/pre309_hash_frozenset.py $PWD; bash ~/tools/cmp.sh /tmp/probes/pre309_hash_int

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds an `AIL_T_FROZENSET` case to `ail_pyhash` that recomputes CPython's frozenset mix from each element's live Python hash, and makes the tuple-table typed path leave `hash()` of a set/frozenset of tuples to the general path.

**Probes (HEAD, then base where relevant)**
- MATCH on HEAD: `r1_basic` (empty/order/int bounds), `r3_tuple`, `r4_routes`, `r6_mixed`, `r7_mixed2`, `r8_tset`, `r10_sem`, `r11_numeric` (int/float aliases), `r12_nested` (500 elems, nested fs), `r13_routes2` (arg/list/attr/dict), `r14_custom` (constant `__hash__`), `r15_ctors` (tuple/set ctor, set ops), `r16_keys`.
- BASE confirms `r1_basic` was broken and is fixed (2,8c2,8).
- Non-feature program: `--debug-dir` C differs from base only by the added runtime branch; program-specific C identical.

**Report claims**
- `hash(frozenset([1,2]))` fixed on both builds: verified.
- 15/15 probes match: verified for the listed types; the broad claim that tuple frozensets always leave the identity table is false for a mixed list/loop route (`r5_set`), but that is pre-existing.
- tests `test_ail_pre309` 24s + `test_ail_safetynet` 122s pass: verified. `update_manifest.py --check` rc=0: verified. `.agent/pipeline.md` untouched (still untracked): verified.
- "Speed not checked" acceptable for this cold branch.

**Pre-existing (wrong identically in kind on base, not blocking)**
- `hash(set([(1,2)]))` returns an int instead of `TypeError` (`r9_sethash`); base also does not raise.
- `frozenset([(1,2)])` reached through a mixed set/frozenset loop still hashes by identity (`r5_set` line 4); base same.
- `hash(frozenset([b'ab', b'cd']))` differs from CPython's randomized bytes hash (`r2_types` line 8); base same.

**Defect**
1. New regression: `ail_pyhash` recomputes the frozenset hash from each element on every call and re-invokes `__hash__`, instead of using the hashes stored at construction. This adds observable `__hash__` side effects and breaks the guarantee that `hash(fs)` is stable for one immutable frozenset. Probe `/tmp/rprobes/r17_sideeffect.py`:
```python
class K:
    def __init__(self):
        self.n = 0
    def __hash__(self):
        self.n += 1
        return self.n

k = K()
fs = frozenset([k])
print(k.n)
h1 = hash(fs)
print(k.n)
h2 = hash(fs)
print(k.n, h1 == h2)
```
Expected (CPython and base): `1`, `1`, `1 True`
Actual (HEAD, both builds): `1`, `2`, `3 False`
(`r19_sideeffect3` shows the same extra calls with a constant `__hash__`: 2 and 3 calls vs 1.)

VERDICT: FIX
1. `hash(frozenset)` re-calls element `__hash__` and is not stable/cached; see probe above, expected `1 / 1 / 1 True`, actual `1 / 2 / 3 False`.
[cost $0.0000, opencode tokens {"total": 727585, "input": 45527, "output": 5837, "reasoning": 19453, "cache.write": 0, "cache.read": 656768}]
    tool time: bash 5.3 min
        124s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         34s bash   cd /tmp/rprobes && for p in r1_basic r2_types r3_tuple r4_routes r5_set; do echo "===== $p"; bash ~/tools/cmp.
         33s bash   cd /tmp/rprobes && for p in r1_basic r2_types r5_set r9_sethash; do echo "===== $p BASE"; bash ~/tools/cmp.sh 
         26s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         21s bash   cd /tmp/rprobes && cat > r6_mixed.py <<'PY' vals = [frozenset([1]), frozenset([(1, 2)])] for v in vals:     pr
         18s bash   cd /tmp/rprobes && cat > r17_sideeffect.py <<'PY' class K:     def __init__(self):         self.n = 0     def 
         14s bash   cd /tmp/rprobes && cat > r14_custom.py <<'PY' class K:     def __hash__(self):         return 42     def __eq_
         14s bash   cd /tmp/rprobes && cat > r11_numeric.py <<'PY' print(hash(frozenset([1, 1.0]))) print(hash(frozenset([1.0]))) 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `adee317` (no push).

- Defect: `hash(frozenset)` re-ran element `__hash__`; now set entries store the element's Python hash at insertion and `ail_frozenset_hash` mixes those stored hashes. `hash(fs)` is stable and calls no `__hash__`.
- Added direct, constant-`__hash__`, tuple-wrapped and nested side-effect cases to `test_ail_pre309.py`.
- Probes (both builds): 8/8 new `/tmp/probes/pre309_fix_*` match CPython; prior `r17_sideeffect`, `r19_sideeffect3` now match; 13 other prior probes still match. Known pre-existing `r2_types`, `r5_set`, `r9_sethash` diffs unchanged; `r18_sideeffect2` still refused by name.
- Final-commit tests: `test_ail_pre309`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 241 s, 0 failed. Also `test_ail_sets_general`, `test_ail_int_dict_set`, `test_ail_tuples` — 3 modules, 162 s, 0 failed.
- `update_manifest.py --check` rc=0; `.agent/pipeline.md` untouched.
[cost $0.0000, opencode tokens {"total": 2151567, "input": 81586, "output": 8610, "reasoning": 18235, "cache.write": 0, "cache.read": 2043136}]
    tool time: bash 14.0 min
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        243s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
        164s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_
         95s bash   cd /tmp/rprobes && for p in r1_basic r2_types r3_tuple r4_routes r5_set r6_mixed r7_mixed2 r8_tset r9_sethash 
         50s bash   cd /tmp/probes && for p in pre309_fix_basic pre309_fix_routes pre309_fix_semantics pre309_fix_ops pre309_fix_m
         40s bash   cd /tmp/probes && for p in pre309_fix_basic pre309_fix_routes pre309_fix_semantics pre309_fix_ops pre309_fix_m
          4s bash   cat /tmp/rprobes/r18_sideeffect2.py; echo ====; cd /tmp/rprobes && timeout 300 bash ~/tools/cmp.sh /tmp/rprobe
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_

## review 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** a set entry now stores the element's CPython `hash()` value (instead of the private table hash), `ail_frozenset_hash` mixes those stored values, and `ail_pyhash` of a frozenset reads them; `hash()` of a tuple-table set/frozenset is sent to the general path. (Two commits: `d7ee69b` + follow-up `adee317`.)

**Probes (`/tmp/rprobes`, HEAD then base)**
- Match on HEAD, differ on base (fix verified): `rv_hash_types`, `rv_sideeffect`, `rv_alias_routes`, `rv_tuple_routes`, `rv_tuple_routes2`, `rv_collide`, `rv_float`, `rv_hash_set`, `rv_nested_tuple`.
- Match on both: `rv_sets`, `rv_dict`, `rv_nan`, `rv_nofeat` (no frozenset/hash feature; behavior and `program.c` unchanged apart from the intended runtime lines).
- `rv_order`: set-repr order differs on both base and HEAD → pre-existing.
- Worker's `/tmp/probes/pre309_fix_*`: 8/8 match. Prior r-probes: all match except `r2_types`/`r5_set`/`r9_sethash` (pre-existing) and `r18_sideeffect2` (refused by name, same on base).
- Tests on final commit: `test_ail_pre309` 28.7 s, `test_ail_safetynet` 118.4 s, 0 failed. `update_manifest.py --check` rc=0.
- Speed: `perf_event_open` is denied here, so no instruction counts. Synthetic 120 M-iteration int set add/discard: HEAD 0.59 s vs base 0.59–0.62 s — no measurable slowdown. The report's parenthetical "no hot path" is inaccurate (all set add/lookup hashing changed), but no regression observed.

**Claims**
- hash(frozenset) fixed and stable without re-calling `__hash__`: verified.
- Side-effect cases added to `test_ail_pre309`: verified.
- Prior probe/test/manifest/pipeline claims: verified, except `test_ail_files`/`test_ail_corpus_findings3` (not re-run, per reviewer rule).
- `DIFFERENCES` row overstates: frozenset-of-tuples reached through a mixed-loop variable still hashes by identity (`r5_set` line 4, expected `3819360209092968377`, got `4353709593231670116` on `g`); base is also wrong, so this is pre-existing, not a new defect.

**Pre-existing:** `hash(set([(1,2)]))` returns an int instead of TypeError; mixed-loop frozenset-of-tuples identity hash; randomized bytes/str hash differences; set-repr ordering; `r18` class-attribute store refusal.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_sets_general`, `test_ail_int_dict_set`, `test_ail_tuples`; hardware instruction counts (perf blocked).

VERDICT: ACCEPT
[cost $0.0743, opencode tokens {"total": 6187082, "input": 120001, "output": 14660, "reasoning": 49093, "cache.write": 0, "cache.read": 6003328}]
    tool time: bash 8.9 min, write 0.0 min
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
        102s bash   date; cd /tmp/rprobes && for p in r1_basic r2_types r3_tuple r4_routes r5_set r6_mixed r7_mixed2 r8_tset r9_se
         57s bash   date; cd /tmp/rprobes && for p in r2_types r5_set r9_sethash; do for wt in /home/runner/work/ail-ci/ail-ci /tm
         43s bash   date; cd /tmp/probes && for p in pre309_fix_basic pre309_fix_routes pre309_fix_semantics pre309_fix_ops pre309
         26s bash   date; cd /tmp/rprobes && for p in rv_hash_types rv_sets rv_sideeffect rv_alias_routes rv_nofeat; do echo "====
         26s bash   date; cd /tmp/rprobes && for p in rv_hash_types rv_sets rv_sideeffect rv_alias_routes rv_nofeat; do echo "====
         17s bash   date; mkdir -p /tmp/speed && cd /tmp/speed && for wt in head base; do case $wt in head) root=/home/runner/work
         14s bash   date; cd /tmp/rprobes && for p in r17_sideeffect r18_sideeffect2 r19_sideeffect3; do echo "===== $p HEAD"; tim

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-27T06:36:38Z
