# job job-std_heapq-11011434  started 2026-11-01T05:34:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented on branch `job-std_heapq-11011434`, committed as `021e8f0`.

- Added 12 realistic `heapq` programs in `lab/stdlib/heapq/`.
- Results: **11/12 build** (1 typed, 10 general); all match CPython 3.12 stdout and exit status on `AIL_IR=0` and `AIL_IR=1`.
- Fixed the shared blocker: `heapq.merge` now works on the general path (`key=`, `reverse=`, empty/infinite streams, stable equal-key order) via `genlib.py` and `prelude_genlib.py`.
- Remaining refusal: `merge_k_lists.py` uses `heapq.merge(*rows)`; starred call arguments in general are out of scope. Exact text and final results are in `lab/stdlib/heapq/RESULTS.md`.
- Probes: `hq_merge_basic`, `hq_merge_routes`, `hq_merge_from`, `hq_merge_custom` — all match CPython on both builds.
- Added `test_ail_std_heapq.py` (11 programs, 2 IR modes) and a 2500-case merge comparison in `test_ail_genlib`.

Final checks passed: `test_ail_std_heapq`, `test_ail_genlib`, `test_ail_heapq_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **0 failed**. `update_manifest.py --check` passes; typed codegen pins unchanged.
[cost $0.0000, opencode tokens {"total": 6191242, "input": 124789, "output": 17576, "reasoning": 19181, "cache.write": 0, "cache.read": 6029696}]
    tool time: bash 22.0 min, write 0.0 min, edit 0.0 min
        407s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hqbase /tmp/hqc /tmp/hqb && git worktree add --detach /tmp/h
        399s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_heapq test_ail_genlib test_
        369s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_std_heapq test_ail_genlib test_
         52s bash   cd /home/runner/work/ail-ci/ail-ci && for f in lab/stdlib/heapq/*.py; do n=$(basename "$f" .py); echo "=== $n"
         29s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hqfinal && mkdir -p /tmp/hqfinal && for f in lab/stdlib/heap
         25s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hqbuild && mkdir -p /tmp/hqbuild && for f in lab/stdlib/heap
         20s bash   python3 - <<'PY' p='/tmp/probes/hq_merge_from.py' s=open(p).read().replace('print(list(join(*[values, [(0, "z"
          6s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hqbuild2 && mkdir -p /tmp/hqbuild2 && for n in merge_logs fr

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Adds `heapq.merge` to the general path (`genlib.py:66` maps it to `_ail_merge`; `prelude_genlib.py:689-755` implements a linear-scan merge with `key=`/`reverse=`), plus 12 lab programs, `test_ail_std_heapq.py`, and a 2500-case comparison in `test_ail_genlib.py`. No compiler/runtime internals or lab/compare sources were changed.

**Probes** (`bash ~/tools/cmp.sh <p> $PWD`; base refuses `heapq.merge`, so all merge diffs below are new):

| probe | CPython | HEAD g/d |
|---|---|---|
| `p_routes.py` (arg/list/attr/dict, key+reverse, `count()` streams) | — | same stdout |
| `p_tie.py` (`__lt__`+`__eq__`, equal keys) | — | same stdout |
| `p_mutate.py` (mutate list between yields) | — | same stdout |
| `p_keyraise.py` | `[1, 2, 3]` | `caught boom` |
| `p_keycalls.py` | `[1]` then `[1, 1, 2, 3, 4]` | `[1, 2, 3]` then `[1, 2, 3, 1, 2, 3, 4]` |
| `p_lt_only.py` | `[c, a, d, b]` (both lines) | `[a, b, c, d]` (both lines) |
| `p_nan.py` | `[nan, nan, 1.0, 2.0]` | `[nan, 1.0, nan, 2.0]` |

**Defects**

1. **Missing CPython single-stream fast path (`prelude_genlib.py:705`).** When only one stream remains, CPython yields its remaining values via `yield from next.__self__` without calling `key`; `_ail_merge` keeps calling `key` on every value. Probe `/tmp/rprobes/p_keyraise.py`:
   ```python
   import heapq
   def key(x):
       if x == 2: raise ValueError("boom")
       return x
   def main():
       try: print(list(heapq.merge([1, 2, 3], key=key)))
       except ValueError as exc: print("caught", exc)
   main()
   ```
   Expected stdout `[1, 2, 3]`; actual `caught boom` (both builds, exit 0). Same root cause shown by `/tmp/rprobes/p_keycalls.py` (key-call side effects: expected `[1]`, actual `[1, 2, 3]`). This is a small, local fix (add the one-head fast path).

2. **Tie-break uses input order where CPython does not (`_ail_merge_before`, `prelude_genlib.py:689`).** CPython's list comparison only consults the `order` field after `==`; this code consults it whenever neither key is `<`. For valid sorted inputs whose elements define only `__lt__` (distinct objects that compare neither less nor equal), CPython's heap output differs. Probe `/tmp/rprobes/p_lt_only.py`:
   ```python
   import heapq
   class Item:
       def __init__(self, name, rank): self.name, self.rank = name, rank
       def __lt__(self, other): return self.rank < other.rank
       def __repr__(self): return self.name
   def main():
       a = [Item("a", 1), Item("b", 1)]
       b = [Item("c", 1), Item("d", 1)]
       print(list(heapq.merge(a, b)))
       print(list(heapq.merge(a, b, reverse=True)))
   main()
   ```
   Expected `[c, a, d, b]` twice; actual `[a, b, c, d]` twice (both builds). `p_nan.py` is the same issue (`[nan, nan, 1.0, 2.0]` vs `[nan, 1.0, nan, 2.0]`). Matching CPython here likely needs its heap algorithm, not just the comparator; the worker's 2500-case test uses only int keys and misses it.

**Pre-existing.** None found; base refuses `heapq.merge` by name, so the differences above are introduced by this change.

**Tests run.** `python3 ../tools/par_check.py -j 2 test_ail_std_heapq test_ail_genlib test_ail_safetynet` → 3 modules, 0 failed. `tools/update_manifest.py --check` → exit 0. `term_rank` (a heapq-using lab/compare task) generated `program.c` is byte-identical to base; only temp paths in `native_report.json` differ.

**Report claims.** 12 programs / 25–45 lines each: verified. 11 build (median_stream typed, merge_logs general): verified. All built programs match CPython in both IR modes: verified by `test_ail_std_heapq`. Merge implemented via genlib/prelude: verified, with defects 1–2. `merge_k_lists.py` refused for `heapq.merge(*rows)`, RESULTS text matches first refusal: verified. Worker probes `hq_merge_*`: re-ran, all same stdout. Tests/registration/manifest/DEVLOG/commit: verified.

**Unverified.** `test_ail_heapq_bisect`, `test_ail_files`, `test_ail_corpus_findings3` were not rerun (reviewer scope); 9 of 10 lab/compare C files not checked; no speed measurement.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1486173, "input": 28499, "output": 7719, "reasoning": 28899, "cache.write": 0, "cache.read": 1421056}]
    tool time: bash 5.6 min
        196s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_std_heap
         65s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/dd_head /tmp/dd_base && AIL_NO_CACHE=1 python3 AIL_CURRENT/a
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p_*.py; do echo "########## $f"; bash ~/tools/cmp.
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/hq_merge_*.py; do echo "##### $(basename $f)"; bash
          9s bash   cat > /tmp/rprobes/p_lt_only.py <<'PY' import heapq  class Item:     def __init__(self, name, rank):         s
          3s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12 && python3 - <<'PY' import sys, random, heapq sy
          3s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/mlx && AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py comp
          2s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p_keyraise.py /tmp/rprobes/p_nan.py; do echo "####

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed both merge defects in `prelude_genlib.py`: ported CPython's heap algorithm/list comparison (identity-aware tie-break) and the single-stream fast path so `key` is not called after one stream remains.

- Probes: 8 (7 reviewer + `p_merge_edges`) — all match CPython on both builds.
- Tests on final commit `0d0745c`: 6 modules, 0 failed (`test_ail_genlib`, `test_ail_std_heapq`, `test_ail_heapq_bisect`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`).
- `tools/update_manifest.py --check` → exit 0.
- No compiler/lab/compare sources changed; no `heapq.merge` usage in lab/compare, so their generated C is unaffected.
[cost $0.0287, opencode tokens {"total": 1662422, "input": 58402, "output": 10634, "reasoning": 14634, "cache.write": 0, "cache.read": 1578752}]
    tool time: bash 13.9 min, edit 0.0 min
        381s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_genlib t
        360s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_genlib t
         43s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/p_keyraise.py /tmp/rprobes/p_keycalls.py /tmp/rpro
         37s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p_keyraise p_keycalls p_lt_only p_nan p_tie p_mutate p_routes; 
          6s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/p_merge_edges.py $PWD
          6s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p_merge_edges.py <<'PY' import heapq  class Box:     def __init__(se
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12 && python3 - <<'PY' import sys, random, heapq sy

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds `heapq.merge` to the general path (`genlib.py:66`, `prelude_genlib.py:689-805`): a faithful port of CPython 3.12's `merge` heap algorithm (identity-aware list comparison, min/max siftup/siftdown/heapify/heapreplace/heappop, single-stream fast path), plus 12 lab programs, `test_ail_std_heapq.py`, and a 2500-case `test_ail_genlib` comparison.

**Probes** (`cmp.sh`; g=general, d=default; all matched CPython stdout/exit on both builds):
- `q_identity_nan`, `q_identity_custom`, `q_key_identity` — same/distinct NaN, `__lt__`-only, `__eq__`-false, shared key object.
- `q_key_side_effects`, `q_errors` — key call order, key raising after one stream remains, non-callable key, non-iterable, `reverse=0`.
- `q_mutate`, `q_alias` — append/mutate source list during iteration, mutate yielded list, mutate dict/list after copy.
- `q_routes`, `q_from_alias`, `q_generator_streams`, `q_types2` — argument/list-item/attribute/dict routes, from-import/alias, generators, infinite and aliased iterators, strings/bytes/floats/bools/int64.
- `p_merge_edges` (worker's probe) — same on g/d.
- Pure-Python differential: 26 adversarial cases (`_ail_merge` vs `heapq.merge`) — all match.
- `q_types` with `key=str.lower` is refused by name (`name 'str' is not defined`); `sorted(key=str.lower)` works on base and HEAD. Named refusal, acceptable, not an algorithm error.

**Tests.** `par_check.py -j 2 test_ail_std_heapq test_ail_genlib test_ail_safetynet` → 3 modules, 0 failed. `test_ail_heapq_bisect test_ail_files test_ail_corpus_findings3` → 3 modules, 0 failed. `update_manifest.py --check` → exit 0.

**Byte-identical C.** `term_rank`, `berth_sim`, `rail_transfer` (`--exact-int`) generated `program.c` are identical to `/tmp/base`; `g12_038` (a gdev heapq user) is identical too. The other seven lab/compare tasks do not import `heapq`, and the diff adds no other library name, so their C is unaffected.

**Claims.**
- Heap algorithm/list comparison + single-stream fast path: **verified**.
- 8 probes match CPython on both builds: **verified** (`p_merge_edges` + independent probes).
- 6 test modules pass on `0d0745c`: **verified**.
- `update_manifest.py --check` exits 0: **verified**.
- “No compiler/lab/compare sources changed”: **false as worded** (`genlib.py` and `prelude_genlib.py`, the general-path compiler/prelude, changed); the substantive part, that no lab/compare source changed and their generated C is unaffected, is **verified**.

**Pre-existing.** `rail_transfer` without `--exact-int` is refused for an int64 constant overflow on both base and HEAD; not caused by this change.

**Unverified.** The other seven non-heapq lab/compare tasks were not compiled individually (provably unaffected); no instruction-count measurement (no gdev program uses `heapq.merge`, and C is identical for heapq users).

VERDICT: ACCEPT
[cost $0.0558, opencode tokens {"total": 3998603, "input": 64444, "output": 13199, "reasoning": 44224, "cache.write": 0, "cache.read": 3876736}]
    tool time: bash 11.3 min
        102s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ddhead1 /tmp/term_head && time AIL_NO_CACHE=1 python3 AIL_CU
         90s bash   sleep 90; cat /tmp/compare_c.log 2>/dev/null; echo ===; ps -eo pid,etimes,cmd | grep -E "compare_c|ail_chatgpt
         60s bash   sleep 60; cat /tmp/review_tests2.log; echo ===; ps -eo pid,etimes,cmd | grep -E "48207|par_check" | grep -v gr
         60s bash   sleep 60; cat /tmp/compare_c.log 2>/dev/null; echo ===; ps -eo pid,etimes,cmd | grep -E "compare_c|ail_chatgpt
         60s bash   sleep 60; tail -5 /tmp/review_tests.log; ps -eo pid,etimes,cmd | grep -E "43392|par_check" | grep -v grep | he
         60s bash   sleep 60; cat /tmp/review_tests2.log; echo ===; ps -eo pid,etimes,cmd | grep -E "48207|par_check" | grep -v gr
         60s bash   sleep 60; cat /tmp/compare_c_gdev.log 2>/dev/null; echo ===; ps -eo pid,etimes,cmd | grep -E "54151|g12_038|gc
         60s bash   sleep 60; cat /tmp/review_tests2.log; echo ===; ps -eo pid,etimes,cmd | grep -E "48207|par_check" | grep -v gr

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T08:11:25Z
