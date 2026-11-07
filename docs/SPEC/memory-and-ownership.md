# Memory and ownership

Python programs are written as if every object is a reference with a lifetime decided by
reference counting. AIL keeps the observable part of that model and says where it cannot, so a
program never reads a freed object and never silently copies where CPython shares.

## MO1 — Assignment shares a container

**Rule.** `ys = xs` binds the same container to a second name. A write through one name is visible
through the other. A copy happens only when the program asks for one (`list(xs)`, `xs[:]`,
`copy.copy`). The IR default is this rule; the legacy emitter's copying behaviour is not.

```python
xs = [1]
ys = xs
ys.append(2)
print(xs)                     # [1, 2]
```

**CPython.** The same.

**Status.** implemented on the IR path (the rule); the legacy path is a named difference, not an
alternative meaning.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A65(a)(b).

## MO2 — Augmented assignment to an item mutates in place

**Rule.** `xs[i] += v`, `d[k] += v` and the other in-place operators mutate the object already in
the container, then store it back. An alias sees the mutation. This holds through a list inside
a list and through a shared outer list.

```python
a = [1]
h = [a, a]
h[1] += [3]
print(a)                      # [1, 3] in both languages
```

**CPython.** The same.

**Status.** implemented (`ail_op_iadd`).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C85.

## MO3 — Typed container fields may be snapshots

**Rule.** On the typed path a container stored in a class field may be a snapshot at the point of
the store. A shape where that would be observable (a field written after the store, an alias
expecting the change) is refused. The rule is "refuse the shape, never answer differently".

```python
class Box:
    def __init__(self, xs: list[int]):
        self.xs = xs          # may be copied on the typed path

b = Box([1])
b.xs.append(2)
print(b.xs)                   # [1, 2]; the field is the program's own list, not the outer alias
```

**CPython.** Stores the reference, so an outer alias also changes.

**Status.** refused where observable; documented difference where not.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C85; [`docs/design/ARENA1.md`](../design/ARENA1.md).

## MO4 — Borrowed parameters and element-written lists

**Rule.** A read-only parameter is borrowed, not copied: the callee reads the caller's buffer. A
`list` parameter that the callee writes element by element (`xs[i] = ...`, `xs[i] += ...` with an
int element) is passed as the caller's buffer, so the caller sees the writes; it is not copied
per call. A parameter that the callee rebinds (`xs = []`) or resizes is not element-written and is
handled by the general rules.

```python
def scale(xs: list[int], k: int) -> None:
    for i in range(len(xs)):
        xs[i] *= k

a = [1, 2]
scale(a, 3)
print(a)                      # [3, 6]
```

**CPython.** Mutates the caller's list in both cases.

**Status.** implemented on the typed path (the `fclist1` change, 2026-11-07); the conditions are
checked before the call is lowered.

**Proof.** [`AIL_CURRENT/DEVLOG.md`](../../AIL_CURRENT/DEVLOG.md) entry "fclist1";
[`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) ownership rules O1-O3.

## MO5 — A stored view would be a snapshot, so it is refused

**Rule.** Following VT11: a dict view kept past a mutation is refused. A loop over `d.items()`
written in the loop header, or `list(d.items())`, is exact; a name holding the view is not.

```python
d = {"a": 1}
items = list(d.items())       # correct: a list
d["b"] = 2
print(items, list(d.items()))
```

**CPython.** A view stored in a name follows the dict and raises if the dict grows during a loop.

**Status.** refused.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C106, C107, C116;
[`docs/LIMITATIONS.md`](../LIMITATIONS.md) 3.

## MO6 — File lifetime is explicit, not reference-counted

**Rule.** A file is closed by `close()`, by the end of its `with` block, or at exit. It is not
closed when its last Python reference goes away. Data written without an explicit close is flushed
at exit, including when an uncaught exception ends the program; the flush happens before the
exception text is printed. `tell()` is a byte offset; `seek` cookies are opaque.

```python
f = open("out.txt", "w")
f.write("x")
# f is not closed here; out.txt is complete only after close or exit
```

**CPython.** Closes when the last reference is collected (immediately under refcounting on
CPython, not under another implementation).

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A17, A18, A19; `test_ail_files`.

## MO7 — FFI buffers are borrowed

**Rule.** A `bytes` passed to C is the program's buffer, not a copy. A `bytearray` may be written
by C, but its length cannot change. A compiled program copies a `bytearray` in and out around the
call. A list passed to C is an `int64`/`double` buffer with the declared element type.

```python
buf = bytearray(16)
fill(buf, 16)                 # C writes into the borrowed buffer
```

**CPython.** A `bytes` object is immutable, so a C extension that writes it is undefined; AIL
declares the borrow.

**Status.** implemented for `bytes`, `bytearray` and typed arrays; the safety contract is in the
FFI chapter (MF5, MF6).

**Proof.** [`docs/FFI.md`](../FFI.md); [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A63.

## MO8 — `is` on numbers

**Rule.** `is` on two numbers is not object identity. The defined identities are `None`, `True`,
`False`, and a small-int cache (the CPython range -5..256) when the compiler can prove both sides
are in it. Any other `is` between numbers is refused (C114/C115) or, where a general-path shape
slips through, stopped by name; it never returns an address-identity answer.

```python
a = 1000
b = 1000
print(a is b)                 # CPython may be True or False; AIL refuses
print(None is None)           # True in both
```

**CPython.** Compares object identity, which for `int` depends on the cache and the compiler's
constant folding.

**Status.** refused by rule.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C114, C115, C115-silent2-1,
C115-silent2-2.

## MO9 — The CPython hybrid copies at the boundary

**Rule.** `ail build --cpython` (MF7) copies a `list[int]` or `list[float]` argument into a
Python list for the original function, copies the result back for a `list`, and refuses a call
that mutated its list argument (the mutation would be lost). Any boundary failure runs the
original Python function, so the hybrid is never less correct than CPython; the standalone build
is not affected.

```bash
ail build --cpython prog.py -o prog
```

**CPython.** The original Python program, unchanged.

**Status.** implemented (explicit mode, not the default).

**Proof.** [`docs/design/CPYTHON_HYBRID.md`](../design/CPYTHON_HYBRID.md) section 2-3;
`test_ail_cpython_hybrid`.

## MO10 — Retention is a fallback, not undefined behaviour

**Rule.** AIL proves ownership, bounds and race freedom where it can. Where a proof fails it
keeps a runtime check: a retain/release on a shared object, a bounds helper on an unchecked index,
the lock around a shared write. The result is a safe program with a cost, never a program with
undefined behaviour. A failed proof prints the ED4 line and keeps the check.

```text
prog.py:12: could not prove index is in range: index may be negative; runtime check kept
```

**CPython.** Does not have these proofs; every operation is checked.

**Status.** implemented.

**Proof.** [`docs/design/SAFETY_PROOF.md`](../design/SAFETY_PROOF.md) sections 1-4;
`test_ail_safetynet`.
