# job job-pre86-10242022  started 2026-10-24T11:33:19Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":724,"duration_api_ms":597,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":769,"duration_api_ms":644,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
​Fixed difference #1: `permutations(xs, None)` now yields the full permutations on both builds.

- Cause: the general path read boxed `r` with `(r).i`, turning `None` into `r=0`.
- Fix: evaluate `r` once, test its tag at run time; `None` means `r=len(pool)`, int/bool is respected, other types raise CPython 3.12’s `TypeError: Expected int as r`. `cruntime.py` was left unchanged.
- Added `test_ail_pre86.py` (5 tests, both builds), registered it, added DEVLOG/DIFFERENCES rows.

Probes, all matching CPython on both builds:
`p86_perm_none`, `p86_perm_none_int`, `p86_perm_none_routes` (argument, call, list item, attribute, dict value, keyword, alias), `p86_perm_none_bounds_loop` (`None,0,1,2,3` over empty/1/2-element pools), `p86_perm_none_types` (bool and bad types), `p86_perm_none_typed_arg`.

Required tests on final commit: `test_ail_pre86`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (261 s). `update_manifest.py --check` passes.

Commit: `98fdbd9`. Pre-existing items observed but not changed: positive literal `list(permutations(...))` still invalid C on the default build (#2); negative `r=-1` on the general path still returns `[]` instead of `ValueError` (open fuzz8 row).
[cost $0.0000, opencode tokens {"total": 6173078, "input": 116383, "output": 14750, "reasoning": 22874, "cache.write": 0, "cache.read": 6019071}]
    tool time: bash 6.8 min, edit 0.0 min
        263s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_pre86 test_ail_safetynet test_a
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p86_perm_none p86_perm_none_int p86_perm_none_routes p86_perm_n
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && cat > test_ail_pre86.py <<'EOF' """pre86: itertools.permutat
         19s bash   cat > /tmp/probes/p86_perm_none_routes.py <<'EOF' from itertools import permutations  class Box:     def __ini
         19s bash   for p in p86_perm_none p86_perm_none_int p86_perm_none_routes p86_perm_none_types p86_perm_none_negative; do e
          9s bash   bash ~/tools/cmp.sh /tmp/probes/p86_perm_none_int.py "$PWD" && bash ~/tools/cmp.sh /tmp/probes/p86_perm_none.p
          9s bash   bash ~/tools/cmp.sh /tmp/probes/p86_perm_none_int.py "$PWD" && bash ~/tools/cmp.sh /tmp/probes/p86_perm_none.p
          8s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p86_perm_none.py <<'EOF' from itertools import permutations print(li

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed commit `98fdbd9` against `work`; base at `/tmp/base` (e9f3bee).

**What the change really does:** in `_lib_permutations` (pyboxed2.py:7104) it evaluates a supplied `r` once into a temp, emits a run-time tag check (None/int/bool allowed, else `TypeError: Expected int as r`), then passes a computed `has_r` flag plus `rv.i` to the unchanged `ail_it_permutations`. Adds `test_ail_pre86.py`, DEVLOG, a DIFFERENCES row and MANIFEST hashes. This matches the report except that "passes the boxed r" and "runtime helper treats None as r=len(pool)" are inaccurate: the helper is unchanged and receives `has_r`/`.i`, not the boxed value.

**Probes (HEAD `g`+`d`, base compared.)**
- `r1_none` (literal/keyword None, empty/1/3 elts): base differs, HEAD matches CPython both builds.
- `r2_routes` (argument, call, list item, attribute, dict value, keyword, twice): HEAD matches both builds.
- `r7_none_dict` (dict xs/r): HEAD matches.
- `r13_global` (global/tuple/class attribute None, None inside function): HEAD matches.
- `r4_side` (r evaluated exactly once; TypeError caught): HEAD matches.
- `r3_types` (True/False, 0/2/3, -1, 1.5, "2", [2], `__index__`): HEAD matches CPython except `r=-1` (pre-existing). Bad types now correctly raise `Expected int as r`.
- `r5_unpack` / `r11_typed` / `r12_typed_lit` (unpacking, typed path, literal r): match.
- `r8_plain` (no itertools): generated `program.c` identical HEAD/base on both builds.
- `r9_comb` (combinations): general C identical; default build fails identically on base (pre-existing #2).
- `r6_nochange`/positive-literal default build: same invalid C on base (pre-existing #2).

**Claims:** fixed #1 verified; cause verified; type handling verified; cruntime unchanged verified; test added/registered verified; `test_ail_pre86`+`test_ail_safetynet` pass (0 failed, 102s); `update_manifest.py --check` rc=0. Not rerun per rule: `test_ail_files`, `test_ail_corpus_findings3`; ASan/icount not run.

**Pre-existing (identical on base):** positive positive-literal `list(permutations(...))` invalid C on default build (#2); `r=-1` returns `[]` instead of `ValueError`; `r=10**10` behavior (#3).

**Defect introduced:** the eager tag check runs before the iterable is materialized, so a non-iterable pool combined with a bad `r` reports the wrong error. Base matched CPython here.

VERDICT: FIX

1. `permutations(<non-iterable>, <bad r>)` reports `Expected int as r` instead of the iterable error. Probe `/tmp/rprobes/r14_order_min.py`:
   ```python
   from itertools import permutations
   try:
       permutations(5, "x")
   except TypeError as e:
       print(e)
   ```
   Expected (CPython and base, both builds): `'int' object is not iterable`
   Actual HEAD (both `g` and `d`): `Expected int as r`
   Same in `/tmp/rprobes/r10_order.py` (`permutations(badit(), badr())`). Fix by materializing the iterable before validating `r` (or move the tag handling into `ail_it_permutations` after `ail__materialize`).
[cost $0.0000, opencode tokens {"total": 930365, "input": 42220, "output": 7268, "reasoning": 13165, "cache.write": 0, "cache.read": 867712}]
    tool time: bash 3.9 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre86 te
         39s bash   cd /tmp/rprobes && cat > r3_types.py <<'EOF' from itertools import permutations for v in (True, False, 2, 0, 3
         24s bash   cd /tmp/rprobes && sed -i 's/^from itertools import combinations, combinations_with_replacement/from itertools
         13s bash   cd /tmp/rprobes && echo "=== HEAD r3 diff"; bash ~/tools/cmp.sh /tmp/rprobes/r3_types.py /home/runner/work/ail
         11s bash   cd /tmp/rprobes && cat > r11_typed.py <<'EOF' from itertools import permutations def count(xs: list, k: int) -
          7s bash   cd /tmp/rprobes && echo "=== HEAD r10"; bash ~/tools/cmp.sh r10_order.py /home/runner/work/ail-ci/ail-ci 2>&1 
          7s bash   cd /tmp/rprobes && cat > r10_order.py <<'EOF' from itertools import permutations def it():     print("iter")  
          7s bash   for m in g d; do echo "-- $m program.c"; diff /tmp/dbg_base_$m/program.c /tmp/dbg_head_$m/program.c | head -10

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer's defect and committed as `086b31f`.

**Change:** moved the `r` tag validation into `ail_it_permutations` after `ail__materialize`, rooted the boxed `r`, and forced the iterable expression into a temp so argument order matches CPython. `permutations(5, "x")` now reports `'int' object is not iterable` on both builds.

**Probes** (both builds):
- Reviewer `r1`–`r14`: all match except pre-existing `r=-1` (`[]` vs `ValueError`) in `r3_types`; `r6`/`r9` default build still fails on the pre-existing positive-literal compile bug.
- New `/tmp/probes`: `p86_perm_order`, `p86_perm_badpool`, `p86_perm_routes_badr`, `p86_perm_none`, `p86_perm_none_bounds_loop`, `p86_perm_none_int`, `p86_perm_none_routes`, `p86_perm_none_typed`, `p86_perm_none_types` all match both builds.
- Pre-existing only: `p86_perm_none_negative` (negative `r`), `p86_perm_none_bounds` / `p86_perm_posvar` (default-build positive-literal compile failure).

**Tests on final commit:** `test_ail_pre86`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (203s). `update_manifest.py --check` rc=0.
[cost $0.0000, opencode tokens {"total": 1392995, "input": 107363, "output": 7313, "reasoning": 9327, "cache.write": 0, "cache.read": 1268992}]
    tool time: bash 9.1 min, edit 0.0 min
        204s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre86 test_ail_safetynet test_ail_files test_ail
        204s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre86 test_ail_safetynet test_ail_files test_ail
         52s bash   cd /tmp/rprobes && for f in r1_none.py r2_routes.py r3_types.py r4_side.py r5_unpack.py r6_nochange.py r7_none
         52s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p86_perm_badpool.py') s=p.read_text().replace(',
         14s bash   cd /tmp/rprobes && for f in r10_order.py r14_order_min.py; do echo "=== $f HEAD"; bash ~/tools/cmp.sh "$f" /ho
         11s bash   cat > /tmp/probes/p86_perm_routes_badr.py <<'EOF' from itertools import permutations  class Box:     def __ini
          3s bash   cd /tmp/rprobes && out=$(bash ~/tools/cmp.sh r3_types.py /home/runner/work/ail-ci/ail-ci 2>&1); echo "$out" | 
          2s bash   cd /tmp/probes && bash ~/tools/cmp.sh p86_perm_none_negative.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -1

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** `_lib_permutations` now evaluates the iterable expression into a temp, evaluates `r` into a temp, and passes the boxed `r` to `ail_it_permutations`; the helper materialises the pool first, then treats tag NONE as `r=len(pool)`, INT/BOOL as `r`, else raises `TypeError: Expected int as r`. It adds `test_ail_pre86.py`, DEVLOG rows, a DIFFERENCES row and MANIFEST hashes.

**Probes (HEAD `g`+`d`, base compared)**
- `v86_none_routes`: HEAD matches CPython both builds; base returns `[()]`. Fix confirmed.
- `v86_types`: HEAD matches except pre-existing `r=-1` (`[]` vs `ValueError`); base also fails on floats/strings/lists.
- `v86_order`: HEAD matches; base returns `[()]`.
- `v86_mutate`: HEAD matches; base returns `[()]`.
- `v86_index` (`__index__` objects): HEAD matches CPython (`Expected int as r`); base returns `[]`.
- `v86_poslit`: general matches; default build has the same invalid C on base (pre-existing #2).
- `v86_argmut`, `v86_argmut2`: HEAD and base match CPython.
- `v86_nofeature`: `--debug-dir` C differs only in the embedded `ail_it_permutations` runtime helper; generated user code is identical.

**Tests:** `test_ail_pre86`, `test_ail_safetynet` pass (102s, 0 failed). `update_manifest.py --check` rc=0. Not rerun per rule: `test_ail_files`, `test_ail_corpus_findings3`.

**Claims:** fix at `086b31f`, the moved validation, the CPython error precedence, and `permutations(5, "x")` matching CPython are verified. The worker's new `/tmp/probes` were not run; `test_ail_files`/`test_ail_corpus_findings3` are unverified. The report omits one issue in the change.

**Pre-existing (identical on base):** `r=-1` returns `[]`; positive literal `list(permutations(...))` emits invalid C on the default build.

VERDICT: FIX

1. `ail_it_permutations` registers `pr_[0]` as a GC root before `ail__materialize` writes it (`cruntime.py:20122-20125`). `AIL_ROOT_N` explicitly requires initialized slots; here `pr_[0]` is uninitialised stack while the collector may run inside `ail__materialize`.
   Probe `/tmp/rprobes/v86_stress.py`:
   ```python
   from itertools import permutations

   print(list(permutations([1, 2, 3], None)))
   print(list(permutations([1, 2])))
   ```
   Build the generated C with `--debug-dir`, then compile with `clang -O0 -g -fsanitize=memory -fno-omit-frame-pointer -DAIL_GC_STRESS`.
   Expected: same output as CPython, no sanitizer report (base does this, exit 0).
   Actual HEAD: exit 86, `MemorySanitizer: use-of-uninitialized-value` in `ail_gc_mark_value`, called from `ail_gc_collect` → `ail_gc_maybe_collect` → `ail_gc_alloc` → `ail_iter` → `ail__materialize` → `ail_it_permutations`.
   Fix: initialise `pr_[0] = ail_box_none();` before `AIL_ROOT_N` (or root `rbox` separately with `AIL_ROOT1`).
[cost $0.0000, opencode tokens {"total": 3414092, "input": 93132, "output": 10585, "reasoning": 38055, "cache.write": 0, "cache.read": 3272320}]
    tool time: bash 4.6 min, edit 0.0 min, write 0.0 min, read 0.0 min
        104s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre86 test
         21s bash   date; python3 /tmp/v86var_driver.py 2>&1 | tail -30
         20s bash   date; cd /tmp/rprobes; for f in v86_none_routes v86_types v86_order v86_mutate; do echo "######## $f BASE"; ba
         15s bash   date; cd /tmp/rprobes; for f in v86_none_routes v86_types v86_order v86_mutate; do echo "######## $f HEAD"; ba
         11s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 -m unittest test_ail_gcstress.GCSt
         11s bash   date; cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "######## v86_big $wt"; ti
         10s bash   date; cd /tmp && rm -rf dbg_head dbg_base; mkdir -p dbg_head dbg_base; cd /tmp/rprobes; for wt in /home/runner
         10s bash   date; cd /tmp/rprobes; for f in r3_types r6_nochange; do echo "######## $f BASE"; bash ~/tools/cmp.sh $f.py /t

FINAL VERDICT: FIX  2026-10-24T12:20:00Z
