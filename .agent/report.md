# job job-pre288-10270335  started 2026-10-26T18:36:18Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114477,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114389,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Fixed:** pre278's first still-differing pre-existing item, `make(4).f()` returning the method (`-1`) instead of the stored field (`40`). The field/method collision refusal now resolves function returns (direct, alias, branch, pass-through parameter, method return), constructors, attributes, list items and dict values; such calls are refused by name on both builds.

**Probes** (`bash ~/tools/cmp.sh`, both builds)
- Refused by name: `p288_v1_return`, `_direct`, `_arg`, `_list`, `_dict`, `_attr`, `p288_ret_alias`, `_if`, `_passthrough`, `_inherited`, `_method`, `_attr_literal` — 12/12.
- Match CPython: `p288_ret_unrelated`, `_other_method`, `_no_collision`, `_class_call` — 4/4.
- Still pre-existing/unchanged: `p288_r6_setattr` (101 vs 102), `p288_r8_nested`, and the field-only lambda cases (named refusals).

**Tests on final commit:** `test_ail_pre288`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 214s, 0 failed. Manifest and `ci_shards --check` clean. Commit `458d2c3`.

**Unverified:** typed-only build in isolation and the full suite (per instructions).
[cost $0.0647, opencode tokens {"total": 6544747, "input": 149784, "output": 14754, "reasoning": 23857, "cache.write": 0, "cache.read": 6356352}]
    tool time: bash 10.9 min
        278s bash   cd AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre288 test_ail_safetynet test_ail_
        215s bash   cd AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre288 test_ail_safetynet test_ail_
         35s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p288_v1_return.py <<'EOF' class C:     def __init__(self, k):       
         30s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre288.py') s=p.read_text() old="""    
         30s bash   for p in /tmp/probes/p288_v1_return.py /tmp/probes/p288_v1_direct.py /tmp/probes/p288_v1_attr.py /tmp/probes/p
         24s bash   cat > /tmp/probes/p288_ret_alias.py <<'EOF' class C:     def __init__(self, k):         self.k = k         sel
         19s bash   for p in /tmp/probes/p288_v1_return.py /tmp/probes/p288_v1_direct.py /tmp/probes/p288_v1_attr.py /tmp/probes/p
          7s bash   cat > /tmp/probes/p288_field_only.py <<'EOF' class C:     def __init__(self, k):         self.k = k         se

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of job pre288 (`458d2c3`)

**What the diff really does:** adds a new 270-line `refuse_field_method_call()` in `pyfront.py` (not an extension of an existing pass — `work`/`d66b434` has no pre278 refusal) and calls it from `pyc._to_c`, `pyfunc._to_c_once`, `pyboxed2.build`, plus a new `test_ail_pre288.py`. It refuses `.name()` calls when the receiver *may* be a class with both a method and a field `name`; new in this job are function-return, method-return and `__init__` parameter resolution.

**My probes** (`/tmp/rprobes`, both builds; base `/tmp/base`):

| probe | CPython | HEAD | base |
|---|---|---|---|
| `r1_exact` (`make(4).f()`) | 40 | refused by name | `-1` (diff) |
| `r6_branch`, `r7_dict`, `r8_attr`, `r10_kw` | ok | refused by name | — |
| `r4_ident`, `r5_append`, `r9_unrelated_param` | ok | same | same |
| `r14_samename` | 3 | **refused** | 3 |
| `r13_scope_min` | 3 | **refused** | 3 |
| `r11_ann` | 3 | **refused** | 3 |
| `r12_forloop` | 70 | -1 | -1 |
| `p288_r6_setattr` | 101 | 102 | 102 |
| `p288_field_only_no_method_return` | 40 | refused (“unknown static kind”) | same refusal |
| `n1_nofeature` (`--debug-dir`) | ok | C byte-identical to base | ok |

Tests on HEAD: `test_ail_pre288` + `test_ail_safetynet` = 2 modules, 106 s, 0 failed. `update_manifest --check` and `ci_shards --check` clean.

**Report claims:** exact case fixed, both builds, branch/dict/attr/constructor routes, the 4 “match CPython” probes, targeted tests, manifest — verified. “Unrelated classes … keep their behaviour” — **false** (r14/r13/r11). “Field/method refusal now resolves function returns” — true, but it resolves them **name-blind** and over-refuses. `test_ail_files`/`corpus_findings3` — not rerun.

**Pre-existing (identical on base, not blocking):** `setattr(self,'f',…)` still prints 102 vs 101; a `for c in [C(...)]` collision receiver still prints -1 vs 70; field-only lambdas refused as before.

**Defects (new vs base):**

1. `r14_samename` — function-return resolution matches *any* `FunctionDef` with the callee’s bare name, ignoring class scope:
   ```python
   class C:
       def __init__(self): self.f = lambda: 1
       def f(self): return 2
   class D:
       def f(self): return 3
   class F:
       def make(self): return C()
   def make(): return D()
   print(make().f())
   ```
   CPython/base/`pre278`: `3`; HEAD: compile refusal `the method .f() ... also stores an instance field named f` (both builds). `F.make` returning `C` is wrongly attributed to the module-level `make`.
2. `r13_scope_min` / `r11_ann` — `_classes_of` for an `ast.Name` scans every assignment and annotation in the *whole tree*, so a same-named local or annotation in another function contaminates the receiver:
   ```python
   class C:
       def __init__(self): self.f = lambda: 1
       def f(self): return 2
   class D:
       def f(self): return 3
   def b():
       x = C()
       return 0
   def a():
       x = D()
       return x.f()
   print(a())
   ```
   CPython/base: `3`; HEAD: compile refusal (both builds). Same with `def a(x: C): ...` elsewhere (`r11_ann`).

**Unverified:** typed-only build in isolation; full suite; `test_ail_files`/`test_ail_corpus_findings3`; the worker’s 12-refusal set beyond the routes I re-ran. No icount check needed: the change is compile-time only and non-feature C is byte-identical.

VERDICT: FIX

1. Restrict function-call resolution to the correct scope (module-level calls must not pick up same-named methods), as in `r14_samename`: expected `3`, actual compile refusal both builds; base prints `3`.
2. Make the `Name` resolver scope-aware (assignments/annotations in an unrelated function must not mark a receiver), as in `r13_scope_min`: expected `3`, actual compile refusal both builds; base prints `3` (also `r11_ann`).
[cost $0.0241, opencode tokens {"total": 997088, "input": 51701, "output": 6351, "reasoning": 16284, "cache.write": 0, "cache.read": 922752}]
    tool time: bash 3.6 min
        107s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         26s bash   cd /tmp/rprobes; for p in r1_exact r2_make_d r3_scope r4_ident r5_append r6_branch r7_dict r8_attr r9_unrelate
         17s bash   cd /tmp/rprobes; for p in r1_exact r2_make_d r3_scope r11_ann; do echo "===== $p BASE"; timeout 300 bash ~/too
         13s bash   cd /tmp/probes; for p in p288_r6_setattr p288_field_only_no_method_return; do for wt in /home/runner/work/ail-
         12s bash   cd /tmp/probes; for p in p288_ret_unrelated p288_ret_other_method p288_ret_no_collision p288_ret_class_call; d
         12s bash   git worktree add /tmp/pre278 f09c398 2>&1 | tail -2; cd /tmp/rprobes; for p in r2_make_d r3_scope r11_ann; do 
          9s bash   cd /tmp/probes; timeout 300 bash ~/tools/cmp.sh /tmp/probes/p288_r6_setattr.py /home/runner/work/ail-ci/ail-ci
          8s bash   cd /tmp/rprobes; cat > r12_forloop.py <<'EOF' class C:     def __init__(self, k):         self.k = k         s

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects in `pyfront.py`:

1. Function-return resolution now walks lexical scopes (current function → enclosing functions → module) instead of matching every `FunctionDef` by bare name. `r14_samename` / `r2_make_d` now print `3` on both builds.
2. `Name` resolution now uses only the receiver’s own scope and stops at the first binding, so unrelated assignments/annotations cannot contaminate it. `r13_scope_min` and `r11_ann` now print `3` on both builds.

**Probes** (22 in `/tmp/probes`, both builds):
- 13 refused by name as intended: `pre288r_ret_{module,kw,branch,list,dict,attr,arg,alias,method,inherited,ctor,inner_call,nested_local}`
- 9 matched CPython exactly: `pre288r_ok_{samename,local_scope,ann_scope,local_shadow,unrelated_arg,list_append,class_call,unknown_shadow,module_var}`

**Tests:** `test_ail_pre288`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 4 modules, 215 s, 0 failed. `update_manifest --check` and `ci_shards --check` clean. Pre-existing `setattr`/`for`-collision differences untouched; full suite not run per rules.

Committed as `62c1462`.
[cost $0.0256, opencode tokens {"total": 887843, "input": 45427, "output": 8478, "reasoning": 18706, "cache.write": 0, "cache.read": 815232}]
    tool time: bash 5.9 min, read 0.0 min
        217s bash   timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre288 test_ail_safetynet test_ail_files test_ail_cor
         55s bash   cd /tmp/probes; for f in pre288r_*.py; do p=${f%.py}; out=$(timeout 300 bash ~/tools/cmp.sh /tmp/probes/$f "$O
         28s bash   cd /tmp/probes; for f in pre288r_ok_*.py; do p=${f%.py}; out=$(timeout 300 bash ~/tools/cmp.sh /tmp/probes/$f 
         27s bash   for p in r14_samename r13_scope_min r11_ann r1_exact r2_make_d r3_scope r4_ident r5_append r6_branch r7_dict r
         26s bash   for p in r14_samename r2_make_d r1_exact r4_ident r6_branch r7_dict r8_attr r10_kw r13_scope_min r11_ann; do e
          1s bash   d=$(mktemp -d /tmp/eXXXX); cp /tmp/rprobes/r14_samename.py $d/p.ail; cd $d; AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=
          0s bash   python3 - <<'PY' from pathlib import Path p=Path('DEVLOG.md') s=p.read_text() entry='''## 2026-10-26 -- pre288
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo status=$?; python3 tools/ci

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review of job pre288 (`62c1462`, on top of `458d2c3`)**

**What the diff really does:** adds `pyfront.refuse_field_method_call()` (called from `pyc._to_c`, `pyfunc._to_c_once`, `pyboxed2.build`), which refuses `.name()` calls when the receiver may be a class defining both a method and an instance field `name`; the second commit restricts function-return lookup to lexical scopes and `Name` lookup to the receiver’s scope. Plus `test_ail_pre288.py`, DEVLOG/DIFFERENCES, manifest/shard updates.

**Probes** (`/tmp/rprobes`, both builds, base `/tmp/base`):

| probe | CPython/base | HEAD |
|---|---|---|
| `rv14_samename` | 3 | 3 |
| `rv13_scope` | 3 | 3 |
| `rv11_ann` | 3 | 3 |
| `rv_param_samename2` | `3 0` | refused both |
| `rv_nestedfunc` | 3 | refused both |
| `rv_ann_then_assign` | 3 | refused both |
| `rv_nofeature` (`--debug-dir`) | ok | C byte-identical to base |

Tests on HEAD: `test_ail_pre288` + `test_ail_safetynet` = 2 modules, 106 s, 0 failed. `update_manifest --check` and `ci_shards --check` clean.

**Report claims:** both review defects fixed — verified (`rv14`/`rv13`/`rv11`); the 22 worker probes match its 13-refused / 9-match table — verified by re-running all 22; manifest/shards — verified. “Resolution stays in the receiver’s lexical scope” — **false for parameters and nested functions** (below). `test_ail_files` / `corpus_findings3` — not rerun (only added+edited modules and safetynet were required).

**Pre-existing (identical on base):** `setattr(self,'f',…)` prints 102 vs 101; `for c in [C(...)]` prints -1 vs 70.

**Defects (new vs base, all named refusals of code that base compiles correctly):**

1. Parameter resolution still matches calls by bare function name across scopes (`calls_by_name`), the same root cause fixed for returns:
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
class F:
    def g(self, x): return x.f()
def g(a, x): return 0
def run(): return F().g(D())
print(run()); print(g(D(), C()))
```
Expected `3\n0`; actual compile refusal “the method .f() … also stores an instance field named f” on both builds.

2. A nested function inside a method treats its first parameter as `self` of that method’s class (`func_class` is propagated into nested defs):
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
class F:
    def __init__(self): self.f = lambda: 4
    def f(self): return 5
    def run(self):
        def inner(x): return x.f()
        return inner(D())
print(F().run())
```
Expected `3`; actual refusal both builds, although `x` is a `D`.

3. An annotation-only statement is treated as a binding even when a later assignment fixes the value; all bindings in the scope are unioned rather than stopping at the effective one:
```python
class C:
    def __init__(self): self.f = lambda: 1
    def f(self): return 2
class D:
    def f(self): return 3
def run():
    x: C
    x = D()
    return x.f()
print(run())
```
Expected `3`; actual refusal both builds.

**Unverified:** `test_ail_files`/`test_ail_corpus_findings3`; typed-only build in isolation; full suite. No icount run: the pass is compile-time only and non-feature C is byte-identical.

VERDICT: FIX
1. `rv_param_samename2`: expected `3\n0`, actual named compile refusal — param resolution must be scoped, not matched by bare callee name.
2. `rv_nestedfunc`: expected `3`, actual named compile refusal — a nested function’s first parameter is not `self` of the enclosing method’s class.
3. `rv_ann_then_assign`: expected `3`, actual named compile refusal — an annotation without a value must not make the receiver a colliding class after `x = D()`.
[cost $0.0220, opencode tokens {"total": 823525, "input": 55829, "output": 4479, "reasoning": 14545, "cache.write": 0, "cache.read": 748672}]
    tool time: bash 3.6 min
        107s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
         54s bash   cd /tmp/probes; for f in pre288r_*.py; do p=${f%.py}; out=$(timeout 300 bash ~/tools/cmp.sh /tmp/probes/$f /ho
         16s bash   cd /tmp/rprobes; sed -i 's/g(C(4))/g(C())/' rv_param_samename.py; for f in rv14_samename rv13_scope rv11_ann r
         15s bash   for p in /tmp/rprobes/r12_forloop.py /tmp/probes/p288_r6_setattr.py; do echo "===== $(basename $p)"; for wt in
         12s bash   cd /tmp/rprobes cat > rv_param_samename2.py <<'EOF' class C:     def __init__(self): self.f = lambda: 1     de
          6s bash   cd /tmp/rprobes; for f in rv_param_samename2 rv_nofeature; do echo "===== $f HEAD"; timeout 300 bash ~/tools/c
          4s bash   d=$(mktemp -d /tmp/dbgXXXX); cp /tmp/rprobes/rv_nofeature.py $d/p.ail; cd $d; for wt in /home/runner/work/ail-
          0s bash   cd /tmp/rprobes; for f in rv14_samename rv13_scope rv11_ann rv_nestedfunc rv_param_samename rv_ann_then_assign

FINAL VERDICT: FIX  2026-10-26T19:22:20Z
