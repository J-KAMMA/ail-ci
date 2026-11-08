# job job-wedge4-11081958  started 2026-11-08T10:59:40Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Committed as `b4f79b6`. Here is the report.

## wedge4 report

**What landed**

1. **Methods** — a method of a plain class (no bases/decorators/`__slots__`/attribute-protocol dunder) is lifted to a typed kernel. `self.<field>` reads/writes become typed parameters; the C wrapper reads them with `PyObject_GetAttrString`, runs the result plus one kernel per written field, and stores back with `PyObject_SetAttrString`. A read-only method may call another method of the same class (fields passed in class-declaration order). Field stores are refused unless the value is proved exactly the field kind.
2. **unresolved-return** — inferred from every `return` when they agree; `and`/`or` is inferred only when all operands share one scalar kind (`x or 0` int; `x or True` unresolved). Mixed int/str is still refused by name.
3. **Parameter kinds** — annotations plus this module's own call sites: `Q(1)` fixes constructor/field kinds, `self.plus(k)` fixes a method parameter. Every hint still crosses the wrapper's exact-type check, so a wrong guess falls back.

Two pre-existing defects had to be fixed first: the trap flag was `static` in the unit but `extern` in the wrapper, so **every module with a subscript failed to import its extension and silently ran pure CPython** (this is why wedge2's indexing "native" functions were inert); the flag now has external linkage, `ail_raise_named(AIL_EXC_INDEX)` routes to the same fallback, and the `str` boundary uses `PyUnicode_IS_ASCII` instead of an O(n) scan per call (which made `json_parse` O(n²)).

**Native share, lab/wedge** (`ulimit -v 2500000`, `-j 2`)
- before: **29/97 (29.9%)** — verified from a clean HEAD export
- after: **35/97 (36.1%)** top-level, plus method kernels `Frame.rows` and `Parser.parse_string` → **37 accelerated callables**
- new top-level names: `set_intersect`, `weighted_sum`, `is_simple_email`, `rising_streak`, `is_ident_start`, `is_ident_char`
- profiled native self-time share 5.0% → 13.5% (indicative; loaded shared runner)

**hybrid / CPython ratio** (geomean **1.043x**)
`ast_lint 1.130, bitset_bloom 1.069, csv_parse 0.889, dataframe_group 0.768, edit_dist 0.921, field_valid 0.938, float_loops 0.967, graph_search 1.120, hashing 1.016, json_parse 1.162, matrix 1.240, rolling_stats 0.640, sort_rank 0.829, tokenizer 2.874, tree_build 1.096`.
`tokenizer` regresses because its CPython loops call the now-native two-line helpers once per character and the prototype wrapper (~300 ns) costs more than the call it replaces; correctness is unaffected.

**New top refusal reasons** (profiled self-time share)
`list-return-kind 19.9%`, `call-can-raise 14.8%`, `not-a-top-level-function 14.4%` (was 20.9%), `tuple-parameter 12.1%`, `nested-list-annotation 8.0%`, `list-str-parameter 5.1%`, `module-constant 3.7%`, `typed-clone-not-wired 3.3%`, `bytes-parameter 2.8%`, `division-can-raise 2.5%`. `indexing-can-raise` is gone; `unresolved-return` now contains only list-returning builders outside the scalar return ABI.

**Tests on the final commit** — 5 modules, 0 failed, 388 s:
`test_ail_safetynet` 199.7 s, `test_ail_corpus_findings3` 334.6 s, `test_ail_files` 141.2 s, `test_ail_examples_hybrid` 26.3 s, `test_ail_cpython_hybrid` 53.0 s (13 tests, including the new method/return/param cases; the method test also calls the native kernel directly, so an extension that failed to import would fail it).

**Probes** (`/tmp/probes/`, `bash ~/tools/cmp.sh` + hybrid build):
- `w4_methods.py` — int/bool/str/list fields, negative index, empty list, method-calls-method, same-typed field order, aliasing, values via attribute/list item/dict value → general same, default same, hybrid same (9 native).
- `w4_returns.py` — bool/int `and`/`or`, empty strings, mixed int/str and int/float refused → all three same (4 native; 3 named refusals).
- `w4_params.py` — annotated, call-site-resolved, conflicting, unannotated ctor/method params, ±2^62 → all three same (8 native; `disagreement` named).
- `w4_widths.py` — values beyond int64 via argument/list item/attribute/dict → standalone refused by name (`int64 constant expression out of range`), CPython and hybrid same (3 native).

**Not done:** nested functions that capture nothing were not lifted; a method containing one stays in CPython with a named reason. I did not implement it rather than change output or closure semantics unproven.
[commandcode stop=end_turn turns=162 out_tokens=141500]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have enough. Here is the review.

**What the change really does** (one line): in the opt-in `build --cpython` hybrid only, it lifts plain-class methods to typed kernels with `self.<field>` read/write crossing the C wrapper, infers return kind from agreeing `return`s (now including same-scalar `and`/`or`), seeds parameter kinds from annotations plus this module's call sites, and fixes two pre-existing extension bugs (the `static` trap flag that made any subscript-bearing extension fail to import, and the O(n) ASCII scan).

**Findings**

1. **Method→method calls bypass CPython dynamic dispatch — wrong output.** The rewriter replaces `self.m(...)` with a direct call to `m`'s kernel, so an override (subclass, instance attribute, or monkeypatched class attribute) is ignored. Probe `/tmp/rprobes/p10_inherit.py`:

```python
class Base:
    def __init__(self, n: int) -> None: self.n = n
    def get(self) -> int: return self.n
    def twice(self) -> int: return self.get() * 2 + self.get()
class Sub(Base):
    def get(self) -> int: return self.n + 100
print(Base(5).twice(), Sub(5).twice())
```
Expected `15 315`, actual `15 15`. `Raiser.get` raising gives CPython `raiser-exc ValueError`, hybrid `raiser 15` (no exception). Same root cause in `/tmp/rprobes/p16_dispatch.py`: `c.get = lambda: 99; c.twice()` expected `198`, actual `2`; `Counter.get = lambda self: 7+self.n` expected `16`, actual `2`. Accelerated: `Base.get`, `Base.twice`/`Counter.get`, `Counter.twice`. Two probes were enough to show it; the report's "a read-only method may call another method of the same class" is exactly the unsound feature. Base has `accelerated: []` for the same probes, so the change introduced it.

No other correctness defect found: method field reads/writes (int/bool/float/list, negative, empty, aliasing, write-then-read, two same-typed fields, `+`/`+=`, INT64_MIN negate and overflow), void methods (refused by name), list-field mutation/subscript stores (refused by name), missing/different-typed fields (fallback), trap and overflow propagation through an inlined callee, non-ASCII `str` fields, `and`/`or` return kinds, call-site parameter hints, and shadowed `len` all match CPython or are refused by name.

**Claims checked**
- Methods lifted, `and`/`or` return inference, call-site and annotated parameter kinds: **verified** (probes p1–p5, p11, p14; worker's `w4_*` probes re-run and match).
- Trap-flag fix: **verified** — base `/tmp/base` build of a subscript program produces `undefined symbol: nth__typed__hybrid_trap` on import (inert extension); HEAD imports and runs native.
- Default (non-hybrid) build unchanged: **verified** — `--debug-dir` `program.c` for a non-feature program is byte-identical on base vs HEAD; diff touches only the hybrid module.
- Native share 29.9%→36.1%, hybrid/CPython ratios, profiled refusal shares, "5 modules 388 s": **unverified**.
- Worker probes listed in the report: I re-ran all four with the hybrid build; all match CPython. Their coverage misses dispatch overrides.

**Tests**: `test_ail_cpython_hybrid` 62.5 s, `test_ail_safetynet` 159.0 s, 0 failed (`-j 2`, `ulimit -v 2500000`).

**Caution (not independently measured)**: the report's own numbers say the now-actually-importing extension makes `tokenizer` 2.874× slower than CPython and the geomean 1.043× slower; if that is accurate it is a real regression for the opt-in mode, though it does not block on correctness.

**Unverified**: native-share and ratio measurements, the other three test modules, speed/instruction counts (the change cannot affect the standalone codegen path).

VERDICT: FIX

1. Method→method calls must not be lifted to direct kernel calls (or must verify the receiver's effective method), because overrides are ignored. Probe `/tmp/rprobes/p10_inherit.py`: expected `15 315` and `raiser-exc ValueError override`, actual `15 15` and `raiser 15`. Same in `/tmp/rprobes/p16_dispatch.py`: expected `instance-shadow 198` / `class-patch 16`, actual `2` / `2`.
[commandcode stop=end_turn turns=69 out_tokens=61154]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Fixed and committed as `c1d794b`. Here is the report.

## What changed

`self.m(...)` is no longer rewritten to a direct kernel call. A method containing any `self.m(...)` call is refused by name (`a call to another method 'm' stays in CPython`) before its kernel is built, so CPython still resolves the attribute dynamically. The callee-field plumbing and `_MethodBody` call rewrite are removed; field-only methods still lift with `self.<field>` through `PyObject_GetAttrString`/`PyObject_SetAttrString`. Default build untouched (only `build --cpython` imports this module).

## Reviewer probes

Re-ran `/tmp/rprobes/p10_inherit.py` and `p16_dispatch.py` on the hybrid:

- p10: `base 15`, `sub 315`, `raiser-exc ValueError override` — matches CPython; `Base.twice` refused by name.
- p16: `instance-shadow 198`, `class-patch 16` — matches CPython; `Counter.twice` refused by name.

## Probes (`bash ~/tools/cmp.sh`, plus hybrid `rh.sh`)

| probe | default/general | hybrid |
|---|---|---|
| `w4_methods`, `w4_returns`, `w4_params`, `w5_dispatch`, `w5_field_methods`, `w5_unannotated_callsite` | same as CPython | same as CPython |
| `w5_dispatch_dynamic` (instance shadow, class patch) | same as CPython | same as CPython |
| `w4_widths` | refused by name (`int64 constant expression out of range`) | same as CPython |

Coverage: int/float/bool/str/list fields, negative/empty, aliasing, write-then-read, `+=`, values via argument/list item/attribute/dict value, subclass and raising overrides, instance shadow, class patch, annotated/unannotated params, agreeing and mixed returns, INT64 widths. The standalone default build's static class-attribute dispatch for `Patch.get = ...` (prints `patch 9`) is pre-existing and unchanged by this hybrid-only patch.

## lab/wedge (census on pre-fix `b4f79b6` vs HEAD)

- wedge2 baseline: 29/97 top-level (29.9%).
- Pre-fix: 35/97 top-level + 2 methods = 37 callables.
- After fix: **35/97 top-level (36.1%) + 2 methods = 37 callables** — identical set; the 9 method-call refusals were already refused under another name.
- New named reason `a call to another method` now covers 9 class methods = 8.7% of profiled CPython self time.
- Top profiled refusal shares now: `unresolved-param` 30.8%, `unresolved-return` 17.4%, `call-can-raise` 14.7%, method-call 8.7%, `to_c-refused` 6.8%, division 4.0%.
- Hybrid/CPython wall ratio: bitset_bloom 1.079, ast_lint 1.131, dataframe_group 0.739, csv_parse 0.892, field_valid 1.011, edit_dist 0.970, float_loops 0.990, graph_search 0.839, hashing 1.039, json_parse 1.284, matrix 1.025, rolling_stats 0.707, sort_rank 1.142, tokenizer 2.553, tree_build 1.012; **geomean 1.043×**.

## Tests on `c1d794b` (`-j 2`, `ulimit -v 2500000`)

`test_ail_safetynet` 79.7 s, `test_ail_corpus_findings3` 137.6 s, `test_ail_files` 61.4 s, `test_ail_examples_hybrid` 14.7 s, `test_ail_cpython_hybrid` 26.5 s — **5 modules, 0 failed, 164 s**. `update_manifest.py --check` passes; tree clean except the harness's untracked `.agent/pipeline.md`.
[commandcode stop=end_turn turns=68 out_tokens=43041]

## review 1
[model commandcode/deepseek-v4.1-flash]
I have everything I need. Final report:

---

**What the change really does.** Hybrid-only (`ail build --cpython`): plain-class methods become typed top-level kernels whose `self.<field>` reads/writes are replayed through `PyObject_GetAttrString`/`PyObject_SetAttrString` by a generated C wrapper, a method containing `self.m(...)` is refused by name, return kinds come from agreeing `return`s, and unannotated parameter kinds come from annotations/call sites; it also removes `static` from the index/key trap flag (a real pre-existing import bug) and uses `PyUnicode_IS_ASCII` at the str boundary.

**Defect found (change-caused, verified against `/tmp/base4`).**

Probe `/tmp/rprobes/m16_readvalue.py`:

```python
class Base:
    def __init__(self, n: int) -> None: self.n = n
    def twice(self) -> int: return self.n + self.n
class Sub(Base):
    def __init__(self) -> None:
        self.i = 5; self.calls = 0
    @property
    def n(self):
        self.calls += 1
        return self.i + self.calls
s = Sub(); print('twice', s.twice(), 'calls', s.calls)
print('base', Base(3).twice())
```

CPython: `twice 13 calls 2` / `base 6`. Hybrid: `twice 12 calls 1` / `base 6` (exit 0). `build.json`: `accelerated ['Base.twice']`, `Sub.n` rejected `not a plain class`. Base: `accelerated []`, same as CPython. The wrapper reads each needed field **once** and re-executes the body; CPython's body reads `self.n` once per occurrence. `_plain_class` gates only the defining class, not subclasses that override a field with a descriptor (`m12_readcount.py` shows the same with prints: two `get n` vs one). A fix is feasible (refuse lifting when the module has a non-plain subclass of that class), so this is not a REJECT.

**Probes (all in `/tmp/rprobes`, run with `~/tools/cmp.sh` + hybrid `rh.sh`).** Match CPython: `m3_early` (early returns, C.f/C.g native), `m4_multi` (multi-field order, loop, `+=`; P.swap refused), `m5_types` (int/float/bool/str fields; T.setint/T.up refused by name), `m6_lists` (list fields, negative/OOB index, mutation refused), `m7_values` (dict/list/attribute values), `m8_dispatch` (field retyped float/bool/str → fallback), `m10_inherit`, `m17_strret`, `m18_toplevelindex` (base `.so` fails with `undefined symbol: at__typed__hybrid_trap`, HEAD imports — report's pre-existing-defect claim confirmed). Failed: `m16_readvalue`/`m12_readcount`. `m11/m13/m14/m15` (partial write-back, `__setattr__` counts) were never accelerated (`not a typed candidate`), so a partial-write double-apply was not reachable/verified.

**Pre-existing (identical on base, not blocking).** `m1_attrproto`: general+default builds fail (`build g/d failed`) on HEAD and base. `m2_propsub`: general/default exit 0 vs CPython exit 1 on HEAD and base.

**Report claims.** Verified: 37 accelerated callables, exactly 2 methods (`Frame.rows`, `Parser.parse_string`), 15/15 wedge modules match CPython (census); 9 `a call to another method` refusals; default build untouched (only `--cpython` imports the module; `--debug-dir` `program.c` byte-identical HEAD vs `work`); `update_manifest.py --check` rc 0; pre-existing trap-flag bug. Not done: nested functions (task step 1 bullet 2) — `m9_nested.py` shows `K.withnested` refused `a nested function captures this method scope` and top-level `inner` neither lifted nor named. False: "inherited field access keeps the subclass's own attribute protocol" holds for *which* protocol runs but not for per-access counts (defect 1).

**Unverified.** Pre-fix "identical set" of 37 (no b4f79b6 build); profiled self-time shares; the other three test modules (`test_ail_files`, `test_ail_corpus_findings3`, `test_ail_examples_hybrid`) — I ran only `test_ail_cpython_hybrid` + `test_ail_safetynet`: 2 modules, 0 failed, 78 s; instruction counts. Spot wall-time (HEAD): tokenizer 2.8×, matrix 1.0×, json_parse 1.2× vs CPython, consistent with the report; the tokenizer regression is real but the default build is untouched.

VERDICT: FIX
1. A lifted field-only method's attribute reads/writes are batched (one `GetAttrString` per distinct field, one `SetAttrString` per written field) instead of one per occurrence in the body. When a subclass of the lifted plain class overrides the field with a descriptor, CPython's per-read semantics change the answer. Probe `/tmp/rprobes/m16_readvalue.py` — expected `twice 13 calls 2` / `base 6`; actual hybrid `twice 12 calls 1` / `base 6` (`m12_readcount.py` likewise prints one `get n` instead of two). `_plain_class` only checks the class that defines the method; subclasses with non-plain bodies (`Sub.n` is in `build.json` as `not a plain class`) must prevent the lift.
[commandcode stop=end_turn turns=53 out_tokens=70066]

FINAL VERDICT: FIX  2026-11-08T13:08:29Z
