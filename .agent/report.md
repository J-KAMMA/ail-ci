# job job-pre53-10241240  started 2026-10-24T03:42:04Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
No next steps. The task is complete and committed as `2d9aff1`; the tree is clean except the harness-owned untracked `.agent/pipeline.md`, and `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 8910326, "input": 333565, "output": 24849, "reasoning": 37352, "cache.write": 0, "cache.read": 8514560}]
    tool time: bash 16.3 min
        386s bash   python3 -m unittest -v test_ail_pre53 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        272s bash   python3 -m unittest -v test_ail_pre53 test_ail_safetynet test_ail_files test_ail_corpus_findings3
         31s bash   cat > /tmp/probes/cshadow_localname.py <<'PY' class C:     @property     def p(self):         return 1  def f(
         30s bash   python3 -m unittest -v test_ail_pre53
         24s bash   for p in cattr_property cattr_inherited cattr_alias cshadow_prop2 cshadow_alias cprop_types cprop_data; do ech
         22s bash   for p in cattr_property cattr_inherited cattr_alias cshadow_prop2 cshadow_alias cprop_types cprop_data; do ech
         22s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && echo manifest-ok for p in catt
         22s bash   mkdir -p /tmp/probes && cat > /tmp/probes/cattr_property.py <<'PY' class C:     def __init__(self):         se

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — job-pre53 (commit `2d9aff1`)

**What the change really does.** It adds a compile-time heuristic in the general path that classifies expressions as "carries a class value" (`_is_class_value`), records class-carrying names/containers/fields while compiling assignments (`_track_class_data`), sets `kind='class'` for `D = C` aliases, and then (a) refuses `X.prop` when `X` is class-valued and `prop` is a `@property`, and (b) makes a subclass class attribute suppress the base property getter at runtime.

**Probes (`/tmp/rprobes`, `bash ~/tools/cmp.sh`, both builds, HEAD vs `/tmp/base`)**

| probe | base | HEAD | cause |
|---|---|---|---|
| direct/alias/list/dict/arg/attr property-from-class | runtime `AttributeError` | refused by name | intended |
| `shadow_method`, `shadow_multi` | same as HEAD | same | pre-existing |
| `plain_class`, `alias_construct`, `alias_overwrite_instance`, `ordinary` prop reads | same | same | ok |
| `field_rebind`, `list_mutate`, `list_append`, `dict_mutate` | **match CPython** | **refused** | **new over-refusal** |
| `if_alias` (class alias chosen in `if`) | runtime diff | runtime diff (not refused) | pre-existing, hole in the fix |

**Defects (new, caused by this change)**
1. `field_rebind` — field that held a class is later rebound to an instance; the read is on the instance, but `class_fields` is only added, never removed, so it is refused. Expected `1`, got `not in the subset: reading the property p from the class`.
2. `list_mutate` / `list_append` / `dict_mutate` — a `[C]` list (`{'k': C}` dict) later has an element replaced/appended with an instance; every subscript of the recorded name is assumed class-valued, so the instance read is refused. Expected `1`, got the same refusal. (Did not test `-j`-heavy suites, speed, or runtime/IO; not applicable/under time.)

**Report claims.** "Class attribute now shadows the base property" — verified. "Property read from a class value … refused by name" — verified for direct/alias/container/field/argument, but `if_alias` still differs and is not refused (claim overstated). Refusal markers, manifest `--check`, `test_ail_pre53` + `test_ail_safetynet` on HEAD (0 failed) — verified.

Pre-existing (identical on base, do not block): `alias_plain`, `alias_name`, `alias_local_plain`, `alias_reassign_local`, `shadow_instance_attr`, `if_alias`, `shadow_multi` (multiple inheritance refusal).

Unverified: instruction-count speed check; runtime/IO ownership (change is compile-time except one extra subclass branch).

VERDICT: FIX
1. Over-refusal of instance property reads after a class-carrying field is rebound to an instance (`field_rebind.py`): expected stdout `1`, actual compile refusal with marker `C?-job-pre53-10241240-1`.
2. Over-refusal after a class-carrying list/dict is mutated (`list_mutate.py` `xs[0]=C()`, `list_append.py` `xs.append(C())`, `dict_mutate.py` `d['k']=C()`): expected stdout `1`, actual compile refusal. The container record must be invalidated on element/field mutation, not only on whole-name reassignment.
[cost $0.0000, opencode tokens {"total": 369597, "input": 57806, "output": 3443, "reasoning": 9980, "cache.write": 0, "cache.read": 298368}]
    tool time: bash 3.4 min
         99s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1500 python3 ../tools/par_check.py -j 2 test
         40s bash   cd /tmp/base && for p in /tmp/rprobes/*.py; do n=$(basename $p .py); echo "===== $n BASE"; bash ~/tools/cmp.sh
         37s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do n=$(basename $p .py); echo "===== $n HEAD
         14s bash   cd /tmp/base && for n in field_rebind list_mutate list_append dict_mutate; do echo "===== $n BASE"; bash ~/too
         12s bash   cd /tmp/rprobes && cat > field_rebind.py <<'PY' class C:     @property     def p(self):         return 1  clas
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; git branch --show-curren
          0s bash   date; pwd; git status --short; git log --oneline work..HEAD; echo ---; git diff --stat work..HEAD
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check 2>&1 | tail -3; echo ---; git s

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both review defects and committed on the current branch.

**Commits**
- `49396a0` — invalidate class-carrying fields/containers on rebinding and mutation
- `3e6ce47` — also invalidate when the data is passed to a call (aliases/arguments)

**Probes** (`bash ~/tools/cmp.sh … $PWD`, both general and default builds)

| result | probes |
|---|---|
| match CPython | `field_rebind`, `field_rebind_arg`, `list_mutate`, `list_append`, `list_append_instance`, `list_extend_instance`, `list_iadd_instance`, `list_alias_mutate`, `list_arg_mutate`, `dict_mutate`, `dict_update_instance`, `dict_alias_mutate`, `dict_arg_mutate`, `empty_then_instance` |
| refused by name (expected) | `direct_still_refused`, `field_rebind_back`, `list_item_class`, `list_append_class`, `dict_item_class` |

The reviewer’s four failing probes now all match (`field_rebind`, `list_mutate`, `list_append`, `dict_mutate`). Fingerprint/alias records are shared, so mutation through `ys = xs` also invalidates `xs`. `if_alias` remains the pre-existing difference noted by the reviewer; it was not changed.

**Required tests** (final commit `3e6ce47`, `-j 2`): `test_ail_pre53`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all passed, 0 failed. `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 1801775, "input": 61740, "output": 11810, "reasoning": 17761, "cache.write": 0, "cache.read": 1710464}]
    tool time: bash 17.9 min
        262s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        231s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        219s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
        141s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/*.py /tmp/rprobes/*.py; do n=$(basename "$p" .py); 
         68s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre53_*.py /tmp/rprobes/field_rebind.py /tmp/rprobe
         60s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre53_*.py /tmp/rprobes/field_rebind.py /tmp/rprobe
         40s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre53_*.py; do n=$(basename "$p" .py); echo "===== 
         27s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/pre53_field_rebind_arg.py /tmp/probes/pre53_list_ar

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — job-pre53, HEAD `3e6ce47`

**What the change really does.** The diff is four commits, not the two named in the report: it refuses reading a `@property` through a class-valued expression (name/alias/list/dict/field/argument), makes a subclass class attribute suppress a base property getter **on reads**, and the last two commits drop class-carrying container/field records on rebinding, item writes, deletion, mutating methods and calls. The report describes only the last two commits.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both builds, HEAD vs `/tmp/base`)

| probe | base | HEAD |
|---|---|---|
| `cattr_property` (first listed difference) | `AttributeError` | refused by name — fixed |
| `cshadow_prop2` | default-build DIFF | both match CPython — fixed |
| review-0 `field_rebind`, `list_mutate`, `list_append`, `dict_mutate` | match | match — claim verified |
| worker `list_alias_mutate`, `dict_alias_mutate`, `list_arg_mutate`, `dict_arg_mutate` | match | match |
| no-feature plain / class-alias programs | identical `program.c` | identical `program.c` (only temp paths in `native_report.json`) |
| `r2_crossfunc_container`, `r2_crossfunc_field2`, `r2_two_instances2` | match CPython | **new compile refusal** |
| `if_alias` | wrong | wrong, identical — pre-existing |
| `r2_shadow_setter` | `5` expected / `1` got | `5` expected / `2` got |

**Defects**

1. Container records are keyed by bare name and leak across function scopes. `r2_crossfunc_container.py`:
```
class C:
    @property
    def p(self): return 1
def first():
    xs = [C]
    print(len(xs))
def show(xs):
    print(xs[0].p)
def main():
    first()
    show([C()])
main()
```
Expected CPython `1\n1`; HEAD refuses at compile time with `reading the property p from the class ... C?-job-pre53-10241240-1`. Base matches CPython.

2. Field records leak across function scopes. `r2_crossfunc_field2.py` (`first()` does `h.o = C`, `show()` builds a fresh `H()` whose `__init__` sets `self.o = C()` and reads `h.o.p`): expected `True\n1`; HEAD compile-refuses the valid instance read. Base matches.

3. Field records are per class, not per instance. `r2_two_instances2.py`:
```
class H:
    def __init__(self): self.o = C()
def main():
    a = H(); b = H()
    a.o = C
    print(bool(a.o))
    print(b.o.p)
main()
```
Expected `True\n1`; HEAD compile-refuses `b.o.p`. Base matches. The record `(H, 'o')` added by `a.o = C` incorrectly applies to `b`.

4. Shadowing is only fixed on reads. `r2_shadow_setter.py` (base property `x`, subclass `x = 2`, then `b.x = 5; print(b.x); print(B.x)`) expects `5\n2`; HEAD prints `2\n2` (base `1\n2`). The assignment path at `pyboxed2.py:9749` still calls the base property setter. Not identical on base, so it is an incomplete fix rather than pre-existing.

**Pre-existing (identical on base, do not block).** `if_alias`; `r2_two_instances` (`a.o.p` prints a property object); `r2_shadow_delete` decorator refusal; mixed class/instance class-attribute reads through a parameter or a `D = C` alias (`AttributeError: 'type' object has no attribute 'v'`).

**Report claims.** Four review-0 probes fixed — verified. Alias/argument invalidation — verified for the listed probes. “Class attribute now shadows the base property” — false for writes (defect 4). `if_alias` pre-existing — verified. `test_ail_pre53` + `test_ail_safetynet` pass on HEAD (`-j 2`, 0 failed); `update_manifest.py --check` rc 0. `test_ail_files`/`test_ail_corpus_findings3` and speed not rerun (change is compile-time except one shadowed-read branch).

VERDICT: FIX
1. `r2_crossfunc_container.py`: container tracking leaks across functions; expected `1\n1`, actual compile refusal of an instance property read (base matches).
2. `r2_crossfunc_field2.py`: field tracking leaks across functions; expected `True\n1`, actual compile refusal (base matches).
3. `r2_two_instances2.py`: field tracking is per class, not per instance; expected `True\n1`, actual compile refusal (base matches).
4. `r2_shadow_setter.py`: class-attribute shadowing is not applied to assignment; expected `5\n2`, actual `2\n2` (base `1\n2`).
[cost $0.0000, opencode tokens {"total": 1673182, "input": 63368, "output": 8320, "reasoning": 22329, "cache.write": 0, "cache.read": 1579165}]
    tool time: bash 5.4 min
        101s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         35s bash   cd /tmp/base && date && for n in r2_crossfunc_container r2_crossfunc_field r2_same_name_scope r2_two_instances
         33s bash   cd /home/runner/work/ail-ci/ail-ci && date && for n in r2_crossfunc_container r2_crossfunc_field r2_same_name_
         20s bash   cd /home/runner/work/ail-ci/ail-ci && for n in pre53_list_alias_mutate pre53_dict_alias_mutate pre53_list_arg_
         20s bash   cd /tmp/rprobes && python3 - <<'PY' base='''class C:     @property     def p(self):         return 1  def main
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for n in field_rebind list_mutate list_append dict_mutate if_alias; do e
         15s bash   cd /tmp/rprobes && for op in insert extend setdefault iadd; do cat > r2_iso_$op.py <<PY class C:     @property
         14s bash   cd /home/runner/work/ail-ci/ail-ci && for n in cattr_property cshadow_prop2; do for wt in $PWD /tmp/base; do e

FINAL VERDICT: FIX  2026-10-24T04:49:25Z
