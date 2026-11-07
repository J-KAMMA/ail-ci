# Evaluation order and determinism

AIL programs are meant to be re-run, compared and fuzzed, so the order of visible effects is part
of the language. This chapter fixes that order and the inputs that are allowed to vary.

## EO1 — Source order is the order of visible effects

**Rule.** Expressions and statements run in source order. An operand that can raise or run code is
evaluated before the next operand is touched. A lowering may not hoist a visible side effect (a
`print`, an append, an FFI call with an effect) in front of an earlier operand, even when that
would be faster.

```python
def f():
    print("f")
    return 1

def g():
    print("g")
    return 2

print(f() + g())              # f, then g, then 3
```

**CPython.** The same left-to-right order.

**Status.** implemented; a lowering bug that moved an effect was found and fixed on
2026-11-03, so this is a rule with a regression behind it.

**Proof.** [`DIFFERENCES.md`](../../DIFFERENCES.md) row `C?-job-fz216-11021859-1`;
`test_ail_fz216.py`.

## EO2 — Changing a container during iteration

**Rule.** Iterating a dict or a set and then changing its size stops at the next iteration step
with `RuntimeError("dictionary changed size during iteration")` or
`RuntimeError("Set changed size during iteration")`. The check is per step, as in CPython; a
change that keeps the size (replace a value) does not stop the loop.

```python
d = {"a": 1, "b": 2}
for k in d:
    d["c"] = 3               # RuntimeError at the next step
```

**CPython.** The same for a size change. CPython's dict check is cheaper and can, in rare
patterns, miss a change; AIL checks the size at each step.

**Status.** implemented.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C4.

## EO3 — Generator expressions are lazy, or refused

**Rule.** A generator expression is lazy. A generator expression whose body can raise, saved in a
name or returned, is refused by name rather than made eager, because an eager body would raise at
a different line and in a different order. Consume it where it is written, write a list
comprehension, or use an explicit generator function.

```python
g = (1 / x for x in [1, 0])    # refused: a lazy body that can raise, kept as a value
print(list(1 / x for x in [1, 0]))   # correct: consumed where written; raises at once
```

**CPython.** Keeps the generator; the `ZeroDivisionError` happens when the generator is advanced.

**Status.** refused (the lazy success shapes are implemented; the stored raising shape is
refused).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) C241, C242,
`C?-job-stdlib2-11011233-1`, `C?-job-stdlib2-11020039-1`.

## EO4 — `print()` evaluates its arguments before writing

**Rule.** On the typed path every argument of a `print()` call is converted with `__str__` before
the first character is written. If the second `__str__` raises, the first argument has not been
printed. CPython writes each argument after its own conversion.

```python
class A:
    def __str__(self):
        print("A", end="")
        return "a"

class B:
    def __str__(self):
        raise ValueError("b")

print(A(), B())
```

**CPython.** Prints `Aa` and then raises. AIL raises before printing.

**Status.** documented difference (declared; not silently changed).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A52(b).

## EO5 — The clock, environment and filesystem are inputs

**Rule.** A program's result is a function of its inputs: argv, stdin, the files it reads, the
environment it names, and the clock. `AIL_CLOCK=<seconds>` pins every clock read and makes
`sleep()` advance the pin without sleeping. Addresses, object ids, thread ids and hash order are
not inputs a program may use; a shape that would expose them is refused (EO8).

```bash
AIL_CLOCK=1700000000 ./prog
```

**CPython.** Reads the real clock and hash order.

**Status.** implemented for the clock and the date/time surface; other determinism sources are
listed in the compare lab.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A28-A30; `test_ail_clock`.

## EO6 — Sorting is stable; the comparison count is not fixed

**Rule.** `sorted`, `list.sort` and `heapq` produce the same order as CPython's stable sort. The
number and the order of `__lt__` calls may differ from Timsort when an unboxed sort is used; a
program may observe the order of the result, not the sequence of comparisons. A NaN sort key is
refused (AR7).

```python
print(sorted(["b", "a", "c"]))   # ['a', 'b', 'c']
```

**CPython.** Timsort; the number of comparisons is part of what a `__lt__` with an effect can see.

**Status.** partly (order is exact; the comparison count is only fixed for the stable paths that
do not use the unboxed sort).

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A52(a), `C?-job-refuzz95-10300605-1`.

## EO7 — Parallel `map` preserves input order

**Rule.** A typed `map` over a range or a list returns results in input order and raises the
exception of the lowest input index, not the one that finished first. The reduction for `submit`
and `map` follows that order (CO2).

```python
with ThreadPoolExecutor(4) as pool:
    out = list(pool.map(work, range(100)))
print(out == [work(i) for i in range(100)])   # True
```

**CPython.** `map` yields in input order too; the exception timing follows the input order.

**Status.** implemented for the recognised shapes.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A66, A74, A75;
[`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md).

## EO8 — No addresses, ids or hash order

**Rule.** A program may compare values. It may not depend on where they live. `id()`, `hash()` of
a `str` in a printed form, the address of an object, a thread id and the iteration order of a
hash set are outside the promise. A construct that would make an answer depend on them (a
`set` of `id`-like keys, a comparison of two object addresses, `repr` of a default object) is
refused or documented as a difference per row.

```python
print(id(1) == id(1))         # CPython True; AIL refuses or answers by the MO8 rule
```

**CPython.** Exposes addresses and hash order.

**Status.** refused / documented per row.

**Proof.** [`docs/spec/DIFFERENCES.md`](../spec/DIFFERENCES.md) A2, A39, A72,
`C?-job-std_pprint-11011616-2`.

## EO9 — A parallel region combines in iteration order

**Rule.** The combine step of a parallel region is the sequential one: partials are combined in
iteration order, never in completion order. With `out[k]` partials the program writes its own
combine and the order is the loop's. This is what makes CO3-CO5 sound and what a locked fallback
must also produce.

```python
partial = [0.0] * 8
for k in par_range(8):
    partial[k] = chunk_sum(data, k)
total = sum(partial)          # deterministic
```

**CPython.** Has no parallel loop; a thread version would need its own lock.

**Status.** implemented for the typed shapes; the reduce order is the design's fixed order
([`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md)).

**Proof.** [`docs/design/PAR_REDUCE.md`](../design/PAR_REDUCE.md);
[`docs/design/TYPED_PARALLEL.md`](../design/TYPED_PARALLEL.md).
