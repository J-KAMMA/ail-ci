# job job-cov29-10290513  started 2026-10-28T20:51:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"033a3934-0ff5-4a30-a851-b1c06bfdda44","session_id":"009e82f4-e95a-48ea-aaf9-13b0e7073a18"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"0f8e0e5f-3fcb-4d36-b780-58b880ddd86c","session_id":"ab1e8c75-e5ee-494c-b8f3-1f107f0dde72"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `805cf94` on `job-cov29-10290513`.

- Census (219 corpus programs, both builds; `lab/profile/run.py` is absent on this tree, so built directly with `default` and `AIL_UNIFIED_FORCE=1`): refusals **24 → 21** default, **24 → 21** unified. Nested-generator refusals **3 → 0**; 3 corpus programs now match CPython on all inputs in both modes.
- Change: nested generator expressions are accepted when both the outer and inner generators are consumed immediately (`sum`, `join`, `any`/`all`/`next`, `list`/`tuple`/`sorted`, unpacking). Saved inner generators and for/comprehension-source outers stay named refusals.
- Added `AIL_CURRENT/test_ail_cov29.py`, registered in `ail_check.MODULES`; updated DEVLOG, manifest, and CI shards.
- Probes in `/tmp/probes/cov29` via `cmp.sh`: `p_basic`, `p_routes`, `p_empty`, `p_consumers`, `p_triple` match on both builds; `p_negative`, `p_side_effects`, `p_side_simple`, `p_refuse_inner_value`, `p_refuse_inner_list`, `p_refuse_any_value` are refused by name.
- Tests on final commit: `test_ail_cov29`, `test_ail_pre41`, `test_ail_pre42`, `test_ail_pre116`, `test_ail_pre211`, `test_ail_fuzz55`, `test_ail_fuzz77`, `test_ail_genlib`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 11 modules, 0 failed. Manifest and shard checks pass.
[cost $0.0512, opencode tokens {"total": 4682303, "input": 122549, "output": 14585, "reasoning": 17553, "cache.write": 0, "cache.read": 4527616}]
    tool time: bash 62.4 min, write 0.0 min
       1334s bash   python3 - <<'PY' p='/tmp/census.py' s=open(p).read().replace("Path('/tmp/census.jsonl')","Path(os.environ.get(
       1109s bash   python3 /tmp/census.py
        620s bash   python3 tools/par_check.py -j 2 --timeout 2400 test_ail_cov29 test_ail_pre41 test_ail_pre42 test_ail_pre116 te
        417s bash   python3 tools/par_check.py -j 2 --timeout 2400 test_ail_cov29 test_ail_pre41 test_ail_pre42 test_ail_pre116 te
         48s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyboxed2.py') s=p.read_text() old
         47s bash   cd /tmp/probes/cov29 && cat > p_routes.py <<'PY' def total(rows):     return sum(sum(x for x in row) for row i
         45s bash   for t in deepseek-v4.1-flash-free/t470 glm-5.3-flash-free/t470 deepseek-v4.1-flash-free/t095 deepseek-v4.1-fla
         41s bash   python3 AIL_CURRENT/test_ail_cov29.py -v

## review 0
[model opencode-go/deepseek-v4.1-flash]
# Review — cov29 (nested generator expressions)

**What the change really does:** relaxes the unconditional "nested generator expression" refusal in `pyboxed2.py` to allow eager lowering when both the outer and inner genexps are classified as immediately consumed; adds `_genexp_parents`, `_genexp_immediate_consumer`, `_nested_value_genexp`, and removes the per-site checks in `expr_GeneratorExp`/`_b_next`. Matches the report's description.

**Probe results** (`bash ~/tools/cmp.sh`, both builds unless noted)
- `p_sum_any`, `p_next_filter`, `p_unpack_exact`, `p_starred`, `p_join_next`, `p_filter`, `p_next_inner`, `p_inner_any_short`: match CPython on both builds.
- `p_iter_nested` (outer iterable is a genexp): named refusal — correct.
- `p_shadow` (user-defined `sum`): named refusal — acceptable.
- `p_unpack`, `p_unpack_ok`: diff identical on base → **Pre-existing** (eager genexp on unpack; inner genexp here is inside a helper function, not syntactically nested).
- Corpus `deepseek t172`, `deepseek t432`, `glm t432`: build and match CPython on all three `lab/corpus/tasks/t432` inputs, both builds. Generated C for `p_plain`/`p_single` differs only in `native_report.json` temp paths (C identical to base).
- Tests: `test_ail_cov29`, `test_ail_safetynet`, `test_ail_genlib` — 3 modules, 0 failed.

**Defect (new, caused by this change):** tuple/list-unpack assignment is treated as an "immediate consumer" although it only pulls `N+1` elements. Eager materialisation then evaluates elements past the error point.

```
rows = [1, 1, 1, 0]
try:
    a, b = (sum(10 // y for y in [x]) for x in rows)
except ValueError:
    print("too many")
except ZeroDivisionError:
    print("zero")
print("done")
```
- CPython 3.12: `too many` / `done`
- HEAD (both builds): `zero` / `done`
- Base: named nested-genexp refusal.

Side-effect form `p_unpack2` (4 rows, `a, b = (sum(f(y) for y in [row]) for row in rows)`) also prints `row 40` on HEAD, which CPython never evaluates. `_genexp_immediate_consumer` should not treat `a, b = gen` (no `*` target) as whole consumption; only starred targets (or a full-materialising consumer) are exact.

**Report claims**
- nested refusals now gone for the 3 named corpus programs — **verified**.
- exact census `24 → 21` / `3 → 0` — **unverified** (not re-run over all 219; time box).
- test registration, DEVLOG, manifest, shards — **verified** present.
- "11 modules, 0 failed" — **partially verified** (3 of them re-run here, all pass).
- probe list in `/tmp/probes/cov29` — **unverified** (not present in this worktree path).

**Unverified:** full census counts; remaining 8 worker test modules; instruction-count impact (change is compile-time only, no runtime edit).

VERDICT: FIX
1. Tuple/list unpack assignment is accepted as an immediate consumer of a nested generator, so eager materialisation runs elements CPython never reaches. Probe `p_unpack3.py` above: expected `too many`/`done`, actual `zero`/`done` on both builds (base refused by name). Also `p_unpack2.py`: expected rows `10,20,30`, actual `10,20,30,40`.
2. `AIL_CURRENT/test_ail_cov29.py` has no unpack case, so it does not catch the regression; add one alongside the fix.
[cost $0.0231, opencode tokens {"total": 1022402, "input": 43092, "output": 6360, "reasoning": 16662, "cache.write": 0, "cache.read": 956288}]
    tool time: bash 3.9 min
        117s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 --timeout 1500 te
         31s bash   cd /tmp/rprobes; for p in p_unpack p_unpack_ok p_shadow p_next_inner p_filter p_iter_nested p_inner_any_short;
         17s bash   cd /tmp/rprobes cat > p_sum_any.py <<'PY' rows = [[0, 1, 9], [0, 0, 0]] print(sum(any(x for x in row) for row 
         12s bash   cd /tmp && rm -rf corpchk && mkdir corpchk && cd corpchk W=/home/runner/work/_temp/w2 for spec in "glm-5.3-fla
         11s bash   cd /tmp/rprobes; cat > p_unpack3.py <<'PY' rows = [1, 1, 1, 0] try:     a, b = (sum(10 // y for y in [x]) for 
          9s bash   cd /tmp/rprobes cat > p_unpack2.py <<'PY' def f(row):     print("row", row)     return row  rows = [10, 20, 30
          7s bash   date; cd /tmp/rprobes; cat p_unpack3.py; echo "--- HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/p_unpack3.py /home/
          6s bash   cd /tmp && rm -rf corpchk && mkdir corpchk && cd corpchk W=/home/runner/work/_temp/w2 for spec in "deepseek-v4

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Committed `42a808b` on `job-cov29-10290513`.

**Fix:** `_genexp_immediate_consumer` now treats a tuple/list unpack as whole consumption only when the target has a direct `*` element. Plain unpack pulls `len(targets)+1` elements, so eager lowering evaluated elements CPython never reaches; it is now refused by name again. Added starred-unpack match and plain-unpack refusal cases to `test_ail_cov29.py`.

**Probes** (`/tmp/probes/cov29fix`, `cmp.sh`, both builds):
- Refused by the nested-generator name: `p_unpack3`, `p_unpack2_side`, `p_unpack_neg`, `p_unpack_exact`, `p_unpack_routes`.
- Match CPython on both builds: `p_star_basic`, `p_star_middle`, `p_star_empty`, `p_star_negative`, `p_star_via_argument`, `p_star_via_list_item`, `p_star_via_attribute`, `p_star_via_dict_value`.

**Census:** 219 corpus programs, both builds: 21 default / 21 unified refusals, nested-generator reason 0 (unchanged by the fix). Corpus `deepseek t172`, `deepseek t432`, `glm t432`: all 3 inputs match CPython on both builds.

**Tests:** `test_ail_cov29`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_genlib`, `test_ail_fuzz77` — 6 modules, 0 failed. Manifest `--check` passes.
[cost $0.0224, opencode tokens {"total": 1423686, "input": 46338, "output": 8469, "reasoning": 10415, "cache.write": 0, "cache.read": 1358464}]
    tool time: bash 19.4 min, edit 0.0 min, write 0.0 min
        833s bash   cd /tmp && CENSUS_OUT=/tmp/census_fix.jsonl python3 /tmp/census.py
        270s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 --timeout 1500 te
         36s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/cov29fix/*.py; do echo "===== $(basename "$p")"; bash ~/
         19s bash   cd /home/runner/work/_temp/w2 && set -e W=$PWD for spec in "deepseek-v4.1-flash-free t172" "deepseek-v4.1-flas
          3s bash   cd /home/runner/work/_temp/w2 && bash ~/tools/cmp.sh /tmp/probes/cov29fix/p_star_empty.py "$PWD"
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check
          0s bash   cd /home/runner/work/_temp/w2 && git status --short && python3 tools/update_manifest.py --check && echo manife
          0s bash   cd /home/runner/work/_temp/w2 && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Removes the blanket compile-time refusal for any generator expression containing another and replaces it with `_nested_value_genexp`: a nested genexp is allowed only when the outer *and* inner are "immediate consumers" (argument of a consuming builtin/method, starred unpack, or unpack into a target with a direct `*`). It also relaxes the nested checks in `_b_next`, `_any_all`, and `expr_GeneratorExp`, adds `test_ail_cov29`, MANIFEST/DEVLOG/ci_shards entries. This matches the report.

**Probes** (`/tmp/rprobes/cov29rev`, `cmp.sh`, both builds; base = `/tmp/base29` @ `work` `f62a36f`):
- `p_unpack3.py`: refused by the nested-generator name on both builds; base same. Verified.
- `p_star_middle.py`: matches CPython both builds. Verified.
- `p_shadow_any/next/sum/all.py`: still refused by name (typed path `pyboxed.py` still rejects), base same. Not a defect.
- Non-feature programs `g.py` (simple genexp) and `n.py` (plain loop): `--debug-dir` `program.c` identical HEAD vs base; only `native_report.json` temp paths differ. Verified C unchanged.
- Corpus `deepseek t172`, `deepseek t432`, `glm t432`: match CPython (stdout/exit) on both builds. Verified.
- `p_start_side.py` / `p_start_kw.py`: **mismatch on HEAD, refused on base** — defect below.

**Tests.** `test_ail_cov29` ok, `test_ail_safetynet` ok (`par_check.py -j 2`, 0 failed). `update_manifest.py --check` rc 0.

**Claims.** Unpack rule, plain-unpack refusal, starred-unpack match, manifest check: verified. Corpus 219 / 21→21 / nested-reason 0 and the 6-module test result: not independently re-run (spot checks only). Speed: change is compile-time only; not measured.

**Pre-existing.** `p_start_simple.py` (`sum((mark(x) for x in [1,2,3]), start(0))`) shows the same "start before marks" reorder on base, so the underlying eager-materialisation timing flaw predates this job; what is new is that the nested form is now accepted instead of refused.

**Defect**
1. A nested generator is accepted even when its eager consumer has other arguments with observable side effects; the generator body runs before those arguments, unlike CPython. `/tmp/rprobes/cov29rev/p_start_side.py`:
```python
def mark(x):
    print("mark", x); return x
def start(v):
    print("start", v); return v
rows = [[1, 2], [3]]
print(sum((sum(mark(x) for x in r) for r in rows), start(0)))
```
Expected (CPython 3.12): `start 0`, `mark 1`, `mark 2`, `mark 3`, `6`. Actual HEAD (both `g` and `d`): `mark 1`, `mark 2`, `mark 3`, `start 0`, `6`. Base refuses by name. Same for `start=start(0)` (`p_start_kw.py`) and other consumers with extra args (`min(..., default=...)`). Fix: treat a consumer call with additional positional/keyword arguments as *not* immediate for the nested outer genexp (keep the named refusal), or evaluate lazily.

**Unverified.** Full 219×2 refusal census; re-running `test_ail_files`/`test_ail_corpus_findings3`/`test_ail_genlib`/`test_ail_fuzz77`; instruction-count impact (compile-time-only change).

VERDICT: FIX
1. Nested generator accepted with an eager consumer that has other side-effecting arguments; output order differs from CPython (`p_start_side.py`: expected `start 0` first, actual last). Base refused, so the change introduced the mismatch.
[cost $0.0317, opencode tokens {"total": 2050362, "input": 59631, "output": 7739, "reasoning": 20368, "cache.write": 0, "cache.read": 1962624}]
    tool time: bash 3.2 min
        102s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_cov29 te
         18s bash   cd /home/runner/work/_temp/w2 && for f in lab/corpus/programs/deepseek-v4.1-flash-free/t172.py lab/corpus/prog
         16s bash   cd /tmp/rprobes/cov29rev && for p in p_start_side.py p_start_simple.py p_shadow_any.py p_shadow_next.py; do ec
         14s bash   mkdir -p /tmp/rprobes/cov29rev && cd /tmp/rprobes && mv p_shadow_any.py p_shadow_next.py p_shadow_sum.py p_sta
          8s bash   cd /tmp/dbg29 && rm -rf dbg_* exe_* && for f in g n; do for w in h b; do wt=/home/runner/work/_temp/w2; [ $w =
          8s bash   cd /tmp && rm -rf dbg29 && mkdir -p dbg29 && printf 'print(sum(x for x in [1,2,3]))\n' > dbg29/g.py && printf 
          5s bash   cd /tmp/rprobes/cov29rev && cat > p_sorted_key_side.py <<'EOF' def mark(x):     print("mark", x)     return x 
          5s bash   cd /tmp/probes/cov29fix && for p in p_unpack3.py p_star_middle.py; do echo "== $p"; bash ~/tools/cmp.sh "$PWD/

FINAL VERDICT: FIX  2026-10-28T23:20:43Z
