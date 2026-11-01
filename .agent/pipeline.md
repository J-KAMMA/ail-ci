# job job-cls1-11020605  started 2026-11-01T21:06:01Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed on `job-cls1-11020605`.

**Changes**
- `object` now settles `isinstance(x, (...))` unconditionally, regardless of tuple order, so `(A, object)` / `(object, A)` match `None`, self and ancestors.
- Shadowed class/builtin names are no longer folded: `issubclass` refuses by name when the call or either operand is a parameter/local. The analogous `isinstance` target shadowing now also refuses by name on typed and general paths.
- Added 3 regression tests (9 total in `test_ail_class_reach`), updated `CLASS_REACH.md`, `DEVLOG.md`, and manifest pins.

**Verification**
- Probes: 10/10 default builds match CPython or are refused by name (`objancestor`, `objorder`, `objpaths`, `objshadow_*`, `isinst_shadow_*`).
- Tests: 7 required modules pass, 0 failed (`test_ail_class_reach`, `typed_inherit`, `virtual_dispatch`, `safetynet`, `files`, `corpus_findings3`, `builtin_shadowing`).
- lab/compare: 10/10 `main.ail` generated C byte-identical to HEAD; 5/5 buildable `main.py` identical, 5 refuse identically on both sides.
- `python3 tools/update_manifest.py --check` exits 0.

Commits: `16c6821`, `ccc901f`.
[cost $0.0000, opencode tokens {"total": 8747570, "input": 148887, "output": 20754, "reasoning": 22921, "cache.write": 0, "cache.read": 8555008}]
    tool time: bash 33.2 min, edit 0.0 min, read 0.0 min
        502s bash   cat > /tmp/cmp_c.sh <<'SH' set -u ROOT=/home/runner/work/ail-ci/ail-ci BASE=/tmp/base/AIL_CURRENT OUT=/tmp/cmp
        500s bash   timeout 2400 python3 tools/par_check.py -j 2 test_ail_class_reach test_ail_typed_inherit test_ail_virtual_disp
        498s bash   bash /tmp/cmp_c.sh 2>&1 | tail -25
        379s bash   timeout 2400 python3 tools/par_check.py -j 2 test_ail_class_reach test_ail_typed_inherit test_ail_virtual_disp
         18s bash   for p in /tmp/probes/objancestor.py /tmp/probes/objorder.py /tmp/probes/objpaths.py /tmp/probes/objshadow_cls.
         12s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_class_reach 2>&1 | tail -5; cd .. && python3 to
         12s bash   for p in /tmp/probes/objancestor.py /tmp/probes/objorder.py /tmp/probes/objpaths.py /tmp/probes/objshadow_cls.
         11s bash   cd AIL_CURRENT && timeout 1200 python3 -m unittest -q test_ail_class_reach 2>&1 | tail -20

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `work..HEAD` (`16c6821` + `ccc901f`)

**What the change really does:** makes a typed `isinstance(x, (...))` with an `object` target settle unconditionally regardless of tuple order, and adds local-binding shadow detection to static `issubclass` folding and to both `isinstance` emitters; adds tests/docs/manifest pins.

**Verified**
- Both named review defects are fixed: `/tmp/probes/objancestor.py` and `objorder.py` default build matches CPython; `/tmp/probes/objshadow_cls/local/left/builtin.py` and `isinst_shadow_*` all refuse by name on both paths.
- All 10 worker probes behave as reported (match CPython or named refusal).
- 7 modules pass on HEAD, 0 failed: `test_ail_class_reach`, `typed_inherit`, `virtual_dispatch`, `safetynet`, `files`, `corpus_findings3`, `builtin_shadowing`.
- All 10 lab/compare `main.ail` generated C is byte-identical to base; the 5 buildable `main.py` are identical and the other 5 refuse identically.
- `python3 tools/update_manifest.py --check` exits 0; 9 tests exist in `test_ail_class_reach`.
- No new wrong output or crash found. Several pre-existing silent answers (lambda/method/`*args`/`**kwargs` shadows) are now named refusals.

**Pre-existing (identical on base, not blocking)**
- `/tmp/rprobes/nested_shadow.py`, `closure_shadow.py`: CPython raises `TypeError`, exit 1; base and HEAD default builds print `True`, exit 0 (nested/closure `isinstance` target shadow).
- `/tmp/rprobes/modshadow_cls.py`, `modshadow_left.py`, `isinst_modshadow.py`: module-level class-name reassignment; CPython raises `TypeError`, exit 1; base and HEAD print answers, exit 0.

**Report claims**
- `object` unconditional: verified for mixed class/object tuples; object-only or non-class tuples are refused by name.
- Shadowed `issubclass` operands/call: verified for top-level and nested parameters/locals; refused by name.
- Analogous `isinstance` shadowing: verified for top-level, lambda and method targets on both paths; false as a universal claim because nested/closure cases still fold silently — but those are pre-existing.
- Tests/manifest/lab-compare claims: verified.

**Unverified:** speed (no runtime hot-path change expected); exact h17/h26 pre-existing differences not rechecked.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2587157, "input": 47740, "output": 11323, "reasoning": 32862, "cache.write": 0, "cache.read": 2495232}]
    tool time: bash 13.9 min
        573s bash   sed 's#BASE=/tmp/base/AIL_CURRENT#BASE=/tmp/basewt/AIL_CURRENT#; s#OUT=/tmp/cmpc#OUT=/tmp/cmpc2#' /tmp/cmp_c.s
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && (timeout 2400 python3 ../tools/par_check.py -j 2 tes
         12s bash   cd /tmp/rprobes && cat > userobject3.py <<'PY' class object:     pass class A:     def __init__(self) -> None:
         12s bash   cd /tmp/rprobes && for p in nested_shadow closure_shadow nonlocal_shadow lambda_shadow method_shadow2; do echo
         12s bash   cd /tmp/probes && for p in objancestor objorder objpaths objshadow_cls objshadow_local objshadow_left objshado
         10s bash   cd /tmp/rprobes && for p in userobject isinst_shadow_param isinst_shadow_object isinst_modshadow shadow_func; 
         10s bash   cd /tmp/rprobes && for p in vararg_shadow kwarg_shadow issub_order; do echo "===== $p BASE ====="; timeout 200
          9s bash   cd /tmp/rprobes && cat > lambda_shadow.py <<'PY' class A:     def __init__(self) -> None: self.x = 1 class B(A

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T23:25:42Z
