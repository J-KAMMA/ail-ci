# job job-prog13-11021400  started 2026-11-02T05:04:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects:

1. **Unknown receiver skip** — `call_skip` now uses the call's argument binding to choose bound vs explicit-receiver form; ambiguous calls are refused by name.
2. **Shadowed class names** — `_name_tags` now consults parameter/local/module bindings before treating a name as its class, including unannotated parameters.
3. **Class-body Optional calls** — module-level refusal now extends recursively to class bodies (including nested classes).

Verification on final commit `e6c9e86`:
- 10 regression probes match CPython on both builds (`p1`, `p2` local/module, `p3`, plus ambiguity/shadowing/aliasing/null/negative cases).
- 11 test modules pass with `-j 2`, including `test_ail_prog13`, `test_ail_safetynet`, `test_ail_files`, and `test_ail_corpus_findings3`.
- `python3 tools/update_manifest.py --check` passes.
- Added P9/P10 regression tests and DEVLOG/report updates.
[cost $0.0000, opencode tokens {"total": 2727700, "input": 77906, "output": 10608, "reasoning": 21074, "cache.write": 0, "cache.read": 2618112}]
    tool time: bash 12.1 min
        422s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 test_ail_prog13 tes
        145s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 1800 python3 tools/par_check.py -j 2 test_ail_optional_l
         38s bash   cd /tmp/probes && for f in p1_this_unknown p2_local_shadow p2_module_shadow p3_classbody x2_ambiguous_refused 
         30s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p = Path('AIL_CURRENT/test_ail
         25s bash   cd /tmp/probes && cat > x1_unbound_unknown.py <<'PY' class C:     def __init__(self, n: int) -> None: self.n =
         20s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 -m unittest -v test_ail_prog13 
         14s bash   cd /tmp/probes && for f in p1_this_unknown p2_local_shadow p2_module_shadow p3_classbody; do echo "##### $f"; 
          8s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p1_this_unknown.py <<'PY' class C:     def __init__(this, n: i

## review 0
[model opencode/deepseek-v4.1-flash-free]
## review 2

**What the diff really does.** It changes only the compile-time Optional lowering in `AIL_CURRENT/python/pkg-v12/optlib.py`: (a) an unannotated parameter now records a binding so it shadows a class name, and a bare name is classified as a class only when no binding/loop in its scope shadows it; (b) `call_skip` now chooses the receiver skip from the call's own argument binding when the receiver is not statically known, refusing ambiguous calls by name; (c) `check_outside` is factored out and recursed into class bodies (and re-applied to each class body). Tests/docs/DEVLOG/manifest are updated. This matches the report.

**Review defects checked (all fixed on HEAD; base reproduces each).**
1. Non-`self` first parameter, unknown receiver: `p1_this_unknown` → `7` on both builds; base both fail.
2. Shadowed class name / `dict.get`: `p2_local_shadow`, `p3_module_shadow`, `p13_shadow_annotated` → `10/None` on HEAD; base crashes/diffs.
3. Class-body Optional calls: `p4_class_body_call` (`4`), `p5_class_body_func` (`7`), `p18_classbody_list` → match on HEAD; base fails to build.

**Other probes (HEAD both builds unless noted).** `p6` (self, unknown recv), `p8` (keyword non-self), `p9` (default `this`), `p10` list item, `p11` dict value, `p12` attribute — all match; all four receiver forms fail on base. `p14` (both binding forms fit) refused → general path → matches. `p15` unbound `C.take(C(9),2)` matches. `p16` feature-free: matches and `--debug-dir` `program.c` byte-identical to base. `p17`/`p19` (class-body defaults) match both. `p21` module rebind to instance matches both. `p22` local rebind exit 1 matches base.
Pre-existing: `p7_extra_args` and `p20_self_kw` are refused by name on HEAD and base alike (not caused by this change).

**Claims.** Unknown-receiver skip — verified. Shadowed names — verified. Class-body recursion — verified. Exact 10 probe files — unverified (not in tree); independent probes agree. `update_manifest.py --check` — verified exit 0. Generated C: all 8 target programs byte-identical HEAD vs base (`g12_026` still typed), and `lab/compare/src/tree_fold/main.ail` `program.c` identical; no speed-relevant C changed. P9/P10 added and passing. “11 test modules” — only the two required re-ran: `test_ail_prog13`, `test_ail_safetynet` pass; other 9 unverified.

**Unverified.** The other 9 test modules; the worker's `/tmp/probes` files; prior review's three carried pre-existing programs.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1183631, "input": 314802, "output": 8297, "reasoning": 17652, "cache.write": 0, "cache.read": 842880}]
    tool time: bash 6.3 min
        173s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         53s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/hlog && mkdir -p /tmp/hlog && date && for f in /tmp/rprobes/
         46s bash   cd /home/runner/work/ail-ci/ail-ci && for f in lab/corpus/programs/deepseek-v4.1-flash-free/t140.py lab/census
         29s bash   cd /tmp && for f in /tmp/rprobes/p*.py; do b=$(basename $f .py); bash ~/tools/cmp.sh $f /tmp/base > /tmp/hlog/
         27s bash   cd /home/runner/work/ail-ci/ail-ci && date && ls /tmp/rprobes/p*.py | xargs -P2 -I{} bash -c 'echo "##### {}";
         19s bash   cd /tmp/rprobes cat > p17_classbody_default.py <<'PY' def f(k: int | None) -> int | None:     if k is None: re
         15s bash   cd /tmp/rprobes cat > p21_module_instance.py <<'PY' class Cache:     def get(self, k: int | None) -> int | Non
         10s bash   cd /tmp && rm -rf cch ccb && AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /home/runner/work/ail-ci/ail-ci/AIL_C

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T06:47:42Z
