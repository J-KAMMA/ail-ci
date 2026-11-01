# job job-covisin1-11020702  started 2026-11-01T22:02:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done and committed as `b95c44b`.

- Snapshot `isinstance` type constants at assignment; preserve forward-reference `NameError`.
- Follow module-rebound class names in constructor calls and static `isinstance`.
- Added 5 regression tests in `test_ail_covisin1.py` and a DEVLOG entry.
- Probes `p11`, `p8`, `p8b`, `p8c`, `p4`, `p5`, `p1e`, `p2`, `p6`, `p1f`, `p8e` match CPython on both builds.
- Targeted tests: `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 0 failed (284s).
- `update_manifest --check` passes. Remaining untracked `.agent/pipeline.md` was left untouched.
[cost $0.0000, opencode tokens {"total": 10723247, "input": 243715, "output": 27101, "reasoning": 51407, "cache.write": 0, "cache.read": 10401024}]
    tool time: bash 14.6 min
        384s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        286s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         29s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p11_attr_snapshot p8_rebind_class p8b_rebind_call p8c_rebind_is
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p11_attr_snapshot.py /tmp/probes/p8_rebind_class.py
         21s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_c
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p11_attr_snapshot.py /tmp/probes/p8_rebind_class.py
         20s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && cd AIL_CURRENT && timeout 1200 pytho
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p4_forward_alias.py /tmp/probes/p5_nested_forward.p

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Diff.** `tuplib._expand_isinstance_type_constants` now snapshots a module type constant into hidden `_ail_snap_*` names at its assignment (with `_ail_defined_*` markers for forward references) and treats builtin exception names as types; `pyboxed2._call_name`/`_static_isinstance_check` route any class name that also appears in `module_names` through the module slot instead of the class definition. Tests, DEVLOG and manifest entries added. This matches the report.

**Verified**
- Review defects fixed on HEAD, both builds: `p11_attr_snapshot` (`True False`), `p8_rebind_class` (`False False`), `p4_forward_alias` / `p5_nested_forward` (exit 1, empty stdout).
- `lab/compare`: all 10 `program.c` byte-identical HEAD vs `work` (`/tmp/base`, 33ae61c).
- `test_ail_covisin1` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check` exit 0.
- Snapshot semantics probes (`p21`–`p24`, `p28`, `p35`, `p38`–`p41`, `p44`, `p48`, `p51`, `p52`, `p55`) match CPython both builds. The worker's `/tmp/probes` files listed in the report also match.
- Unconditional rebinding probes (`p30`, `p31`, `p55`) now match CPython; base differed.
- `p25`–`p27`, `p33`, `p34`, `p36`, `p46`, `p47`, `p50` are named compile-time refusals (acceptable).

**Defect**
1. Any module-level binding of a class name — even one not executed, including annotation-only — disables its constructor. `pyboxed2._call_name` skips `_call_class` whenever the name is in `module_names`, and the dynamic call path then raises `TypeError: 'type' object is not callable`. Probe `p29_rebind_conditional.py`:
```python
class A: pass
class B: pass
if False:
    A = B
x = A()
print(type(x).__name__)
```
CPython: `A`, exit 0. HEAD default and general: empty stdout, exit 1, `TypeError: 'type' object is not callable`. Base matches CPython. Same root cause and result for `p43_for_rebind.py` (`for A in []: pass`), `p53_try_rebind.py` (unexecuted `else: A = B`), `p54_unpack_rebind.py`, `p56_annotation_rebind.py` (`A: int`), `p57_cond_ann.py`, and `p59_func_cond_call.py` (call inside a function). `isinstance` itself still works in these cases (`p42`, `p58`).

**Pre-existing**
- `p37_attr_non_type.py`: `T = b.x` with `b.x = 5`; CPython raises `TypeError` exit 1, both HEAD and base print `False` exit 0.

**Claim check**
- Snapshot at assignment, forward `NameError`, 5 tests + DEVLOG, listed probes, manifest check: verified.
- "Follow module-rebound class names in constructor calls": false as stated — only unconditional rebinding works; conditional/annotation bindings regress (defect 1).
- 4-module test claim: only `test_ail_covisin1` and `test_ail_safetynet` re-run (0 failed); `test_ail_files` and `test_ail_corpus_findings3` unverified.

**Unverified**
- `test_ail_files`, `test_ail_corpus_findings3` (not run per review scope).
- Speed/icount: change is compiler-front-end only and `lab/compare` C is identical, so no runtime hot-path change was measured.

VERDICT: FIX
1. `p29_rebind_conditional.py` (and `p43`, `p53`, `p54`, `p56`, `p57`, `p59`): expected `A` / exit 0; actual empty stdout / exit 1 `TypeError: 'type' object is not callable` (both builds). A class name bound anywhere at module level, even in an unexecuted branch or an annotation, must not lose its constructor when that binding did not run.
[cost $0.0000, opencode tokens {"total": 1276391, "input": 80174, "output": 7157, "reasoning": 20932, "cache.write": 0, "cache.read": 1168128}]
    tool time: bash 7.0 min
        170s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_cov
         81s bash   cd /tmp && rm -rf lc && mkdir -p lc/h lc/b ok=1 for t in berth_sim chain_relax echo_pack ledger_bin rail_trans
         52s bash   cd /home/runner/work/ail-ci/ail-ci for p in /tmp/rprobes/p2*.py /tmp/rprobes/p3*.py /tmp/rprobes/p4*.py; do ec
         34s bash   cd /home/runner/work/ail-ci/ail-ci for p in /tmp/rprobes/p4[2-9]*.py /tmp/rprobes/p5*.py; do echo "===== $(bas
         27s bash   ls /tmp/probes | tr '\n' ' '; echo; cd /home/runner/work/ail-ci/ail-ci for p in p11_attr_snapshot p8_rebind_cl
         11s bash   cd /tmp/base for p in p43_for_rebind p53_try_rebind p54_unpack_rebind p42_cond_rebind_isinstance; do echo "===
         10s bash   cd /tmp/rprobes cat > p56_annotation_rebind.py <<'EOF' class A: pass A: int x = A() print(type(x).__name__) EO
         10s bash   cd /tmp/rprobes cat > p58_ann_isinstance.py <<'EOF' class A: pass A: int print(isinstance(A(), A)) EOF cat > p

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `8f176b0`.

- Fixed the review defect: module-bound class names now stay constructible when the rebinding did not execute. `p29`, `p43`, `p53`, `p54`, `p56`, `p57`, `p59` all match CPython (`A`, exit 0) on default + general; executed rebindings `p30`, `p31`, `p55` also match.
- Added new boundary probes: executed `if`, non-class/function rebinding, and class values through argument, list item, attribute and dict. All match CPython.
- `lab/compare`: all 10 `main.ail` sources generate byte-identical C vs base `33ae61c`.
- Final tests: `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` passes.
- Known pre-existing `p37_attr_non_type` silent difference remains unchanged.
[cost $0.0423, opencode tokens {"total": 4026703, "input": 108837, "output": 9829, "reasoning": 14021, "cache.write": 0, "cache.read": 3894016}]
    tool time: bash 14.7 min, edit 0.0 min, write 0.0 min
        285s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        283s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        101s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do b=$(basename $p .py); out=$(timeout 300 b
         83s bash   chmod +x /tmp/cc_capture.sh && cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/labcmp && mkdir -p /tmp/labcm
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py; do b=$(basename $p .py); out=$(timeout 300 ba
         27s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check && for p in p29_rebind_conditio
         24s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p29_rebind_conditional p43_for_rebind p53_try_rebind p54_unpack
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/n*.py; do b=$(basename $p .py); out=$(timeout 300 b

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Diff.** `tuplib` now snapshots unstable module type constants (attribute values, later-rebound or forward names) into hidden `_ail_snap_*` names and adds `_ail_defined_*` forward markers; `pyboxed2` routes every module-bound class name through the module slot and registers those classes in `class_values` so the dynamic call path can construct them.

**Verified claims**
- Review probes `p11_attr_snapshot` (`True False`), `p8_rebind_class` (`False False`), `p4_forward_alias`/`p5_nested_forward` (exit 1, empty stdout) now match CPython on both builds. (NameError text names the hidden `_ail_defined_*` alias; stdout/exit match.)
- `p29`, `p30`, `p31`, `p32`, `p43_const_extra_read`, `p44_tuple_attr_mutation`, and worker probes `n1`–`n8` match CPython.
- Fresh `program.c` for all 10 `lab/compare` `main.ail` builds is byte-identical HEAD vs base `33ae61c`.
- `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` passes.
- Claim that module-bound class names "stay constructible" is **false in general**: keyword construction now refuses to build.

**Defect (change-caused regression)**
1. A module-bound class constructor with keyword arguments is now a compile-time refusal. The new dynamic path (`pyboxed2.py:2704`, `pyboxed2.py:7887`) sends all calls of a class in `module_names` through `call_value`, which refuses keywords at `boxclosure.py:372`.
```python
class A:
    def __init__(self, x, y=2):
        self.x = x; self.y = y
class B: pass
if False:
    A = B                      # only this dead binding makes A module-bound
a = A(x=3)
print(a.x + a.y)
```
CPython/base: `5`, exit 0. HEAD: both builds fail with `not in the subset: keyword arguments in a call through a function value`.
Same defect: `p46_rebound_ctor_kwargs` (CPython `7 4`; base wrong `5 6`), `p53_rebind_exc_kwargs` (CPython `7 f`; base wrong `7 x`), and `p45` (`5 6`) now all refuse instead of matching. `_call_class` already handles keyword arguments, so this can be exact.

**Pre-existing (identical on base, not blocking)**
- `p56`/`p57` unstable alias chains: CPython `True False`; both builds `False True` (snapshot re-expands an earlier unstable constant at the later assignment).
- `p50`/`p51` class rebound to a non-type used in `isinstance`: CPython TypeError exit 1; both builds print `False`, exit 0.
- `p49` module tuples naming `BaseException`/`LookupError`/`ArithmeticError`/`UserWarning` are refused identically on base (`_ISINSTANCE_EXC_NAMES` remains incomplete).

**Unverified.** Speed/icount on gdev, the 148-module census, `p37_attr_non_type`, and worker probes `p43`/`p53`–`p59` (not present in `/tmp/probes`).

VERDICT: FIX
1. `p54_kw_dead_if.py` (and `p45`/`p46`/`p53`): a module-bound class constructor with keyword arguments is refused (`keyword arguments in a call through a function value`) in both builds; expected CPython output `5` for p54, `7 4` for p46, `7 f` for p53.
[cost $0.0374, opencode tokens {"total": 2582726, "input": 84687, "output": 8423, "reasoning": 20368, "cache.write": 0, "cache.read": 2469248}]
    tool time: bash 8.8 min
        285s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_a
         79s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmpC_head /tmp/cmpC_base && mkdir -p /tmp/cmpC_head /tmp/cmp
         22s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/n*.py; do b=$(basename $p); echo "===== $b"; timeou
         17s bash   cd /tmp/base && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p47_rebound_default p48_rebound_subcl
         17s bash   cd /tmp/base && for p in p40_kw_ctor p41_default_ctor p42_kw_exc p43_const_extra_read p44_tuple_attr_mutation;
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p40_kw_ctor p41_default_ctor p42_kw_exc p43_const_extra_read p4
         12s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p29_rebind_conditional p30_rebind_constructor p31_rebind_static
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p47_rebound_def

FINAL VERDICT: FIX  2026-11-01T23:18:37Z
