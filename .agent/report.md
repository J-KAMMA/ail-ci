# job job-decexact2-11020258  started 2026-11-01T17:59:19Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `cca79f0`.

**Defect:** a plain class attribute bound after a getter-only `@property` in the same class body was ignored by the read/store shadow blockers. Both paths now include the property owner itself when `_class_defines_plain_attr` is true (`pyboxed2.py:6492`, `:11654`).

**Probes (all match CPython on both `g`/`d` builds):**
- `p_sameclass_after` (0,5,0), `p_sameclass_ann`, `p_sameclass_setter_then_attr`
- `p_sameclass_attr_then_prop` (still raises by name), `p_sameclass_after_via`, `p_sameclass_after_inherit`
- `p_sameclass_after_subprop`, `p_sameclass_after_classstore`, `p_sameclass_after_function`, `p_sameclass_after_deep`
- regressions: `p_prop_ro_regress`, `p_prop_setter_regress`, `p_subplain_regress`, `p_attr_after_prop2`

**Tests:** `test_ail_int64_default`, `test_ail_stdtop1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 678 s, 0 failed. Added a regression test for the same-class case. `update_manifest.py --check` clean. DEVLOG entry added.
[cost $0.0000, opencode tokens {"total": 1295662, "input": 33748, "output": 6060, "reasoning": 11182, "cache.write": 0, "cache.read": 1244672}]
    tool time: bash 12.0 min, edit 0.0 min
        680s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 test_ail_int64_defa
         32s bash   cd /tmp/probes && for p in p_sameclass_after p_sameclass_ann p_sameclass_setter_then_attr p_sameclass_attr_the
          8s bash   mkdir -p /tmp/probes && cd /tmp/probes && cat > p_sameclass_after.py <<'EOF' class A:     @property     def x(
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline -8 && git status --short
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 3000 python3 tools/par_check.py -j 2 test_ail_int64_defa
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git diff --stat && git diff -- AIL_CURRENT/python/pkg-v12/pyboxed2.py AI
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rn "_class_defines_plain_attr" --include=*.py . | head -50

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: `job decexact2` (same-class property shadowing)

**What the change really does.** Removes `d != c` from both property shadow-blocker lists (`pyboxed2.py:6492`, `:11655`), so a class's own later plain binding of the property name now blocks its property for read and store. Plus one regression test, DEVLOG, manifest hashes. This matches the report; no hidden change.

**Probes (HEAD, both `g`/`d`; base where noted).**
- Review defect fixed: `p_sameclass_after` → `0,5,0` exit 0 (base: `1` then `AttributeError: property 'x' ... no setter`, exit 1).
- Same-class paths match CPython: via argument/list/dict, annotation with value, property+setter then attr, repeated binding, class-level store, `+=`/`*=` augmented store, tuple-unpack store, `__init__` instance attr.
- Subclass/interaction: `p_subprop_then_plain`, `p_subplain_after_subprop`, `p_subsetter_plain`, `p_owner_subsetter_prop`, `p_two_owners_plain`, `p_subprop_plain_base_inst` all match (including exit statuses and error class/message).
- Annotation-only `x: int` correctly does not shadow (same on base).
- Worker's named probes `p_sameclass_after{,_via,_inherit,_subprop,_classstore,_function,_deep}`, `p_sameclass_ann`, `p_sameclass_setter_then_attr`, `p_sameclass_attr_then_prop`, `p_attr_after_prop2`, `p_prop_ro_regress`, `p_prop_setter_regress`, `p_subplain_regress`: all match CPython.
- Non-feature C unchanged: `p_plain_nonfeature` and `p_prop_no_plain` `program.c` byte-identical base vs HEAD via `--debug-dir`.

**Claims.** Commit, both blocker edits, regression test, DEVLOG, `update_manifest.py --check` clean: verified. All listed probes: verified (2 via equivalents). "5 modules, 678 s": only the edited module + safetynet rerun here.

**Tests.** `test_ail_int64_default` + `test_ail_safetynet`: 2 modules, 455 s, 0 failed.

**Pre-existing (identical on base and HEAD, does not block):** `p_method_after_prop` (property then plain method in the same body: HEAD/base `AttributeError: 'A' object has no attribute 'x'` vs CPython bound method then `5`).

**Unverified:** `test_ail_stdtop1`, `test_ail_files`, `test_ail_corpus_findings3`; icount (generated C is unchanged for all non-feature programs).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 734650, "input": 31793, "output": 5857, "reasoning": 9768, "cache.write": 0, "cache.read": 687232}]
    tool time: bash 9.1 min
        456s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 2400 python3 ../tools/par_check.py -j 2 test
         22s bash   cd /tmp/rprobes && date && for p in p_sameclass_after p_sameclass_via p_sameclass_setter p_sameclass_after_twi
         14s bash   cd /tmp/probes && for p in p_sameclass_after_via p_sameclass_after_subprop p_sameclass_after_classstore p_same
         13s bash   cd /tmp/probes && for p in p_attr_after_prop2 p_sameclass_setter_then_attr p_sameclass_after_inherit p_subplai
         11s bash   cd /tmp/rprobes && cat > p_subprop_plain_base_inst.py <<'EOF' class A:     @property     def x(self):         
          9s bash   cd /tmp/rprobes && cat > p_sameclass_annonly.py <<'EOF' class A:     @property     def x(self):         return
          8s bash   cd /tmp/rprobes && cat > p_init_instance_attr.py <<'EOF' class A:     @property     def x(self):         retur
          5s bash   cd /tmp/rprobes && date && for p in p_method_after_prop p_sameclass_after; do echo "##### $p BASE"; timeout 30

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T19:40:59Z
