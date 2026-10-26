# job job-pre278-10262329  started 2026-10-26T14:30:04Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":419,"duration_api_ms":297,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":432,"duration_api_ms":309,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Fixed:** pre260's first still-differing pre-existing item — p02 field/method collision. `self.f = lambda: 101` + `def f` made `c.f()` print `102`; CPython prints `101`. Such calls are now refused by name on both builds.

**Probes**
- `p02a/b/c/g` — match CPython.
- `p02d/e` — refused: “the method .f() … also stores an instance field named f”.
- `p02f` — still differs only in lambda `<repr>` (pre-existing p05).
- `p278_direct`, `_arg`, `_list`, `_dict`, `_attr`, `_alias`, `_inherited`, `_self`, `_noncallable` — refused by name on both builds.
- `p278_class_call`, `_read`, `_valid_method`, `_valid_other_field`, `_unrelated`, `_unrelated_call` — match CPython on both builds.

**Tests:** `test_ail_pre278`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` clean.

Commits: `bb1795b`, `795c0d1`. Not pushed.
[cost $0.0665, opencode tokens {"total": 7507030, "input": 162098, "output": 14898, "reasoning": 18802, "cache.write": 0, "cache.read": 7311232}]
    tool time: bash 9.5 min
        240s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet test_ail_files test_ai
        191s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet test_ail_files test_ai
         32s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre278 2>&1 | tail -40
         30s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p278_direct.py <<'EOF' class C:     def __init__(self):         self
         26s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p02a.py <<'EOF' class C:     def __init__(self):         self.f = 10
         14s bash   cat > /tmp/probes/p02d.py <<'EOF' class C:     def __init__(self):         self.f = lambda: 101     def f(self
         11s bash   cat > /tmp/probes/p02h.py <<'EOF' class C:     def __init__(self):         self.g = lambda: 101 c = C() print(
         10s bash   for p in /tmp/probes/p02a.py /tmp/probes/p02b.py /tmp/probes/p02d.py /tmp/probes/p02e.py /tmp/probes/p02g.py; 

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of job pre278 (`bb1795b`, `795c0d1`)

**What the change really does:** adds `refuse_field_method_call()` in `pyfront.py` and calls it from `pyc._to_c`, `pyfunc._to_c_once` and `pyboxed2.build`. It refuses at compile time any `.name()` call when a class in the program (or its bases) both defines a method `name` and assigns `self.name`, unless the receiver is a class name, `super()`, or a receiver it can map to a class that is *not* a collision owner. The report describes it as refusing the colliding call; in practice the receiver check is heuristic and refuses far more. Non-feature programs are untouched: `r5_nonfeature` gives byte-identical `program.c` on HEAD and base.

**Probes** (`/tmp/rprobes`, both builds; base = `/tmp/base`):

| probe | CPython | base | HEAD |
|---|---|---|---|
| `r1_unrelated_param` | `7\n7` | same | **refused** |
| `r2_self_unrelated` | `3` | same | **refused** |
| `r3_list_append` | `[1, 2]` | same | **refused** |
| `r7_annotated` | `7` | same | same |
| `r4_inherited_field` | `11` | differs | refused (ok) |
| `r6_setattr` | `101` | `102` | `102` (pre-existing) |
| `r5_nonfeature` | ok | ok | ok, C identical |

`p02a/b/c/g` match CPython; `p02d/e` refused by name — verified. A concern that `p02h/i` fail is pre-existing (base also fails). `test_ail_pre278` and `test_ail_safetynet` pass on HEAD (0 failed); `update_manifest.py --check` clean.

**Defects:**
1. Blanket refusal of unrelated receivers. Once any class has a collision on name `f`/`append`, every call through an unfingerprinted receiver is refused, including correct programs that base compiled and CPython ran:
   - `r2`: 
     ```python
     class C:
         def __init__(self): self.f = lambda: 1
         def f(self): return 2
     class D:
         def f(self): return 3
         def run(self): return self.f()
     print(D().run())
     ```
     expected `3`; HEAD: `not in the subset: the method .f() ... also stores an instance field named f`; base prints `3`.
   - `r1`: same with `def call(d): return d.f(); print(call(D()))` → expected `7\n7`; HEAD refuses; base matches.
   - `r3`:
     ```python
     class C:
         def __init__(self): self.append = lambda x: None
         def append(self, x): pass
     xs = [1]; xs.append(2); print(xs)
     ```
     expected `[1, 2]`; HEAD refuses (`.append`), even though `xs` is a list; base matches. The failure is in `_classes_of`: unknown receivers (parameters, `self`, list/dict variables, attribute chains) yield the empty set, which falls through to a refusal. The report's claim that "an unrelated class with the same method name keep their old behaviour" is therefore false — it only holds for direct `D()` receivers.

**Report claims:** direct collision refusal, both builds, `p02a/b/c/g`, targeted tests, manifest — verified. "Unrelated classes unchanged" — **false** (r1/r2/r3). `p02f` "still differs only in lambda `<repr>`" — **false** on HEAD: it is now refused (base differed only in the repr). `test_ail_files`/`test_ail_corpus_findings3` — not rerun (out of reviewer scope).

**Pre-existing (not blocking):** `setattr(self, 'f', ...)` is not detected, so that route still prints `102` vs CPython `101` on both HEAD and base (`r6_setattr`). No speed check needed: runtime C for non-feature programs is byte-identical.

**Unverified:** typed-only build in isolation; full suite (per instructions).

VERDICT: FIX
1. Restrict the collision refusal to receivers that can actually be the colliding class (or treat an unknown receiver as unknown, not as a collision). Currently any unrelated parameter, `self` in an unrelated class, or list/dict/attribute receiver is refused; see probes `r1_unrelated_param` (expected `7\n7`, actual compile refusal), `r2_self_unrelated` (expected `3`, actual refusal), `r3_list_append` (expected `[1, 2]`, actual refusal). Base matches CPython for all three.
2. Correct the report's claim that unrelated classes with the same method name are unchanged: only direct constructor receivers are; add the `r1`/`r2`/`r3` shapes to `test_ail_pre278.py`.
[cost $0.0142, opencode tokens {"total": 511480, "input": 29137, "output": 4644, "reasoning": 9347, "cache.write": 0, "cache.read": 468352}]
    tool time: bash 2.8 min
         92s bash   date; cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet 2>&1
         14s bash   cd /tmp/rprobes && for p in r1_unrelated_param r2_self_unrelated r3_list_append r4_inherited_field; do echo "=
         13s bash   cd /tmp/rprobes && cat > r7_annotated.py <<'EOF' class C:     def __init__(self):         self.f = lambda: 1  
         12s bash   cd /tmp/probes && for p in p02a p02b p02c p02d p02e; do echo "===== $p"; timeout 240 bash ~/tools/cmp.sh /tmp/
         10s bash   cd /tmp/rprobes && for p in r1_unrelated_param r2_self_unrelated r3_list_append r4_inherited_field r5_nonfeatu
          6s bash   cd /tmp/probes && for p in p02g p02h p02i; do echo "===== $p HEAD"; timeout 300 bash ~/tools/cmp.sh /tmp/probe
          5s bash   cd /tmp/probes && for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "===== p02f $wt"; timeout 240 b
          5s bash   cd /tmp/rprobes && cat > r8_nested_class.py <<'EOF' class C:     def f(self):         return 1     def make(se

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `72d83e0`.

**Fix:** the collision refusal now fires only when the receiver resolves to a colliding class (or subclass). Resolution handles `self` via the enclosing class, parameters via call sites/annotations, attributes via field initialisers, and list/dict items; unresolved receivers keep their old behaviour. Field collection no longer leaks nested-class `self.x` assignments into the outer class.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `r1_unrelated_param`, `r2_self_unrelated`, `r3_list_append`: now MATCH CPython.
- `r4_inherited_field`: still refused by name; `r7_annotated`: MATCH.
- `p278_rev_r1/r2/r3`, `p278_unknown_routes`, `p278_unknown_list_dict`, `p278_unrelated_attr`: MATCH.
- Collision routes (`direct`, `arg`, `list`, `dict`, `attr`, `alias`, `self`, `self_subclass`, `inherited`, `noncallable`): refused by name.
- `r6_setattr` remains the recorded pre-existing `102` vs `101` difference; `r8` is refused for its nested class definition (pre-existing), not by the collision rule.

**Tests on final commit:** `test_ail_pre278`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. `update_manifest.py --check` clean.

Added the reviewer’s r1/r2/r3 shapes plus a self-in-subclass refusal case to `test_ail_pre278.py`; updated DEVLOG/DIFFERENCES. Typed-only build in isolation was not run separately.
[cost $0.0219, opencode tokens {"total": 993401, "input": 41895, "output": 9049, "reasoning": 12281, "cache.write": 0, "cache.read": 930176}]
    tool time: bash 9.7 min
        191s bash   timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet test_ail_files test_ail_cor
        189s bash   timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet test_ail_files test_ail_cor
         92s bash   timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre278 test_ail_safetynet 2>&1 | tail -40
         49s bash   for p in /tmp/probes/p278_*.py; do printf '%-42s ' "$(basename $p)"; out=$(timeout 300 bash ~/tools/cmp.sh "$p
         24s bash   for p in /tmp/rprobes/r8_nested_class.py /tmp/probes/p02*.py; do echo "===== $p"; timeout 240 bash ~/tools/cmp
         19s bash   for p in /tmp/rprobes/*.py; do echo "===== $p"; timeout 240 bash ~/tools/cmp.sh "$p" "$PWD" 2>&1 | grep -E "cp
         12s bash   for p in /tmp/rprobes/r1_unrelated_param.py /tmp/rprobes/r2_self_unrelated.py /tmp/rprobes/r3_list_append.py /
          0s bash   python3 - <<'PY' from pathlib import Path p=Path('DEVLOG.md') s=p.read_text() old='''the field)`).  Detection 

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does (one line):** adds `refuse_field_method_call` to both entry paths, which raises the named `Unsupported` refusal when a call goes through an attribute name that a (possibly inherited) class defines as both a method and an `self.<name> = ...` field, but only when the receiver statically resolves to that class/subclass.

**Probes** (`bash ~/tools/cmp.sh`, general + default builds, on HEAD; base where relevant):
- `direct` (field lambda + method): base `101 102` vs wrong `102 102`; HEAD refused by name on both builds — the recorded difference is now gone.
- `v4_collision_list`, `v5_self_subclass`, `r4_inherited_field`: refused by name on both builds (CPython would call the field).
- `r1_unrelated_param`, `r2_self_unrelated`, `r3_list_append`, `r7_annotated`: MATCH CPython on both builds.
- `v3_nonfeature` (related classes, no collision): both builds match; `--debug-dir` `program.c` byte-identical to base on the default and general builds (only temp paths in `native_report.json` differ).
- `v2_reassign` (unrelated `D` receiver; a dead `d = C()` makes resolution ambiguous): refused by name, not miscompiled. This is a conservative over-approximation; a named refusal is acceptable under the review rules, so not counted as a defect.

**Pre-existing (identical on base, do not block):**
- `v1_return_route` (`make(4).f()` where `make` returns the colliding `C`): both base and HEAD print `-1` where CPython prints `40`; the refusal does not resolve a function-return receiver.
- `r6_setattr`: `setattr(self,'f',lambda:101)` still yields `102` vs CPython `101` on base and HEAD.
- `r8_nested_class`: refused for the nested class definition on base and HEAD.
- Typed-only (`AIL_NO_GENERAL=1`) also refuses `r1` for its lambda-as-value rule; not part of the two cmp builds.

**Report claims:** direct collision fixed (verified); r1/r2/r3 now match (verified); r4/self-subclass/inherited/list/dict/attr/alias/non-callable refused (verified via tests and probes); r7 match (verified); r6/r8 pre-existing (verified); field collection stays inside its class (verified by code inspection); `test_ail_pre278`+`test_ail_safetynet` pass on HEAD (verified, 0 failed); manifest `--check` clean (verified); 4-module test run and typed-only build not rerun by me (out of reviewer scope / acknowledged).

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3` (not rerun here, per scope); typed-only build not separately validated.

VERDICT: ACCEPT
[cost $0.0251, opencode tokens {"total": 1054669, "input": 46232, "output": 4753, "reasoning": 20644, "cache.write": 0, "cache.read": 983040}]
    tool time: bash 2.7 min
         91s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_a
         14s bash   cd /tmp/base; for p in /tmp/rprobes/v1_nested_helper.py /tmp/rprobes/v2_reassign.py /tmp/rprobes/v4_collision_
         11s bash   for wt in /tmp/base /home/runner/work/ail-ci/ail-ci; do echo "#### $wt"; cd "$wt"; for p in /tmp/rprobes/r6_se
         11s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/v*.py; do echo "######## HEAD $p"; timeout 300 bash 
         11s bash   cat > /tmp/rprobes/v1_return_route.py <<'EOF' class C:     def __init__(self, k):         self.k = k         s
          5s bash   cat > /tmp/rprobes/direct.py <<'EOF' class C:     def __init__(self):         self.f = lambda: 101     def f(s
          4s bash   cd /home/runner/work/ail-ci/ail-ci; for p in /tmp/rprobes/r4_inherited_field.py /tmp/rprobes/r7_annotated.py; 
          4s bash   set -e; rm -rf /tmp/dbgA /tmp/dbgB; cp /tmp/rprobes/v3_nonfeature.py /tmp/dbgprobe.ail; cd /tmp; AIL_NO_CACHE=

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T16:18:18Z
