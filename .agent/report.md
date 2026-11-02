# job job-covisin1-11020842  started 2026-11-01T23:44:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `b27a3e8` on `job-covisin1-11020842`.

**Defect fixed:** module-bound class constructors with keyword arguments no longer refuse. `call_value` now evaluates keyword values once (after positional, call-site order) and passes them to `_call_class` for each candidate class in the module-slot dispatch. A new `_class_only_module_names` analysis (greatest fixpoint over class aliases) enables this only when every module-level binding of the name is the class itself or another class name; names that may hold a function/plain value keep the prior named compile-time refusal.

**Probes (all match CPython on both builds, stdout + exit):**
- p54_kw_dead_if (`5`), p45_kw_ctor_conditional (`5 6`), p46_rebound_ctor_kwargs (`7 4`), p53_rebind_exc_kwargs (`7 f`)
- p60 kw-only/defaults, p61 alias chain, p62 keyword evaluation order, p63 program with a `__call__` class, p68 normal ctor kwargs, p72 exception ctor kwargs
- Non-class bindings still refused by name: p64/p67/p69/p70; p65/p66 (attribute/list class values) keep pre-existing refusals.

**Verification:** `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed. `update_manifest.py --check` passes. Generated C for all 10 `lab/compare` tasks is byte-identical HEAD vs working tree.
[cost $0.0000, opencode tokens {"total": 4707163, "input": 179307, "output": 14555, "reasoning": 22293, "cache.write": 0, "cache.read": 4491008}]
    tool time: bash 8.6 min, edit 0.0 min
        237s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
        198s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 2400 python3 ../tools/par_check.py -j 2 test_ail_cov
         27s bash   cd /home/runner/work/ail-ci/ail-ci && args=(); for f in $(find lab/compare/src -name main.ail | sort); do args
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p4*.py /tmp/probes/p5*.py /tmp/probes/p6*.py; do ec
         13s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py >/dev/null && python3 tools/update_mani
          7s bash   cd /tmp/probes && cat > p67_kw_alias_then_value.py <<'EOF' class A:     def __init__(self, x):         self.x 
          5s bash   cd /tmp/probes && cat > p62_kw_eval_order.py <<'EOF' def val(tag, v):     print(tag)     return v class A:    
          3s bash   cd /tmp/probes && cat > p73_kw_ctors_test.py <<'EOF' class A:     def __init__(self, x, y=2):         self.x =

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Diff.** `_class_only_module_names` (pyboxed2.py:1729) textually classifies module bindings; `kw_class_safe` is threaded into `call_value`, which evaluates keyword values once and passes them to `_call_class` for each candidate class. Other module-bound names still keep the named keyword refusal.

**Verified claims**
- p54 (`5`), p45 (`5 6`), p46 (`7 4`), p53 (`7 f`): match CPython on both builds.
- p60–p63, p68, p72, p73: match; p64/p67/p69/p70 still refuse by name. p65/p66 refuse identically on base.
- Keyword evaluation order: p62 and my r17 (`a b c 103`) match.
- `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- `update_manifest.py --check`: passes. All 10 `lab/compare` `program.c` are byte-identical HEAD vs base (I rebuilt them).

**Defect (new silent difference)**
1. `_class_only_module_names` treats every `ast.ClassDef` as binding the class, ignoring `decorator_list` (pyboxed2.py:1766). A class decorator rebinds the name to whatever it returns, so the name is not class-only. The new keyword path then compiles a program the base refused and silently produces the wrong value.
```python
def deco(cls):
    def f(x):
        return x + 5
    return f
@deco
class A:
    def __init__(self, x=0):
        self.x = x
class B:
    pass
if False:
    A = B
print(A(x=3))
```
CPython: `8`, exit 0. HEAD: both builds print `<A object>`, exit 0. Base: both builds refuse by name (`keyword arguments in a call through a function value`). Fix: count a `ClassDef` with `decorator_list` as `'other'` (or model the decorator), restoring at least the named refusal.

**Pre-existing (not blocking)**
- Forward alias `A = B` before `class B` with kwargs (r30): HEAD prints `3`, exit 0 vs CPython NameError exit 1; the same class-hoisting difference already occurs on base with a positional call (r31), so the root is pre-existing.
- Module-level walrus rebinding a class name is still a named refusal (the name becomes a frame local); acceptable.
- p65/p66 refusals are identical on base.

**Unverified.** gdev instruction counts (no runtime change; the 10 lab C files are identical), wider suite, 148-module census.

VERDICT: FIX
1. Decorated `ClassDef` is classified as a class-only binding; `A(x=3)` now compiles to `<A object>` (exit 0) where CPython gives `8` (exit 0) and base refused by name. Probe and outputs above.
[cost $0.0000, opencode tokens {"total": 3436484, "input": 79270, "output": 11789, "reasoning": 41489, "cache.write": 0, "cache.read": 3303936}]
    tool time: bash 5.5 min, write 0.0 min
        192s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         45s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cmpC_head /tmp/cmpC_base && mkdir -p /tmp/cmpC_head /tmp/cmp
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p53_rebind_exc_
         14s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r01_walrus_func r02_walrus_class r03_walrus_plain r04_sta
         10s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r17_kw_order_rebind r18_dispatch_multi r19_kw_unknown r20
          7s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r30_forward_alias_kw r31_forward_alias_pos r32_type_alias
          6s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r33_class_body_call r34_lambda_call; do echo "===== $p HE
          5s bash   date; cd /home/runner/work/ail-ci/ail-ci && for p in r11_walrus_after_assign_func r12_walrus_after_assign_clas

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the named defect and committed as `d950b27`.

- `_class_only_module_names` now classifies a `ClassDef` with `decorator_list` as `'other'`, restoring the named compile-time refusal for keyword construction instead of silently constructing the undecorated class.
- Probe `p74_decorated_class_kw`: CPython `8`; default and general builds now refuse by name (`not in the subset: keyword arguments in a call through a function value`), matching base.
- Regression probes `p45`, `p46`, `p53`, `p54`, `p60`–`p63`: all match CPython on both builds.
- Added regression test `test_decorated_class_binding_keeps_keyword_refusal`.
- Required tests on final commit: `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed.
- All 10 `lab/compare` `main.ail` generated `program.c`: byte-identical current vs HEAD.
- `python3 tools/update_manifest.py --check`: passes.
- Pre-existing, unchanged: positional calls on decorated classes still ignore the decorator (`p75`/`p76`, both builds).
[cost $0.0000, opencode tokens {"total": 1808535, "input": 388481, "output": 5943, "reasoning": 7007, "cache.write": 0, "cache.read": 1407104}]
    tool time: bash 7.6 min, edit 0.0 min
        193s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_covisin1 test_ail_
        191s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_covisin1 test_ail_
         44s bash   cd /tmp && rm -rf /tmp/cmp_c_current /tmp/cmp_c_base && mkdir -p /tmp/cmp_c_current /tmp/cmp_c_base && fail=0;
         19s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p53_rebind_exc_
          3s bash   cat > /tmp/probes/p76_decorated_class_unbound.py <<'EOF' def deco(cls):     def f(x):         return x + 5    
          2s bash   cat > /tmp/probes/p75_decorated_class_pos.py <<'EOF' def deco(cls):     def f(x):         return x + 5     ret
          1s bash   cd /tmp && rm -rf /tmp/cbase && mkdir /tmp/cbase && cd /home/runner/work/ail-ci/ail-ci && git archive HEAD AIL
          1s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p74_decorated_class_kw.py <<'EOF' def deco(cls):     def f(x):      

## review 1
[model opencode/deepseek-v4.1-flash-free]
## review

**Diff.** Two commits, not one: `b27a3e8` is the actual fix for the named defect (keyword arguments on a module-bound class are precomputed once and passed to `_call_class` per slot-dispatch branch, gated by a new `_class_only_module_names` class-only-binding analysis); `d950b27` is a follow-up that treats a decorated `ClassDef` as an `'other'` binding so such keyword calls keep the named compile-time refusal. The report describes only the second and attributes the named fix to it — inaccurate, but the net behaviour is right.

**Probes** (both builds, HEAD vs CPython):
- Named defect: `p54` `5`, `p45`, `p46` `7 4`, `p53` `7 f` — all same stdout/exit on default and general. Fixed.
- Regression set `p60`–`p63`: same stdout/exit.
- Mine: `r1_kw_types_alias`, `r2_kw_from_containers`, `r3_kw_eval_once`, `r6_kw_errors`, `r7_kw_default_effect` — same stdout/exit; covers negative/`None`/`bool`/str args, list/dict/attribute values, one-shot evaluation, defaults, keyword-only, missing/unknown/extra-arg TypeErrors.
- `r8`, `r9`, `r10`, `r11`, `r12` — named compile-time refusal (non-class value / class reached via arg, list, dict, attribute, walrus); acceptable per task.
- `r13`/`r14` starred target: HEAD exit 1 empty stdout, CPython exit 1 empty stdout; matches.
- `r4` (`del` of class name) — named refusal; acceptable.
- Decorated: `p74` refuses by name on both builds, identical to base; `p75`/`p76`/`r29` and plain decorated `r15` differ identically on base.

**Tests.** `test_ail_covisin1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed (192s). `tools/update_manifest.py --check`: pass.
**Codegen / speed.** All 10 `lab/compare/src/*/main.ail` `program.c` byte-identical HEAD vs base; 3 sampled `gdev` `program.c` also identical, so no hot-path change. No icount needed.

**Report claims.** Named defect fixed (verified in effect; misattributed to `d950b27` instead of `b27a3e8`). Decorated RuleDef → `'other'` (verified). `p74` CPython `8`, refusal both builds (verified). `p45/46/53/54/60-63` match (verified). New test added (verified). 4 modules pass (verified). 10 `lab/compare` C identical (verified). Manifest check (verified). Decorated positional pre-existing (verified).

**Pre-existing (not blocking).** Forward alias `A = B` before `B` is defined: CPython NameError, both builds exit 0 and print the value (`r30`/`r31`); the keyword form was refused on base and now inherits the same pre-existing result. Decorated-class positional calls ignore the decorator (`p75`/`p76`/`r29`), and plain decorated-class keyword calls do too (`r15`) — identical on base.

**Unverified.** Full suite (by design not run), 148-module census, icount (codegen identical, so no expected change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2027206, "input": 63962, "output": 8466, "reasoning": 24794, "cache.write": 0, "cache.read": 1929984}]
    tool time: bash 6.9 min
        193s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
         58s bash   cd /tmp && rm -rf gdh gdb && mkdir -p gdh gdb && fail=0; for f in g00_000 g01_000 g02_000; do for side in h b;
         49s bash   cd /home/runner/work/ail-ci/ail-ci && date && for p in /tmp/rprobes/r0*.py /tmp/rprobes/r1[0-9]*.py /tmp/rprob
         45s bash   cd /tmp && rm -rf cc_head cc_base && mkdir -p cc_head cc_base && cd /home/runner/work/ail-ci/ail-ci && date &&
         19s bash   cd /home/runner/work/ail-ci/ail-ci && date && for b in p45_kw_ctor_conditional p46_rebound_ctor_kwargs p53_reb
          7s bash   cd /home/runner/work/ail-ci/ail-ci && date && for b in r1_kw_types_alias r2_kw_from_containers r3_kw_eval_once
          6s bash   cd /home/runner/work/ail-ci/ail-ci && date && for b in p74_decorated_class_kw p75_decorated_class_pos p76_deco
          6s bash   cd /tmp/base && date && for b in p74_decorated_class_kw p75_decorated_class_pos p76_decorated_class_unbound p7

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T02:09:56Z
