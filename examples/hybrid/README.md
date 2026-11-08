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

The installed `ail` command cannot build a hybrid, and neither can the SDK bundled in the wheel.
`ail build` forwards to the SDK's `compile`, which has no `--cpython`; the bundled SDK refuses
`build` by name (see the finding below).  Only the source-checkout command above produces a hybrid.
The installed `ail` still runs the same program on the default standalone build:

```sh
ail run examples/hybrid/collatz.py 200000      # default build; same stdout and exit status
```

Every example accepts the small argument shown by its test.  `collatz.py` also accepts a single
start above the loop range; passing `2**63 + 1` exercises the int64 boundary fallback.

## Rules for an accelerated function

- Be a top-level function, not a method, nested function, class, or generator:
  `def f(n: int) -> int:` at module level is a candidate; a `def f(self, ...)` inside a `class` is not.
- Annotate every parameter `int`, `bool`, `float`, `str`, `list[int]`, or `list[float]`, and return
  `int`, `bool`, `float`, or `str`: `def f(n: int) -> int:`.
- Do not print: `print(n)` keeps the function in CPython.
- Do not mutate a list parameter: `xs.append(1)` keeps the function in CPython.
- Do not index, divide by a non-constant, call an unproven function, raise, assert, use
  `try`/`with`/`import`, touch a global, delete, or assign an attribute/index:
  `return xs[0]` and `return a % b` are refused (a nonzero constant divisor such as `n % 2` is
  allowed because it cannot raise).
- Do not compare numbers with `is`: `return a is b` keeps the function in CPython.
- Keep int literals inside int64, and let an int expression overflow only when the function returns
  `int` or `bool` so the wrapper can fall back: `def f(n: int) -> int: return n * n` is safe, while
  a module-level `print(f(2 ** 63 + 1))` emits no unit at all (see the finding below).

## Measured table

Default arguments, median of 3 runs each, CPython 3.12.3 on the four-core CI runner.  Times are
wall clock milliseconds for the whole program, including process start-up.

| example | accelerated | python3 ms | hybrid ms | speed-up |
| --- | --- | ---: | ---: | ---: |
| `collatz.py` | yes | 1500 | 79 | 19.0x |
| `mandel_rows.py` | yes | 717 | 27 | 26.2x |
| `prime_count.py` | yes | 912 | 44 | 20.8x |
| `checksum_text.py` | yes | 16.3 | 17.9 | 0.9x (before obs5; not re-timed) |
| `sum_squares_list.py` | yes | 123.8 | 127.6 | 1.0x (before obs3; not re-timed) |
| `fallback_demo.py` | yes | 12.8 | 24.0 | 0.5x |

`fallback_demo.py` is slower because it makes only four calls and pays the wrapper and extension
load cost; it is there to show the boundary, not to be fast.

## Findings

**The installed `ail` cannot build a hybrid, and neither can its bundled SDK.**  `packaging/ail_lang/cli.py`
maps `ail build` to the SDK's `compile` command and does not forward `--cpython`, so the flag reaches
a parser that has no such option:

```sh
ail build --cpython examples/hybrid/collatz.py -o /tmp/collatz-hybrid
# ail_chatgpt.py: error: unrecognized arguments: --cpython
```

The wheel does bundle `ail_lang/sdk/ail_chatgpt.py`, but an exported SDK (`kind:
ail_language_sdk`, with `SDK_README_JA.md`) refuses `build` by name, so calling that file directly
does not help either:

```sh
SDK=$(python3 -c 'import ail_lang, pathlib; print(pathlib.Path(ail_lang.__file__).parent / "sdk")')
python3 -B "$SDK/ail_chatgpt.py" build --cpython examples/hybrid/collatz.py -o /tmp/collatz-hybrid
# ail_chatgpt.py: error: this language SDK supports: doctor, integrity, cache, compile, ...
```

Both refusals happen before the hybrid lane runs, in files this lane does not own
(`packaging/ail_lang/cli.py` and the SDK export), so the examples and the test build from a
checkout with `python3 AIL_CURRENT/ail_chatgpt.py build --cpython`.

**Fixed in obs5: `%`, `//` and `/` with a variable divisor.**  Accepted when both operands are
proven int/bool/float; a zero divisor abandons the native call and CPython re-runs it, so the
ZeroDivisionError is CPython's own.  (`prime_count.py` was written with trial division by
repeated subtraction while `%` was refused; it is left as it was.)

**Fixed in obs5: `ord` of one character.**  `ord(x)` raises unless `x` is a str of length one;
an element of a proven str (`s[i]`, `for ch in s`) always is, so the hybrid now accepts that
call (`ail_cpython_hybrid._single_char`) and `checksum_text.py`'s `rolling_hash` is accelerated.
`ord(p)` of a `str` parameter of unknown length stays in CPython.

**Fixed in obs3: a `list[float]` parameter produced no mixed-mode unit.**  `to_c` passes such a
list as an `ail_flist` struct, which the base mixed mode does not call; the hybrid now builds that
unit itself and its wrapper passes the struct (`ail_cpython_hybrid._unit_abi`), so
`sum_squares_list.py` is accelerated.  Before obs3 it was not even listed as rejected:

```python
def f(xs: list[float]) -> float:
    return 0.0
print(f([1.0]))
```

`build.json` had `"accelerated": []` and an empty `"rejected"` map.

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
