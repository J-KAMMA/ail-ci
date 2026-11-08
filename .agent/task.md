**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
# wedge4: hybrid-native methods and inferred return kinds (the top 2 remaining refusals)

Lane: hybrid
Needs: wedge2

wedge2 (integrated) made indexing native and named every refusal; there are no silent refusals left. It moved the
native share only from 24.7% to 29.9% (29/97 functions in lab/wedge), and gave no speedup. The top remaining refusal
reasons, by profiled self time, are:

| Reason | Share |
|---|---|
| not-a-top-level-function (methods, nested functions) | 20.9% |
| unresolved-return | 20.4% |
| call-can-raise | 13.0% |
| unresolved parameter kinds (`node`, `adj`, `words`, `data`) | ~29% together |

Real libraries are mostly classes, so methods matter most for the coming wedge3 run on real libraries.

## Work, in this order

Stop after each step that lands cleanly.

1. **Methods.** Let a method of a plain class (no metaclass, no `__slots__` tricks, no `__getattr__`) go native when
   its body passes the existing safety gate.
   - `self` attribute reads and writes go through the CPython object. Keep it correct first; fast comes later.
   - Nested functions that capture nothing count the same as top-level functions.
2. **unresolved-return.** Infer the return kind from every `return` in the function, where all of them agree. Where
   they do not agree, refuse by name, as today.
3. **Unresolved parameter kinds.** Use the call sites inside the module and the parameter annotations, when present.
   Never guess: a parameter whose kind cannot be proven stays on CPython.

## Rules

- Output must match CPython byte for byte. Anything not proven stays on CPython with a named reason.
- Do not change the default (non-hybrid) build.

## Tests

Add tests to the hybrid test modules covering:
- methods: attribute reads and writes, a method calling a method, and an exception raised inside a method;
- returns of mixed kinds;
- annotated and unannotated parameters.

Run them one after another under `ulimit -v 2500000`.

## Report

- the native share before and after on lab/wedge;
- the hybrid/CPython ratio for each module;
- the new top refusal reasons;
- test results with times.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
