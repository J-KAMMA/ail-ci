# CPython hybrid examples

The hybrid keeps the whole program running in CPython and compiles selected top-level typed
functions into a C extension module.  The boundary checks every argument and result; a value it
cannot carry exactly (a different type, an int outside int64, a mutated list) re-enters the
original Python function.  Output and exit status therefore stay CPython's.  The flag is opt-in:
`ail build --cpython SRC -o DIR`; the default standalone build is unchanged.

## Build and run

From a checkout:

```sh
python3 AIL_CURRENT/ail_chatgpt.py build --cpython examples/hybrid/collatz.py -o /tmp/collatz-hybrid
/tmp/collatz-hybrid/collatz 200000
python3 examples/hybrid/collatz.py 200000          # same stdout and exit status
```

With the installed `ail` command:

```sh
ail build --cpython examples/hybrid/collatz.py -o /tmp/collatz-hybrid
/tmp/collatz-hybrid/collatz 200000
```

Every example accepts the small argument shown by its test.  `collatz.py` also accepts a single
start above the loop range; passing `2**63 + 1` exercises the int64 boundary fallback.

## Rules for an accelerated function

- Be a top-level function, not a method, nested function, class, or generator.
- Annotate every parameter `int`, `bool`, `float`, `str`, `list[int]`, or `list[float]`, and return
  `int`, `bool`, `float`, or `str`: `def f(n: int) -> int:`.
- Do not print: `print(n)` keeps the function in CPython.
- Do not mutate a list parameter: `xs.append(1)` keeps the function in CPython.
- Do not index, divide by a non-constant, call an unproven function, raise, assert, use
  `try`/`with`/`import`, touch a global, delete, or assign an attribute/index:
  `return xs[0]` and `return a % b` are refused (a nonzero constant divisor such as `n % 2` is
  allowed because it cannot raise).
- Do not compare numbers with `is`, and do not need an int beyond int64 unless the function
  returns `int`/`bool` so the overflow wrapper can fall back.

## Measured table

Default arguments, median of 3 runs each, CPython 3.12.3 on the four-core CI runner.  Times are
wall clock milliseconds for the whole program, including process start-up.

| example | accelerated | python3 ms | hybrid ms | speed-up |
| --- | --- | ---: | ---: | ---: |
| `collatz.py` | yes | 1500 | 79 | 19.0x |
| `mandel_rows.py` | yes | 717 | 27 | 26.2x |
| `prime_count.py` | yes | 912 | 44 | 20.8x |
| `checksum_text.py` | no | 16.3 | 17.9 | 0.9x |
| `sum_squares_list.py` | no | 123.8 | 127.6 | 1.0x |
| `fallback_demo.py` | yes | 12.8 | 24.0 | 0.5x |

`fallback_demo.py` is slower because it makes only four calls and pays the wrapper and extension
load cost; it is there to show the boundary, not to be fast.

## Findings

**`%` with a variable divisor is refused.**  The body gate treats `Mod` like division because the
divisor can be zero.  A constant nonzero divisor is allowed.

```python
def f(a: int, b: int) -> int:
    return a % b
```

`build.json` rejects `f` with `"division or power can raise"`.  `prime_count.py` therefore does
trial division by repeated subtraction.

**`ord` is an unsafe call.**  A single call with no loop may not reach the emitter at all, but a
loop over a `str` parameter shows the refusal:

```python
def f(s: str) -> int:
    h = 0
    for ch in s:
        h += ord(ch)
    return h
print(f("abc"))
```

`build.json` rejects `f` with `"a call can raise or have side effects"`.  `checksum_text.py` is
the full version of this example and runs entirely in CPython.

**A `list[float]` parameter produces no mixed-mode unit.**  It is not even listed as rejected; the
analysis finds no unit to select.

```python
def f(xs: list[float]) -> float:
    return 0.0
print(f([1.0]))
```

`build.json` has `"accelerated": []` and an empty `"rejected"` map.  The same function with
`list[int]` is accelerated.  `sum_squares_list.py` keeps the requested `list[float]` and records
this limit.

**A direct call with a non-annotated type demotes the whole function.**  The module kind analysis
sees the float before the hybrid selection does:

```python
def f(n: int) -> int:
    return n + 1
print(f(2.5))
```

No unit is emitted, so there is nothing to fall back from.  `fallback_demo.py` reaches the same
wrapper through `g = f` and calls `g(2.5)`; the function stays accelerated and the float call
still falls back at the boundary.

**A large int literal in the module also stops unit emission.**  Constructing the value at run
time avoids the analysis-time big-int mark:

```python
def f(n: int) -> int:
    return n + 1
print(f(2 ** 63 + 1))
```

No unit is emitted.  `fallback_demo.py` uses `int("9223372036854775809")` and the function stays
accelerated; the boundary then falls back for that value.
