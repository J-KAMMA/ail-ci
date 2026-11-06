# An explicit big-integer type for Python syntax (ffbig0 design note, 2026-11-06)

Status: **design note and probes only.** No compiler behaviour changes in this branch. The
twelve programs in `lab/bigtype/` and `lab/bigtype/check_model.py` are the executable model of
the rules below; `--exact-int` is unchanged. Implementation belongs to ffbig1.

Today an integer is either int64 (the default; overflow stops loudly, LIMITATIONS 1-2) or
`--exact-int` for **every** integer in the program (about 20x slower, LIMITATIONS 1-2). fcbig1
widens only constants it can prove safe in an int64 place. There is no way to say "this one
variable is an exact integer". This note proposes that way.

## 1. Spelling

Recommended spelling, and the only one used by the probes:

```python
from ail.types import BigInt

count: BigInt = 0
values: list[BigInt] = []
```

The wheel ships a tiny pure-Python module:

```python
# packaging/ail/types.py
"""Type markers for AIL programs that must also run on CPython."""

BigInt = int
```

`BigInt` is used **only as an annotation**: a local, module or class variable, a parameter, a
return, a field, or inside `list[BigInt]` (and later other containers). At run time it is the
plain builtin `int`; CPython 3.12 runs the source unchanged with no third-party package. The AIL
compiler reads the annotation from the syntax tree and nowhere else.

Alternatives and their cost:

| option | CPython runs unchanged | cost / why not |
| --- | --- | --- |
| `from ail.types import BigInt`, `BigInt = int` (recommended) | yes | one ~100-byte module in the wheel and one import level. Zero run-time cost; the annotation is erased at run time. A type checker sees an alias of `int`, not a distinct type. |
| `class BigInt(int)` with exact operators | yes | CPython now pays a Python-level call per arithmetic operation and every value becomes a subclass; semantics still differ from AIL's checked int64 places, and the compiler would have two integer class models. Rejected as the shipped marker. |
| `BigInt = NewType("BigInt", int)` | yes | no wheel module, but `NewType` is a callable that returns a plain `int`; annotations do not propagate through arithmetic in most tools, and the AIL side still needs the same parser work. A fallback if a wheel module is unacceptable. |
| `typing.Annotated[int, "BigInt"]` | yes | needs `typing` at import (a real module cost in a compiled program's source too), makes `list[Annotated[int, ...]]` verbose, and adds an `Annotated` unwrapping rule to the AIL parser. No benefit over the alias. |
| a new AIL keyword, `int!`, or brace syntax | **no** | violates the stop rule: the spelling must run on CPython 3.12 without a third-party package. |
| `--exact-int` for the whole program | yes | already exists; keeps every int exact and pays the whole-program exact cost. It remains the escape hatch, not the per-variable answer. |

The wheel currently ships `ail_lang/`; ffbig1 adds a top-level `ail/` package (`ail/__init__.py`
may be empty, `ail/types.py` holds the alias) and the wheel backend's file list. A program that
never imports `ail.types` gets byte-identical C, as with the proclib rule.

## 2. Rules

### 2.1 What a BigInt place is

A **BigInt place** is a syntactic position whose annotation is `BigInt`:

* `x: BigInt = ...` at module, function or class-body level;
* a parameter and a return: `def f(x: BigInt) -> BigInt`;
* a field: a class-body annotation, or `self.x: BigInt = ...` in a method;
* an element position of `list[BigInt]`: the literal list, `append`, `insert`, `extend`, an item
  store, and the loop variable of `for x in values` when `values: list[BigInt]`;
* a default argument whose parameter is `BigInt` (`def f(x: BigInt = 2 ** 100)`).

A **plain int place** is the same list with annotation `int`. An unannotated local is not a
place; it takes the kind of its first stored value (see 2.5).

The first implementation should support exactly these five: local/module/global, parameter,
return, field and `list[BigInt]`. `dict[str, BigInt]`, `tuple[BigInt, ...]`, `set[BigInt]` and
comprehensions are a later extension; they need the same item-store hook but more surface.

### 2.2 Arithmetic

* If either operand is a BigInt, the operation is exact and the result is BigInt. This includes
  `+ - * // % ** divmod << >> & | ^`, unary `- + abs ~`, and `pow(a, b[, m])`.
* `int <op> BigInt` and `BigInt <op> int` both give BigInt (commutativity is preserved).
* Comparisons (`< <= == != > >=`) return `bool`; `bool(BigInt)` is the usual truth value. No
  BigInt is created by a comparison.
* `BigInt / x` follows CPython: it is a float division, not a BigInt result. `float(BigInt)` uses
  the existing correctly rounded conversion and can raise `OverflowError: int too large to
  convert to float`.
* `str(BigInt)`, `repr(BigInt)`, `f"{x}"`, `hex/oct/bin(BigInt)` and `BigInt.bit_length()` are
  exact and reuse the existing big-int conversions. `int(BigInt)` is a demotion at a plain int
  boundary (2.3), not an operation that changes the type in the middle of an expression.
* `int(text)` in a BigInt place parses exactly; in a plain int place it is the existing int64
  parse with the loud stop for a value outside int64. `int(text, base)` follows the same rule.
* `sum(list[BigInt])`, `min/max(list[BigInt])` return BigInt; `len`, `range` bounds, indexing and
  other places that C requires to be an `int64`/`Py_ssize_t` check the value and raise the
  CPython error when it does not fit, rather than wrapping.
* A BigInt used as a dict key or set element keeps the existing one-type, canonical hash: a
  value that fits int64 is represented in its small form, so `hash(2**64 - 2**64 + 5) == hash(5)`.

### 2.3 BigInt into a plain int place

Every store into an annotated plain int place is a check point: assignment, parameter binding,
return from a function whose return is `int`, a field store, a `list[int]` item store, and an
unpacking target. If the value is BigInt:

* inside int64: demote to the int64 form, silently (the value is unchanged);
* outside int64: **stop loudly** with `OverflowError` before any further output from that
  statement. The recommended message keeps the existing prefix and names the place:

  ```text
  OverflowError: BigInt 1267650600228229401496703205377 does not fit int64 in argument x of takes_int (line 9)
  ```

The check is a run-time check, not a compile error: the value may be small on one call and big on
another. It is the same no-silent-wrap rule as LIMITATIONS 2, but the source type is BigInt rather
than an overflowing int64 operation.

The opposite direction (a plain int into a BigInt place) is a promotion: the int64 value becomes
BigInt. It is not an error, and it is the normal way a counter is added to a big accumulator.

### 2.4 Literals

A literal or constant expression beyond int64 is allowed **only** when the place it initialises
is a BigInt place. Then it is emitted exactly (the existing exact-mode literal/string path), not
refused:

```python
x: BigInt = 2 ** 100          # allowed
items: list[BigInt] = [2 ** 70, 3 ** 50]   # allowed
def f(x: BigInt = 2 ** 100) -> BigInt: ... # allowed (default is a BigInt place)
```

In a plain int place the existing rules are unchanged: a constant whose folded result fits int64
is admitted (the fcbig1 safe subset), a constant expression outside int64 is refused at compile
time with the source line and the `--exact-int` hint, and a run-time arithmetic result outside
int64 stops with the existing `OverflowError`. `x: int = 2 ** 100` therefore stays a compile-time
refusal, not a silent BigInt.

### 2.5 Aliasing and inference

Explicit annotations are the contract; unannotated names are inferred locally to keep ordinary
programs fast:

* `y = x` where `x` is BigInt makes `y` BigInt (no check, no copy; the value is immutable).
* `y: int = x` is the plain int check point.
* A local with no annotation takes the kind of its first assignment and keeps it in that scope.
  A later store that conflicts is a compile-time error unless it is a plain int -> BigInt
  promotion or a BigInt -> int check point. This is deliberately monomorphic per scope; a function
  is not re-instantiated per call.
* A parameter or return with no annotation is a plain int64 place. Passing a BigInt to it is the
  checked boundary of 2.3. This is the "explicit only" choice: users who want big values in a
  helper annotate the helper. It keeps the analysis local and makes the stop predictable (see
  owner decision D4).
* Aliasing through a container follows the container annotation: `list[BigInt]` items are
  BigInt; `list[int]` item stores are check points. An unannotated list whose first stores are
  BigInt is a BigInt list.

### 2.6 Function boundaries

A call is a boundary between scopes:

* a plain int argument to a `BigInt` parameter is promoted;
* a BigInt argument to an `int` parameter is checked and can raise (the negative probe);
* a BigInt return to an `int` caller is checked; a plain int return to a BigInt caller is
  promoted;
* an unannotated function is plain int64 on both sides unless the annotation pass proves it is
  called only from BigInt scopes (not in v1).

No whole-program propagation and no implicit "this call made the callee exact". A BigInt helper is
declared, not guessed.

### 2.7 What the type is not

BigInt is not a new run-time class. It is the existing exact-int representation with a static
annotation; `type(x) is int`, `isinstance(x, int)`, `x == 5`, `hash(x)` and dictionary keys behave
exactly as in CPython. It never turns a float into an exact value, never changes `//` or `%`
sign rules, and never changes a plain int operation.

## 3. Runtime: reuse `--exact-int`

The exact-int machinery already has both representations and both need no new C:

| layer | file | what holds the exact value |
| --- | --- | --- |
| C core | `AIL_CURRENT/python/pkg-v12/bigint_core.py` (`CORE`) | limb magnitudes and the algorithms (add/sub/mul, Knuth D, shifts, decimal and radix conversion, two's complement) |
| boxed general runtime | `AIL_CURRENT/python/pkg-v12/bigint_obj.py` (`EARLY`, `LATE`) | `ail_bigobj` (sign, `n`, `d[]`), `ail_big_finish` (canonical demotion), `ail_big_addsub`, `ail_big_mul`, `ail_big_divmod`, `ail_big_shl/shr`, `ail_big_bitop`, and the cold overflow entries `ail__ov_add1`, `ail__ov_sub`, `ail__ov_mul`, `ail__ov_floordiv`, `ail__ov_pow`, `ail__ov_shl` |
| boxed tag | `AIL_CURRENT/python/pkg-v12/cruntime.py` | `AIL_T_BIG` (line 11243), `AIL_K_BIG` (line 11261), the operator arms at `ail_op_add/sub/mul` (around 15333-15572) and the unbox check `AIL_UNBOX_CHK` (around 17625) |
| tagged typed path | `AIL_CURRENT/python/pkg-v12/tint_typed.py` | `ail_tint` (inline `int64_t i` or `ail_tbig *b`), `ail_tint_from_int64`, `ail_tint_demote`, `ail_tint__slow_*` |
| tagged general path | `AIL_CURRENT/python/pkg-v12/tint.py` | the same `ail_tint` over the boxed `ail_bigobj`, used by the unified lowering |
| IR | `AIL_CURRENT/python/pkg-v12/ir/driver.py`, `ir/lower.py` | the tagged parameter/result ABI `TINT_SIGS` / `TINT_ACTIVE`, and the `ail_tint` locals |

The canonical rule is already the one BigInt needs: every result goes through
`ail_big_finish` / `ail_tint_demote`, so an in-range value is the small form and the type stays
one `int`. The proposed type does not add a tag or a second representation; it only tells the
compiler which scopes may use the existing exact lowering.

### 3.1 Cost per operation from 3 probes

Three probe programs were built with `--exact-int`, checked against CPython (stdout equal), and
timed on the 4-core runner. Each runs `N = 10,000,000` iterations with a ~100-bit left operand:

| probe | body per iteration | user CPU, median of 7 (s) | incremental ns/op | total ns/iteration |
| --- | --- | ---: | ---: | ---: |
| control (no big op) | `total = total + i` | 0.80 | - | 80 |
| `add` | `total = total + (a + i)` | 0.84 | **4.0** | 84 |
| `mul` | `total = total + (a * (i \| 1))` | 1.01 | **21.0** | 101 |
| `div` | `total = total + (a // ((i & 1023) + 1))` | 1.09 | **29.0** | 109 |

"incremental" is the probe minus the control, so it excludes the loop and accumulator; the loop
control is also exact in this build, which is why the totals are large. The probes are:

```python
# add.py                                  # mul.py / div.py differ only in the middle expression
def main() -> None:
    a = 2 ** 100
    i = 0
    total = 0
    while i < 10000000:
        total = total + (a + i)            # mul: a * (i | 1)   div: a // ((i & 1023) + 1)
        i = i + 1
    print(total % (10 ** 20))
```

`tools/icount.c` was built as `cc -O2 -w -include signal.h -include stdlib.h -o icount
tools/icount.c`, but this runner denies `perf_event_open` (`/proc/sys/kernel/perf_event_paranoid`
is 4 and the job has no root), so the numbers are user CPU from `/usr/bin/time`, not instruction
counts. The three probes and the control are in `/tmp/probes/bigtype_cost/` and are not part of
the change. The 20x figure in LIMITATIONS is for a whole program in `--exact-int`; with the
proposed per-scope marking, only BigInt-marked scopes pay the tagged cost.

The meaningful design number is therefore the **incremental** one: a big add is about 4 ns, a big
multiply by a small value about 21 ns, and a big floor division by a small value about 29 ns on
this machine. The first is the common accumulator update; the last two are the ones a rewrite
should avoid inside a hot loop when the value is known to be int64.

## 4. Interaction with fcbig1 and `--exact-int`

* **fcbig1** proves a constant safe for a plain int64 place: a folded result that fits, a mask
  bounded by an int64 constant, an int64 literal. It is unchanged. The BigInt rule is disjoint:
  a literal beyond int64 is admitted only because the destination is a BigInt place, not because
  it was proven. Precedence is: BigInt annotation first; otherwise fcbig1's proof; otherwise the
  existing refusal. A constant that fcbig1 already proves in a plain int place keeps its int64
  type and pays no exact cost; putting a BigInt annotation on it is a user request to pay the
  exact cost, not a prerequisite.
* **`--exact-int`** keeps meaning "every int in this program". It wins over the annotations:
  under `AIL_EXACT_INT=1` / `compile --exact-int`, plain int places no longer stop on a value
  outside int64 (as today) and the BigInt annotations are documentation. Turning the flag off
  restores the per-place checks. This preserves the existing oracle and keeps one switch that
  says "I want CPython ints everywhere".
* The build-cache key must include the new mode (or the set of BigInt-marked units), exactly as
  it includes `AIL_EXACT_INT` today. A program with no `ail.types` import and no annotations
  must produce byte-identical C to the current default build.

## 5. Implementation map for ffbig1

The runtime is already there; the work is annotation parsing, per-scope marking, routing and
checks. Files:

| file | change |
| --- | --- |
| `packaging/ail/types.py` (new) | `BigInt = int`; `packaging/ail/__init__.py` (new, empty). |
| `packaging/ail_wheel_backend.py` | ship the top-level `ail/` package alongside `ail_lang/`; extend the wheel check/smoke test. |
| `AIL_CURRENT/ail_modules.py` | resolve `from ail.types import BigInt` as an annotation-only import: do not compile, export or execute the module. (The resolver is the top-level module, where `BUNDLED_DIR` is defined; there is no `python/pkg-v12/ail_modules.py`.) |
| `AIL_CURRENT/python/pkg-v12/intmode.py` | add `exact_scope(name)` returning the per-unit BigInt marks (parameters, return, locals/fields) and `any_exact_scope()` for the loop gate; `exact()`, `exact_python()` and `int64_python()` keep their meaning. |
| `AIL_CURRENT/python/pkg-v12/bigcap.py` | a new annotation pass (or a small new `bigint_type.py` imported here): collect BigInt locals, params, returns, fields and `list[BigInt]` items, then add those units to `marked()`; propagate through calls of marked units. This is the same "capable unit" set that drives the exact lowering. |
| `AIL_CURRENT/python/pkg-v12/pyfront.py` | record the annotation on the syntax tree/scopes; allow a literal beyond int64 in a BigInt place (the existing exact literal path) and keep the plain-place refusal. |
| `AIL_CURRENT/python/pkg-v12/pyc.py` | route a BigInt-marked unit to the exact attempt: skip the int64 literal/constant refusal for that scope, use the tagged/unified plan, and keep the ordinary int64 route for unmarked units. |
| `AIL_CURRENT/python/pkg-v12/unified.py` | make `exact_enabled()` / the per-function exact plan include BigInt-marked units; keep those locals boxed/tagged and unmarked units as they are. |
| `AIL_CURRENT/python/pkg-v12/pyboxed2.py` | include BigInt-marked units in the `biggate` reachability/marking so the general-path piece carries the exact runtime, and only those. |
| `AIL_CURRENT/python/pkg-v12/biggate.py` | select the `AIL_T_BIG`/tint runtime for a BigInt-marked unit, not for the whole program; a program without BigInt imports must stay byte-identical. |
| `AIL_CURRENT/python/pkg-v12/pyfunc.py` | **one hook only**, inside the existing per-function `_tint_sigs` loop where `_f` is already bound (the `for _i, _f in enumerate(fns if ...)` at line 38806): (a) widen that loop's gate from `_python_surface` to `(_python_surface or intmode.any_exact_scope())`; (b) as its first body statement bind `_bigunit = intmode.exact_scope(_f.name)` (`None` for an ordinary unit); (c) in the `_params`/`_ret` expressions at lines 38834-38838, tint a parameter named in `_bigunit` and a `_bigunit` BigInt return, guarding the `None` case explicitly: `_all_tint or ... or (_bigunit is not None and _bigunit.param(n))` and `_all_tint or _needs_tint or (_bigunit is not None and _bigunit.ret)`. The guard is required: `exact_scope()` is `None` for an ordinary unit, and once the loop gate is widened every unmarked function in a BigInt program reaches these expressions; without the guard they raise `AttributeError` instead of staying on the int64 path. `_python_surface` at 38742 and `GLOBAL_INT_TINT` keep their whole-program meaning: they say whether module-int storage is exact and whether the loop can run, never whether an individual unit is exact. Use a fresh name such as `_bigunit`; `_unit` is already bound for the fast-emit path at 38989 and 39019, so reusing it would be a collision. |
| `AIL_CURRENT/python/pkg-v12/tint.py`, `tint_typed.py`, `cruntime.py`, `bigint_core.py`, `bigint_obj.py`, `ir/driver.py`, `ir/lower.py` | **unchanged**: the exact representation, the tagged ABI and the IR lowering are reused. |
| `AIL_CURRENT/test_ail_bigint_type.py` (new) | the positive/negative cases, both builds, and the `--exact-int` precedence; register through `AIL_CURRENT/tests.d/` as the repository rules require. |
| `docs/PORTING.md`, `docs/LIMITATIONS.md`, `DIFFERENCES.md`, `DEVLOG.md` | the user-facing spelling, the new stop and the interaction text. |

The one `pyfunc.py` hook sits where `_f` is already bound, so no undefined name is needed and no
whole-program flag has to change meaning. It feeds the existing per-function signature computation
(`TINT_SIGS`, `TINT_ACTIVE`, the `ail_tint` locals) instead of replacing it, and it uses a fresh
local (`_bigunit`) because `_unit` is already bound later in the same function. Every use of
`_bigunit` carries an explicit `_bigunit is not None` guard so the ordinary (unmarked) units that
the widened loop now visits keep their int64 signature. `pyfront.py` rewrites
a BigInt-place literal to the exact parse the exact mode already emits, so no second `pyfunc.py`
literal hook is needed; that is a precondition of this design.

### 5.1 Boundary check hook

The BigInt -> int check needs one new C-level helper per place (or one shared helper with a
reason string). Recommend a single `ail_bigint_to_int64`-style helper in `bigint_obj.py` /
`tint_typed.py` returning a status, and emit the check in the same place the existing int64
conversion is emitted. No new value representation, root discipline or GC tag.

## 6. Twelve programs and the reference checker

`lab/bigtype/` holds the 12 programs and `expected/*.txt` (plain CPython 3.12 with
`BigInt = int`). `check_model.py`:

1. runs each program with `BigInt = int` and compares stdout with `expected/<program>.txt`;
2. runs it again with `BigInt` as an `int` subclass that keeps exact arithmetic and instruments
   the annotated places with an in-memory AST rewrite;
3. treats the plain int check points of rule 2.3 the same way: an unannotated parameter or
   return, a `list[int]` item store, and every unpacking target (including nested and starred
   targets) is checked, so a BigInt stored there raises the modelled `OverflowError`;
4. prints every promotion, demotion and overflow and compares the counts with the rule table.

`--write-expected` regenerates the CPython files; `--show-flows` lists every flow.

| program | what it probes | promote int64 | promote beyond | demote | overflow |
| --- | --- | ---: | ---: | ---: | ---: |
| `01_factorial.py` | annotated accumulator and return: `30!` | 1 | 0 | 0 | 0 |
| `02_fibonacci.py` | `F(100)` beyond `2**63` | 2 | 0 | 0 | 0 |
| `03_modpow.py` | `pow` with BigInt base/exponent/modulus | 1 | 2 | 0 | 0 |
| `04_counter_field.py` | class field `total: BigInt`, 1000 bumps then `2**70` | 2 | 1 | 0 | 0 |
| `05_list_sums.py` | `list[BigInt]` literal and loop sum | 3 | 2 | 0 | 0 |
| `06_mix_divmod.py` | `//` and `%` mixing BigInt and plain int, both signs | 0 | 1 | 0 | 0 |
| `07_str_int_roundtrip.py` | 40-digit `str`/`int` round trip and a parser | 0 | 2 | 0 | 0 |
| `08_bigint_to_int_param.py` | **negative:** BigInt into `x: int`, must stop | 0 | 1 | 0 | **1** |
| `09_literal_and_demotion.py` | literals beyond int64 in BigInt places, then in-range demotion | 0 | 2 | 1 | 0 |
| `10_bigint_param_return.py` | BigInt parameter and return, plain int promoted at a call | 1 | 1 | 0 | 0 |
| `11_bitops_compare.py` | `&`, `>>`, comparison, subtraction with BigInt | 0 | 2 | 0 | 0 |
| `12_list_largest_sum.py` | `list[BigInt]`, `max` loop and `sum` | 1 | 2 | 0 | 0 |

Result on this branch:

```text
$ python3 lab/bigtype/check_model.py
OK 01_factorial.py  output=match flows=match
...
OK 12_list_largest_sum.py  output=match flows=match
12/12 programs classified as the rules predict
```

`08` is the deliberate mismatch between the two models: with `BigInt = int`, CPython prints the
big value in `expected/08_bigint_to_int_param.txt`; the modelled run raises the proposed
`OverflowError`, catches it (the program catches it so the checker run stays complete) and records
one overflow. That is the rule the implementation must add, not a CPython behaviour.

## 7. Owner decisions

| id | question | recommendation | cost if the other way |
| --- | --- | --- | --- |
| D1 | Spelling: wheel alias, `NewType`, `Annotated`, or new syntax? | `from ail.types import BigInt`, `BigInt = int` in the wheel (section 1). | New syntax fails the CPython stop rule; a subclass pays Python-level arithmetic and creates a second int model; `Annotated` makes every container spelling heavier. |
| D2 | How much surface in v1? | locals, parameters, returns, fields and `list[BigInt]`; defer dict/tuple/set/comprehensions. | Shipping all containers at once multiplies the AST and checker cases; deferring keeps the first PR reviewable. |
| D3 | Unannotated alias/flow | local first-store inference; explicit `int` is the check point; a BigInt operand makes the result BigInt. | Requiring an annotation on every alias is noisier; inferring across calls needs whole-program analysis. |
| D4 | Unannotated parameter/return | explicit-only: plain int64, so a BigInt argument is the checked boundary. | Implicit per-call BigInt inference would make code silently slow and needs cloning; not recommended for v1. |
| D5 | BigInt into plain int outside int64 | run-time `OverflowError` naming the place; in-range demotion is silent. | A compile-time refusal cannot see the value; a silent truncation violates the no-silent-wrap rule. |
| D6 | `--exact-int` precedence | global exact mode wins; BigInt annotations become documentation. | Making annotations override exact mode would make `--exact-int` no longer mean "every int" and would break existing exact tests. |
| D7 | Literal beyond int64 in a BigInt place | allow it; emit the existing exact literal path. | Refusing it would make `x: BigInt = 2**100` need a workaround and undercut the type's purpose. |
| D8 | Wheel location | top-level `ail/types.py` to match the spelling; ship it in `ail_wheel_backend.py`. | `ail_lang.types` avoids a second package but changes the recommended spelling and ties the marker to the CLI package. |
| D9 | Performance target | per-unit exact lowering, not whole-program; reuse `ail_tint`/`AIL_T_BIG`. | A new representation or a whole-program switch repeats the 20x cost LIMITATIONS records. |

## 8. Open questions and risks

* **Optimization boundary.** A BigInt value passed through an unannotated helper is checked at
  the boundary; if that helper is hot, the program pays a check it may not need. Measure this on
  a real workload before widening inference (D3/D4).
* **Containers.** `list[BigInt]` is in v1; a `dict[str, BigInt]` value store and tuple unpacking
  need the same check hook and are deliberately left for a follow-up.
* **Class methods.** The typed path's legacy emitter does not type module/class int statics as
  `ail_tint` (the `GLOBAL_INT_TINT` condition in `pyfunc.py`); a BigInt class field must use the
  object path or force the tagged ABI. This is the first case to probe in ffbig1.
* **Message text.** The `OverflowError` wording should be one string built from the place, so the
  checker and the C runtime cannot drift; the existing `OverflowError: integer overflow in <op>`
  prefix stays for plain int64 operations.
* **Not measured.** The probes give operation costs, not a whole-program ratio. The expected
  win depends on how much of the hot loop is inside BigInt-marked units; that is an ffbig1
  measurement, not a claim of this note.
