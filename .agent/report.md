# job job-pre56-10241244  started 2026-10-24T03:48:11Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `fdba04d`.

**Change**
- Added a shared AST check in `AIL_CURRENT/ail_chatgpt.py` that refuses compile-time-known integer `**` / two-argument `pow()` results outside int64 by name, on both builds.
- Covers module, local, nested-name, list-item, dict-value and class-attribute routes.
- Left valid powers unchanged: `2**62`, `(-2)**63`, `3**39`, modular `pow()`, negative exponents, shadowed `pow`, comprehensions/lambdas.
- Added `AIL_CURRENT/test_ail_pre56.py`, registered it, updated `DEVLOG.md`, `DIFFERENCES.md`, `SEMANTICS.md` and the manifest.

**Probes (17, both builds)**
- Refused by name: `pow1`, `pow2`, `pow3`, `pow_local`, `pow_list`, `pow_dict`, `pow_attr`, `pow_nested` (8).
- Matched CPython: `pow_ok`, `pow_shadow`, `pow_arg`, `pow_comp`, `pow_lambda`, `pow_neg`, `pow_bound`, `pow_global`, `pow_mut` (9).
- Runtime-only operands, e.g. `def f(a): return a**40` with `a=10`, still stop with `integer overflow`; unchanged from the base and covered by the documented int64 limit. The second listed pre-existing difference was not touched.

**Tests on final commit**
- `test_ail_pre56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed.
- Targeted `test_ail_multifile` import-time-refusal test: passed.
- `update_manifest.py --check`: passed.
[cost $0.0000, opencode tokens {"total": 7713078, "input": 189845, "output": 46223, "reasoning": 5394, "cache.write": 0, "cache.read": 7471616}]
    tool time: bash 12.2 min
        341s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet test_ail_files test_ail
        263s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet test_ail_files test_ail
         35s bash   for p in pow1 pow2 pow3 pow_local pow_list pow_dict pow_attr pow_ok pow_shadow pow_arg pow_comp pow_lambda pow
         20s bash   cat > /tmp/probes/pow_comp.py <<'EOF' a = 10 print([a**80 for a in [1]]) print([a**40 for a in [1]]) EOF cat >
         19s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() old="""    def 
         13s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/ail_chatgpt.py') s=p.read_text() start=s.index('
         13s bash   mkdir -p /tmp/probes; cat > /tmp/probes/pow1.py <<'EOF' a = 10 print(a**40) EOF cat > /tmp/probes/pow2.py <<'E
         10s bash   git add AIL_CURRENT/test_ail_pre56.py AIL_CURRENT/ail_chatgpt.py AIL_CURRENT/ail_check.py AIL_CURRENT/MANIFEST

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does (one line):** adds a whole-module constant-propagation AST pass that refuses `**` / two-argument `pow()` whenever its operands can be resolved to integer constants whose exact result exceeds int64; it does not change code generation.

**Tests / build checks**
- `test_ail_pre56`, `test_ail_safetynet`: 2 modules, 0 failed.
- `python3 ../tools/update_manifest.py --check`: passes.
- A no-power program's `--debug-dir` generated C is byte-identical to base (only `native_report.json` differs).
- Known cases `a = 10; a**40` and `pow(10, 40)` are refused by name on both builds.
- Valid-boundary probe (`2**62`, `(-2)**63`, `3**39`, `10**18`) matches CPython on both builds.

**Report claims**
- “Refuses known integer `**`/`pow()` results outside int64 on both builds” — **verified**.
- “Covers module, local, nested, list-item, dict-value, class-attribute routes” — **verified** (test module passes; my list/dict probes are refused).
- “Left valid powers unchanged” — **false** for values whose container is mutated after the constant assignment (defects 1–3), and for shadowed class names (defect 4).
- “17 probes … 8 refused / 9 matched” — **unverified** (worker probe files were not available here).
- “Runtime-only operands still stop with `integer overflow`, unchanged from base” — **verified** (`def f(a): return a**40; f(10)` identical on base and HEAD).
- Second listed pre-existing case (`-INT64_MIN`) — **unverified / not touched**.

**Defects**

1. Mutating a list after assigning it is wrongly refused.
```python
xs = [10]
xs[0] = 1
print(xs[0]**40)
```
Expected (CPython and base): `1`, exit 0. Actual HEAD: compile fails on both builds with “the integer ** result does not fit…”. Base matches CPython.

2. Mutating a dict value after assigning it is wrongly refused.
```python
d = {0: 10}
d[0] = 1
print(d[0]**40)
```
Expected: `1`, exit 0. Actual HEAD: same compile-time refusal on both builds. Base matches CPython.

3. Aliased container mutation is wrongly refused.
```python
xs = [10]
ys = xs
ys[0] = 1
print(xs[0]**40)
```
Expected: `1`, exit 0. Actual HEAD: same compile-time refusal on both builds. Base matches CPython.

4. A parameter that shadows a class name is ignored.
```python
class C:
    a = 10
def f(C):
    return C.a**40
print(1)
```
Expected (CPython and base): `1`, exit 0. Actual HEAD: compile fails on both builds with “the integer ** result does not fit…”, because the class constant table is consulted without checking the parameter shadowing `C`. Base matches CPython.

Root cause: the constant collector does not model mutation through `Subscript` stores, aliases, or calls, and the class-constant lookup does not respect local/parameter shadowing. These are false refusals of programs that CPython (and base AIL) run correctly.

**Pre-existing (not blocking):** run-time-only power overflow (`def f(a): return a**40; f(10)`) still prints `integer overflow` on base and HEAD identically.

VERDICT: FIX
1. `xs = [10]; xs[0] = 1; print(xs[0]**40)` — expected `1`, actual compile-time refusal.
2. `d = {0: 10}; d[0] = 1; print(d[0]**40)` — expected `1`, actual compile-time refusal.
3. `xs = [10]; ys = xs; ys[0] = 1; print(xs[0]**40)` — expected `1`, actual compile-time refusal.
4. `class C: a = 10` / `def f(C): return C.a**40` / `print(1)` — expected `1`, actual compile-time refusal.
[cost $0.0000, opencode tokens {"total": 417171, "input": 26713, "output": 3601, "reasoning": 9001, "cache.write": 0, "cache.read": 377856}]
    tool time: bash 3.5 min
        128s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet 2>&1 | tail -20
         20s bash   date; for p in p_list_mut p_dict_mut p_alias p_param_shadow_class p_rebind_class; do echo "===== $p"; bash ~/t
         13s bash   date; for p in /tmp/rprobes/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | tail 
          8s bash   for p in p_param_shadow_class p_rebind_class; do echo "===== $p base"; bash ~/tools/cmp.sh "/tmp/rprobes/$p.py
          8s bash   cat > /tmp/rprobes/p_inst.py <<'EOF' class C:     a = 10 class D:     def __init__(self, v):         self.a = 
          8s bash   cat > /tmp/rprobes/p_two_classes.py <<'EOF' class C:     a = 10 class D:     a = 1 print(C.a, D.a) EOF echo BA
          8s bash   cat > /tmp/rprobes/p_class_attr.py <<'EOF' class C:     a = 2 print(C.a) EOF bash ~/tools/cmp.sh /tmp/rprobes/
          6s bash   cat > /tmp/rprobes/p_runtime.py <<'EOF' def f(a):     return a**40 print(f(10)) EOF echo HEAD; bash ~/tools/cm

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Committed `56ee34d` on `job-pre56-10241244`.

**Tests on final commit:** `test_ail_pre56`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (261 s). `update_manifest.py --check` passes.

**Probes:** 18 run with `cmp.sh` on both builds.
- Reviewer cases 1–4 (`p_list_mut`, `p_dict_mut`, `p_alias_mut`, `p_param_shadow_class`): match CPython.
- 7 more valid programs match CPython: alias/dict mutation, index mutation, argument mutation, nested list/tuple mutation, enclosing-scope shadowing, boundary powers.
- 4 overflowing constants refused by name: list item, aliased read, local scalar, class attribute.
- 3 class-object probes hit AIL's pre-existing class-attribute-rebinding / class-in-list limitation after compilation; they do not test the power refusal path. The non-alias class mutation case behaves the same on base.
[cost $0.0000, opencode tokens {"total": 1824265, "input": 74952, "output": 11726, "reasoning": 24051, "cache.write": 0, "cache.read": 1713536}]
    tool time: bash 10.4 min, edit 0.0 min, write 0.0 min
        263s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet test_ail_files test_ail
        263s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet test_ail_files test_ail
         56s bash   ls /tmp/probes; for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD" 2>&
         40s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd AIL_CURRENT && python3 ../t
          0s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre56 2>&1 | tail -30
          0s bash   git status --short && git diff --stat && python3 tools/update_manifest.py --check
          0s bash   git log --oneline -5 && git status && ls
          0s bash   git status --short && python3 tools/update_manifest.py --check && echo MANIFEST_OK

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does:** adds a new compile-time AST pass (`_check_int64_powers`, `ail_chatgpt.py:485`) that evaluates constant integer `**` / two-argument `pow()` operands (through names, containers, class attributes) and refuses an out-of-int64 result by name on both builds. The second commit adds alias/mutation/shadow tracking. It also adds `test_ail_pre56.py`, a DIFFERENCES row, DEVLOG/SEMANTICS entries and manifest updates. This matches the report.

**Verified**
- HEAD `56ee34d`; manifest `--check` passes.
- Original cases `a=10; a**40` (o1) and `pow(10,40)` (o2) are refused by name on both builds.
- Boundaries: `2**62`, `(-2)**63`, `pow(2,62)`, modular `pow`, negative exponents, `0**0`, `0**100`, `1**100`, `(-1)**101` match CPython (b1); `2**63`, `3**40`, `(-10)**41`, `pow(2,63)` refused (b3, o3–o5).
- Refused-through shapes: list item (c1), dict value (c2), aliased read (q1), local scalar (q2), class attribute (a1).
- Mutated/aliased containers and parameter-shadowed class names compile and match: c3, c4, c6, c7, f1, f3, f4, s1, s7.
- `test_ail_pre56` and `test_ail_safetynet` pass on HEAD (`-j 2`, 0 failed, 126 s). I did not rerun `test_ail_files` / `test_ail_corpus_findings3` (outside the stated reviewer scope).
- A no-feature program's generated `program.c` is byte-identical to base.

**Defect**
1. **Class-body constants leak into method/comprehension scopes, causing false compile-time refusals of valid programs.** `_check_scope` passes a class body's `known` values as `inherited` into nested functions/comprehensions (`ail_chatgpt.py:432-439`), but Python methods and class-body comprehensions resolve names globally, not through the class namespace.

   - `/tmp/rprobes/n2.py`:
     ```python
     a = 2
     class C:
         a = 10
         def f(self):
             return a**40
     print(C().f())
     ```
     Expected (CPython and base, both builds): `1099511627776`. Actual HEAD: build fails with `the integer ** result does not fit in a 64-bit signed integer...`.

   - `/tmp/rprobes/n3.py` (same with `pow(a, 40)`): expected `1099511627776`; actual HEAD refuses `pow()` on both builds.

   - `/tmp/rprobes/x1.py`:
     ```python
     a = 2
     class C:
         a = 10
         xs = [a**40 for _ in [0]]
     print(C.xs)
     ```
     Expected `[1099511627776]`; actual HEAD refuses `**`.

   - `/tmp/rprobes/x2.py` (module list `[2]` used in a method, class attribute `xs=[10]`): expected `1099511627776`; actual HEAD refuses `**`.

   All four match CPython on base on both builds, so this is a regression introduced by the new pass.

**Pre-existing (not blocking)**
- Nested-container overflow `/tmp/rprobes/c5.py` (`xs=[[10]]; xs[0][0]**40`) still traps at runtime on both base and HEAD.
- `a2.py`, `n4.py`, `n8.py` class-attribute rebinding / class-in-list cases give the same `AttributeError` on base and HEAD.
- `s2.py`, `s3.py`, `s6.py`, `f2.py`, `c8.py` behave identically on base (runtime overflow or default-build C error).
- `-2**63` / `-pow(2,63)` already trapped at runtime on base; HEAD now refuses them by name. CPython succeeds, but the pre-existing difference is not newly introduced.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; runtime instruction counts (the pass is compile-time only, generated code unchanged).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1116617, "input": 108495, "output": 13479, "reasoning": 25299, "cache.write": 0, "cache.read": 969344}]
    tool time: bash 6.8 min, write 0.0 min
        152s bash   cat > /tmp/runprobes.sh <<'EOF' #!/bin/bash wt=$1; shift for p in "$@"; do   echo "===== $(basename $p)"   tim
        128s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre56 test_ail_safetynet 2>&1 
         50s bash   date; echo ====HEAD; /tmp/runprobes.sh "$PWD" /tmp/rprobes/n*.py 2>&1 | tee /tmp/nhead.log; echo ====BASE; /tm
         37s bash   date; /tmp/runprobes.sh /tmp/base /tmp/rprobes/c5.py /tmp/rprobes/c8.py /tmp/rprobes/a1.py /tmp/rprobes/a2.py 
         27s bash   date; echo ====HEAD; /tmp/runprobes.sh "$PWD" /tmp/rprobes/m*.py 2>&1 | tee /tmp/mhead.log; echo ====BASE; /tm
          9s bash   date; echo ====HEAD; /tmp/runprobes.sh "$PWD" /tmp/rprobes/x1.py /tmp/rprobes/x2.py 2>&1; echo ====BASE; /tmp/
          5s bash   cat > /tmp/rprobes/nofeature.py <<'EOF' xs = [1, 2, 3] total = 0 for x in xs:     total += x * x print(total) 
          0s bash   cat > /tmp/rprobes/q1.py <<'EOF' xs = [10] ys = xs print(ys[0]**40) EOF cat > /tmp/rprobes/q2.py <<'EOF' def f

FINAL VERDICT: FIX  2026-10-24T04:49:32Z
