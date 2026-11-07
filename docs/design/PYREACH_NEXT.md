# Python typed-path reach: the next five reasons

Date: 2026-11-07. Branch: `job-pyreach9-11071331`. Tree: `0ec0443` (export of `staging:integ`).
Design only; this lane changes no compiler code. The measurement it rests on is
`lab/pyreach9/RESULTS.md` (134 programs: 37 typed, 81 general, 16 refused).

The goal is the owner's: plain Python (the `.py` a person or an AI actually writes) should
build on the typed path. Every step below must keep the rule from `SEMANTICS.md`: a program
either produces **byte-identical stdout/exit to CPython**, or is **refused by name**. A change
that would emit different output is not a fix; it is a regression with better performance.

## How the five were chosen

The task ranks a reason by *programs whose only remaining blocker is that reason* (`sole` in
`RESULTS.md`), counting also the programs it appears in. That gives:

| # | reason | sole | programs touched |
|---:|---|---:|---:|
| 1 | generated-prelude (compiler-injected module code checked as user code) | 5 | 16 |
| 2 | int64-literal | 3 | 4 |
| 3 | parameter-readonly (a container parameter cannot be mutated) | 3 | 4 |
| 4 | generator-yield | 3 | 4 |
| 5 | unsupported-module (`json`, `statistics`, `collections`, `itertools`, ...) | 2 | 21 |

The rest of this document designs those five. The **high-appearance next tier** —
dict-of-containers (18 programs), tuple-unpack (16), mixed-container (15), value-kind-lost
(14), module-level-constant (13), mixed-return-kind (10), bytes-str-methods (9) — is listed
at the end with its own steps, because several of those steps move more programs per hour
than reasons 2-4. They are the pyreach10 batch.

The census is honest about its limits: `strictmode` cannot always locate a refusal, so 41 of
the 97 non-typed blocker lists are `strict_incomplete`. A “sole” program whose list is
complete is a certain move; one whose list is incomplete may reveal a second blocker after
the first is fixed. Each step below says which of its programs are complete-list moves.

---

## 1. Compiler-generated module preludes are checked as user code

### What the census sees

16 programs and 128 blocker instances (the largest single count) are refusals in code the
user did not write. `stdlib5.prelude(name)` reads `python/pkg-v12/prelude_<name>.py` and
`smalllib5.run_array` appends `prelude_array.py`; `pyboxed2`'s regex pass appends `_ail_re_*`.
Those sources are Python, they implement a stdlib module for the general path, and
`strictmode.collect` then checks them with the same subset rules as the program. Examples:

- `prelude_array.py`: `_AilArray.__init__` with a default argument, `__delitem__`,
  `_AIL_ARRAY_PRELUDE = True`, `_AIL_ARR_MISSING = _AilArrayMissing()`, `_ail_arr_check`
  returning `str` on one path and a value on another.
- namedtuple: `_AilNT.__eq__/__lt__/__len__/__iter__/__contains__/__hash__`, `_replace`,
  `_asdict`.
- csv: `_AilCsvReader.__next__`, `_AIL_CSV_ESCAPE_NUMERIC = False`.
- enum: `_AilIntEnum`'s numeric dunders and `_ail_en_<Enum>_<MEMBER> = <Enum>(...)` constants.
- deque: `_AilDeque_*.buf` has field type `array`.
- datetime: `_ail_dt_from_iso_datetime` (`'s' is annotated str`, caller supplies bytes).
- regex: `_ail_re_dp/ds/dm/sub0`, which `pyboxed2._native_re` already replaces with native
  primitives on the normal build — but the `--strict` check runs before/without that pass.

Five programs have nothing else wrong: `vibe/berth_sim/python-0.py`,
`vibe/rail_transfer/python-0.py`, `gdev/g01_008.py`, `gdev/g11_002.py`, and
`vibe/berth_sim/ail-0.py`. The last is not a prelude blocker: its sole blocker is a
compiler-generated lowering name (`_ail_l1l` bound from popping rows of 1 fields in one
place and 5 in another), so typing the prelude does not move it.

### Semantics that must hold

The prelude *is* the module's implementation, so its observable behaviour must be
CPython-identical (or the module call refused by name). Exempting it from the subset check
without compiling it correctly would be a silent difference, so “ignore the prelude” is not
enough.

### Where it is decided

`python/pkg-v12/stdlib5.py:prelude`, `python/pkg-v12/smalllib5.py:run_array`,
`python/pkg-v12/rebrt.py` / `pyboxed2._native_re`, `python/pkg-v12/strictmode.py:collect`,
`python/pkg-v12/pyfunc.py:to_c`, `AIL_CURRENT/ail_chatgpt.py:_load_sources` /
`_strict_blockers` (the text handed to the collector).

### The change

Three layers, in order:

1. **Attribution (reporting).** Mark the generated ranges when `_load_sources` merges a
   prelude, and have `strictmode` label a blocker `generated: true` when its line is inside
   one. A user blocker stays a refusal; a prelude blocker is reported separately as
   “module support code not typed”. This changes no build decision.
2. **Type the preludes module by module**, starting with `prelude_array.py` (two sole
   programs), then namedtuple/enum/csv/deque/datetime. Keep `_native_re` applied before the
   strict check so the regex engine is not checked as Python.
3. **If a prelude cannot be typed**, the general-path implementation may be called from typed
   user code only through an explicit ABI, never by declaring the program typed. That mixed
   program is an architecture decision (see Owner decision).

### Proof obligations

- `compile --syntax python --strict` exits 0 for each moved program, and the default build
  produces byte-identical stdout/exit to CPython on its public and hidden cases.
- The emitted C compiles and does not link the general-path runtime into a program that
  previously did not need it (or the difference is measured and accepted).
- No `.ail`-source build changes (compare the generated C of all ten `lab/compare/src/*.ail`
  against the parent commit, as earlier pyreach lanes did).

### Programs moved

- array prelude: `vibe/berth_sim/python-0.py`, `vibe/rail_transfer/python-0.py` (2, both
  `strict_incomplete`, so fixing them may reveal a later blocker). `vibe/berth_sim/ail-0.py`
  is not an array move: its sole blocker is the `_ail_l1l` lowering-name conflict above.
- namedtuple: 0 clean moves. `gdev/g01_022.py` carries the namedtuple prelude blockers but
  also a `tuple[Field, ...]` annotation, a module-level `FIELDS` list and a false caller
  conflict, so typing the prelude alone does not move it. `gdev/g06_008.py` has no
  NamedTuple; its blockers are the tuple-repr helper (`_ail_trepr_s_i`) and a `set` walked
  as a sequence.
- enum: `gdev/g25_000.py`, `gdev/g25_022.py` (both `strict_incomplete`).
- csv: `gdev/g01_032.py` (incomplete, and also an unsupported builtin). deque:
  `gdev/g11_002.py` (1, `strict_incomplete`).
- datetime: `gdev/g01_008.py` (1, complete list).
- regex: `gdev/g20_010.py`, `gdev/g20_030.py`, `compare/tally_lang`, `compare/term_rank`
  (these also carry other blockers).

### Steps

| step | work | files | tests | probes | moves |
|---|---|---|---|---|---|
| 1a | attribution: mark prelude lines, `generated` flag in `ail.strict/1` | `ail_chatgpt._load_sources`, `strictmode.py` | `test_ail_strict` | `--strict --json` on `berth_sim/python-0.py` shows the array blockers as `generated: true`, the rest as user | 0 (exposes the real count) |
| 1b | type `prelude_array.py`: plain-positional `__init__`, `__delitem__`, module constants, `_ail_arr_check` return | `prelude_array.py`, `pyfunc.py` (`_function` dunder/`__init__`, module constants) | `test_ail_std_array`, `test_ail_array_core`, `test_ail_array_ref` | array indexing, slice, `del a[i]`, `a.typecode`, empty array, negative index, both builds | 2 |
| 1c | namedtuple prelude: `__eq__/__lt__/__len__/__iter__/__contains__/__hash__`, `_replace`, `_asdict` | `prelude_namedtuple.py` (or wherever `_AilNT` is built), `pyfunc.py` | `test_ail_collections` | `_replace`, `_asdict`, compare two namedtuples, tuple unpacking, both builds | 0 clean (prerequisite for `g01_022`) |
| 1d | enum prelude: numeric dunders and member constants | `prelude_enum.py`, `pyfunc.py` module constants | `test_ail_collections` | `IntEnum + int`, `<`, `str`, member iteration, both builds | 2 |
| 1e | csv prelude `__next__` / iterator protocol | `prelude_csv.py`, `iterlower.py` | `test_ail_std_csv`, `test_ail_csv_writer` | reader over 0/1/many rows, `next()`, `for row in reader`, both builds | 1 |
| 1f | deque prelude `buf` field type | `prelude_collections.py` (or `prelude_deque.py`), `pyfunc.py` | `test_ail_std_collections`, `test_ail_deqctr` | deque append/popleft/index, empty, both builds | 1 |
| 1g | run `_native_re` before the strict check | `pyboxed2._native_re`, `strictmode.py` | `test_ail_strict`, `test_ail_std_re` | a regex program types under `--strict` and matches CPython | 2-4 |

**Owner decision for 1c/1d/1e:** whether the preludes may be rewritten freely (they are
compiler output, not user source). Options: (a) rewrite them into the subset; (b) keep them
and add the missing subset constructs (dunders, default arguments); (c) compile them with the
general path. (a) is safest for semantics and smallest; it is the recommendation.

**Owner decision for the mixed path:** a typed function calling a general-path module
implementation needs a defined ABI and a defined failure mode. Options: (a) never mix (port
everything); (b) mix behind an explicit wrapper and mark the program `typed+general`; (c)
refuse. Until (b) is decided, do not claim programs that need it.

---

## 2. int64 literal

### What the census sees

4 programs, 3 sole: `compare/chain_relax/main.py` (`parse(a[2], 0, 18446744073709551615)`
and `M = (1 << 64) - 1`) and `vibe/chain_relax/python-0.py`,
`vibe/chain_relax/python-1.py` (`parse_bounded(..., 18446744073709551615)` and
`SEED > 18446744073709551615`). `rail_transfer` also has `INF = 1 << 200`.

All are refused at compile time: `pyfunc.py:14892` and `pyfront.py:241` (the front end's
constant folder). The refusal is correct today: Python's int is unbounded and the compiler's
is int64, so emitting a wrapped value would be a silent difference.

### Semantics that must hold

The literal's value is outside int64. Python computes it exactly. The only safe typed-path
moves are contexts where the *result is exactly representable for every int64 operand*:

- `x & (2**64 - 1)` is `x` for every int64 `x` (all ones mask; `x` may be negative).
- `x > (2**64 - 1)` is `False`, `x <= (2**64 - 1)` is `True` for every int64 `x`.
- `x < 2**64` and `x <= 2**64 - 1` are `True`, `x >= 2**64` is `False`, for every int64 `x`
  (int64 max is `2**63 - 1`).

Anything else (`print(2**64)`, arithmetic, a list element, a return value) must stay refused
by name. `--exact-int` already gives the exact answer on the general path; using it does not
make the program typed.

### Where it is decided

`python/pkg-v12/pyfront.py:int_constant` / `refuse_literal` / `refuse`, `intmode.py`
(`exact_python`, `HINT`), `pyfunc.py:14892` (`_const` / literal emission), and the
`--exact-int` reader. The folding site is `pyfront`'s constant expression walker.

### The change

A **context-aware constant allow-list**, not a widened literal:

1. When the folder sees an integer constant outside int64, do not refuse yet. If its parent
   is `BitAnd` and it is a right operand, replace the `&` with the left operand (drop the
   mask). If its parent is a comparison against an int64-typed operand, fold the comparison
   to the knowable truth value. Otherwise refuse exactly as today.
2. `(1 << 64) - 1` and `0xFFFFFFFFFFFFFFFF` must fold to the same allow-listed constant, so
   the folder evaluates the expression and then applies rule 1.

This is a source-level rewrite with an exact proof per shape; it never emits the constant.

### Proof obligations

- Every allow-listed shape is proved by an exhaustive property over int64 (the mask identity
  and the comparison truth values), stated in a comment and pinned by tests.
- A probe prints `x & M` and `x > M` for `x` in `{0, 1, -1, INT64_MIN, INT64_MAX}` and matches
  CPython.
- `print(18446744073709551615)` still refuses by name; `--exact-int` still produces the exact
  value on the general path.

### Programs moved

`compare/chain_relax/main.py` (mask + `(1<<64)-1`); `vibe/chain_relax/python-1.py` (comparison);
`vibe/chain_relax/python-0.py` only if its `parse_bounded` bound is one of the folded shapes
(verify before claiming). `rail_transfer`'s `1 << 200` is an `INF` used in comparisons and
would need a second allow-list shape (`x < 2**200` is `True`, `x >= 2**200` is `False`).

### Steps

| step | work | files | tests | probes | moves |
|---|---|---|---|---|---|
| 2a | mask/comparison allow-list for `2**64-1` / `0xFFFFFFFFFFFFFFFF` | `pyfront.py` constant folder, `intmode.py` | `test_ail_optint_exact`, `test_ail_pre9` / `test_ail_pre345` (they pin the refusal text) | `x & M`, `x > M`, `x <= M` for the five boundary values; bare literal still refused | 1-2 |
| 2b | extend the allow-list to `2**200` (`INF`) comparisons | `pyfront.py` | same | `INF = 1 << 200; x < INF`, `x >= INF`, both builds | 1 (`rail_transfer`) |

**Needs owner decision.** A context-aware literal is a language-semantics change: the same
source text means different things in different positions (allowed as a mask, refused as a
value). Options: (a) context-aware allow-list (above; keeps exactness, adds a rule the
reference must document); (b) a typed big-int type (correct, large); (c) keep the refusal
(0 moved; the program stays general/refused). Recommendation: (a), with the rule written in
`SEMANTICS.md` and every shape proved.

---

## 3. Container parameters cannot be mutated

### What the census sees

4 programs, 3 sole: `gdev/g08_002.py` (recursive 8-queens mutating `cols: Set[int]` with
`add/remove`), `gdev/g08_034.py` (dict parameter), `gdev/g04_010.py` (shell sort assigning
`items[j] = ...` in place), `vibe/ledger_bin/python-0.py` (`pos` is a parameter and cannot be
reassigned).

The typed path passes containers as borrowed read-only views. `fclist1` (already in the
tree: `pyfunc._scan_written_lists`, `_WRITTEN_LISTS`, `ctx.written_lists`) is a proof that a
parameter is written element-by-element and never resized, and then passes the caller's
buffer as a writable pointer. Today that path exists only for the `array` and `float-list`
kinds (`_written_list_argument` and the store branch at `pyfunc.py:26226`); `list`, `dict`
and `set` still hit the read-only refusal at `pyfunc.py:26203/26234` and `collib.py:1995/2717`.

### Semantics that must hold

CPython passes the object, so a callee's element store is visible to the caller. A store
that does not resize is exactly representable as a pointer into the caller's buffer. A resize
(`append`, `add`, `remove`, `pop`, `del`) changes the object's storage; if the caller keeps
using its own variable, that is also visible, so it needs either a boxed object (general
path) or a copy-in/copy-out that is proved unaliased.

### Where it is decided

`pyfunc.py:_scan_written_lists` (the proof), `_written_list_argument` (the call-site check),
`pyfunc.py:26226-26234` (the store), `collib.py:1995` / `2717` (dict/set methods),
`rebinding.py:369` (parameter reassignment message).

### The change

1. Extend the existing fclist1 store path from `array`/`FLIST` to `LIST` (element stores that
   never resize). The proof already requires “never resizing”, so the C is a bounds-checked
   `ail_list_set` on the caller's buffer.
2. Leave `set`/`dict` mutation refused for now; it needs reference semantics (Owner
   decision).
3. `pos` reassignment (a scalar parameter) is a different, smaller rule; handle separately
   (allow reassigning a parameter to a new scalar when the function does not return it and no
   closure captures it).

### Proof obligations

- A function that sorts its `list[int]` parameter in place leaves the caller's list sorted;
  a function that only reads never gets a writable pointer; a function that appends is still
  refused by name.
- Aliasing: `f(x); g(x)` sees both mutations; `a = b; f(a)` changes `b` too; a slice/copy
  passed to a written parameter is not silently written back.
- Both builds, CPython byte-identical.

### Programs moved

`gdev/g04_010.py` (1, complete-list) with step 3a. `gdev/g08_002.py` and `gdev/g08_034.py`
(2) need step 3b.

### Steps

| step | work | files | tests | probes | moves |
|---|---|---|---|---|---|
| 3a | fclist1 for `LIST` element stores (no resize) | `pyfunc.py` (`_written_list_argument`, store branch) | `test_ail_fclist1`, `test_ail_list_ops`, `test_ail_safety_itermut` | in-place sort of a list param, aliased names, read-only callee, append still refused, empty list, negative index, both builds | 1 |
| 3b | `dict[k] = v`, `d.setdefault`, `set.add/remove` on a proven written parameter | `pyfunc.py`, `collib.py` | `test_ail_fclist1`, `test_ail_int_dict_set`, `test_ail_collections` | recursive set mutation (8-queens), dict accumulation, alias, both builds | 2 |
| 3c | scalar parameter reassignment when unobservable | `pyfunc.py:3404`, `rebinding.py` | `test_ail_pyreach_shapes` | `def f(pos): pos += 1; return pos`, caller's `pos` unchanged, both builds | 1 (`ledger_bin/python-0`) |

**Needs owner decision for 3b.** Allowing a typed function to mutate the caller's dict/set
is a language change (the current rule is an ownership rule, not an oversight: `SEMANTICS`
section 3 says the array a program is given lives in the caller's memory and nothing writes
it). Options: (a) reference semantics for all container parameters (matches Python, needs
boxed storage or a proven in-place update); (b) copy-in/copy-out, refused when the parameter
may alias or escape; (c) keep the refusal. Recommendation: (a) only behind the existing
“never resizes, never escapes” proof; a resizing mutation stays refused.

---

## 4. Generators (`yield`)

### What the census sees

4 programs, 3 sole: `gdev/g16_000.py` (infinite Fibonacci), `g16_006.py` (sliding windows),
`g16_030.py` (infinite Hamming), `g16_038.py` (tokenizer). All refuse at
`pyfunc.py:13594-13596` (“this language has no generators”).

### Semantics that must hold

A generator is lazy and one-shot: it produces a value, suspends, and resumes; an infinite
generator cannot be materialised. `g16_000` is consumed by `zip(range(20), fibonacci())` and
`g16_030` by `[next(gen) for _ in range(20)]`, so an eager lowering would hang. `g16_006`
and `g16_038` are finite and consumed by a full `for` loop.

### Where it is decided

`pyfunc.py:13594` (`_STMT_SHAPE_REFUSALS['Yield']`), the function emitter, `iterlower.py`,
`genlib.py`, `prelude_genlib.py`.

### The change

Two independent pieces:

1. **Eager lowering for the safe shape.** A function whose `yield` sites are the whole body
   (no early `return value`, no `next`/`send` call on its result, finite by construction:
   no `while True` and every `while` has a decreasing bound the proof can see) may be
   rewritten to append to a list and return it, when every use is a full consumption
   (`for x in f(...)`, `list(f(...))`, `sum/any/all/join`). This is CPython-identical for
   those uses; the proof must also show the generator is not stored or aliased.
2. **A real iterator** (state machine or a C struct with a resume point) for lazy/infinite
   generators. This is a runtime feature and is larger than one step; it is the only way to
   move `g16_000`/`g16_030`.

### Proof obligations

- Eager shape: a generator with a side effect between yields has the same output order; a
  generator stored in a variable is refused; `next()` on a generator is refused; an infinite
  generator is refused (the proof checks the loop bound).
- Real iterator: `next`, `for`, `send`/`throw`/`close` (if built), exhaustion, reuse.
- Both builds, CPython byte-identical.

### Programs moved

Step 4a: `g16_006`, `g16_038` (2, complete-list). Step 4b (real iterator): `g16_000`,
`g16_030` (2).

### Steps

| step | work | files | tests | probes | moves |
|---|---|---|---|---|---|
| 4a | eager lowering for finite, fully-consumed generators | `pyfunc.py`, `genlib.py`, `iterlower.py` | `test_ail_genlib`, `test_ail_gen_speed` | sliding windows (0/1/n items), tokenizer (empty string, operators), side-effect order, stored generator refused, `next()` refused, both builds | 2 |
| 4b | iterator protocol / state machine for lazy generators | `genlib.py`, `prelude_genlib.py`, `cruntime.py` | `test_ail_genlib`, new `test_ail_genlazy` | Fibonacci first 20 via `zip`, Hamming first 20, infinite generator not materialised, `next`, exhaustion, both builds | 2 |

**Needs owner decision.** Eager lowering changes *when* side effects happen relative to
consumption; it is only safe under the stated proof. A real iterator changes the runtime.
Options: (a) eager only, refuse lazy (2 moved, small); (b) real iterator (4 moved, large);
(c) keep refusal. Recommendation: (a) now, (b) queued separately.

---

## 5. Standard-library module support

### What the census sees

21 programs (the largest family), 2 sole, 32 blocker instances:

- `json` 8 programs: `json.loads(s)` “the type of the result is not declared here”,
  `json.dumps(x)` “the type of this value is not known here”, `json.dump(obj, fp)`,
  `json.JSONEncoder`, `cls=`.
- `statistics` 3: `median`, `stdev`, `pstdev`, `geometric_mean`, `harmonic_mean`; one
  refusal notes that `stdev` of floats needs CPython's exact fractions.
- `collections` 5: `Counter`, `OrderedDict`, `defaultdict`, `deque`.
- `itertools` 4: `pairwise`, `takewhile`, `dropwhile`, `groupby`, `permutations` tuple shape.
- `functools` 1 (`partial`), `re` 2 (pattern used as a value / `re.Match` annotation),
  `tempfile` 1.

These are mostly **loud refusals**, which is the right failure mode, but they keep ordinary
Python off the typed path. Several are one function away.

### Semantics that must hold

Each added function must match CPython exactly (including edge cases: empty input,
`statistics` on one value, `json` escaping and key order, `groupby` reusing the key, tuple
vs list results). If exactness is not reachable, refuse by name (the `statistics` refusal
above is the model).

### Where it is decided

`python/pkg-v12/stdlib3.py`, `stdlib4.py`, `stdlib5.py`, `smalllib5.py`, `jsonlib.py` /
`jsonrt.py`, `statlib.py` / `statbrt.py`, `collib.py`, `itlib.py`, `relib.py`, `rebrt.py`;
the Python front end refuses by name in `pyfunc.py`.

### Programs moved

`json` typing (5a): `g21_000`, `g21_004`, `g21_008`, `g21_012`, `g21_022`, `g13_024`.
`statistics` (5b): `g03_012`, `g03_018`, `g03_032` (1 sole move, `g03_032`, whose blocker
list is `strict_incomplete`).
`itertools` (5c): `g18_014`, `g18_026`, `g14_022`, `g16_032`.
`collections` (5d): `g05_018`, `vibe/echo_pack/python-0`, `vibe/echo_pack/python-1`,
`vibe/term_rank/python-1`, `compare/term_rank`.

### Steps

| step | work | files | tests | probes | moves |
|---|---|---|---|---|---|
| 5a | `json.loads` uses the declared target type; `json.dumps` of a typed value | `jsonlib.py`, `jsonrt.py`, `pyfunc.py` inference | `test_ail_std_json`, `test_ail_json_fast` | loads into `list[int]`, `dict[str,int]`, nested; dumps of int/str/bool/None; empty; escaping; both builds | 5-6 |
| 5b | `statistics.median/stdev/pstdev/geometric_mean/harmonic_mean` on typed lists | `statlib.py`, `statbrt.py`, `stdlib5.py` | `test_ail_std_statistics`, `test_ail_std_stat` | empty (raises), one value, even/odd median, int vs float list, both builds | 3 |
| 5c | `itertools.pairwise/takewhile/dropwhile/groupby` in `for`/comprehension | `itlib.py` | `test_ail_modules`, `test_ail_modules3` | empty, one, many; takewhile stops; groupby key reuse; both builds | 4 |
| 5d | `Counter`/`OrderedDict`/`defaultdict`/`deque` typed | `collib.py`, preludes | `test_ail_modules`, `test_ail_sets_general` | Counter most_common, OrderedDict order, defaultdict default factory, deque endpoints; both builds | 4-5 |
| 5e | `tempfile.TemporaryDirectory`, `re.Match` annotation / compiled pattern value | `filelib.py`, `relib.py`, `pyfunc.py` | `test_ail_files`, `test_ail_std_re` | with-block file write and read, `m.group`, pattern bound to a name; both builds | 2 |

No owner decision: every item is a loud refusal today, so adding it is a pure widening; the
exactness rule still applies.

---

## Next tier (pyreach10): high appearance, more programs per step

These do not make the sole-ranked five but move more programs. Their reasons and counts
(from `RESULTS.md`):

| reason | programs | AI-typical | first step |
|---|---:|---|---|
| dict-of-containers | 18 | 4/24 | extend `_dict_of_containers_sites` to a value that is a list *or* a nested list; the lowering exists |
| tuple-unpack | 16 | 7/24 | `for a, b in list_of_tuples` and `a, b = fn()` (a tuple literal/list row) |
| mixed-container | 15 | 4/24 | a list that gets bool and int is one int list (bool is int in Python); a list that gets str and int is refused |
| value-kind-lost | 14 | 9/24 | keep the container kind through a subscript / call result; bytes indexing returns a 1-byte bytes |
| module-level-constant | 13 | 6/24 | constant-fold module-level pure calls (`set(...)`, `frozenset(...)`, `str.maketrans(...)`, `{}` and `[]` literals) |
| mixed-return-kind | 10 | 7/24 | a function that returns `bytes` or `int` needs a tagged union; or refuse with a rewrite |
| bytes-str-methods | 9 | 6/24 | implement `bytes.isdigit/lstrip/strip/index/decode` (the str versions exist) |

The highest-value single step in this tier is **module-level constant evaluation**
(6 AI programs) and **bytes methods** (6 AI programs): both are narrow and do not change
language semantics (pure builtins already have C implementations).

## Cross-cutting work

1. **`strictmode` completeness.** 41 of 97 lists are incomplete. Steps that need an exact
   “sole” count should re-run `strictmode` after each neutralisation or raise the
   `BUDGET_SECONDS` for the census (it is 120 s per program). This does not change builds.
2. **`ail.strict/1` `generated` flag** (step 1a) is a prerequisite for measuring the other
   reasons: until prelude blockers are separated, a census of user code is contaminated.
3. **A census command in CI.** `lab/pyreach9/census.py -j 2` on a small fixed corpus (the 10
   compare and 24 vibe programs, ~4 min) would make typed-reach a tracked number, like the
   compare benchmarks.

## Ready-to-queue task text

Copy one block per task. Each names its files, tests, probes and expected moves.

### T1 — pyreach10a: attribute compiler-generated prelude blockers

```
Goal: a --strict blocker in compiler-generated module code is reported separately from a
blocker in the user's source, and the JSON schema gains "generated": true.
Files: AIL_CURRENT/ail_chatgpt.py (_load_sources / _strict_blockers: keep the ranges of
  stdlib5.prelude and the regex pass), AIL_CURRENT/python/pkg-v12/strictmode.py (label a
  blocker whose line is in a generated range; do not change the neutralisation),
  AIL_CURRENT/python/pkg-v12/... prelude merge metadata.
Tests: test_ail_strict; add a case to test_ail_strict.py that --strict --json on a program
  with `from array import array` marks the _AilArray blockers generated.
Probes: /tmp/probes/p_prelude_attr.py = `from array import array; def f(): a = array('i',[1]);
  print(a[0])`; `bash ~/tools/cmp.sh /tmp/probes/p_prelude_attr.py $PWD`; and
  `--strict --json` must list user blockers (if any) separately.
Moves: 0 build decisions; makes the census of user code exact.
```

### T2 — pyreach10b: type the array prelude

```
Goal: `from array import array` builds typed for the integer and 'd' typecodes.
Files: AIL_CURRENT/python/pkg-v12/prelude_array.py (plain-positional __init__, __delitem__,
  module constants), pyfunc.py (module-level Constant, dunder where needed).
Tests: test_ail_std_array, test_ail_array_core, test_ail_array_ref, test_ail_safetynet.
Probes: array create/index/slice/del/typecode/append; empty, negative index; both builds.
Expected: vibe/berth_sim/python-0.py, vibe/rail_transfer/python-0.py become strict-typed
  (2 programs; both blocker lists are strict_incomplete).
```

### T3 — pyreach10c: int64 constant allow-list (needs owner decision)

```
Goal: `x & (2**64-1)`, `x > (2**64-1)`, `x <= (2**64-1)`, `x < (1<<200)`, `x >= (1<<200)`
  fold exactly; every other out-of-int64 literal still refuses by name.
Files: AIL_CURRENT/python/pkg-v12/pyfront.py (constant folder), intmode.py (document),
  SEMANTICS.md (the rule).
Tests: test_ail_optint_exact, test_ail_pre9, test_ail_pre345 (update refusal text only if
  the shapes change).
Probes: x in {0,1,-1,INT64_MIN,INT64_MAX} for each shape; bare literal refused; --exact-int
  still exact. Both builds.
Expected: compare/chain_relax/main.py and vibe/chain_relax/python-1.py (verify python-0).
Options for the owner: (a) context-aware allow-list [recommended]; (b) typed bigint;
  (c) leave refused.
```

### T4 — pyreach10d: element-written list parameters (fclist1 for LIST)

```
Goal: a function may assign xs[i] = v into a list[int]/list[str] parameter that it never
  resizes; the caller sees the stores, exactly as CPython.
Files: AIL_CURRENT/python/pkg-v12/pyfunc.py (_written_list_argument: LIST kind; the store
  branch at 26226: LIST as well as array/FLIST).
Tests: test_ail_fclist1, test_ail_list_ops, test_ail_safety_itermut, test_ail_safetynet.
Probes: in-place sort of a list param; aliased names; read-only callee; append still
  refused; empty list; negative index; both builds.
Expected: corpus/gdev/g04_010.py (1, complete list).
```

### T5 — pyreach10e: dict/set parameter mutation (needs owner decision)

```
Goal: set.add/remove and d[k]=v on a parameter proven written and never resized.
Files: pyfunc.py, collib.py (the read-only refusals at collib.py:1995/2717).
Tests: test_ail_fclist1, test_ail_int_dict_set, test_ail_collections.
Probes: recursive 8-queens (set add/remove); dict accumulation; alias; resizing still
  refused; both builds.
Expected: corpus/gdev/g08_002.py, corpus/gdev/g08_034.py (2).
Options: (a) reference semantics behind the written/never-resizes proof [recommended];
  (b) copy-in/copy-out, refused on alias; (c) keep refused.
```

### T6 — pyreach10f: finite generator eager lowering (needs owner decision)

```
Goal: a finite generator consumed by a full for/list/sum is lowered to a list; next(),
  storing the generator, and any unbounded loop stay refused by name.
Files: pyfunc.py (Yield), genlib.py, iterlower.py.
Tests: test_ail_genlib, test_ail_gen_speed.
Probes: sliding windows (0/1/n), tokenizer (empty, operators), side-effect order, stored
  generator refused, next() refused, both builds.
Expected: corpus/gdev/g16_006.py, corpus/gdev/g16_038.py (2).
Owner options: (a) eager only [recommended]; (b) real iterator (T7); (c) keep refused.
```

### T7 — pyreach10g: lazy iterator protocol

```
Goal: real generators for infinite/lazy uses (Fibonacci via zip, Hamming via next).
Files: genlib.py, prelude_genlib.py, cruntime.py.
Tests: test_ail_genlib, new test_ail_genlazy.
Probes: first 20 via zip and via next; exhaustion; two generators interleaved; both builds.
Expected: corpus/gdev/g16_000.py, corpus/gdev/g16_030.py (2).
```

### T8 — pyreach10h: json typed through the declared destination

```
Goal: json.loads(s) into a declared type and json.dumps(x) of a typed value build typed;
  an undeclared result is still refused by name.
Files: jsonlib.py, jsonrt.py, pyfunc.py inference.
Tests: test_ail_std_json, test_ail_json_fast.
Probes: loads list[int], dict[str,int], nested; dumps of int/str/bool/None; empty; escaping;
  both builds.
Expected: g21_000, g21_004, g21_008, g21_012, g21_022, g13_024 (5-6).
```

### T9 — pyreach10i: statistics on typed lists

```
Goal: median/stdev/pstdev/geometric_mean/harmonic_mean match CPython or refuse by name.
Files: statlib.py, statbrt.py, stdlib5.py.
Tests: test_ail_std_statistics, test_ail_std_stat.
Probes: empty (raises), one value, even/odd median, int vs float list; both builds.
Expected: g03_012, g03_018, g03_032 (3; g03_032 is a sole move but its blocker list is
  strict_incomplete).
```

### T10 — pyreach10j: module-level pure constants

```
Goal: `X = set(...)`, `X = frozenset(...)`, `X = str.maketrans(...)`, `X = {}`/`[]` at module
  level are evaluated once and readable by functions.
Files: pyfunc.py module constants, pyboxed2 general path parity.
Tests: test_ail_pyreach_shapes, test_ail_modules.
Probes: STOP_WORDS membership, LOWER translate, DIGIT_VALUE lookup, mutation of the constant
  refused; both builds.
Expected: 6 AI programs (module-level-constant 13 programs, 6 vibe).
```
