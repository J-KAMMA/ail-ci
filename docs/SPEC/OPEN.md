# Open questions

These are the questions the specification cannot settle from the repository's existing decisions.
Each is marked **owner decision**: the owner chooses, the specification then records the choice.
The cost line names the trade in speed, safety and how easy the language is for an AI to write
correctly (AI-writability).

The list is ordered by how much a choice changes the language. The first section is the set of
decisions that the rest of the specification assumes are settled; the second is the smaller set of
questions that only affect an edge.

## A. Decisions the language cannot avoid

### O1 — Integer precision (owner decision)

The default is int64 with loud overflow (VT2). Is that the final language, or does the language
promise exact integers by default?

* **int64 default** (current): fast, simple, catches a class of bugs, needs `--exact-int` for
  exact code. Cost: an AI that writes Python arithmetic can get a loud stop it did not expect;
  the ports of number-heavy code need a mode.
* **exact by default**: matches Python, no mode, slower (about 20x) and a larger runtime. Cost:
  the whole point of the typed path is speed, so this is a new language, not a mode.
* **int64 with per-value `BigInt`** (VT3, accepted design but not built): fast default, exact
  where named. Cost: a new annotation and a demotion rule; AI-writability is good if the
  annotation is simple.

**Recommendation.** Keep int64 as the default, ship VT3 for exact hotspots, keep `--exact-int` for
whole-program ports. Revisit if the corpus shows int overflow is a common porting failure.

### O2 — Container iteration order (owner decision)

Dicts keep insertion order (settled). Sets iterate in insertion order (VT10, AR9). Is that the
final rule?

* **insertion order** (current): deterministic, reproducible, easy to explain; differs from
  CPython's hash order.
* **hash order**: matches CPython but is not reproducible for `str` across runs and exposes the
  hash. Not compatible with the determinism rule (EO5, EO8).
* **sorted order**: deterministic but changes `set.pop()` and is O(n log n) or needs a sorted
  structure.

**Recommendation.** Keep insertion order. It is the only choice that satisfies "fixed output from
fixed input"; document it as a declared difference (A2) and never expose the hash.

### O3 — Float formatting and `repr` (owner decision)

`repr(float)`, `str(float)` and f-string formatting follow CPython's algorithms for the built
formats. Is the shortest-round-trip spelling part of the language, or is `%.17g` acceptable?

* **CPython shortest repr** (current): exact match, more runtime work.
* **fixed precision**: cheaper, but `print(0.1 + 0.2)` would differ and every float output would
  need a difference row.

**Recommendation.** Keep CPython's shortest repr. Float output is common and a silent formatting
difference would break the compatibility claim for no speed that matters.

### O4 — Class semantics (owner decision)

Single inheritance and `@staticmethod` / `lru_cache` are modelled (VT12); multiple inheritance,
metaclasses and dynamic attribute creation are not. Is that the final class model?

* **the modelled subset**: fast, provable, covers the corpus's classes; refuses some Python
  patterns.
* **full CPython classes**: every pattern works, but the typed path cannot represent the object
  shape statically and many programs fall back to the general path.

**Recommendation.** Keep the modelled subset, grow it from corpus evidence (the class-reach
reports), and never approximate: a class shape outside the subset is refused by name.

### O5 — Identity of values (`is`) (owner decision)

`is` on numbers is refused (MO8); `is None` / `is True` / `is False` are exact. Is that the final
rule, or should `is` on a number mean `==`?

* **refuse** (current): never answers with an address; an AI that writes `x is 5` gets a named
  error and rewrites to `==`.
* **`is` as `==` for numbers**: convenient, but `x is None` and `x is 5` would have different
  meanings and a silent difference from CPython.
* **CPython identity**: exposes the small-int cache and the compiler's folding; not deterministic
  across shapes.

**Recommendation.** Keep the refusal. It is the one rule that makes "no silent difference"
possible for `is`.

### O6 — Exceptions as values or as control flow (owner decision)

AIL has exceptions with values and `try`/`except`, but no exception hierarchy beyond the modelled
built-ins and no user-defined exception with arbitrary attributes. Is that the final model?

* **modelled built-ins + user classes without attributes**: compiles well; some libraries need an
  attribute (`.args`, `.errno`) which the modelled set provides.
* **full Python exceptions**: flexible; requires arbitrary object attributes in the exception
  path and weakens the typed analysis.

**Recommendation.** Keep the modelled set, add attributes from corpus evidence, refuse the rest by
name.

### O7 — Contracts and effects in Python syntax (owner decision)

The specification describes refusals and proofs but not how a program *declares* an effect or a
contract. Options:

* **decorators**: `@pure`, `@no_raise` — readable, but adds decorators to the modelled set and
  collides with CPython's meaning of an unknown decorator (currently a refusal).
* **annotations / comments**: `# ail: pure` — no new syntax, easy for an AI, but easy to get
  wrong and invisible to a type checker.
* **`assert` as a contract**: already Python, but `assert` is removable with `-O` in CPython and
  must be defined here (a refusal? a runtime check? a static assumption?).

**Recommendation.** Use annotations for contracts the compiler checks (a small closed set) and
`assert` for runtime facts; do not add decorators. Write the choice into a chapter before building
it.

### O8 — Recursion limit (owner decision)

The default build has a fixed 50,000-frame guard (MIGRATING item 3), not CPython's 1,000. Is
50,000 the language's limit?

* **fixed 50,000**: more headroom than CPython, same answer for programs under it; a program
  between 1,000 and 50,000 recursions that CPython rejects works here (a declared difference).
* **CPython 1,000**: exact compatibility for the failure case; rejects deep divide-and-conquer
  code.
* **unbounded / heap stack**: matches a "no arbitrary limit" language, but can exhaust memory.

**Recommendation.** Keep a documented fixed limit (currently 50,000), expose it in the difference
table, and never allow a silent stack overflow.

### O9 — `str` width and Unicode (owner decision)

The typed path is UTF-8; the general runtime is 16-bit with named stops above U+FFFF (VT7). Is the
16-bit general runtime the final answer, or must the general path be 32-bit/UTF-8 too?

* **typed UTF-8, general 16-bit** (current): typed code is correct for all Unicode; some general
  shapes stop by name above U+FFFF.
* **general 32-bit**: all code points, more memory per string.
* **all UTF-8**: matches the typed path; more work in the general runtime and a rewrite of the
  string opcodes.

**Recommendation.** Move the general runtime to UTF-8 (the typed path's model) and delete the
16-bit notes; until then, keep the named stops rather than a silent truncation.

### O10 — The concurrency memory model (owner decision)

D1-D5 and R1-R5 (CO3-CO8) are the current model: refuse shared int `+=`, opt-in fixed float
chunking, ordered list buffers, GIL for native container calls, bounded borrow. Is that the final
memory model?

* **the D/R model**: provable, deterministic, covers the typed shapes; refuses some reductions.
* **a full data-race-free model with atomics**: more expressive, much more work and a much larger
  proof obligation.
* **CPython's GIL everywhere**: simple and compatible; no parallel speed-up.

**Recommendation.** Keep the D/R model, build D2/D3 as designed, and add an explicit reduction
(PAR_REDUCE) before widening the model. Never ship a parallel path that is not in the model.

## B. Smaller questions

### O11 — The name and scope of a compatibility mode (owner decision)

`--compat cpython` does not exist (CM2). Options for what a mode would mean:

* **oracle only** (current): `--diff` and the hybrid; no semantics switch.
* **a full mode**: every row answers as CPython does (arbitrary ints, hash order, tracebacks,
  `None` for an unmatched group). Cost: it is a second implementation, not a flag.
* **a per-row set**: `--compat int,set,re` enabling the CPython answer for the named rows; a
  smaller surface, but a combinatorial test matrix.

**Recommendation.** Do not ship a mode until the corpus asks for it. Name the current tools
precisely (CM2) and keep the open question here.

### O12 — FFI safety contract (owner decision)

`trust=True` skips the prototype check for a type the stub cannot spell (MF4). Is that the final
contract, or should `trust=True` also skip ownership/range checks?

* **current**: only the prototype spelling; calls and ownership still checked.
* **full trust**: fewer checks, more speed, a C mistake becomes an AIL crash.

**Recommendation.** Keep `trust=True` narrow. If a C API cannot be expressed, add the type to the
stub language; do not widen trust.

### O13 — Standard-library surface (owner decision)

The built standard library is a declared subset (MF3). Which subset is the language's, and how is
it extended?

* **census-driven**: add a module when the corpus needs it; the census is the list.
* **a fixed small core**: easier to prove, refuses more programs.
* **CPython's whole library via the general path**: matches CPython, but the general path is
  about 20x slower and the modules' effects must still be analysed.

**Recommendation.** Keep the census-driven subset, require a result file for each addition, and
never let a module exist on one path only without saying so.

### O14 — Environment, clock and randomness determinism (owner decision)

`AIL_CLOCK` pins the clock (EO5). What about `random`, `os.environ` and file-system order?

* **pin all three** (`AIL_RANDOM_SEED`, a fixed environ, sorted directory iteration): fully
  reproducible; a program cannot observe the host's order.
* **pin the clock only** (current): reproducible time, but `random` and `os.listdir` still vary.

**Recommendation.** Pin `random` with an explicit seed when the program asks, and sort directory
iteration; document both as part of the input model. Do not pin `os.environ` — it is already an
input the program names.
