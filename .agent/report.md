# job job-cov21-10290431  started 2026-10-28T19:44:46Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"74322749-6f86-43e6-b6bd-15a15f78f239","session_id":"b7a65174-ff88-4775-82ed-b3d4c4aad960"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"00338150-6c1a-4e10-89cb-8b67f503e48a","session_id":"78991816-49da-4992-a6d9-f24b5a971ddc"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done. Commit `8539bc9` on `job-cov21-10290431`.

**Change:** Support a generator expression nested inside another when both are consumed at creation (`sum`/`min`/`max`/`list`/`set`/`dict`/`sorted`, comprehension source, unpack target, or `.join` on a string literal). Saved inner generators, `any`/`all`/`next` consumers, rebound builtins, and user-class `join` remain named refusals.

**Corpus (219 programs, both builds):**
- default: 24 → 21 compile-time refusals
- `AIL_UNIFIED_FORCE=1`: 24 → 21
- Unlocked: deepseek t172/t432, glm t432; all 3 inputs match CPython on both builds. Imports excluded from construct ranking.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- Match CPython: `nested_sum.py`, `nested_join.py`, `nested_empty.py`, `nested_types.py`, `nested_sources.py`, `nested_flat.py`
- Refused by name: `nested_refuse.py`, `nested_shadow.py`, `nested_custom_join.py`

**Tests:** added `test_ail_cov21.py`, registered in `ail_check.MODULES`, manifest clean. Required run: `test_ail_cov21`, `test_ail_pre41`, `test_ail_pre42`, `test_ail_pre116`, `test_ail_pre166`, `test_ail_check`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 49 tests OK, 1 skipped. New module re-run on final commit: 3 tests OK.
[cost $0.0492, opencode tokens {"total": 3940388, "input": 111501, "output": 14702, "reasoning": 20521, "cache.write": 0, "cache.read": 3793664}]
    tool time: bash 59.9 min
       1693s bash   mv /tmp/cov21_profile.py /tmp/cov21/cov21_profile.py 2>/dev/null; cd /tmp/cov21 && time python3 cov21_profile.
       1111s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest test_ail_cov21 test_ail_pre41 test_ail_pre42 
        188s bash   cd /tmp/cov21 && time python3 recheck_refused.py | grep -E '^(default|force)'; cd /home/runner/work/_temp/w2/A
        120s bash   cd /tmp/cov21 && cp profile.json profile_before.json && nohup python3 cov21_profile.py > profile_after.log 2>&
         96s bash   cd /tmp/cov21 && cat > recheck_refused.py <<'EOF' import os, subprocess, sys, json, concurrent.futures, shutil
         78s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && python3 -m unittest test_ail_pre42 -v 2>&1 | tail -30; echo ===; 
         49s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > nested_sum.py <<'EOF' rows = [[1, 2, 3], [4, 5], [], [-2, 7]] 
         48s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT/python/pkg-v12 && python3 - <<'EOF' from pathlib import Path p=Path(

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: cov21 nested generator expressions

**What the change does:** Replaces the blanket refusal of a generator expression nested in another with an AST-parent whitelist: both outer and inner must sit in a "consumed in place" context (`for`/comprehension source, starred, tuple-unpack, one of `list/tuple/set/frozenset/dict/sorted/sum/min/max/bytes/bytearray/Counter/array`, or `.join` on a string literal). This matches the report, but the claim "read to exhaustion at the point it is created" is false for several of those contexts (see defects).

**Probes** (`bash ~/tools/cmp.sh`, both builds; base `/tmp/rbase` = `work`):

| probe | HEAD | base |
|---|---|---|
| p_order (`sum(gen, start_with_side_effect)`) | **103→3, exit 0 both** | refused by name |
| p_forbreak (`for r in gen: break`) | **exit 0→1, missing stdout** | refused by name |
| p_unpack2 (`a,b = gen` over 4 elems) | **ValueError→RuntimeError** | refused by name |
| p_dict (`dict(gen)` malformed elem #0, later elem raises) | **consumer TypeError→inner TypeError** | refused by name |
| p_any / p_next / p_customjoin / p_rebound2 | refused by name | refused |
| p_empty / p_neg / p_sortedkey / p_min(const) / p_plain | match CPython | match |
| p_unpack (single genexp unpack) | RuntimeError vs ValueError | **identical** |

Non-feature C: `--debug-dir` `program.c` byte-identical HEAD vs base for `p_plain` (only `native_report.json` temp paths differ).

**Claims:** corpus 24→21 counts *unverified* (no re-profile); the 3 named programs (deepseek t172/t432, glm t432) verified accepted and matching CPython stdout+exit on all 3 inputs, both builds. `test_ail_cov21` + `test_ail_safetynet` pass on HEAD (2 modules, 0 failed). Manifest `--check` clean. Other listed test modules not rerun. Probe list in `/tmp/probes` not rerun (unverified). "Saved/any/all/next/rebound/user-join refuse by name": verified.

**Defects (all were named refusals on base, so the change caused them):**

1. `for`/`async for` iterable is not exhaustion — the loop can `break`. `_nested_genexp_materialised_safely` returns True for `ast.For.iter`, so the outer generator is eagerly materialised.
```
rows = [[1], [2], [3]]
def bad(x):
    if x == 3: raise RuntimeError("boom")
    return x
for r in (sum(bad(v) for v in row) for row in rows):
    print(r); break
print("done")
```
CPython: `1\ndone`, exit 0. HEAD, both builds: no stdout, `RuntimeError: boom`, exit 1.

2. Materialisation happens before sibling arguments are evaluated. `sum(gen, start)`, `min(gen, default=...)`, `sorted(gen, key=...)` are all trusted regardless of arity.
```
rows = [[1], [2]]
def bump():
    rows.append([100]); return 0
print(sum((sum(v for v in row) for row in rows), bump()))
```
CPython: `103` (gen consumed after `bump()`). HEAD both builds: `3`. Silent stdout difference, exit 0.

3. Tuple/list unpack target is not exhaustion: CPython pulls only `len(target)+1` elements.
```
rows = [[1], [2], [3], [4]]
def bad(x):
    if x == 4: raise RuntimeError("boom")
    return x
a, b = (sum(bad(v) for v in row) for row in rows)
```
CPython: `ValueError: too many values to unpack (expected 2)`, exit 1. HEAD both builds: `RuntimeError: boom` (evaluates element 4), exit 1.

4. Same class for consumers that validate element-by-element: eager materialisation runs later inner generators that CPython never reaches.
```
rows = [[1], [2, "a"]]
print(dict((sum(v for v in row) for row in rows)))
```
CPython: `TypeError: cannot convert dictionary update sequence element #0 to a sequence`. HEAD both builds: `TypeError: unsupported operand type(s) for +: 'int' and 'str'`.

Fix direction: drop `For` (break) and unpack targets from the safe set, and for calls require the generator to be the sole positional argument with no keywords and no incremental-validation consumer (`dict`); otherwise keep the named refusal. The rest of the change (nested `sum`/`join` single-argument, list-comprehension source) is sound.

**Pre-existing:** `a,b = (single genexp)` over too many elements yields a different exception than CPython on base and HEAD alike.

**Unverified:** full corpus refusal counts (24→21); worker's `/tmp/probes/*` outputs; the other listed test modules; instruction 5 speed (no runtime/emission path changed for existing programs).

VERDICT: FIX

1. `for ... in <nested gen>: break` is accepted but eagerly evaluates elements CPython never reaches (p_forbreak: expected `1\ndone` exit 0, actual `RuntimeError: boom` exit 1 in both builds).
2. Eager materialisation precedes sibling-argument evaluation (p_order: expected `103`, actual `3`, exit 0 both builds).
3. Tuple-unpack target only consumes `n+1` elements (p_unpack2: expected `ValueError: too many values to unpack`, actual `RuntimeError: boom`).
4. Incrementally-validating consumers see later elements first (p_dict: expected `dict` element TypeError, actual inner `+` TypeError).
[cost $0.0255, opencode tokens {"total": 1279682, "input": 51171, "output": 6133, "reasoning": 17514, "cache.write": 0, "cache.read": 1204864}]
    tool time: bash 5.5 min
        181s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_ail_cov21 te
         52s bash   cd /home/runner/work/_temp/w2 && for p in p_order p_sortedkey p_unpack p_any p_dict p_min p_attr p_plain; do e
         29s bash   cat > /tmp/rprobes/corpus_check.sh <<'EOF' #!/bin/bash wt=$1 prog=$2; task=$3; d=$(mktemp -d /tmp/ccXXXX) cp "
         27s bash   cd /tmp/rprobes && cat > p_rebound.py <<'EOF' def list(x):     return "shadow" rows = [[1], [2]] print(list(su
         16s bash   cd /tmp/rbase && for p in p_order p_unpack p_dict; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py 
         11s bash   cd /tmp/rprobes && cat > p_unpack2.py <<'EOF' rows = [[1], [2], [3], [4]] def bad(x):     if x == 4:         r
         11s bash   cd /tmp/rprobes && cat > p_forbreak.py <<'EOF' rows = [[1], [2], [3]] def bad(x):     if x == 3:         raise
          3s bash   cd /tmp/dbg_head && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/_temp/w2/AIL_CURRENT/ail_cha

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all four review defects and committed as `8281346`.

- Removed `for`/`async for` iterables and tuple/list unpack targets from the nested-genexp safe set.
- Calls now require the generator to be the sole positional argument with no keywords; removed `dict` and other incremental validators (`set`, `frozenset`, `bytes`, `bytearray`, `Counter`, `array`).
- Kept single-argument `list`/`tuple`/`sorted`/`sum`/`min`/`max`, comprehension sources, starred unpacks, and string-literal `.join`.

Probes (both builds, `cmp.sh`):
- Match CPython: `nested_sum`, `nested_join`, `nested_sources`, `nested_flat`, `nested_types`, `nested_empty`, `nested_star`, `nested_consume`.
- Refused by name: `nested_shadow`, `nested_custom_join`, `nested_refuse`, `nested_sortedkey`, `nested_dict`, `nested_unpack2`, `nested_order`, `nested_forbreak`, `nested_next`.

Corpus: only the three nested-genexp programs (deepseek t172/t432, glm t432) exist; all still compile on both builds and match CPython on all 3 inputs, so refusals remain 24 -> 21. Manifest `--check` clean.

Final-commit tests: `test_ail_cov21`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (373s).
[cost $0.0226, opencode tokens {"total": 1110682, "input": 51510, "output": 7610, "reasoning": 11946, "cache.write": 0, "cache.read": 1039616}]
    tool time: bash 16.1 min
        461s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov21 te
        376s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov21 te
         96s bash   cd /home/runner/work/_temp/w2 && for p in nested_sum nested_join nested_sources nested_flat nested_types neste
         29s bash   cd /home/runner/work/_temp/w2 && for spec in "deepseek-v4.1-flash-free t172" "deepseek-v4.1-flash-free t432" "
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check 
          0s bash   cd /home/runner/work/_temp/w2 && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/python/pkg-v12/pyboxed2.py AIL_
          0s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' import ast, glob rows=[] for p in glob.glob('lab/corpus/prog
          0s bash   cd /home/runner/work/_temp/w2 && git log --oneline -15 && git status --short && ls

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: job-cov21 (HEAD 8281346, diff `work..HEAD`)

**What the change really does:** In the general path it replaces the blanket refusal of every nested generator expression with a whitelist (`_nested_genexp_materialised_safely`): a nested generator is allowed when it is a comprehension source, a `Starred`, a sole positional argument of `list`/`tuple`/`sorted`/`sum`/`min`/`max` (unless that builtin is rebound anywhere), or a `.join` on a string literal; `for`/unpack targets and incremental consumers were removed. The fused `any`/`all`/`next` handlers still refuse nested generators unconditionally.

**Defect found (introduced by this change).** Treating a comprehension source as a point where the generator is "read to exhaustion" is false: a comprehension can abort early when its `if` filter or element expression raises, so later source elements are never pulled in CPython, but the eager materialisation evaluates them first. Base refused these programs by name; HEAD accepts them and prints the wrong exception.

1. Probe `/tmp/rprobes/p_filter_raise.py`
```python
rows = [[1], [2], [3]]
def bad(v):
    if v == 3: raise RuntimeError('elt')
    return v
def flt(x):
    if x == 2: raise ValueError('flt')
    return True
try:
    print([x for x in (sum(bad(v) for v in row) for row in rows) if flt(x)])
except Exception as e:
    print(type(e).__name__, e)
```
Expected (CPython): `ValueError flt`. Actual HEAD, both builds: `RuntimeError elt` (base: named refusal).
`/tmp/rprobes/p_gen_filter_raise.py` (same with `list(x for ... if flt(x))`) and `/tmp/rprobes/p_inner_filter_raise.py` (`sum(x for x in (bad(v) for v in [1,2,3]) if flt(x))`) show the identical `ValueError flt` vs `RuntimeError elt` divergence.

**Other probes (HEAD, both builds):**
- Named refusals, acceptable: `p_for_inner` (loop break), `p_next_inner`, `p_any_inner`/`p_all_inner` (handler-specific message), `p_join_var` (non-literal receiver), `p_sorted_kw` (keyword), `p_dict_consumer`, `p_shadow_sum`, `p_min_default`, `p_star_call`.
  - `p_star_call` (`print(*(sum(...) for ...))`) is a *spurious* refusal: the emitter's local parent map is built from the generator subtree, so it can never see the `Starred` parent. Conservative only; not a defect.
- Matches CPython: `p_star_list` (`[*(...)]`).
- `p_mutate` is an infinite loop in CPython too (list appended while iterated); not a valid probe.

**Claims:**
- Removed `for`/unpack targets, require sole positional arg / no keywords, removed `dict` & incremental validators, kept the listed consumers — **verified** in the diff.
- "Comprehension sources are safe" — **false** (see defect).
- Probes refused by name / match — **mostly verified** for the categories above; `p_star_call` is refused although the safe-set says it should compile.
- Corpus 24→21 refusals and "3 corpus programs match on all inputs" — **unverified** (no corpus re-profile run).
- Tests: re-ran `test_ail_cov21` + `test_ail_safetynet` on HEAD (`-j 2`): 2 modules, 0 failed. `test_ail_files` / `test_ail_corpus_findings3` not re-run. The new test module does not cover the aborting-comprehension case.
- Speed: compile-time screening only; no runtime codegen change, so not checked.

**Unverified:** full corpus refusal counts, the three corpus fixtures, `test_ail_files`, `test_ail_corpus_findings3`, and C-output identity for non-feature programs (code path is unchanged for non-nested genexps, so expected equal).

VERDICT: FIX
1. Comprehension sources are not exhaustion points. `_nested_genexp_materialised_safely` returns True for `isinstance(par, ast.comprehension) and par.iter is node`, but a comprehension's filter/element can raise (or otherwise abort) after consuming only part of the source. `/tmp/rprobes/p_filter_raise.py` (and `p_gen_filter_raise.py`, `p_inner_filter_raise.py`) are refused by name on the base but now compile on both builds and print `RuntimeError elt` where CPython prints `ValueError flt`. Either drop the comprehension-source case from the safe set or restrict it to comprehensions whose filter and element cannot raise before the source is exhausted; add this case to `test_ail_cov21.py`.
[cost $0.0190, opencode tokens {"total": 563081, "input": 43923, "output": 4350, "reasoning": 13816, "cache.write": 0, "cache.read": 500992}]
    tool time: bash 13.2 min
        353s bash   date; cd /home/runner/work/_temp/w2 && for p in p_any_inner p_all_inner p_next_inner p_for_inner p_star_call p
        163s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_cov
        121s bash   cd /home/runner/work/_temp/w2 && timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/p_mutate.py $PWD 2>&1 | tail -20
        120s bash   pkill -f 'p_mutate|exe_g|exe_d' 2>/dev/null; cd /home/runner/work/_temp/w2 && sed -n '9040,9080p' AIL_CURRENT/
         19s bash   cd /tmp/rprobes && cat > p_filter_raise.py <<'EOF' rows = [[1], [2], [3]] def bad(v):     if v == 3:         r
         15s bash   date; cd /home/runner/work/_temp/w2 && for p in p_filter_raise p_inner_filter_raise p_gen_filter_raise; do ech
          2s bash   cd /tmp && rm -rf sc && mkdir sc && cp /tmp/rprobes/p_star_call.py sc/p.ail && cd sc && AIL_UNIFIED_FORCE=1 AI
          0s bash   cd /home/runner/work/_temp/w2 && grep -rn "nested inside another generator\|nested generator" AIL_CURRENT --in

FINAL VERDICT: FIX  2026-10-28T21:57:57Z
