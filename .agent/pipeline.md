# job job-pre64-10241803  started 2026-10-24T09:07:26Z  worker=oc reviewer=oc (GitHub)
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
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `19891cf` on `job-pre64-10241803`.

The task file contained no difference list beyond the `p16` bare-annotation note, so I reproduced that: a module-level bare annotation (`x: note(...)`) was not evaluated, losing call side effects. Module-level whole-call annotations now run as CPython does; class-body calls and calls nested in larger annotations are refused by name. Function-local and `from __future__ import annotations` behaviour is unchanged.

- Fix: `AIL_CURRENT/ail_syntax.py`; new `AIL_CURRENT/test_ail_pre64.py`
- Tests: `test_ail_pre64`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — **4 modules, 0 failed** (264 s)
- Manifest `--check` and `ci_shards.py --check` pass
- Probes: 13 matched CPython on both builds (`bare_ann_side_module/attr/sub`, `bare_ann_routes`, `bare_ann_side_local`, `bare_ann_function_call_local`, `bare_ann_future_module/class/attr`, `bare_ann_list`, `bare_module_multi`, `bare_local_read`, `bare_local_after_assign`)
- Refused by name on both builds: `bare_class_side`, `bare_ann_nested_call`
- Not run: gdev instruction counts (compile-time-only change).
[cost $0.0000, opencode tokens {"total": 5452766, "input": 155052, "output": 13471, "reasoning": 30483, "cache.write": 0, "cache.read": 5253760}]
    tool time: bash 16.8 min, edit 0.0 min
        342s bash   python3 tools/par_check.py -j 2 test_ail_pre64 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        266s bash   python3 tools/par_check.py -j 2 test_ail_pre64 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         53s bash   for p in bare_ann_side_module.py bare_ann_side_attr.py bare_ann_side_sub.py bare_ann_routes.py bare_ann_side_l
         52s bash   for p in bare_ann_side_module.py bare_ann_side_attr.py bare_ann_side_sub.py bare_ann_routes.py bare_ann_side_l
         46s bash   cat > /tmp/probes/bare_ann_nested_call.py <<'PY' def note():     print('eval')     return int x: note() | int 
         42s bash   mkdir -p /tmp/probes && cat > /tmp/probes/bare_module_read.py <<'PY' x: int try:     print(x) except Exception
         29s bash   cat > /tmp/probes/bare_annotations_module.py <<'PY' x: int print(__annotations__) PY cat > /tmp/probes/bare_an
         29s bash   for n in int float str bool bytes list dict; do printf '%s\nprint("after")\n' "$n" > /tmp/probes/ann_expr_$n.p

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the diff really does:** Adds a `future_annotations` flag and, in `ann_assign`, turns a module-level bare annotation whose whole expression is a `Call` into that call as an expression statement; class-body calls and calls nested in larger annotations raise `SyntaxErrorAIL`.

**Claims**
- Module-level whole-call annotations run as CPython does — **false for attribute/subscript targets**: CPython also evaluates the target's value/slice subexpressions; the new code runs only the annotation.
- Class-body/nested calls refused by name — verified (both builds).
- Function-local and `from __future__ import annotations` unchanged — verified.
- Listed probes matched — verified for the files run (`bare_ann_side_module/attr/sub`, `bare_ann_routes`, `bare_ann_list`, `bare_ann_future_*`, `bare_module_multi`); their attr/sub probes use side-effect-free targets, so they miss the defect.
- Tests: `test_ail_pre64` ok 4.5s, `test_ail_safetynet` ok 128s, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass. C for a no-annotation program is byte-identical to base.

**Defect (caused by the change)**
1. Module-level bare annotation with an attribute/subscript target does not evaluate the target subexpressions, so the annotation sees stale state or names never bound.
   - `u_order_sub.py`:
     ```
     state={'x':0}
     def note(v): print('note',v)
     def touch(): state['x']=5; return 0
     items=[10]
     items[touch()]: note(state['x'])
     print('after')
     ```
     CPython: `note 5` / `after`. HEAD (g and d): `note 0` / `after`. Base: only `after` (so the wrong value is new output, not pre-existing).
   - `q_attrobj.py`: `obj().value: note()` — CPython prints `obj`, `note`; HEAD prints only `note` (base printed neither).
   - `q_subobj.py`: `obj()[idx()]: note()` — CPython `obj`, `idx`, `note`; HEAD only `note`.
   - `u_walrus.py`: `(h := H()).v: note(h)` — CPython prints the note; HEAD now fails to build with `not in the subset: name 'h' is not defined` (base built).

Fix: either evaluate the target's value/slice subexpressions before the annotation, or refuse these targets by name too.

**Pre-existing (not blocking):** `__annotations__` access is refused; base also differs on these target-evaluation cases (it dropped both target and annotation).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1267114, "input": 96644, "output": 6939, "reasoning": 15627, "cache.write": 0, "cache.read": 1147904}]
    tool time: bash 7.1 min
        130s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ai
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_pre64 test_ail_
         38s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_ann p_ann2 p_attr p_sub p_subobj p_attrobj p_local p_future p
         35s bash   cd /home/runner/work/ail-ci/ail-ci && for p in q_ann q_local q_future q_if q_attrc q_attrobj q_subc q_subneg q
         25s bash   cd /tmp/rprobes && cat > u_order_sub.py <<'PY' state = {'x': 0} def note(v):     print('note', v) def touch():
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for p in bare_ann_global_write bare_ann_mod_call bare_ann_side_attr bare
         15s bash   cd /tmp/rprobes && cat > t_ret.py <<'PY' def note():     print('side')     return 5 x: note() print('after') P
         12s bash   cd /tmp/rprobes && cat > r_anns.py <<'PY' x: int y: str print(sorted(__annotations__.items())) PY cat > r_anns

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer defect: module-level whole-call bare annotations now evaluate the attribute target’s value, or the subscript target’s value/index/slice, before the annotation, matching CPython’s order.

Commit: `996a6e2`

Probes (both g and d builds via `cmp.sh`):
- `/tmp/probes/pre64_target_attr_order.py` — same stdout
- `/tmp/probes/pre64_target_sub_order.py` — same stdout (negative index + slice lo/hi/step)
- `/tmp/probes/pre64_target_mixed.py` — same stdout (walrus, object/index, list/dict/attribute values, negative/large/empty)
- `/tmp/probes/bare_ann_routes.py`, `bare_ann_side_*.py`, `bare_ann_future_*.py`, `bare_ann_function_*.py` — same stdout
- `/tmp/probes/bare_ann_nested_call.py` — refused by name (`bare annotation`)
- Reviewer probes `u_order_sub`, `u_order_attr`, `q_attrobj`, `q_subobj` — now same stdout; `u_walrus` now builds and prints the note in order, with only the pre-existing object-repr difference (`<H object>` vs `<__main__.H object at ...>`).

Tests on final commit with `-j 2`: `test_ail_pre64` 18.0s, `test_ail_files` 134.4s, `test_ail_corpus_findings3` 214.9s, `test_ail_safetynet` 129.2s — 4 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass.
[cost $0.0000, opencode tokens {"total": 1226159, "input": 51497, "output": 6343, "reasoning": 16063, "cache.write": 0, "cache.read": 1152256}]
    tool time: bash 7.0 min, edit 0.0 min, write 0.0 min
        266s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         61s bash   for p in u_order_sub u_order_attr u_walrus q_attrobj q_subobj q_attrc q_subc q_subneg p_attr p_attrobj p_sub p
         49s bash   for p in /tmp/probes/pre64_target_attr_order.py /tmp/probes/pre64_target_sub_order.py /tmp/probes/pre64_target
         21s bash   for p in u_order_sub u_order_attr u_walrus q_attrobj q_subobj; do echo "===== $p"; bash ~/tools/cmp.sh /tmp/rp
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre6
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre6
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && python3 tools/ci_shards.py -
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
Review complete.

**What the change really does.** In the source pass, a module-level bare `AnnAssign` whose annotation is a whole `Call` is replaced by one expression statement: for a Name target just the call; for an Attribute target the value expression then the call; for a Subscript target the value, index or slice parts, then the call. Class-body calls and any call nested inside a larger annotation raise `SyntaxErrorAIL` ("bare annotation ..."). This matches the report, with one hole (below).

**Claims checked**
- Module-level whole-call annotations and target order (attr, subscript, slice, negative, tuple index, walrus, object/index): verified on HEAD for supported forms (`r1,r3,r4,r8,r19,r20,r21,r28`), both g/d builds same stdout as CPython.
- Worker probes `pre64_target_attr_order/sub_order/mixed`: verified same stdout.
- Reviewer probes `u_order_sub/u_order_attr/q_attrobj/q_subobj/q_subneg/q_attrc/q_subc`: verified fixed (base differs). `u_walrus` verified, only known object-repr diff.
- `bare_ann_nested_call` and class-body call: verified refused by name.
- No-feature C unchanged: `--debug-dir` `program.c` byte-identical to base for an annotation-free program and a bare-annotation/no-call program.
- `test_ail_pre64` (17.5s) and `test_ail_safetynet` (121.5s) pass on HEAD; `update_manifest.py --check` and `ci_shards.py --check` pass. Worker's `test_ail_files`/`test_ail_corpus_findings3` runs not re-run (review rule: only added/edited modules + safetynet) — unverified.
- No gdev counts: source-pass-only change, no runtime/hot-path effect.

**Pre-existing (not blocking)**
- Function-local attribute/subscript bare annotations still do not evaluate target subexpressions, unlike CPython. `r2_attr`: CPython `after2 9`, base `0`, HEAD `7`. Same for `r14_future_target` (targets not evaluated under `future annotations`), identical on base.
- Multi-dimensional slice targets as *expressions* are already refused by AIL ("not in the subset: the Slice expression form"), on base and HEAD.

**Defect**
1. New ungraceful compile failure on subscript target whose slice is a tuple (or trailing comma). `bare_annotation_text` emits `ast.unparse(Tuple[Slice,...])`, e.g. `(g, 1:2, 3:4, note())`, which is invalid Python, so the compiler reports raw `invalid syntax` instead of a named refusal.
   Probe `/tmp/rprobes/r27_min.py`:
   ```python
   class Grid:
       def __getitem__(self, k):
           return 0
   def note(tag):
       print('note', tag)
   g = Grid()
   g[1:2, 3:4]: note('multi')
   print('after')
   ```
   Expected (CPython 3.12): `note multi` / `after`, exit 0. Actual HEAD: both builds fail with `p.ail:7:7: invalid syntax` (no executable); base builds and runs (already missing `note multi`, so the content difference is pre-existing, but the build failure is caused by this change). Same for `g[1:2,]: note('one-slice')` (`r23`) and `g[1:2, idx()]: note('multi')` (`r16`). Fix: spell tuple elements individually, handling `Slice`, or raise `SyntaxErrorAIL` naming the tuple-slice form.

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 2117810, "input": 67556, "output": 9284, "reasoning": 34826, "cache.write": 0, "cache.read": 2006144}]
    tool time: bash 8.8 min
        124s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1200 python3 tools/par_check.py -j 2 test_ail_pre64 test
         76s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/probes/bare_ann_*.py /tmp/probes/bare_annotation_*.py /tmp/p
         48s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/p_*.py; do echo "##### $(basename $p)"; bash ~/tools
         40s bash   cd /home/runner/work/ail-ci/ail-ci; for p in bare_ann_global_write bare_ann_mod_call bare_annotation_eval_loca
         40s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r1_basic r2_attr r3_sub r4_object r5_future r6_nocall r7_star r
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in u_order_sub u_order_attr u_walrus q_attrobj q_subobj q_subneg q
         32s bash   cd /tmp/base && for p in u_order_sub u_order_attr u_walrus q_attrobj q_subobj q_subneg q_attrc q_subc; do echo
         16s bash   ls /tmp/probes/ 2>/dev/null | grep -E 'pre64|bare_ann' ; cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/pro

FINAL VERDICT: FIX  2026-10-24T10:11:42Z
