# job job-wedge4-11082211  started 2026-11-08T13:13:47Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect.

- `_field_override_subclass` now refuses method lifting when any module-local subclass (or MRO mixin) rebinds a field name (`property`, method, slot, ...) or defines an attribute-protocol hook. Subclasses that only override methods still allow the parent's field-only methods to lift.
- Probes: `m16_readvalue.py` and `m12_readcount.py` now match CPython (`twice 13 calls 2`, two `get n`); additional property, mixin, `__setattr__`, field-method, plain-subclass and `__slots__` probes all match.
- Tests: `test_ail_cpython_hybrid` 15/15 (44.8 s), `test_ail_files` 18/18 (104.7 s), `test_ail_corpus_findings3` 2/2 (241.7 s), `test_ail_safetynet` 5/5 (131.4 s).
- Added regression test, DEVLOG entry; `update_manifest.py` run, `--check` rc 0. Committed as `007ad60`.
[cost $0.0000, opencode tokens {"total": 1518089, "input": 90770, "output": 6791, "reasoning": 9328, "cache.write": 0, "cache.read": 1411200}]
    tool time: bash 9.2 min, edit 0.0 min
        478s bash   bash -c 'ulimit -v 2500000; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; for m in test_ail_files test_ail_c
         45s bash   bash -c 'ulimit -v 2500000; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_
         12s bash   bash -c 'ulimit -v 2500000; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_
         10s bash   mkdir -p /tmp/probes2 && cat > /tmp/probes2/msetattr.py <<'PY' class Base:     def __init__(self, n: int) -> N
          5s bash   mkdir -p /tmp/probes && cat > /tmp/probes/m16_readvalue.py <<'PY' class Base:     def __init__(self, n: int) -
          3s bash   cd /tmp && rm -rf /tmp/probes/out12 && python3 /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py buil
          1s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/DEVLOG.md') s=p.read_text(encoding='utf-8') entr
          0s bash   git status && git log --oneline -10

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** In the hybrid only, `_field_override_subclass` now walks the module's top-level class graph and refuses every method of a plain class when a same-module descendant (or a same-module base of one) binds a field name or defines `__getattr__`/`__setattr__`/`__slots__`, with a named reason; it also adds one regression test and a DEVLOG entry.

**Defect (change-caused).** `_field_override_subclass` indexes `classes[name]` for every base on a descendant's MRO (`AIL_CURRENT/ail_cpython_hybrid.py:284`) without checking that the base is module-local. A very ordinary local mixin whose base is `object` raises `KeyError` in the planner; `build()` catches it and silently disables the whole extension.

Probe `/tmp/rprobes/p_local_mixin_object.py`:

```python
class Mixin(object):
    pass
class Base:
    def __init__(self, n: int) -> None: self.n = n
    def twice(self) -> int: return self.n + self.n
class Sub(Base, Mixin):
    pass
s = Sub(3); print('twice', s.twice())
print('base', Base(3).twice())
```

CPython and hybrid stdout match (`twice 6` / `base 6`, exit 0). But the build report is wrong:
- base (`work`): `{"accelerated": [], "rejected": {"Base.twice": "not a typed candidate, stays in CPython"}, "note": null}`
- HEAD: `{"accelerated": [], "rejected": {}, "note": "no extension: 'object'"}`

Expected: a named per-method refusal (as on base) and no exception; actual: a planner `KeyError: 'object'` turned into a generic `no extension` note. This also falsifies the report's unqualified "MRO mixin" claim for a non-local/`object` base. `class Sub(Base, object): pass` (`/tmp/rprobes/p_object_base2.py`) shows the same.

**Probes.** `m16_readvalue` now matches CPython and `Base.twice` is rejected with `subclass 'Sub' can change field access...`; `p_mixin_sub` (local mixin property), `p_twolevel_sub`, `p_slots_sub`, `p_setattr_sub` all refuse by name; `p_plain_sub` still accelerates `Base.twice`; `p_nested_sub`, `p_alias_sub`, `p_if_sub`, `p_cond_sub`, `p_dynamic_sub` fall back safely (analyzer refuses the module). General/default builds match CPython for `m16_readvalue` and `p_nonmethod`; `--debug-dir program.c` is byte-identical HEAD vs `work` for `p_nonmethod`.

**Pre-existing (not blocking).** `/tmp/rprobes/p_base_rebind.py` (assigning `Base.n = P()` after the class body) gives `twice 22 calls 1` / `base 24 calls 2` on both HEAD and `work`, vs CPython `23/2` and `27/4`. Same batching root cause, but not the subclass defect the review named.

**Tests.** `test_ail_cpython_hybrid` ok 47.1 s (15 tests), `test_ail_safetynet` ok 138.9 s, `test_ail_files` ok 105.1 s, `test_ail_corpus_findings3` ok 237.1 s; `python3 tools/update_manifest.py --check` rc 0.

**Report claims.** Verified: review defect fixed (`m16`), property/mixin/slots/`__setattr__` refusals, plain-subclass lifting, test times/counts, manifest. False: "MRO mixin" is not handled when the mixin/base is not module-local (planner `KeyError`). Unverified: `m12_readcount` (not present here), exact pre-fix accelerated set, instruction counts (planning-only change).

VERDICT: FIX
1. `_field_override_subclass` raises `KeyError` on a descendant whose MRO contains a non-module-local base (e.g. `class Mixin(object)`, `class Sub(Base, object)`). Probe `/tmp/rprobes/p_local_mixin_object.py`; expected a named refusal and `"note": null`, actual `{"accelerated": [], "rejected": {}, "note": "no extension: 'object'"}`. Guard `classes[name]` at `AIL_CURRENT/ail_cpython_hybrid.py:284` (skip/refuse unknown bases) and add a test.
[cost $0.0000, opencode tokens {"total": 2087217, "input": 99316, "output": 11857, "reasoning": 34412, "cache.write": 0, "cache.read": 1941632}]
    tool time: bash 7.6 min
        377s bash   date; cd /home/runner/work/ail-ci/ail-ci && ulimit -v 2500000; python3 tools/par_check.py -j 2 test_ail_cpytho
         14s bash   cd /tmp/rprobes; for p in m16_readvalue p_nested_sub p_alias_sub p_if_sub p_plain_sub p_mixin_sub p_twolevel_s
          9s bash   cd /tmp/rprobes; for p in p_object_base2 p_plain_sub m16_readvalue; do echo "===== BASE $p"; bash rh.sh /tmp/r
          9s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import ast, importlib.util, json spec=impor
          6s bash   date; cd /tmp/rprobes; for p in m16_readvalue p_nonmethod; do echo "===== cmp $p"; bash ~/tools/cmp.sh /tmp/rp
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import ast, importlib.util, json spec=impor
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import ast, importlib.util, json spec=impor
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import ast, importlib.util spec=importlib.u

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the reviewer's defect and committed as `e9775ef`.

- `_field_override_subclass` now treats any non-module-local MRO base (`object`, builtins, imports) as unverifiable and refuses the parent class's methods by name instead of raising `KeyError` and disabling the extension.
- Added `test_subclass_with_uninspectable_base_refuses_by_name` covering both `class Mixin(object)` and `class ViaObject(Base, object)`.
- Probes: `p_local_mixin_object` and `p_object_base2` now match CPython, rejected `Base.twice` with a named reason, no `note`; `p_plain_sub` still accelerates; `m16_readvalue`/`p_mixin_sub`/`p_twolevel_sub`/`p_slots_sub`/`p_setattr_sub` still refuse by name. General/default probes unchanged.
- Tests: `test_ail_cpython_hybrid` 45.9s, `test_ail_safetynet` 133.0s, `test_ail_files` 105.9s, `test_ail_corpus_findings3` 247.5s — 4 modules, 0 failed. `update_manifest.py --check` passes (manifest updated before tests).
[cost $0.0000, opencode tokens {"total": 1184580, "input": 37532, "output": 5116, "reasoning": 6828, "cache.write": 0, "cache.read": 1135104}]
    tool time: bash 5.3 min, edit 0.0 min
        286s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 2500000; python3 tools/par_check.py -j 2 test_ail_cpython_hybr
         14s bash   cd /tmp/rprobes && for p in p_plain_sub p_mixin_sub p_twolevel_sub p_slots_sub p_setattr_sub m16_readvalue; do
          8s bash   cd /tmp/rprobes && for p in p_local_mixin_object p_object_base2 m16_readvalue p_nonmethod; do echo "===== cmp 
          4s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 2500000; python3 -X utf8 -B -m unittest -q test_ai
          2s bash   cd /tmp/rprobes && bash rh.sh /tmp/rprobes/p_local_mixin_object.py /home/runner/work/ail-ci/ail-ci; echo =====
          1s bash   cd /tmp/rhsDYS && cat out/build.json; echo; cd /tmp/rprobes && bash rh.sh /tmp/rprobes/p_nonmethod.py /home/ru
          1s bash   cd /tmp/base && git log --oneline -3 2>/dev/null; ls AIL_CURRENT/ail_cpython_hybrid.py 2>/dev/null && cd /tmp/
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c

## review 1
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** It adds `_field_override_subclass`: a plain class's methods are refused by name when a module-local descendant (or a local class on its MRO) binds a field name or an attribute hook; any descendant whose MRO contains a non-module-local base is also refused (commit e9775ef turns the previous `KeyError` into a named per-method refusal). Two tests are added.

**Defect found: none caused by this change.** The review's defect is fixed: `m16_readvalue` now refuses `Base.twice` (`subclass 'Sub' can change field access...`) and matches CPython (`twice 13 calls 2` / `base 6`); base still prints `twice 12 calls 1`. `p_local_mixin_object` and `p_object_base2` match CPython with a named refusal and `note None`; `p_plain_sub` still accelerates `Base.twice`. Alias/conditional/decorated/dynamic/nested/post-rebind probes all either match CPython or are refused, with no crash.

**Pre-existing (identical on base, not blocking).**
- `p_base_rebind` (`Base.n = P()` after the class body, with a data descriptor): expected `twice 23 calls 2` / `base 27 calls 4`; actual `22/1` and `24/2` on both HEAD and base. `_plain_class` only inspects the class body.
- `q_dup_sub` (subclass with `@property n`, later shadowed by `class Sub: pass`, old class kept via alias): expected `twice 13 calls 2`, actual `12/1` on both HEAD and base; the `classes` name-keyed dict loses the earlier subclass.

**Claims verified.** The named reason/no-note behaviour, `p_plain_sub` acceleration, unchanged general/default build (`program.c` byte-identical HEAD vs `/tmp/base` for `p_nonmethod`), `update_manifest.py --check` rc 0, and tests `test_ail_cpython_hybrid` 47.8 s + `test_ail_safetynet` 132.7 s, 0 failed.

**Unverified.** Speed (hybrid-only refusal path; no hot-code change expected); `test_ail_files`/`test_ail_corpus_findings3` (worker-reported only); wider suite not run per instructions.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2041869, "input": 76001, "output": 8580, "reasoning": 31144, "cache.write": 0, "cache.read": 1926144}]
    tool time: bash 4.1 min
        134s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 2500000; time python3 ../tools/par_check.py -j 2 t
         23s bash   cd /tmp/rprobes; for p in p_alias_sub p_base_rebind p_classattr_sub p_cond_sub p_decorated_sub p_dynamic_sub p
          9s bash   cd /tmp/rprobes; for p in m16_readvalue p_local_mixin_object p_object_base2 p_plain_sub; do echo "===== BASE $
          9s bash   cd /tmp/rprobes; for p in m16_readvalue p_local_mixin_object p_object_base2 p_plain_sub; do echo "===== HEAD $
          9s bash   cd /tmp/rprobes; for p in p_if_sub p_cond_sub p_post_rebind p_alias_sub p_dynamic_sub p_init_subclass p_nested
          9s bash   cd /tmp/rprobes; for p in p_if_sub p_cond_sub p_post_rebind p_alias_sub p_dynamic_sub p_init_subclass p_nested
          6s bash   cd /tmp/rprobes; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do for p in p_local_mixin_object p_objec
          5s bash   cd /tmp/rprobes; for p in q_post_sub p_post_rebind p_base_rebind; do d=$(mktemp -d /tmp/rhXXXXXX); cp $p.py $d

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T15:16:48Z
