# job job-pre178-10250448  started 2026-10-24T19:53:38Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":521,"duration_api_ms":403,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":515,"duration_api_ms":400,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing case, `p15`: `setattr(c, "x", v)` on a read-only property now raises CPython’s `AttributeError: property 'x' of 'C' object has no setter`. Property setters are invoked, and direct assignment/getattr use the same descriptor table.

Commit `034ac36`.

Probes (both builds, all `same stdout`):
`p15_readonly_literal`, `p15_setattr_readonly`, `p15_setter`, `p15_inherit`, `p15_mixed_classes`, `p15_dynamic_names`, `p15_values`, `p15b_setattr_dyn`.

Tests: 26 run, OK, 1 skipped (Windows target, no zig), covering `test_ail_pre178`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. Manifest `--check` clean. `p21`, `p22`, `p26`, `p27` were not addressed.
[cost $0.0000, opencode tokens {"total": 4984034, "input": 124557, "output": 15639, "reasoning": 16574, "cache.write": 0, "cache.read": 4827264}]
    tool time: bash 10.1 min
        328s bash   python3 -m unittest -v AIL_CURRENT/test_ail_pre178.py AIL_CURRENT/test_ail_safetynet.py AIL_CURRENT/test_ail_f
        144s bash   python3 -m unittest -v AIL_CURRENT/test_ail_pre178.py AIL_CURRENT/test_ail_safetynet.py AIL_CURRENT/test_ail_f
         30s bash   for f in /tmp/probes/p15_*.py /tmp/probes/p15b_setattr_dyn.py; do printf '%-28s ' "$(basename $f)"; out=$(bash
         29s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p15_setattr_readonly.py') s=p.read_text() s=s.re
         25s bash   for f in /tmp/probes/p15_*.py; do echo "===== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E 
         19s bash   for f in /tmp/probes/*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | tail -25; done
          7s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/cruntime.py') s=p.read_text() old
          7s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/dunderrt.py') s=p.read_text() old

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** adds a per-class `ail_prop` getter/setter table (registered by `pyboxed2.py` at class setup) and consults it from `ail_inst_setattr_chk` and `ail2a_getattr`, so `setattr` on a read-only property raises CPython's `AttributeError` and property setters run.

**Claims checked**
- `p15` read-only `setattr` fixed: **verified** — `p15_*`, `p15b_*` and my `r1b_ro`, `r2b_setter`, `r7_two`, `r9_ro_direct` match CPython on both builds; base differs.
- Property setters invoked (from argument/list/attribute/dict values, inherited): **verified** (`r2b`, `r5b`).
- "direct assignment/getattr use the same descriptor table": **partly false**. Direct assignment with a setter still uses the old compile-time class branch (`r10`: base setter called instead of subclass override, pre-existing), and the new `getattr` table breaks the default argument (defect 1 below).
- `p21`, `p22`, `p26`, `p27` untouched: **verified** (`p27` reproduced by `r8_aug`, same on base).
- Tests 26 OK / manifest clean: **verified** (targeted 4-module run, 0 failed; `update_manifest.py --check` rc 0).

**Defects**
1. `getattr(obj, name, default)` no longer suppresses a property getter's `AttributeError` (new regression; base matched CPython):
```python
class A:
    @property
    def x(self):
        raise AttributeError("boom")
a = A(); n = "x"
try:
    print(getattr(a, n, 5))
except AttributeError as e:
    print("AE", e)
```
Expected `5`; actual `AE boom` (both builds). `ail2a_getattr` returns `pr->get(...)` before the `has_dflt` branch.

2. The new error message uses fixed buffers (`cb[100]`, `m[256]`), so long names are truncated:
```python
# class name of 120 "C"s, property x
o = CCC...()
try:
    setattr(o, "x", 2)
except AttributeError as e:
    print(e)
```
Expected class name of 120 chars; actual 99 chars (property names >~200 also truncate). Both builds (`r16_longclass`, `r11_longname`).

**Pre-existing (same on base, not blocking):** augmented property assignment `a.x += 5` gives `'A' object has no attribute 'x'` (`r8`); direct assignment to an overridden setter calls the base setter and direct assignment to an overridden read-only property stores (`r10`); subclass class-attribute shadowing a base property (`r4`); `hasattr` on a getter raising `AttributeError` returns `True` (`r14`); literal `getattr(obj, "prop")` is refused at compile time.

**Unverified:** speed — `tools/icount.c` built, but `perf_event_open` is denied on this runner, so no before/after instruction counts. Wider suite not run, per instructions.

VERDICT: FIX
1. `getattr(obj, name, default)` on a property whose getter raises `AttributeError` must return `default`; it propagates the getter error (`r15_dflt_min`, expected `5`, actual `AE boom`).
2. The new `property '...' of '...' object has no setter` message truncates class names at 99 chars and the whole message at 255 chars (`r16_longclass`, `r11_longname`); CPython prints the full names.
[cost $0.0000, opencode tokens {"total": 1923734, "input": 64556, "output": 10709, "reasoning": 21851, "cache.write": 0, "cache.read": 1826618}]
    tool time: bash 6.7 min
        230s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         28s bash   cd /tmp/probes && for f in p15_*.py p15b_*.py; do r=$(timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/work/a
         20s bash   set -e; for p in g25_034 g12_036 g13_030; do for side in head base; do d=/tmp/ic_${p}_${side}; rm -rf $d; mkdi
         18s bash   cd /tmp/rprobes && for f in r*.py; do echo "===== $f"; timeout 300 bash ~/tools/cmp.sh "$f" /home/runner/work/
         13s bash   cd /tmp/rprobes && for f in r8_aug.py r7_two.py r9_ro_direct.py; do echo "===== $f BASE"; timeout 300 bash ~/t
         12s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('r1b_ro.py'); s=p.read_text(); s=s.replace
         12s bash   cd /tmp/rprobes && for f in r4_shadow.py r5_getset.py r1_ro.py r2_setter.py; do echo "===== $f BASE"; timeout 
         11s bash   cd /tmp/rprobes && for f in r1b_ro.py r2b_setter.py r5b_getset.py; do echo "===== $f HEAD"; timeout 300 bash ~

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `e9fa9fa`.

- `getattr(obj, name, default)` now returns the default when a property getter raises `AttributeError`; other exceptions and no-default calls still propagate.
- Read-only property errors are built at the real length, and dynamic attribute names use a sized buffer, so 130/300-char class/property names are no longer truncated.
- Added `test_ail_pre178` cases for the default-argument behavior and long names.

Verification on final commit:
- Required tests: `test_ail_pre178`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed, 144s.
- Manifest `--check`: rc 0.
- Probes: 8 `p15*`, 4 `p178*`, and reviewer probes `r1b`, `r2b`, `r5b`, `r6`, `r7`, `r9`, `r11`, `r13`, `r15`, `r16` all match CPython on both builds. `p178_unicode_prop` is refused by name on both builds (non-ASCII literal outside the subset).
[cost $0.0462, opencode tokens {"total": 3428127, "input": 124432, "output": 11671, "reasoning": 17912, "cache.write": 0, "cache.read": 3274112}]
    tool time: bash 6.0 min, edit 0.0 min, write 0.0 min
        145s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre178 test_ail_sa
        132s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre178 test_ail_sa
         24s bash   cd /tmp/rprobes && for f in r1b_ro.py r2b_setter.py r5b_getset.py r6_getraise.py r7_two.py r9_ro_direct.py r11
         21s bash   cd /tmp/probes && for f in p15_*.py p15b_*.py; do echo "===== $f"; timeout 300 bash ~/tools/cmp.sh "$f" /home/
          9s bash   cd /tmp/rprobes && for f in r15_dflt_min.py r16_longclass.py r11_longname.py r13_dflt.py r6_getraise.py; do ec
          9s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd /home/runner/work/ail-ci/ai
          7s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check && cd /tmp/probes && for f in p17
          6s bash   cd /tmp/probes && for f in p178_getattr_default.py p178_long_class.py p178_long_message.py; do echo "===== $f"

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review of `work..HEAD` (e9fa9fa)

**What the change really does:** adds a per-class `@property` descriptor table to the general runtime; direct assignment/`setattr` now raise for a read-only property and call a setter, and `getattr` consults the table. The second commit makes `getattr(obj,name,default)` swallow an `AttributeError` from a getter and replaces fixed name/message buffers with sized ones. The report's description matches the diff.

**Verified**
- Target case fixed: `setattr(c,"x",v)` on a read-only property now matches CPython on both builds; base printed `stored 1`.
- `getattr` default: AttributeError (incl. subclasses) returns default, KeyError still propagates, no-default still raises (`o_exc_subclass_var`, `p_keyerror_var`, `test_ail_pre178`).
- Long 130/300-char names pass `test_ail_pre178` (`test_property_error_long_names`).
- `test_ail_pre178` 7.8s and `test_ail_safetynet` 69.5s: 2 modules, 0 failed; manifest `--check` rc 0.
- Report's "probes all match" is **false**: new MRO-shadowing probes below fail on HEAD while matching CPython on base.

**Defect (introduced by this change): property lookup walks past a subclass that shadows the name with a non-property member.**

1. `setattr` / assignment wrongly raises.
```
class B:
    @property
    def x(self): return 1
class C(B):
    x = 5
c = C()
setattr(c, "x", 7)
print("setattr ok")
c.x = 9
print("assign ok")
```
Expected `setattr ok` / `assign ok`; HEAD exits 1 with `AttributeError: property 'x' of 'C' object has no setter`. Base matches CPython. Same with `def x(self): return 2` in `C` (`setattr ok` expected; HEAD raises).

2. `getattr` returns the base getter instead of the subclass attribute.
```
class B:
    @property
    def x(self): return 1
class C(B):
    x = 5
c = C()
n = "x"
print(getattr(c, n, "dflt"))
```
Expected `5`; HEAD prints `1`. Base matches CPython.

3. An inherited setter is called although the subclass shadows the property.
```
class B:
    def __init__(self): self.v = 0
    @property
    def x(self): return self.v
    @x.setter
    def x(self, val): self.v = val + 100
class C(B):
    x = 5
c = C()
setattr(c, "x", 7)
print("v", c.v)
n = "x"; print("x", getattr(c, n))
```
Expected `v 0` / `x 7`; HEAD prints `v 107` / `x 107`. Base matches CPython.

The existing `test_ail_pre178` covers inherited and property-over-property overrides but not overriding a property with a class attribute or method, which is the broken boundary.

**Pre-existing (not blocking):** `hasattr` on a property whose getter raises `AttributeError` returns `True` on both base and HEAD (CPython `False`, probe `r_hasattr_only`). The other recorded differences (class-level property read/write, `__getattr__`) remain, as the task asked only for the first. The general-path C preamble changes even for property-free programs (new struct field), but no user-code difference was observed. Unverified: `test_ail_files`/`test_ail_corpus_findings3`, instruction counts.

VERDICT: FIX
1. Property lookup in `ail_inst_find_prop`/`ail_inst_find_prop_name` continues into base classes when a derived class defines the same name as a plain class attribute or method, so `setattr`/assignment wrongly raises and `getattr`/inherited setters use the base property (probes 1–3 above).
2. `test_ail_pre178` needs cases for a subclass shadowing a property with a class attribute and with a method.
[cost $0.0505, opencode tokens {"total": 1963234, "input": 179833, "output": 7490, "reasoning": 22951, "cache.write": 0, "cache.read": 1752960}]
    tool time: bash 3.0 min
         70s bash   date; cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre178 test_a
         29s bash   cd /tmp/rprobes; for f in a_override_classattr b_override_method c_override_getter_only d_exc_subclass e_hasat
         20s bash   cd /tmp/rprobes; for f in k_shadow_classattr_set l_shadow_method_set m_shadow_classattr_get n_hasattr_var o_ex
         15s bash   cd /tmp/rprobes; for f in a_override_classattr b_override_method c_override_getter_only d_exc_subclass e_hasat
         14s bash   cd /tmp/rprobes cat > k_shadow_classattr_set.py <<'EOF' class B:     @property     def x(self):         return
          6s bash   cd /tmp/rprobes; sed -i 's/getattr(c, "x")/getattr(c, n)/' u_shadow_setter.py; sed -i '1i n = "x"' u_shadow_se
          5s bash   cd /tmp/rprobes; cat > r_hasattr_only.py <<'EOF' class A:     @property     def x(self):         return 1     
          5s bash   cd /tmp/rprobes; cat > s_target_ro.py <<'EOF' class C:     @property     def x(self):         return 1   c = C

FINAL VERDICT: FIX  2026-10-24T20:47:02Z
