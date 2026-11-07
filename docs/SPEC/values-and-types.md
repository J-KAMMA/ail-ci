# Values and types

This chapter fixes the value model: what a name can hold, how wide an integer is, what `None`
means, and which container and class behaviour is part of the language.

## VT1 — Python syntax, optional annotations

**Rule.** AIL source is Python source. Annotations are hints to the compiler and the tools; they
do not create a run-time check and a program may omit all of them. The compiler chooses the
representation, typed or general, from the whole program.

```python
def total(xs):          # no annotation: still a valid AIL program
    return sum(xs)

def total2(xs: list[int]) -> int:   # annotation: a hint, still optional
    return sum(xs)
```

**CPython.** The same, except CPython never uses annotations to choose a representation.

**Status.** implemented.

**Proof.** [`docs/WHY.md`](../WHY.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md)
introduction; the compare-lab `.py` sources in `lab/compare/src`.

## VT2 — `int` is 64-bit by default

**Rule.** `int` is a signed 64-bit value. Arithmetic whose result leaves int64 stops the program;
it never wraps and never silently promotes. A value that is statically known to need more than
int64 is refused at build time, naming the line and `--exact-int`. Exact arbitrary-precision ints
are opt-in for the whole program with `--exact-int` / `AIL_EXACT_INT=1` (about 20x slower).

```python
x = int("9223372036854775807")
print(x + 1)                  # loud stop; CPython prints 9223372036854775808
```

**CPython.** `int` is arbitrary precision.

**Status.** implemented (default int64 and exact mode).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A1; [`docs/LIMITATIONS.md`](../LIMITATIONS.md)
1-2; [`docs/MIGRATING.md`](../MIGRATING.md) 1-2; `test_ail_int64_default`,
`lab/limits/01_int_literal_beyond_int64.py`, `lab/limits/02_int_overflow_runtime.py`.

## VT3 — Per-value big ints (planned)

**Rule.** A local, parameter, return, field or `list[BigInt]` element annotated `BigInt` is exact
without making the rest of the program exact. An operation whose operand is BigInt is exact. A
BigInt that enters a plain `int` place is demoted silently when it fits int64 and stops loudly when
it does not. There is no silent truncation.

```python
from ail.types import BigInt

count: BigInt = 0
values: list[BigInt] = [2 ** 100]
```

**CPython.** Every int is exact, so CPython has no boundary to cross.

**Status.** planned (design accepted; not built in the compiler on this tree).

**Proof.** [`docs/design/BIGINT_TYPE.md`](../design/BIGINT_TYPE.md), owner decisions D1-D5 there.
Do not cite this rule as implemented until the design note's tests exist.

## VT4 — `None` is an exact tagged value

**Rule.** `None` is one exact value, distinct from every number, string, container and object. A
place that may hold `None` is an optional place with an explicit tag; tests with `is None` /
`is not None` are exact. There is no `None` in a place declared `str` or `bytes`.

```python
def find(xs: list[int], v: int):
    for i, x in enumerate(xs):
        if x == v:
            return i
    return None

i = find([1, 2], 2)
print(i is None)              # False
```

**CPython.** The same for `None`; CPython also has `None` in the place of a `str` in a few library
APIs, which AIL refuses or models with an explicit marker.

**Status.** partly (P1 of the roadmap; the tagged None is built for the shapes named in
CALLSITE_SPEC, not for every library API).

**Proof.** [`docs/ROADMAP.md`](../ROADMAP.md) P1; [`docs/design/CALLSITE_SPEC.md`](../design/CALLSITE_SPEC.md);
[`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A8, A24, A42, A45.

## VT5 — `float` is IEEE binary64

**Rule.** A float is an IEEE 754 binary64 value. One operation is C's double operation and agrees
with CPython. A result that CPython computes with a special algorithm uses that algorithm
(`sum()` of floats, see AR5; `math.fsum` is not built).

```python
print(0.1 + 0.2)              # 0.30000000000000004 in both languages
```

**CPython.** The same for a single operation. CPython uses exact fractions in a few library
routines; AIL follows those routines only where a rule says so.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A15, C1.

## VT6 — `bool`, truth values and identity

**Rule.** `bool` is a distinct truth type with `True` and `False`. It is not a number for
identity: `True is 1` is `False`, as in CPython. `is` on numbers is governed by MO8, not by
object identity.

**CPython.** `bool` is a subclass of `int`, so `True == 1`; AIL keeps that arithmetic equality and
the distinct identity.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C115-silent2-2, C114, C115.

## VT7 — `str` is Unicode text

**Rule.** `str` is a sequence of Unicode code points. The typed path carries UTF-8 and has no
16-bit ceiling. The general runtime carries 16-bit units, so a character above U+FFFF is refused
or stopped by name in the places recorded in A22, A59, C191 and C192.

```python
print("héllo", len("héllo"), "é".encode())   # 5 b'h\xc3\xa9'
```

**CPython.** CPython uses a flexible internal representation; a code point above U+FFFF always
works.

**Status.** partly (typed path UTF-8; general path 16-bit with named stops).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A13, A22, A59, C191, C192.

## VT8 — `str` and `bytes` are separate types

**Rule.** A `str` and a `bytes` are never compared for equality or order. Mixing them is refused
at build time or stopped by name; it is never coerced to text. The place where a library call
accepts both is resolved statically from the program text, and an ambiguous value is treated as
`bytes`, so the typed path refuses it with a rewrite hint (`encode` / `decode`).

```python
print("a" == b"a")            # CPython 3.12: False; AIL refuses the comparison
```

**CPython.** `==` between `str` and `bytes` is `False`; ordering raises `TypeError`; some
functions accept either.

**Status.** implemented (refusal by name; A71/A72 for the library calls).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A71, A72; the strict probe note in
`lab/compare_cand/RESULTS-log_scan.md`.

## VT9 — `bytes` and `bytearray`

**Rule.** `bytes` is immutable, `bytearray` mutable. On the general path both are prelude classes.
The built codecs are UTF-8, ASCII and Latin-1 and their aliases, with `strict`, `ignore` and
`replace`. Another codec named by a literal is refused; one computed at run time raises
`LookupError`.

**CPython.** Any registered codec; CPython has the full codec registry.

**Status.** partly (general path; the typed path covers a smaller set).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A59, A72, C177, C210-C212;
[`docs/LIMITATIONS.md`](../LIMITATIONS.md) 16.

## VT10 — Containers and their order

**Rule.** The containers are `list`, `tuple`, `dict`, `set` and `frozenset`. `set` and `frozenset`
iterate in insertion order, not hash order; `set.pop()` removes the first element in that order.
The set operators `|`, `&`, `-`, `^` and their in-place forms keep the left operand's order and
then the new elements of the right operand. A dict keeps insertion order, as in CPython 3.7+.

```python
s = {3, 1, 2}
print(list(s))                # [3, 1, 2] here; CPython's order follows the hash
```

**CPython.** Dicts keep insertion order; sets follow hash order, which for `str` changes between
runs.

**Status.** implemented (both paths).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2; `test_ail_sets_general`.

## VT11 — Dict views are snapshots and are refused as values

**Rule.** AIL has no live view object. `d.items()`, `d.keys()` and `d.values()` are exact when
consumed where they are written. Keeping a view in a name, field, item or container is refused,
because the stored value would be a snapshot and a loop over it would not raise when the dict
changes size. To keep a snapshot, write `list(d.items())`.

```python
d = {"a": 1}
v = d.items()                 # refused by name: a view kept in a name
print(list(d.items()))        # correct: [('a', 1)]
```

**CPython.** A view is live: it follows a later store and a loop over it raises when the dict
changes size.

**Status.** refused (with the residual named in LIMITATIONS: a view returned from a function can
still reach the general path as a stale snapshot).

**Proof.** [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 3; [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md)
C105-C107, C116; `lab/limits/03_dict_view_is_snapshot.py`.

## VT12 — Classes and records

**Rule.** A class may have at most one base. The modelled decorators are `@staticmethod` on a
method and `@functools.lru_cache` / `@lru_cache` / `@cache`; any other decorator is refused by
name. Class bodies, `__init__`, properties, class methods, inherited methods and `dataclass`
equality (where supported) keep CPython's answer. Operator methods have no `NotImplemented`
(A51); multiple inheritance, metaclasses outside the modelled set, and dynamic attribute creation
are not built.

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return isinstance(other, Point) and (self.x, self.y) == (other.x, other.y)
```

**CPython.** Multiple inheritance, arbitrary decorators, metaclasses and unrestricted dynamic
attributes.

**Status.** partly (single inheritance and the common forms; see A51 for the class-library
differences and LIMITATIONS 6-7 for the refusals).

**Proof.** [`docs/LIMITATIONS.md`](../LIMITATIONS.md) 6-7; [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md)
A45, A51, A52; `test_ail_class_reach`.

## VT13 — Text I/O, `sys.argv` and the clock

**Rule.** Text files are UTF-8 unless `encoding=` names ASCII or Latin-1. `sys.argv` holds `str`.
The wall clock is an input: `AIL_CLOCK=<seconds>` pins every clock read and makes `sleep()`
advance it without sleeping. `time`, `datetime` and the date/time formatting rules in A28-A30
are part of the value model, not an accident of the host.

**CPython.** Uses the locale encoding for text files (the same as UTF-8 under `PYTHONUTF8=1`) and
has no clock pin.

**Status.** implemented for the declared surface; other encodings and tz databases are refused.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A16, A28-A30; `test_ail_clock`,
`test_ail_files`.
