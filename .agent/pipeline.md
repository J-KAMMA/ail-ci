# job job-pre157-10250225  started 2026-10-24T17:30:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114632,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":114352,"duration_api_ms":0,"is_error":true,"num_turns":1,"stop_reason":null,"total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server_tool_use"

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the first still-differing item: attribute reads on a class value (alias, argument, list/dict item, instance attribute, cell, nonlocal). Class attributes now resolve through the class’s base chain; `__name__`, `getattr`/`hasattr`, and missing-attribute text match CPython 3.12.

Commit: `dee7647` (not pushed).

Probes (`cmp.sh`, general + default builds):
- `cv1.py`, `cva.py` — alias, argument, containers, attribute, inheritance, local/cell/nonlocal: both builds same as CPython.
- `cv3.py`, `cvc.py` — `getattr`/`hasattr`, `__name__`: both same.
- `cvf.py` — direct `C.x` regression: both same.
- `pre157_final.py` — int/str/list/dict/tuple/bool/None attrs, function return, unpacking, loop source, missing attr: both same.
- `cv_unicode.py` — refused by name on both builds by the pre-existing non-ASCII literal limit.

Tests on final commit:
- `test_ail_pre157` 1/1 OK
- `test_ail_safetynet` 5/5 OK
- `test_ail_files` 18 tests OK (1 skipped)
- `test_ail_corpus_findings3` 2/2 OK

Manifest updated and `--check` passes. Class-value method reads and class-attribute writes remain separate, uncovered behaviours.
[cost $0.0863, opencode tokens {"total": 9351274, "input": 224041, "output": 21548, "reasoning": 20885, "cache.write": 0, "cache.read": 9084800}]
    tool time: bash 10.3 min
        203s bash   (python3 AIL_CURRENT/test_ail_files.py > /tmp/files.log 2>&1; echo $? > /tmp/files.rc) & (python3 AIL_CURRENT/
        117s bash   (python3 AIL_CURRENT/test_ail_pre157.py > /tmp/pre157.log 2>&1; echo $? > /tmp/pre157.rc) & (python3 AIL_CURRE
        116s bash   (python3 AIL_CURRENT/test_ail_pre157.py > /tmp/pre157b.log 2>&1; echo $? > /tmp/pre157b.rc) & (python3 AIL_CUR
         47s bash   (python3 AIL_CURRENT/test_ail_files.py > /tmp/filesb.log 2>&1; echo $? > /tmp/filesb.rc) & (python3 AIL_CURREN
         36s bash   for p in /tmp/probes/cv1.py /tmp/probes/cv2.py /tmp/probes/cv3.py /tmp/probes/cva.py /tmp/probes/cvb.py /tmp/p
         29s bash   cat > /tmp/probes/cv_unicode.py <<'EOF' class Échec:     valeur = -7  A = Échec print(A.valeur) try:     print
         17s bash   cat > /tmp/probes/cva.py <<'EOF' class B:     k = 1     tag = "base" class C(B):     k = 2     def __init__(se
         15s bash   mkdir -p /tmp/probes cat > /tmp/probes/cv1.py <<'EOF' class C:     x = 5     def __init__(self):         self.

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** it registers each general-path class's class-body attributes as `(interned name id, module slot)` pairs on the class object, and makes `ail_inst_getattr`, `getattr`, `hasattr` and `__name__` resolve them through the class's base chain, with CPython's text. `ail_check`, `MANIFEST`, `DEVLOG`, `DIFFERENCES` and one new test are updated. This matches the report's description.

**Verified**
- Alias, argument, list/dict item, instance attribute, cell, nonlocal, inheritance, `getattr`/`hasattr`, `__name__`, missing-attribute text: `a_basic2`, `f_containers`, `c_types`, `l_mut` all match CPython on both builds. First listed pre127 item does fail on `/tmp/base` (probes reproduce it) and is fixed on HEAD.
- Class-attr mutation/aliasing (`bytearray`, list, dict) keeps CPython semantics.
- Non-feature program `m_nofeature` unchanged behaviour on both builds.
- Tests on HEAD: `test_ail_pre157` 1/1 OK, `test_ail_safetynet` 5/5 OK; `update_manifest.py --check` passes; commit has the co-author line; diff is compiler/tests/docs only.
- Report's "class-value method reads / class-attribute writes remain uncovered" is true.

**Pre-existing (identical on base, not blocking)**
- Reading a method/function through a class value still raises `AttributeError` (`d_methods`).
- `e.code` on an exception instance (class attrs are not copied to exception instances) (`e_exc`).
- Class attribute named `args` hits the exception-args special case (`j_special`, same on base).

**Not checked:** speed (`tools/icount` fails with `perf_event_open: Permission denied`; wall time 5 ms both builds, no signal), `test_ail_files`/`test_ail_corpus_findings3` (not re-run per instructions), `cv_unicode` refusal.

VERDICT: FIX

1. Duplicate class-body assignment: alias/`getattr` return the first value, CPython (and AIL's own direct `C.x`) returns the last. Probe `/tmp/rprobes/b_dup.py` (`class C: x=1; x=2`): expected `2 / 2 / 2`, HEAD prints `1 / 2 / 1` on both builds. Also `/tmp/rprobes/g_dup2.py`: expected `4 2`, actual `4 1`. Cause: `pyboxed2.py:2349` registers every duplicate, while `ail_class_attr_find_id` returns the first, whereas the direct path (`pyboxed2.py:5055`) uses `hits[-1]`.
2. Base-chain walk ignores a subclass's own methods/properties, so it returns a shadowed base class attribute. Probe `/tmp/rprobes/h_shadow2.py` (`class B: x=1` / `class C(B): def x(self): ...`): expected `<function C.x ...>` then `10`, HEAD prints `1` then `10` on both builds. `k_prop.py` shows the same for a subclass property (expected property object, HEAD `1`). The lookup in `ail_class_attr_find_id` must stop at a class that defines the name as a method/property.
3. Array-entry shape (only def/class at top level) never runs `_init_class_attrs`; the class-attribute slot stays zero. Probe `/tmp/rprobes/i_array2.py` (`class C: x=5` / `def f(xs): A=C; print(A.x)`), built and run with an empty input file: HEAD prints `<unbound>`, expected `5` (base at least raised `AttributeError`). `_array_entry_main` gets `setup_lines` but not `main_ctx`'s class-attr initialisation.
[cost $0.0348, opencode tokens {"total": 1411223, "input": 93320, "output": 7557, "reasoning": 20618, "cache.write": 0, "cache.read": 1289728}]
    tool time: bash 4.3 min, write 0.0 min
        119s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         21s bash   cd /tmp/rprobes; for p in a_basic b_dup c_types d_methods e_exc; do echo "===== $p HEAD"; bash ~/tools/cmp.sh 
         18s bash   cd /tmp; mkdir -p spd; cd spd; cp ~/corpus/gdev/g11_034.py p.ail; python3 p.ail | tail -2; for tag in head bas
         17s bash   cd /tmp/rprobes; echo "===== l_mut BASE"; bash ~/tools/cmp.sh /tmp/rprobes/l_mut.py /tmp/base 2>&1 | grep -v '
         17s bash   cd /tmp/rprobes; for p in l_mut m_nofeature; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rprobes/$p.py /
         13s bash   cd /tmp/rprobes; for p in a_basic2 f_containers g_dup2; do echo "===== $p HEAD"; bash ~/tools/cmp.sh /tmp/rpro
         13s bash   cd /tmp/rprobes; for p in b_dup d_methods e_exc; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes/$p.
         12s bash   cd /tmp/rprobes; for p in h_shadow j_special k_prop; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp/rprobes

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all three review defects and committed as `db874b4`.

- `b_dup`/`g_dup2` now match CPython; `h_shadow2`/`k_prop` are refused by name; `i_array2` prints `5` on both builds.
- Probes `/tmp/probes`: `p_dup`, `p_order`, `p_containers` match CPython on both builds; `p_array` (empty input) = `3 1 base base [2, 3] 3 3` on both; `p_method_arg` is refused by name.
- Tests: `test_ail_pre157` 4/4, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass; `update_manifest.py --check` passes.
- Commit has the co-author line; only compiler/tests/docs changed.
[cost $0.0568, opencode tokens {"total": 4416971, "input": 130867, "output": 15724, "reasoning": 25004, "cache.write": 0, "cache.read": 4245376}]
    tool time: bash 11.2 min
        331s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre157 test_ail_safetynet test_ail_files test_ai
        124s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet 2>&1 | tail -30
         52s bash   cd /tmp/rprobes; R=/home/runner/work/ail-ci/ail-ci; for p in b_dup g_dup2 h_shadow2 k_prop d_methods a_basic a
         29s bash   cd /tmp/rprobes; R=/home/runner/work/ail-ci/ail-ci; for p in b_dup g_dup2 h_shadow2 k_prop d_methods a_basic a
         22s bash   R=/home/runner/work/ail-ci/ail-ci; for p in p_dup p_order p_containers; do echo "########## $p"; bash ~/tools/
         22s bash   R=/home/runner/work/ail-ci/ail-ci; for p in p_dup p_order p_containers; do echo "########## $p"; bash ~/tools/
         22s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_pre157.py') s=p.read_text() old=""" cla
         21s bash   cd /tmp/rprobes; for p in b_dup g_dup2 h_shadow2 k_prop i_array2; do echo "########## $p BASE"; bash ~/tools/c

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** registers each user class's attributes (name id → shared module slot) on the class object and resolves class-value attribute reads through the base chain at run time; also adds class-body ordering, method/property shadow sentinels, array-entry class-attribute initialisation, and a new `infer_kind` rule that treats any `ast.Name` equal to a class name as that class value.

**Probes** (`bash ~/tools/cmp.sh`, both builds unless noted):

| probe | CPython | HEAD | base |
|---|---|---|---|
| `sources.py` (arg/list/dict/tuple/return/getattr/`__name__`) | match | match | AttributeError |
| `mutate.py` (shared list attr, alias mutation) | match | match | AttributeError |
| `order.py` (duplicate attr, method then attr) | match | match | AttributeError |
| `via_instance.py` (instance attr, loop, dict of list) | match | match | AttributeError |
| `missing.py` (missing attr text, getattr default, hasattr method) | match | match | NotImplementedError |
| `branch_alias.py` (alias assigned in both branches) | match | match | AttributeError |
| `shadow_local.py`, `shadow_param.py`, `alias_rebind.py`, `global_rebind.py` | see defects | wrong value | AttributeError |

**Defects**

1. Local/parameter name shadowing a class name silently reads the wrong class (`pyboxed2.py:3541` `infer_kind` ignores the local binding; `expr_Attribute` then resolves statically).
```
class A:
    x = 1
class B:
    x = 2
def f():
    A = B
    return A.x
print(f())
```
Expected `2`; both builds print `1` (base: AttributeError, so the change caused the wrong value).
```
class A:
    x = 1
class B:
    x = 2
def f(A):
    return A.x
print(f(B))
```
Expected `2`; both builds print `1`. This is the task's own "class passed as an argument" case.

2. Rebinding a class name at module/global scope is resolved to the original class.
```
class A:
    x = 1
class B:
    x = 2
A = B
print(A.x)
```
Expected `2`; both builds print `1`.
```
class A:
    x = 1
class B:
    x = 2
def f():
    global A
    A = B
    return A.x
print(f(), A.x)
```
Expected `2 2`; both builds print `1 1` (base: AttributeError).

Both are one root cause: the unconditional `if node.id in self.classes: return 'class:' + node.id` in `infer_kind`.

**Report claims**
- "Fixed all three review defects" — misleading: the task asked for one pre-existing difference; the change fixes ordinary class-value reads but introduces the silent mis-resolution above. `test_ail_pre157` does not cover shadowed/rebound names.
- `p_dup`, `p_order`, `p_containers`, `p_array` match CPython: **verified**.
- `p_method_arg` "refused by name": **verified**, but it is a runtime `NotImplementedError`, not a compile-time refusal (the task allowed compile-time refusal).
- `test_ail_pre157`, `test_ail_safetynet` pass: **verified** (`-j 2`, 2 modules, 0 failed). `test_ail_files` / `test_ail_corpus_findings3`: not re-run per reviewer instructions.
- `update_manifest.py --check`, co-author line, only compiler/tests/docs: **verified**.

**Pre-existing:** base fails every class-value read with `AttributeError`/NotImplementedError; that is the difference the task addressed.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`, speed (perf_event_open denied here), worker's `b_dup`/`g_dup2` probes (not present).

VERDICT: FIX
1. Shadowed local/parameter class name gives wrong attribute: `def f(A): return A.x; print(f(B))` expected `2`, actual `1` on both builds.
2. Module/global class-name rebind gives wrong attribute: `A = B; print(A.x)` expected `2`, actual `1`; global variant expected `2 2`, actual `1 1`.
[cost $0.0294, opencode tokens {"total": 1768603, "input": 69183, "output": 6555, "reasoning": 16833, "cache.write": 0, "cache.read": 1676032}]
    tool time: bash 4.4 min
        125s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre1
         25s bash   mkdir -p /tmp/rprobes && cd /tmp/rprobes && cat > shadow_local.py <<'EOF' class A:     x = 1 class B:     x = 
         25s bash   cd /tmp/rprobes; for f in shadow_local shadow_param alias_rebind sources mutate order; do echo "########## $f 
         22s bash   ls /tmp/probes 2>/dev/null | head -40; for f in p_dup p_order p_containers p_array p_method_arg; do if [ -f /t
         17s bash   cd /tmp/rprobes && cat > branch_alias.py <<'EOF' class B:     x = 1 class C:     x = 2 def f(flag):     if fla
         13s bash   cd /tmp/rprobes && cat > global_rebind.py <<'EOF' class A:     x = 1 class B:     x = 2 def f():     global A 
         10s bash   rm -rf /tmp/spd && mkdir -p /tmp/spd && cd /tmp/spd for g in g00_000 g00_002; do   cp ~/corpus/gdev/$g.py src.
          9s bash   rm -rf /tmp/dbgq && mkdir -p /tmp/dbgq/head /tmp/dbgq/base && cd /tmp/rprobes for f in plain nocv; do   for m 

FINAL VERDICT: FIX  2026-10-24T18:27:38Z
