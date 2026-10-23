# job job-fuzz57-10231355  started 2026-10-23T04:56:39Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed: read-only `@property` assignment silently stored an attribute; now general path raises CPython’s `AttributeError` (subclass-accurate) and typed path refuses by name.

Commit `2e94aea`. Final required tests on that commit: `test_ail_fuzz57`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed. Manifest `--check` passes. New `test_ail_fuzz57.py` has 4 tests.

Probes (`cmp.sh`, both builds):
- `p_prop1`, `p_prop_ro`, `p_prop_ro_uncaught`: same stdout
- `p57_basic_setter`, `p57_nested_getters`, `p57_readonly_alias`, `p57_readonly_sources`, `p57_readonly_subclass`, `p57_readonly_types`: same stdout
- `p57_class_level`, `p57_delete`: refused by name
- Other pre-existing differences, also reproduced on base: `p57_augassign` reports `'C' object has no attribute 'x'` instead of “property … has no setter”; `p57_getattr_fallback` lacks `__getattr__` fallback.

No `DIFFERENCES`/`DEVLOG` file exists in this export, so no record rows were added.
[cost $0.0000, opencode tokens {"total": 4185881, "input": 104285, "output": 12903, "reasoning": 12373, "cache.write": 0, "cache.read": 4056320}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change reviewed:** `2e94aea` — read-only `@property` assignment now raises instead of silently storing.

**Verification run**
- `test_ail_fuzz57`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` on HEAD: 4 modules, 0 failed.
- `tools/update_manifest.py --check`: passes.
- Generated C for a program with no properties is byte-identical to base (`--debug-dir`).
- Probes on both builds; base used at `/tmp/base57`. Read-only assignment works for direct variable, list item, attribute, dict value, aliasing, repeated loops, inherited properties, and inherited setters (`p1`, `p2`, `p3`, `p7`, `p16`, `p25`, `p31`–`p33`).

**Defects**
1. **A property shadowed by a non-property in a subclass now wrongly raises.** The owner scan includes any ancestor property without checking which class in the MRO first defines the name.
   Probe `p17`:
   ```python
   class Base:
       @property
       def x(self): return 1
   class Sub(Base):
       def x(self): return 5
   s = Sub()
   try:
       s.x = 7; print("stored")
   except AttributeError as e: print("AE", e)
   ```
   Expected `stored` (CPython, and base build). Actual on HEAD both builds: `AE property 'x' of 'Sub' object has no setter`. Same with a class attribute shadow (`Sub.x = 5`, `p18`): base matches CPython, HEAD raises.
2. **Error text is truncated for long names.** `ail2_prop_no_setter` uses `char tn[80], buf[200]`.
   - `p8`: class name of 120 `C`s → CPython prints all 120; HEAD prints 79.
   - `p34`: property name of 200 `q`s → CPython message length 239; HEAD 199.
   Both builds affected.

**Pre-existing (base identical)**
- `setattr(c, "x", v)` on a read-only property silently stores (`p15`).
- Class-level property read/assignment (`p22`, `p21`) runs and fails, rather than being refused by name.
- `__getattr__` fallback missing (`p26`); augmented assignment reports `'C' object has no attribute 'x'` (`p27`).
- `del c.x` is refused by name (`p20`), matching the report.

**Report claims**
- Intended read-only fix: verified.
- Typed-path refusal by name: unverified; default build matched general output on every probe I ran.
- Tests/manifest/commit: verified.
- “p57_class_level refused by name”: false for the class-level read/assignment probes I wrote (they run, identical to base).
- Augassign/`__getattr__` pre-existing: verified.
- No `DIFFERENCES`/`DEVLOG` files present: verified.

**Speed:** no effect; no gdev program assigns to a property-named attribute, and the new runtime branch is emitted only for such assignments.

VERDICT: FIX
1. Do not treat an inherited property as the owner when a more-derived class shadows the name with a plain method or class attribute; `p17`/`p18` should print `stored`, as CPython and the base build do.
2. Stop truncating the `AttributeError` text: long class/property names (`p8`, `p34`) must appear in full.
[cost $0.0000, opencode tokens {"total": 1881359, "input": 119460, "output": 10593, "reasoning": 16266, "cache.write": 0, "cache.read": 1735040}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed both defects in commit `1b729e1`.

- Property reads/assignments now follow the first MRO class defining the name; subclass methods/class attributes shadow inherited properties correctly.
- `ail2_prop_no_setter` builds its message from allocated strings, so long names print in full.
- Probes `p8`, `p17`–`p21`, `p34`: same stdout as CPython on both builds. Existing `p57_*` probes passed except the pre-existing augassign/`__getattr__` differences; class-level/delete probes refused by name.
- Final tests: `test_ail_fuzz57`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_dunders` — 42 run, 0 failed, 1 skipped. Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 3150308, "input": 96239, "output": 10291, "reasoning": 15298, "cache.write": 0, "cache.read": 3028480}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Change reviewed:** `1b729e1` (property owner scan + no-setter message), on top of `2e94aea`.

**Verification run**
- `test_ail_fuzz57`, `test_ail_safetynet`, `test_ail_dunders` on HEAD: 3 modules, 0 failed.
- `tools/update_manifest.py --check`: passes.
- Generated `program.c` for a property-free gdev program is identical to base; no speed concern.
- Re-ran the worker's `p8`, `p17`–`p21`, `p34`: all match CPython on both builds.

**Defects**
1. A class that rebinds a property to a class attribute (same class) is now wrongly treated as read-only. Base matched CPython here.
   ```python
   class C:
       @property
       def x(self): return 1
       x = 5
   c = C()
   try:
       c.x = 7
       print("stored")
   except AttributeError as e:
       print("AE", e)
   ```
   Expected (CPython and base): `stored`. Actual HEAD, both builds: `AE property 'x' of 'C' object has no setter`.
2. The new read branch for a subclass whose plain method shadows an inherited property turns a read into a crash. `_property_read` emits `ail_inst_getattr`, which cannot return the bound method.
   ```python
   class Base:
       @property
       def x(self): return 1
   class Sub(Base):
       def x(self): return 5
   print(type(Sub().x).__name__)
   ```
   Expected: `method`. Actual HEAD, both builds: uncaught `AttributeError: 'Sub' object has no attribute 'x'`, exit 1. (Base printed `int`, also wrong, but the change converts it into a new crash; if bound methods are unsupported this should be a named compile-time refusal.)

**Pre-existing (same on base):** `x += 1` on a read-only property reports `'C' object has no attribute 'x'`; `__getattr__` fallback missing. Class-level/delete constructs are refused at build time.

**Report claims**
- Owner scan fixes for `p17`/`p18` and long-name messages `p8`/`p34`: verified.
- “Subclass methods/class attributes shadow inherited properties correctly”: false for reads of a method shadow before assignment (`p1` above); assignment and class-attribute shadow work.
- `p8`, `p17`–`p21`, `p34` same stdout: verified. Class-level/delete refusal: verified by build failure.
- Tests/manifest: verified.

VERDICT: FIX
1. `_attr_definers`/assignment must respect a class attribute binding in the same class as a property: `class C: @property x ...; x = 5` then `c.x = 7` must store, not raise.
2. Reading a method-shadowed inherited property before assignment must not become a new runtime `AttributeError`; either return the method value or refuse the construct by name at compile time.
[cost $0.0000, opencode tokens {"total": 1808467, "input": 168192, "output": 5486, "reasoning": 23525, "cache.write": 0, "cache.read": 1611264}]

FINAL VERDICT: FIX  2026-10-23T05:37:54Z
