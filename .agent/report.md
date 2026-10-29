# job job-cov31-10290700  started 2026-10-28T22:17:56Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"b0c15eb1-fc04-4348-bac5-3471c31ea51c","session_id":"3887e985-eaaf-4a7c-8e59-fc872739a5da"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"7a5c509f-b186-490a-bc38-e64ccfdc3fb9","session_id":"a4205b93-395c-42eb-a638-38fabd31c48c"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed `6f1e86f` on `job-cov31-10290700`.

**Construct:** nested generator expressions. Corpus refusals: default build **24 → 21** of 219; forced-general build **21 after** (same three programs now build). The three fixed programs are deepseek `t172`, deepseek `t432`, glm `t432`; each matches CPython 3.12 on all three corpus inputs and both builds.

Supported only when the outer generator is consumed at once, every inner generator is eagerly consumed, and element/lazy clauses are side-effect free. Partial consumers (`next`/`any`/`all`), saved generators, breakable `for` loops, and side-effecting inner elements remain named compile-time refusals.

**Probes** (`bash .agent/cmp.sh`, both builds):
- Match CPython: `p_cov31_nested_eager`, `p_cov31_consumers`, `p_cov31_min_join`
- Refused by name: `p_cov31_nested_refuse`, `p_cov31_nested_refuse_saved`, `p_cov31_refuse_any_inner`, `p_cov31_refuse_for_break`, `p_cov31_refuse_saved_outer`, `p_cov31_side_effects`

**Tests:** 106 targeted generator/regression tests passed (1 skipped), including pre41/pre42. Final required run: `test_ail_cov31`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 27 tests passed, 1 skipped. `tools/update_manifest.py --check` exits 0.
[cost $0.0882, opencode tokens {"total": 5750556, "input": 283710, "output": 17990, "reasoning": 31000, "cache.write": 0, "cache.read": 5417856}]
    tool time: bash 72.0 min
       1503s bash   cp /tmp/profile_default.json /tmp/profile_default_before.json && cd /home/runner/work/ail-ci/ail-ci && python3
       1216s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_cov31 test_ail_pre41 test_ail_p
        830s bash   cat > /tmp/profile_corpus.py <<'PY' import os,sys,json,subprocess,tempfile,shutil,time,re from pathlib import 
        239s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_cov31 test_ail_safetynet test_a
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup env FORCE=1 python3 /tmp/profile_corpus.py > /tmp/profile_general_
         48s bash   cat > /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/test_ail_cov31.py <<'PY' """cov31: a nested generator expres
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p_cov31_*.py; do echo "##### $(basename $p)"; bash 
         37s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** it removes the blanket refusal of nested generator expressions and allows them only when the outer is consumed at once (`list`/`sum`/... argument, comprehension iterable, starred or tuple/list unpack) and each inner is eagerly consumed with side-effect-free elements; everything else stays a named refusal (`pyboxed2.py:2540-2556`, `12466-12537`, `6509`).

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`, both builds; base = worktree of `work`):

| probe | CPython | HEAD | base |
|---|---|---|---|
| `p_nested_ok` | ok | both match | refused (expected) |
| `p_unpack_caught` | `valueerror` | `indexerror` (g and d) | named refusal (both builds) |
| `p_unpack_extra_raise` | `ValueError` | `IndexError` (g and d) | named refusal |
| `p_unpack_div_caught` | `zerodiv` | both match | refused |
| `p_any_inner_side`, `p_any_elt_gen`, `p_any_inner_next`, `p_any_iter_short` | refused by name on HEAD | — | refused |
| `p_saved_outer_mutate/nomut/attr` | refused by name on HEAD | — | refused |
| `p_plain` | `--debug-dir` C identical to base | — | — |

**Claims:** three corpus programs (`deepseek t172/t432`, `glm t432`) verified: all 3 inputs, both builds, stdout+exit match CPython. Refusal counts 24 → 21 default and 21 general are consistent with the worker's profile JSON, but I did not re-run the whole 219-program profile (Unverified as an independent measurement). `test_ail_cov31` and `test_ail_safetynet` pass; `update_manifest.py --check` exits 0. The added tests do not cover the tuple/list-unpack path the new predicate enables.

**Defect:** `_genexp_consumed_now` (`pyboxed2.py:12477-12481`) treats a plain tuple/list unpacking target as consuming the generator to exhaustion. CPython stops such an unpack after `len(target)+1` elements (raising `ValueError` if an extra exists); the eager lowering materialises every element first, so a later element's exception changes the observable result. Also, base refuses all these programs by name, so this is a regression, not pre-existing.

```python
def main() -> None:
    xs = [10, 20, 30]
    try:
        a, b = (xs[i] + y for i in range(4) for y in (z for z in [0]))
    except ValueError:
        print("valueerror")
    except IndexError:
        print("indexerror")

main()
```
Expected (CPython 3.12): `valueerror`, exit 0. Actual (HEAD, both builds): `indexerror`, exit 0.

VERDICT: FIX
1. Nested generator expression allowed as the right-hand side of a plain tuple/list unpack materialises all elements instead of stopping after the target length; the probe above prints `indexerror` instead of CPython's `valueerror` on both builds (base refuses by name). The unpack branch in `_genexp_consumed_now` must be restricted (e.g. only starred/exhaustive unpacks) or the emitted unpack must preserve partial-consumption semantics.
[cost $0.0282, opencode tokens {"total": 1251789, "input": 57761, "output": 5741, "reasoning": 21055, "cache.write": 0, "cache.read": 1167232}]
    tool time: bash 3.5 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov31 test_ail_s
         24s bash   cat > /tmp/rprobes/check_corpus.sh <<'SH' set -u wt=$1 root=/home/runner/work/ail-ci/ail-ci for rel in deepsee
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_*.py; do echo "##### $(basename $p)"; bash ~/too
         10s bash   cat > /tmp/rprobes/p_unpack_caught.py <<'PY' def main() -> None:     xs = [10, 20, 30]     try:         a, b =
         10s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p_unpack_caught.py /tmp/rprobes/p_any_inner_side.p
          6s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dd_h /tmp/dd_b && AIL_NO_CACHE=1 AIL_UNIFIED_FORCE=1 python3
          6s bash   cat > /tmp/rprobes/p_saved_outer_mutate.py <<'PY' def main() -> None:     xs = [1, 2, 3]     e = (xs[i] for i 
          6s bash   cat > /tmp/rprobes/p_any_iter_short.py <<'PY' def main() -> None:     xs = [1]     print(any(x > 0 for x in (x

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `ab9c5dc`.

**Defect:** `_genexp_consumed_now` treated a plain tuple/list unpack RHS as exhausting the outer generator. It now requires a `*` target (starred/exhaustive); plain unpack remains a named refusal. `pyboxed2.py:12466`.

**Counts (unchanged):** default 24 → 21 of 219; forced general 21. The three allowed corpus programs still match CPython on all 3 inputs/both builds; AST scan found no corpus plain-unpack nested genexp.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `p_plain_extra` (reviewer probe), `p_plain_toofew`, `p_plain_raise_late` → refused by name.
- `p_starred_basic`, `p_starred_empty`, `p_starred_routes` (argument/list item/attribute/dict value), `p_starred_negative` → match CPython, both builds.

**Tests:** `test_ail_cov31`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (352s). Added a starred matching case and a plain-unpack refusal to `test_ail_cov31.py`. `update_manifest.py --check` passes; DEVLOG/DIFFERENCES updated.
[cost $0.0236, opencode tokens {"total": 1446695, "input": 58356, "output": 8559, "reasoning": 9284, "cache.write": 0, "cache.read": 1370496}]
    tool time: bash 8.2 min, edit 0.0 min
        354s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov31 test_ail_s
         58s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov31 2>&1 | tai
         25s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/check_corpus.sh <<'SH' set -u root=$PWD for rel in deepseek-v
         24s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_plain_extra p_plain_toofew p_plain_raise_late p_starred_basic
         23s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/check_corpus.sh <<'SH' set -u root=$PWD for rel in deepseek-v
          4s bash   cd /tmp/probes && cat > p_starred_empty.py <<'PY' def main() -> None:     try:         a, *b = (i for i in [] 
          2s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/p_plain_extra.py $PWD 2>&1 | tail -40
          2s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/p_starred_empty.py $PWD 2>&1 | tail -40

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** it lets the general path build a nested generator expression (instead of refusing it by name) when the outer generator is consumed at once and every inner generator is an argument of a “consuming” builtin/method, provided the element/lazy clauses look side‑effect free; the second commit narrows the unpack rule to a starred target.

**Probes** (`bash ~/tools/cmp.sh`, both builds unless noted):
- `p4_starred_basic` → matches CPython (verified).
- `p5_plain_unpack_extra` → refused by name on HEAD (base also refused) (verified).
- `p8_dictroute` → matches CPython (verified).
- `p9_exc_order`, `p10_mutate_start`, `p3_user_join` → silent differences, all refused by name on base (defects below).
- `p1_shadow_sum`, `p2_any_short`, `p6_all_short`, `p7_gen_mutation` → refused by name.
- Non‑feature program: generated `program.c` byte‑identical to base (verified).
- Actual corpus `deepseek t172`, `deepseek t432`, `glm t432` → all 3 inputs match on both builds (verified).

**Claims:** starred-allowed / plain-unpack-refused, corpus match, and `update_manifest.py --check` (rc 0) verified. “Counts unchanged (24→21 / 21)” and the corpus AST scan not re‑run (unverified). “values, order, exceptions and exit status match CPython” is **false** (p9/p10/p3).

**Tests:** `test_ail_cov31`, `test_ail_safetynet` on HEAD → 0 failed (133 s). `test_ail_files` / `test_ail_corpus_findings3` not re‑run. No pre-existing differences found. Speed not applicable (compile‑time check only).

VERDICT: FIX
1. Inner generator is materialised before sibling arguments of the consuming call are evaluated, so exception order changes.
   Probe:
   ```python
   def main() -> None:
       xs = [1]
       try:
           print(list(y for y in [sum((1 // z for z in [1, 0]), xs[5])]))
       except ZeroDivisionError:
           print("zerodiv")
       except IndexError:
           print("indexerror")
   main()
   ```
   Expected (CPython): `indexerror`; actual both builds: `zerodiv`.

2. The outer generator’s outermost iterable is excluded from the side‑effect screen, so eager materialisation misses mutation during iteration.
   Probe:
   ```python
   def bump(xs):
       xs.append(99)
       return 0
   def main() -> None:
       xs = [1, 2, 3]
       print(list(y for y in [sum((i for i in xs), bump(xs))]))
       print(xs)
   main()
   ```
   Expected: `[105]` then `[1, 2, 3, 99]`; actual both builds: `[6]` then `[1, 2, 3, 99]`.

3. A user‑defined method whose name is in the eager set (e.g. `join`) is trusted even though it need not consume its argument.
   Probe:
   ```python
   class C:
       def join(self, it):
           return "ignored"
   def main() -> None:
       try:
           print(C().join(a for a in (1 // z for z in [0, 1])))
       except ZeroDivisionError:
           print("zerodiv")
   main()
   ```
   Expected: `ignored`; actual both builds: `zerodiv`.
[cost $0.0274, opencode tokens {"total": 1231250, "input": 60508, "output": 5749, "reasoning": 19137, "cache.write": 0, "cache.read": 1145856}]
    tool time: bash 4.0 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_cov31 test_ail_s
         24s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_shadow_sum p2_any_short p3_user_join p4_starred_basic p5_plain
         23s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/check_corpus31.sh <<'SH' set -u root=$PWD for rel in deepseek
         14s bash   cd /tmp/rprobes cat > p9_exc_order.py <<'PY' def main() -> None:     xs = [1]     try:         print(list(y fo
         13s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p3_user_join p4_starred_basic p5_plain_unpack_extra; do echo "===
          9s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p9_exc_order p10_mutate_start; do echo "=== $p BASE"; bash ~/tool
          9s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_shadow_sum p2_any_short p5_plain_unpack_extra p6_all_short p7_
          6s bash   cd /tmp && cat > /tmp/nofeat.py <<'PY' def main() -> None:     xs = [3, 1, 2]     print(sorted(x for x in xs))

FINAL VERDICT: FIX  2026-10-29T00:49:38Z
