# job job-rbpre395-10281537  started 2026-10-28T06:39:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"f3ef2a1b-762e-4b27-af85-ea414186a82f","session_id":"7931e812-54db-4ea9-87e4-e4817ed037a1"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"4e19d21b-38c3-4bc2-addc-9f948411ae99","session_id":"bd302e34-c2b5-4140-a4a6-586e1d59cc6a"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Re-applied pre395 on `job-rbpre395-10281537`, committed as `5f4eb0b`.

- Runtime: `ail_op_getitem`/`ail_op_getslice` now name the subscribed class; item assignment wording unchanged.
- Added `test_ail_pre395.py`; registered in `ail_check.MODULES` and `ci_shards.json` (38.8). Added DIFFERENCES row `C?-job-rbpre395-10281537-1`, DEVLOG entry, and refreshed `MANIFEST.json` (`--check` rc 0).
- Probes via `cmp.sh` (both builds): `p01_direct`, `p02_slices`, `p03_routes`, `p04_dunderpatch` all matched CPython stdout/exit.
- Tests (`-j 2`): pre395 17.9s, safetynet 132.8s, files 137.2s, corpus_findings3 246.9s — 4/4 passed, 0 failed.
- `tools/diff_ids.py` is absent from this tree, so it could not be run. One out-of-scope pre-existing difference remains: `A[slice('a','b')]` still reports the slice-index error on both builds.
[cost $0.0000, opencode tokens {"total": 1451057, "input": 50935, "output": 7115, "reasoning": 6255, "cache.write": 0, "cache.read": 1386752}]
    tool time: bash 7.0 min, edit 0.0 min, write 0.0 min
        382s bash   git add AIL_CURRENT/MANIFEST.json && python3 tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_a
         26s bash   for p in /tmp/probes/p0*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tail -80
          6s bash   python3 - <<'PY' p='/tmp/probes/p02_slices.py' s=open(p).read().replace("    show('strslice', A, slice('a', 'b
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre395-10281000 2>&1 | tail -5 && git log --oneline -3 FET
          0s bash   python3 tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>
          0s bash   python3 - <<'PY' from pathlib import Path p=Path('DEVLOG.md') s=p.read_text() entry='''## 2026-10-28 -- re-app
          0s bash   python3 tools/diff_ids.py; echo "diff_ids rc=$?"; python3 tools/update_manifest.py; echo "update rc=$?"; pytho
          0s bash   git add DEVLOG.md && git status --short && git diff --cached --stat && python3 tools/update_manifest.py --chec

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** Faithfully re-applies pre395: adds `ail__raise_class_not_subscriptable` and routes `AIL_T_CLASS` in `ail_op_getitem`/`ail_op_getslice` to it, so `A[0]` / `A[1:2]` say `type '<name>' is not subscriptable`, plus test/manifest/shard/DEVLOG/DIFFERENCES. Runtime and test hunks are byte-identical to `c9a1876..FETCH_HEAD` except the current tree's `ail__raise_item_tname` default, which the worker correctly kept (both sides' fixes).

**Probes** (cmp.sh both builds; base `/tmp/base` = f7e5753):
- `p01_direct` (int/neg/2**40/bool/None/float/str/empty/tuple keys, subclass, alias): HEAD matches CPython; base differs.
- `p02b_exc` (E/F exception subclasses, index+slice): HEAD matches; base differs.
- `p05_routes` (arg, list item, dict value, attribute, return, slices, assignment, deletion): matches except `del` wording, identical on base.
- `p07_attrclass`, `p09_uncaught`, `p14_indexkey`: match. `p11/p12/p17_long200` (127/128/200-char names): match.
- `p19_long_slice` (201-char class, index and slice): MISMATCH — defect.
- `p16_sliceargs`: `slice(None,None)`/step 0 fixed; `slice('a','b')` pre-existing on base.
- `p18_inst`: plain instance matches CPython; `E()[0]` pre-existing.
- `p03_unicode`, `p04_getitem`, `p10_builtinexc`: refused by name (acceptable).
- `p06_nofeature`: both builds match; `--debug-dir program.c` differs from base only by the new helper and the two `AIL_T_CLASS` cases (no unrelated codegen change).

**Claims:** verified — both builds, alias/subclass/arg/list/dict/attr/return, slices, assignment, `5f4eb0b`, tests 4 modules 270 s 0 failed, `update_manifest --check` rc 0, `diff_ids.py` absent. False — “plain instance `A()[0]` still prints `'instance'`”: HEAD and base both print `'A'`, matching CPython (`p18_inst`); only the exception instance `E()[0]` prints `'exception'`. Unverified — speed (not measured; cold branch), full suite (not run per scope).

**Pre-existing (identical on base):** `E()[0]` → `'exception'`; `del A[0]` → `doesn't support`; `A[slice('a','b')]` → slice-index error; `__class_getitem__`/builtin generic subscription/`int[0]` and non-ASCII identifiers refused/unsupported.

VERDICT: FIX
1. `ail__raise_class_not_subscriptable` does not apply CPython's `%.200s` cap to the class name, so a name over 200 chars appears in full. Probe `p19_long_slice.py` (class named 201 `M`s, then `C[0]` and `C[slice(1,2)]`, printing `len(str(e))`): expected `228` for both (200-char name), actual `229` for both on both builds; a 300-char name gives 328 vs 228. `ail__raise_item_tname` already caps at 200, so this helper should too. The same bug is present in the accepted pre395 source, i.e. it is inherited rather than introduced by conflict resolution.
[cost $0.0000, opencode tokens {"total": 1426441, "input": 69420, "output": 7635, "reasoning": 22794, "cache.write": 0, "cache.read": 1326592}]
    tool time: bash 7.4 min
        273s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; python3 ../tools/par_check.py -j 2 test_ail_pre395 test_
         32s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/p0*.py; do echo "===== $p"; bash ~/tools/cmp.s
         26s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/p01_direct.py /tmp/rprobes/p05_routes.py /tmp/
         23s bash   cat > /tmp/rprobes/p10_builtinexc.py <<'PY' def show(label, c):     try:         c[0]     except TypeError as 
         19s bash   python3 - <<'PY' for n in (200,201,210):     name='L'*n     open(f'/tmp/rprobes/p17_long{n}.py','w').write(f"c
         17s bash   cat > /tmp/rprobes/p02b_exc.py <<'PY' class E(Exception): pass class F(E): pass def main():     for label, c i
         12s bash   cd /home/runner/work/ail-ci/ail-ci; date; for p in /tmp/rprobes/p17_long201.py /tmp/rprobes/p17_long210.py; do
         12s bash   cat > /tmp/rprobes/p16_sliceargs.py <<'PY' class A: pass def main():     for label, s in (('str', slice('a', '

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect: `ail__raise_class_not_subscriptable` now caps the class name at 200 characters, matching `ail__raise_item_tname` and CPython (cruntime.py:14439).

- Probes (both builds via `cmp.sh`): `p19_len1/199/200/201/250/300` (index, slice, negative index) and `p19_routes` (201-char class via alias, list item, dict value, attribute, argument, return) all match CPython.
- Tests on final commit `a038735`: `test_ail_pre395`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 271 s, 0 failed.
- `tools/update_manifest.py --check` rc 0; `tools/diff_ids.py` is absent.
- DEVLOG entry added at top, including correction of the earlier plain-instance claim.
- Committed with explicit `git add`; not pushed.
[cost $0.0000, opencode tokens {"total": 429134, "input": 22143, "output": 3424, "reasoning": 2415, "cache.write": 0, "cache.read": 401152}]
    tool time: bash 10.2 min, edit 0.0 min
        275s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_ail_files test_ai
        273s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_ail_files test_ai
         46s bash   python3 - <<'PY' for n in (1,199,200,201,250,300):     name='M'*n     open('/tmp/probes/p19_len%d.py'%n,'w').w
          9s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p19_long.py <<'PY' def show(label, c, key):     try:         c[key] 
          7s bash   python3 - <<'PY' name='L'*201 open('/tmp/probes/p19_routes.py','w').write('''class %s:     def __add__(self, o
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo rc=$?
          0s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre395 test_ail_safetynet test_ail_files test_ai
          0s bash   python3 tools/update_manifest.py --check; echo rc=$?; python3 tools/diff_ids.py 2>&1 | tail -3; echo diff_ids_

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** Re-applies pre395 (new `ail__raise_class_not_subscriptable`, `AIL_T_CLASS` cases in `ail_op_getitem`/`ail_op_getslice`, test/shard/DIFFERENCES/DEVLOG), plus the review-0 fix that truncates the class name to 200 chars (`cruntime.py:14439`).

**Probes** (cmp.sh, both builds; base `/tmp/base`):
- `len199/200/201/300` (index+slice): HEAD matches CPython; 200 name kept, 201/300 truncated to 200 (228 chars). Verified the cap fix.
- `routes201` (201-char class via list item, dict value, attribute, argument, return, negative index, reverse slice): matches.
- `ascii_attr`, `dunder` (class with `__add__`): match.
- `inst`: `A()[0]` matches; `E()[0]` and `del A[0]` differ — identical on base (pre-existing).
- `unicode`: non-ASCII class refused by name (acceptable). `builtins`: builtin class values refused by name.
- `--debug-dir`: a no-subscript program's C is byte-identical to base; a program using ordinary subscripting gains only the new helper + two class cases (expected runtime-fragment delta, no semantic change).
- Tests on HEAD: `test_ail_pre395` 17.8s, `test_ail_safetynet` 131.8s, 0 failed. `update_manifest.py --check` rc 0; `tools/diff_ids.py` absent.

**Claims:** cap matching `ail__raise_item_tname`/CPython — verified. Routes through alias/list/dict/attr/arg/return — verified. Plain-instance correction — verified. Manifest/diff_ids claims — verified. "4 modules, 271s" — partially verified (2 of 4 run; files/corpus unverified).

**Pre-existing (same on base):** `E()[0]` → `'exception'`; `del A[0]` → `doesn't support`; `__class_getitem__` unsupported (both builds error, only wording changes); builtin/non-ASCII names refused.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, full suite, speed (error path only; no hot code).

**What the change really does vs report:** consistent; the cap is an extra beyond the accepted pre395 diff but is the review-0 defect fix and matches CPython.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1162350, "input": 34471, "output": 5267, "reasoning": 14772, "cache.write": 0, "cache.read": 1107840}]
    tool time: bash 3.6 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 780 python3 ../tools/par_check.py -j 2 test_ail_pre3
         29s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && python3 - <<'PY' for n in (199,200,201,300):     name='M'*n     op
         15s bash   cd /tmp/rprobes && cat > dunder.py <<'PY' class A:     def __init__(self, v): self.v = v     def __add__(self,
          9s bash   cd /tmp/rprobes && cat > builtins2.py <<'PY' def show(label, c, k):     try:         c[k]     except TypeError
          9s bash   cd /tmp/rprobes && cat > builtins.py <<'PY' def show(label, c, k):     try:         c[k]     except TypeError 
          7s bash   cd /tmp && rm -rf dbg_head dbg_base && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$( [ "$wt" 
          6s bash   cd /tmp/rprobes && python3 - <<'PY' n=201; name='L'*n open('routes201.py','w').write(f'''class {name}:     pas
          2s bash   cd /tmp && rm -rf dbg3_head dbg3_base && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do tag=$( [ "$wt

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T08:36:54Z
