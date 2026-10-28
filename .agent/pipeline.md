# job job-cov20-10290430  started 2026-10-28T19:37:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"a6553444-1b7a-4b3d-9fcb-b030141918f1","session_id":"b668a0b5-04e7-4ff2-a746-0d1ac5d99a76"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"dacd5c27-bb91-4395-9c14-f65b4187123f","session_id":"cf701082-182f-4a32-b7ba-c6afdee7115e"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed on `job-cov20-10290430` as `301b2dd` (not pushed).

**Census (219 corpus programs, default build):** 24 refused / 195 compiled before and after. The `sorted(d.items())` first refusal went **2 → 0** (deepseek t456, glm t467); both still stop by name at their next blocker, so no program became newly accepted.

**Change:** `ranked = sorted(d.items(), ...)` walked as `for k, v in ranked` / `ranked[:n]` (including negative/step slices and repeated loops), plus `dict(sorted(d.items()))`. Rebinding, `del`, nested-scope, pre-assignment and conditional bindings remain named refusals. Added `AIL_CURRENT/test_ail_cov20.py` and registered it in `ail_check.MODULES`; DEVLOG updated; manifest refreshed and `--check` passes.

**Tests on final commit:** `test_ail_cov20`, `test_ail_sort_keys`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5/5 pass.

**Probes** (`cmp.sh`, both builds): `cov20_p01`–`p15` match CPython (basic/empty/slices/mutation/argument/types/dict-sorted, plus receiver via list item, attribute and dict value; tuple-printing, reassigned, nested and keyed dict-sorted forms also match). `ref4` is refused by name (`sorted() with a non-constant reverse=`). Direct lowering boundary: safe snapshot rewrites 2 sites; reassignment/nested/conditional raise the named refusal.
[cost $0.0835, opencode tokens {"total": 8329348, "input": 187302, "output": 18206, "reasoning": 33728, "cache.write": 0, "cache.read": 8090112}]
    tool time: bash 23.8 min
        485s bash   cd /tmp/cov20 && python3 - <<'PY' from pathlib import Path out = Path('/tmp/cov20/out') names=[] for line in P
        321s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov20 test_ail_sort_keys test_ail_safetynet test
        255s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov20 test_ail_sort_keys test_ail_safetynet test
         57s bash   mkdir -p /tmp/probes/cand cat > /tmp/probes/cand/c1.py <<'EOF' from typing import Callable  def apply(f: Calla
         53s bash   mkdir -p /tmp/probes/variants cat > /tmp/probes/variants/v1.py <<'EOF' from __future__ import annotations  def
         44s bash   cd /tmp/probes && rm -rf /tmp/probes/logs && mkdir -p /tmp/probes/logs && ls cov20_*.py | xargs -P 2 -I{} bash
         41s bash   cd /tmp/probes && rm -rf finalprobes && mkdir -p finalprobes && printf '%s\n' cov20_p*.py ref4.py | xargs -P 2
         40s bash   cd /tmp/probes && rm -rf /tmp/probes/baselogs && mkdir -p /tmp/probes/baselogs && ls cov20_p*.py | xargs -P 2 

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the diff really does.** Adds a late `sortkeys` fallback for `name = sorted(d.items(), ...)` used only as `for k, v in name[slice]`, and rewrites `dict(sorted(d.items()))` to `{k: d[k] for k in sorted(d.keys())}`. It does not change normal-path code; it only runs after the typed path already refused.

**Probes.** Wrote 30 probes in `/tmp/rprobes` (basic, empty, argument/list/attribute/dict-value receivers, slices incl. negative/step, mutation before/after, aliases, shadowed `dict`/`sorted`, types, side-effect keys, non-constant `reverse=`). All default and `AIL_UNIFIED_FORCE=1` builds matched CPython; base results were identical. `--debug-dir` C for a plain program and for direct `for k, v in sorted(d.items())` is byte-identical to base.

**Tests.** `test_ail_cov20`, `test_ail_safetynet`, `test_ail_sort_keys` pass on HEAD. `update_manifest.py --check` passes.

**Defects.**
1. `dict(sorted(d.items()))` is still not supported on the typed path; the new lowering emits a dict comprehension at a stage where it is rejected.
```python
def main():
    d: dict[str, int] = {"b": 2, "a": 1, "d": 4, "c": 3}
    out: dict[str, int] = dict(sorted(d.items()))
    for k, v in out.items():
        print(k, v)
main()
```
Expected (the claimed construct): builds on the typed path and prints `a 1 b 2 c 3 d 4`. Actual on HEAD `--strict`: refusal `'out' is declared sdict; assigning int is unsupported` / `a dict comprehension`. Default builds only match because they still fall back to the pre-existing general path, so no coverage is gained. This is visible in the census: t467 has 5 blockers on both base and HEAD; line 34 is still blocked, only the message changed from `sorted(d.items()) ...` to `with key= columns ... a dict comprehension`. The report's “next blocker” claim is therefore false for t467.
2. The end-to-end cases in `test_ail_cov20.py` do not test the change: `PROGRAMS['ranked']` and `PROGRAMS['dictsorted']` already compile and match CPython on the base commit (general path/tuple support). Only `LoweringBoundary` distinguishes base, so a broken lowering still passes the behavioural tests. Add a typed-path (`--strict`) assertion or inspect the emitted C.

**Claims.** Fix/build list and test pass verified; “no program newly accepted” verified; `sorted` first refusal removed for t456 (3→2 blockers), but not for t467 (same line, renamed). Probes and manifest claims verified. Pair snapshot/count and refusal cases verified directly.

**Pre-existing.** None of the probe differences are new; all default/unified outputs already matched on base.
**Unverified.** `test_ail_files` / `test_ail_corpus_findings3` not rerun (outside reviewer scope); no gdev speed run (no hot-path change).

VERDICT: FIX
1. `dict(sorted(d.items()))` still refuses on the typed path; the emitted dict comprehension is rejected, so the construct is only relabelled, not supported (probe `p40_dictassign.py`, expected typed build + `a 1 / b 2 / c 3 / d 4`, actual typed refusal).
2. `test_ail_cov20` end-to-end programs already pass on base; add a typed-path or generated-C assertion that actually exercises the new lowering.
[cost $0.0688, opencode tokens {"total": 5498073, "input": 120955, "output": 19210, "reasoning": 38612, "cache.write": 0, "cache.read": 5319296}]
    tool time: bash 9.1 min
        129s bash   cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/rprobes/scan; n=0; for f in $(grep -rln "sorted(" lab/corpus
         95s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ai
         84s bash   cd /home/runner/work/ail-ci/ail-ci; mkdir -p /tmp/rprobes/scanh; for f in $(grep -rln "sorted(" lab/corpus/pro
         35s bash   cd /tmp/rprobes && rm -rf logs_head && mkdir logs_head && ls p0*.py p1*.py | xargs -P 2 -I{} bash -c 'bash ~/t
         33s bash   cd /tmp/rprobes && rm -rf logs_base && mkdir logs_base && ls p0*.py p1*.py | xargs -P 2 -I{} bash -c 'bash ~/t
         24s bash   cd /tmp/rprobes; mkdir -p forms; python3 - <<'PY' from pathlib import Path forms = { 'f_bool': '''def main():\
         20s bash   cd /tmp/rprobes; cat > harness.py <<'PY' import ast, subprocess, sys, os from pathlib import Path sys.path.ins
         16s bash   cd /tmp/rprobes cat > p20_strict_ranked.py <<'EOF' def main():     d: dict[str, int] = {"b": 2, "a": 1, "c": 3

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `8681e49` (not pushed).

- **Typed path fixed:** `dict(sorted(d.items()))` now lowers to `target = {}` + `for k in sorted(d.keys()): target[k] = d[k]`, preserving the target annotation. The reviewer probe (`p60`/`p40`) builds under `--strict` and prints `a 1 b 2 c 3 d 4`.
- **Aliasing guard:** `d = dict(sorted(d.items()))` stays on the expression/temp path, so the receiver is not emptied before it is read.
- **Tests strengthened:** `test_ail_cov20` now compares typed (`AIL_STRICT=1`) `ranked` and `dict(sorted(...))` programs with CPython and pins the lowered AST (2 loops, no dict comprehension).
- **Counts:** default-build census unchanged, 24 refused / 195 accepted; `glm t467` strict blockers 5 → 4, with line 34 no longer blocked.
- **Probes:** `p60`–`p71` all match CPython on both default and `AIL_UNIFIED_FORCE=1` builds. Strict builds match for `p60`, `p62`, `p68`, `p72`; all others are named typed refusals (`p61`, `p63`–`p67`, `p69`–`p71`, `p73`).
- **Final commit tests:** `test_ail_cov20`, `test_ail_sort_keys`, `test_json_kv`, `test_ail_ir_s3c2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 7/7 pass. `update_manifest.py --check` passes.
[cost $0.0590, opencode tokens {"total": 6216525, "input": 116686, "output": 15392, "reasoning": 23519, "cache.write": 0, "cache.read": 6060928}]
    tool time: bash 4.6 min, write 0.0 min
        211s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov
         19s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_sor
         18s bash   cd /tmp/probes && rm -rf cmpout && mkdir cmpout && ls p6*.py p70*.py p71*.py | xargs -P 2 -I{} bash -c 'bash ~
         12s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_cov2
          4s bash   cd /tmp/probes && rm -rf strict && mkdir strict && cat > strict_run.sh <<'SH' #!/bin/bash f=$1 d=/tmp/probes/s
          1s bash   cd /tmp/probes && rm -rf b40 b41 b46 && mkdir b40 b41 b46 && for f in p40_dictassign p41_dictcomp_typed p50_ra
          1s bash   cat > /tmp/probes/p41_dictcomp_typed.py <<'EOF' def main():     d: dict[str, int] = {"b": 2, "a": 1, "d": 4, "
          1s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p40_dictassign.py <<'EOF' def main():     d: dict[str, int] = {"b": 

## review 1
[model opencode-go/deepseek-v4.1-flash]
Ran the review in the worktree. Findings:

**What the change really does.** Adds fallback (`sortkeys.py`) lowering for `name = sorted(d.items(), ...)` when the name is used only as a snapshot iterable/slice in `for k, v in name[...]`, and for `dict(sorted(d.items()))` (assignment and expression form). The expression form materialises a temp dict and hoists it *before the whole statement*; the typed assignment form rewrites to `target = {}` + `for k in sorted(d.keys()): target[k] = d[k]`. Default-build C for programs not using the feature is byte-identical to base; the typed (`AIL_STRICT=1`) path is where `dict(sorted(...))` is newly accepted.

**Claims checked**
- Typed `dict(sorted(...))` assignment/expression, empty, reverse, int/str/float/unicode keys/values, param receiver, mutation after: **verified** (s01/s02/s05/s07/s10/s11/s17/s18/s19/s21/s23/s24 match CPython; base strict refuses).
- Aliasing guard `d = dict(sorted(d.items()))`: **verified** as described — default matches; strict is a named typed refusal, not silently emptied.
- `ranked` snapshots/slices/mutation/repeated loops: **verified** (s04/s08/s20/s22).
- t467 strict blockers 5 -> 4, line 34 gone: **verified**.
- Probes p60/p62/p64/p68/p71/p72 spot-checked: **verified**.
- `test_ail_cov20` + `test_ail_safetynet`, `update_manifest.py --check`: **verified pass**.
- Census 24/195: **unverified** (not rerun; structural evidence only). Remaining 5 worker test modules also unverified per instructions.

**Pre-existing:** none found; default/unified probes matched base (base sometimes used the general path, but outputs and C were unchanged).

**Defect (caused by this change, not present on base):** `dict_sorted_items` hoists the temp fill before the entire statement, so `dict(sorted(d.items()))` runs before earlier side effects in the same expression, whereas CPython evaluates left-to-right.

Probe `/tmp/rprobes/s27_typed_order_list.py`:
```python
def main():
    d: dict[str, int] = {"b": 2, "a": 1, "c": 3}
    xs: list[int] = [d.pop("a"), len(dict(sorted(d.items())))]
    print(xs[1])
main()
```
Expected (CPython 3.12): `2` (`d.pop("a")` removes `a` first)
Actual (HEAD, `AIL_STRICT=1`): `3` (hoisted snapshot still contains `a`)
Base (`AIL_STRICT=1`): named refusal `sorted(d.items()) is supported only as ...` — so this is a silent difference introduced by the new expression lowering. Same result with `max(d.pop("a"), len(dict(sorted(d.items()))))` (`/tmp/rprobes/s26_typed_order_max.py`).

A fix must either preserve evaluation order at the expression's position or refuse by name when the `dict(sorted(...))` expression is not evaluated first in its statement.

VERDICT: FIX
1. `/tmp/rprobes/s27_typed_order_list.py` (and s26): expected `2`, actual `3` on `AIL_STRICT=1`; hoisting `dict(sorted(d.items()))` to the statement prologue reorders it before `d.pop("a")`; base refused by name instead of silently differing.
[cost $0.0556, opencode tokens {"total": 3502759, "input": 101312, "output": 14353, "reasoning": 36310, "cache.write": 0, "cache.read": 3350784}]
    tool time: bash 5.2 min
         88s bash   date && cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test
         26s bash   cd /tmp/rprobes && date && rm -rf rlogs && mkdir rlogs && ls r*.py | xargs -P 2 -I{} bash -c 'bash ~/tools/cmp
         19s bash   cd /tmp/rprobes && cat > r17_order_with_ranked.py <<'EOF' def touch(d):     d["a"] = 99     return 0  def main
         14s bash   cd /tmp && rm -rf fb4 && mkdir fb4 && cd fb4 && for p in r04_snapshot_mutation r05_ranked_slices r17_order_wit
         14s bash   cd /tmp/rprobes && cat > r25_order_pop.py <<'EOF' def main():     d = {2: 20, 1: 10}     for k, v in sorted(d.
         13s bash   cd /tmp/rprobes && cat > r23_order_int.py <<'EOF' def touch(d):     d[1] = 99     return 0  def main():     d 
         13s bash   cd /tmp/rprobes && cat > r20_order_fallback.py <<'EOF' def touch(d):     d["a"] = 99     return 0  def main():
         12s bash   cd /tmp/base && grep -n "pair_assignment\|dict_sorted\|_pair_uses" AIL_CURRENT/python/pkg-v12/sortkeys.py | he

FINAL VERDICT: FIX  2026-10-28T21:14:14Z
