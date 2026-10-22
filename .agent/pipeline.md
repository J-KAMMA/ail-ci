# job job-fuzz29-10230630  started 2026-10-22T21:31:32Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `685148c`.

**Cause:** general path copied every class attribute onto each instance, so a class-body `list`/`dict` became per-instance instead of shared. Now each class attribute is lazily cached in a module-lifetime slot and shared by instances and class reads.

**Probes** (`bash ~/tools/cmp.sh`, both builds, all matched CPython):
- `p31`, `q01` shared list/dict, empty, nested, shadow assignment, access via arg/list item/attribute/dict
- `q02` inherited/shared class attrs, subclass redefinition, negative/huge ints
- `q03` nested lists/dicts; `q04` set/bytes/tuple class attrs
- `q05` int64 boundaries, bool/str/float; `q06` class reads before construction

**Tests:** 7 modules, 0 failed, on final commit: `test_ail_fuzz29`, `test_ail_typed_inherit`, `test_ail_dunders`, `test_ail_virtual_dispatch`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`. Manifest update/check pass.

**Other differences seen:** multiple inheritance and `issubclass` are refused by name; assigning a class attribute through the class (`Mid.tag = ...`) still raises `AttributeError` on both builds (same on base, pre-existing); `__dict__` remains unsupported. This export has no `DIFFERENCES.md` or `DEVLOG.md`, so no record rows/entry were added.
[cost $0.0000, opencode tokens {"total": 5043820, "input": 116011, "output": 19221, "reasoning": 20652, "cache.write": 0, "cache.read": 4887936}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Reviewed** `685148c` (`git diff work..HEAD`): `pyboxed2.py` class attributes now lazily cached in module-lifetime slots; new `test_ail_fuzz29.py`. Base worktree `/tmp/base` at `work`.

**Probes run (`bash ~/tools/cmp.sh … HEAD` and `/tmp/base`)**
- Shared list/dict/set/tuple, nested, mutation via arg/list item/dict value/attribute/class read, during iteration, instance shadowing, two independent classes: **match** (`p1,p5,p8,p9,p10,p11,p12,p13,p14,p15,p22`). Base errored on class reads / printed independent lists.
- Inherited shared attr, subclass redefinition, `super().__init__`: **match** (`p5,p8,p17`).
- Nested class, multiple inheritance, `issubclass`, class-attribute assignment: **refused by name / same AttributeError** (`p2,p19,p16,p18`), base same.
- Non-literal class attr from a rebound global: **HEAD silently wrong** (`p20,p21`).
- No-feature programs (`n1,n2`): `program.c` byte-identical to base for both builds; only `native_report.json` paths differ.

**Defect**
`C.attr` where `attr` is a non-literal expression is now evaluated at first read, not at class-definition time:
```python
x = 10
class C:
    y = x + 1
x = 20
def main() -> None:
    print(C.y)
main()
```
CPython: `11`. HEAD: `21` (both builds). Base: runtime `AttributeError: 'type' object has no attribute 'y'` (no stdout). Since base is not identical, this is a new silent wrong answer introduced by the new class-read path; it should either fill slots at the class-definition point or refuse non-literal class reads by name. (`p21`, `[1]` vs `[2]`, same cause.) Instance reads have the same timing bug pre-existing (`p23`, `p3b`, `p3c` wrong on both builds).

**Claims**
- Verified: commit; mechanism; manifest `--check` (rc 0); shared mutable fix; MI/`issubclass`/class-assign refusals; no `DIFFERENCES.md`/`DEVLOG.md`.
- Unverified: exact worker probe files (`p31,q01..q06`) not present; the statement that all probes match is false for the boundary above. Other five test modules were not rerun (per instructions); `test_ail_fuzz29` and `test_ail_safetynet` pass (0 failed, 117s). `__dict__` claim not checked.
- Speed: `tools/icount` unavailable (`perf_event_open: Permission denied`), so not measured; C unchanged for programs without class attrs.

**Pre-existing (identical on base, non-blocking):** `p3b,p3c,p23` (class-attr expression evaluated at construction/read time rather than class-definition time), `p6` (side-effecting class-body expression re-evaluated on each construction), `p2,p16,p18,p19` (refusals / class assign).

**Tests:** `cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_fuzz29.py test_ail_safetynet.py` → 0 failed.

VERDICT: FIX
1. Non-literal class-attribute reads (`C.y`) are evaluated lazily at read time and are now silently wrong: probe above prints `21`, CPython `11` (both builds); base refuses with `AttributeError`. Fill class-attr slots at the class-definition point in the module body, or refuse non-literal class reads by name. Variant `p21` prints `[2]` instead of `[1]`.
[cost $0.0000, opencode tokens {"total": 1582149, "input": 58890, "output": 8307, "reasoning": 25672, "cache.write": 0, "cache.read": 1489280}]

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `d1e4e9b`.

**Fix:** Class-attribute slots are now filled where the class definition executes in the module body, matching CPython's single class-body evaluation. Lazy filling remains only for the array-entry shape where no module body runs. This also stops side-effecting class-body expressions from re-running on every construction.

**Probes** (`bash ~/tools/cmp.sh`, both builds):
- `rev1` rebound global after class body → `11`, matches
- `rev2` `list(vals)` frozen at definition (`[1]`, not `[2]`), matches
- `rev3` side-effecting class attr runs once across instances, matches
- `rev4` inheritance, subclass redefinition, shared mutation via arg/dict, negative/large ints, matches
- `rev6` empty/zero/negative/float/bool/tuple/set/nested, aliasing, instance shadowing, matches
- `rev7` reads via argument, list item, dict value, attribute, matches
- `rev8` classes before/after global rebinding, matches
- `rev5` class attr referencing another class attr is refused by name (same pre-existing unsupported construct on both builds)

**Tests on final commit:** `test_ail_fuzz29`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 0 failed (243s). Additional `test_ail_typed_inherit` and `test_ail_dunders` → 0 failed (141s). Manifest update/check rc 0. No `DEVLOG.md`/`DIFFERENCES.md` exists in this export.
[cost $0.0000, opencode tokens {"total": 1575620, "input": 50509, "output": 6731, "reasoning": 7852, "cache.write": 0, "cache.read": 1510528}]

## review 1
[model opencode/deepseek-v4.1-flash-free]
**Review of `d1e4e9b` (plus `685148c`)**

Change: class attributes now live in module-lifetime slots, evaluated once at the class-definition statement in the module body; class reads go through the slot, instance construction shares it, and a lazy fill remains for the array-entry shape.

**Probes (HEAD vs CPython; base = `/tmp/base`)**
- `p1_shared`: shared list/dict via instance/subclass, class reads, shadowing — match (base fails).
- `p2_deftime`: global rebound after class body, `list()` frozen, side effect once, `None`/`True` — match (base fails).
- `p3_inherit`: Base/Mid/Leaf attr override, shared mutation through subclass — match (base fails).
- `p4_sources`: reads through arg/list item/dict value/attribute; negatives, 1e6, float, bool, str, tuple, `None` — match (base fails).
- `p5_nofeature`: no class attrs — match; generated `program.c` byte-identical to base in both builds (`native_report.json` only differs).
- `p6a`: dataclass `default_factory=list` still per-instance — match.
- `p7`, `p9`, `p10`, `p12`–`p15`, `p18`, `p20`, `p21`, `p24`: array-entry, `Base.attr` in methods, mutation during iteration, augmented assignment, `super().__init__`, class aliasing, defaults, comprehensions/slices, cross-class attr reference, array-entry lazy fill — match (base fails most).
- `p22`/`p23`: within-class attr reference and duplicate class names — named refusal, identical on base.
- `p16b`: `main()` never called — existing named refusal, identical on base.

**Pre-existing (identical on base, non-blocking)**
- `p8`: class-level assignment `C.v = [...]` unsupported.
- `p11`: attribute read through class alias `g = C` unsupported.
- `p19`: attributes on exception subclasses not copied.
- `p17`/`p17b`: huge ints beyond 64-bit produce `integer overflow` (module-level too).
- `p6b`: dataclass field defaults not exposed as class attrs.
- Same-class attr reference (`rev5`/`p22`) refused by name.

**Report claims**
- `d1e4e9b` commit and manifest check (`rc 0`) — verified.
- rev1–rev4, rev6–rev8 match CPython; rev5 refused by name on both builds — verified.
- Definition-time evaluation and one-shot side effects — verified (p2, rev3).
- Lazy fill only for array-entry — verified by code and `p24` (87 on both builds).
- "No DEVLOG/DIFFERENCES" — verified absent.
- `test_ail_fuzz29` + `test_ail_safetynet`: re-run on HEAD, **0 failed** (117s).
- Additional modules and files/corpus_findings3 not re-run (outside reviewer protocol).
- Speed: `tools/icount.c` cannot run here (`perf_event_open: Permission denied`); 20-run wall clock and outputs on `g25_032`, `g25_034`, `g14_030` identical HEAD vs base, no visible regression.

No defect attributable to this change was found.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1795164, "input": 60030, "output": 9844, "reasoning": 19946, "cache.write": 0, "cache.read": 1705344}]

FINAL VERDICT: ACCEPT  2026-10-22T22:35:31Z
