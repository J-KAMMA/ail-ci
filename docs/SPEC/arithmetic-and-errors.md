# Arithmetic and errors

This chapter fixes what the operators mean when a value is unusual: overflow, division, negative
exponents, NaN, complex results, set order, and the wording of a trap a program can read.

## AR1 — Integer arithmetic is checked, never wrapping

**Rule.** `+`, `-`, `*`, `//`, `%`, `**`, unary `-`, `abs()` and an `int()` conversion are checked
against int64. A result outside it stops with

```text
OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)
```

on stderr, with exit 1, after the stdout already written. It never returns a wrapped value. A
constant expression outside int64 is refused at build time with the file and line. `--exact-int`
gives CPython's exact integers.

```python
x = 2 ** 62
print(x * 4)                  # loud stop; CPython prints 18446744073709551616
```

**CPython.** Returns the exact integer.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1; [`docs/LIMITATIONS.md`](../LIMITATIONS.md)
1-2; `test_ail_int64_default`; `lab/limits/02_int_overflow_runtime.py`.

## AR2 — True division of two ints is rounded once

**Rule.** `a / b` for two ints computes the exact quotient and rounds once, as CPython's
`long_true_divide` does. It is not `(double)a / (double)b` when either operand is beyond 2**53,
because converting both first rounds twice.

```python
print((4611686018427387904 // 52) / 3)
# 2.9562089861714024e+16 in both languages
```

**CPython.** The same exact-then-round rule.

**Status.** implemented.

**Proof.** [`DIFFERENCES.md`](../../DIFFERENCES.md) row `C?-job-fz227-11050703-1`; `test_ail_fz227.py`.

## AR3 — Negative integer exponents

**Rule.** `int ** n` with a negative `n` is a float in Python. AIL gives the float when `n` is a
constant; when `n` is only known at run time it stops loudly with
`negative exponent on an integer`. Use `float(x) ** n`, or keep the exponent non-negative.

```python
print(2 ** -1)                # 0.5 in both languages
n = -1
print(2 ** n)                 # loud stop; CPython prints 0.5
```

**CPython.** Returns the float in both cases.

**Status.** implemented (loud stop).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A5.

## AR4 — Float `//`, `%` and `divmod`

**Rule.** Float floor division, modulo and `divmod` use CPython's `float_divmod`: the sign of a
zero remainder follows the divisor, infinities and NaNs behave as CPython's routine does. They
are not `floor(a / b)` plus a sign fix.

```python
print(1.0 // 0.1, -0.0 % 2.0)  # 9.0 0.0
```

**CPython.** The same algorithm.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C173; `test_ail_fuzz45`.

## AR5 — Float `sum()` uses CPython's compensated sum

**Rule.** `sum()` over floats uses CPython 3.12's `builtin_sum_impl`: Neumaier compensation for
float items, plain addition for the first item after an int prefix and for int items inside the
float run, compensation dropped when a non-number ends the run, and the final `c` rule. The
result is bit for bit CPython's. `math.fsum` is not built.

```python
print(sum([0.1] * 10))         # 1.0 in both languages
```

**CPython.** The same algorithm.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C1, A15; `test_ail_spec_fixes`.

## AR6 — Array sums have one fixed order

**Rule.** `ail_array` (`ta.sum`, `ta.dot`, `ta.matmul`) reduces in a fixed 16-lane,
1024-block order along the reduced axis. `ta.matmul` uses the same order as `ta.dot`, so a row
times a column agrees with the dot product. The builtin `sum(a)` keeps CPython's meaning and is
not this rule.

```python
import ail_array as ta

a = ta.array([0.1] * 10)
print(ta.sum(a))              # fixed order, not CPython's builtin sum
```

**CPython.** No array module; `sum()` of the Python list is the CPython algorithm of AR5.

**Status.** implemented for the f64 array surface in this tree; f32/f16 and GPU reductions are
later stages.

**Proof.** [`AIL_CURRENT/docs/design/TYPED_ARRAY.md`](../../AIL_CURRENT/docs/design/TYPED_ARRAY.md)
TA3, TA4 and section 3.5; `lab/array/RESULTS.md`.

## AR7 — NaN has no identity in an unboxed float

**Rule.** A NaN float compares unequal to itself. AIL therefore cannot reproduce CPython's
identity shortcut on an unboxed NaN. The language chooses a loud boundary instead of a different
answer:

* a NaN used as a dict/set key, with `in`, with `list.count` / `index` / `remove` on the typed
  path stops by name where CPython's identity would change the answer;
* a tuple comparison that reaches a NaN raises `ValueError` (CPython answers `False`);
* sorting with a NaN key is refused (CPython's Timsort order is input-dependent).

```python
nan = float("nan")
print(nan == nan)             # False in both languages
print((1, nan) < (1, 2))      # CPython False; AIL raises ValueError
```

**CPython.** Uses object identity inside `in`, `count`, `index`, `remove` and tuple comparison,
so one NaN object can be found while another is not.

**Status.** implemented (named stop / refusal).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A7, C119, C140, C141,
`C?-job-refuzz95-10300605-1`; [`docs/CLI.md`](../CLI.md) loud stops.

## AR8 — No complex type

**Rule.** AIL has no complex value. A complex literal is refused; a constant expression with a
complex result is refused with an explanation. A run-time negative base with a fractional
exponent is a known bug on the current tree, not a language rule, and must not be relied on.

```python
print((-4.0) ** 0.5)          # refused: a negative number raised to a fractional power
```

**CPython.** Returns a complex number.

**Status.** refused.

**Proof.** [`docs/MIGRATING.md`](../MIGRATING.md) 11-12; [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C5.

## AR9 — Sets are ordered deterministically

**Rule.** A set is not a hash-ordered structure in the language. It iterates in insertion order,
and `pop()` removes the first element in that order (VT10). Set operators keep a deterministic
order: the left operand's elements first, then the elements only in the right operand; symmetric
difference is left-only then right-only.

**CPython.** Hash order, which for `str` changes between runs.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2; `test_ail_sets_general`.

## AR10 — `re` has no `None` for an unmatched group

**Rule.** `m.group(i)` of a group that did not take part raises `ValueError`; CPython returns
`None`. `re.I` over a non-ASCII subject raises `ValueError` because the case-folding tables are
not built.

```python
import re
m = re.match(r"(a)?b", "b")
print(m.group(1))             # CPython None; AIL raises ValueError
```

**CPython.** Returns `None`, because CPython has a `None` for a `str`.

**Status.** refused by rule (loud stop).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A8; [`docs/MIGRATING.md`](../MIGRATING.md) 13.

## AR11 — Trap messages

**Rule.** The text a program can read from a built-in trap is CPython 3.12's for the list in A12:
invalid literals, the six division-by-zero spellings, index errors, pop errors, key errors, file
errors, unpacking errors, `list.index`, `str.index`, `max([])`, `min([])` and `EOF when reading a
line`. Other runtime-built messages keep their own wording; the text of an uncaught exception on
stderr is outside the promise (ED2, ED3, ED7).

```python
try:
    1 % 0
except ZeroDivisionError as e:
    print(e)                  # integer modulo by zero
```

**CPython.** The same for the A12 list. CPython raises `TypeError` in a few places where AIL has
no `TypeError` and raises `RuntimeError` or `ValueError` with CPython's text.

**Status.** implemented for A12; the rest is documented per row.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A12, A45, A71, C244, C186, C187.

## AR12 — Narrow numeric rules

**Rule.** The remaining numeric edges are fixed rather than left to C:

* a negative shift count raises `ValueError: negative shift count` (C183);
* `abs(-0.0)` is `0.0`, with the sign cleared (C225);
* one-argument `round()` of NaN/inf raises CPython's `ValueError` / `OverflowError`, not an
  uncatchable trap (C251);
* `round()` with an `__index__` `ndigits` that overflows stops by name (C180);
* `enumerate` past INT64_MAX stops with `OverflowError: enumerate() index integer overflow`
  (C228);
* `range(0, 5, 0)` raises `ValueError: range() arg 3 must not be zero` (C229);
* a `range` slice whose own start/stop/step leaves int64 stops by name (C224).

**CPython.** Does not have an int64 boundary for these.

**Status.** implemented / refused by name per row.

**Proof.** the C ids named beside each item in [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md).
