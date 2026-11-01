# AIL tutorial

About 20 minutes. You need a working setup from [INSTALL.md](INSTALL.md): `pip install` the
`ail-lang` package (or use a git checkout) and a C compiler. Check with:

```sh
ail doctor
```

AIL compiles a subset of Python 3.12 to C. Its rule: a compiled program prints exactly what
CPython 3.12 prints, or the compiler refuses it. There are two code paths:

- the **typed path**: fast, plain C code;
- the **general path**: slower, but covers more of Python (dynamic values, printing a dict, and so
  on). When the typed path cannot take a program, the compiler builds it on the general path and
  says so.

Every Python sample on this page is built and run by a test
(`AIL_CURRENT/test_ail_tutorial.py`) and must print what CPython prints, so the code and the
`output` blocks below are not hand-edited guesses. Paths and hashes in compiler messages differ on
your machine, so they are left out.

In a git checkout there is no `ail` command. Use `python3 AIL_CURRENT/ail_chatgpt.py compile
prog.py -o prog` where this page says `ail build prog.py -o prog`, and run the program yourself.

## 1. Hello world

Put this in `hello.py`:

<!-- sample: hello -->
```python
print("Hello, AIL!")
```

```sh
ail run hello.py          # compile to a temporary executable and run it
ail build hello.py -o hello && ./hello
```

```output
Hello, AIL!
```

`ail build` writes a small native executable (about 16 KB) that needs only the C library.
`ail build` will not overwrite an existing `-o` file; delete it first when you rebuild.

## 2. A typed program: the fast path

Annotate function parameters, results and empty containers. `stats.py`:

<!-- sample: stats -->
```python
def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def main() -> None:
    temps: list[float] = [21.5, 19.0, 23.25, 18.75, 22.0]
    print(f"days: {len(temps)}")
    print(f"mean: {mean(temps):.2f}")
    print(f"max:  {max(temps)}")
    warm = [t for t in temps if t > 20.0]
    print("warm days:", warm)


main()
```

```output
days: 5
mean: 20.90
max:  23.25
warm days: [21.5, 23.25, 22.0]
```

If `ail build` prints no `note:` line, the program is on the typed path. To be sure, build with
`--strict`: it never falls back to the general path. It builds a typed program exactly as before
and refuses anything else (next section).

## 3. The general path, the note, and `--strict`

Some programs the typed path cannot take. `counts.py` prints a whole dict:

<!-- sample: counts general -->
```python
def main() -> None:
    counts: dict[str, int] = {"b": 1, "a": 2}
    print(counts)


main()
```

```output
{'b': 1, 'a': 2}
```

The build works and the program prints what CPython prints, but the compiler tells you it took
the slower route:

```note
note: counts.py:3:5: built on the general path (about 20x slower) because print() given a dict[str, int], not a number or a str.
```

How to read the note: `counts.py:3:5` is where the first blocker is (file, line, column);
"built on the general path" says the whole program (or the part named) is not typed-fast;
"about 20x slower" is the rough cost; the text after "because" is the reason; and
`write instead:` (later in the same line) is a rewrite that keeps the code on the typed path.

`--strict` turns the note into an error and lists every blocker, ranked by how much code each one
keeps off the typed path. Nothing is built (exit status 3):

```strict
strict: 1 typed-path blocker; nothing was built (ranked by the code each one keeps off the typed path)
1. counts.py:3:5  blocks 4 lines (main)
code:          print(counts)
why not typed: print() given a dict[str, int], not a number or a str.
write instead: print an element or a measurement (`print(xs[0])`, `print(len(xs))`), or one line per element (`for x in xs: print(x)`)
```

(In the real output the lines after the first are indented.) Follow the hint and print one line
per element. `counts2.py`:

<!-- sample: counts2 -->
```python
def main() -> None:
    counts: dict[str, int] = {"b": 1, "a": 2}
    for key in sorted(counts):
        print(key, counts[key])


main()
```

```output
a 2
b 1
```

This builds with `--strict`. Use `--strict` in CI and in speed-critical projects (`ail build
--strict`, `ail run --strict`, `AIL_STRICT=1`, or `strict = true` in `ail.toml`); leave it off
while you are only getting a program to work. `ail check prog.py` does the source and type check
alone and needs no C compiler.

### A refusal

Some programs neither path can build. They are refused at compile time, by name, with
`file:line:col` and a `write instead:` hint. Nothing is built, and the exit status is 3.
`double.py`:

<!-- sample: double refuse -->
```python
def main() -> None:
    x = 5
    print(eval("x * 2"))


main()
```

```refusal
double.py:3:5: not in the subset: call to eval(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one
write instead: define `eval` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str)
```

Other things refused this way include `exec`, `locals()`, `async def`, and imports of third-party
packages such as `numpy`. The list of what is built is in `AIL_CURRENT/AIL_REFERENCE.md` and
`AIL_CURRENT/AIL_REFERENCE_MORE.md`.

## 4. Integers

`int` is a signed 64-bit integer by default. A program whose values fit prints what CPython
prints; `//` and `%` floor like Python (`-7 // 2` is `-4`), and `/` always gives a float.

<!-- sample: ints -->
```python
def fact(n: int) -> int:
    r: int = 1
    for i in range(2, n + 1):
        r *= i
    return r


print(fact(20))
print(-7 // 2, -7 % 2, 2 ** 40)
print(7 / 2, 7 // 2, 7 % 2)
```

```output
2432902008176640000
-4 1 1099511627776
3.5 3 1
```

A result that leaves int64 stops the program; it never wraps silently. Standard output written
before the stop is kept, the exit status is 1, and the error names the operation and the opt-in:

<!-- sample: int_stop stop args=9223372036854775807 -->
```python
import sys

n: int = int(sys.argv[1])
print("before")
print(n + 1)
```

```stdout
before
```

```stderr
OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)
```

A value the *source* needs beyond int64, such as a literal or a constant expression, is refused
at compile time instead. The message names the file, line and column, and says how to opt in:

<!-- sample: int_static static -->
```python
def main() -> None:
    print(10 ** 30)


main()
```

```refusal
int_static.py:2:11: int64 constant out of range: 1000000000000000000000000000000
  write instead: keep the value inside int64, or compile with --exact-int (or AIL_EXACT_INT=1) for exact big ints, about 20x slower
```

Build with `ail build --exact-int` (in a checkout, `python3 AIL_CURRENT/ail_chatgpt.py compile
--exact-int`) or set `AIL_EXACT_INT=1` to get CPython's exact (arbitrary size) integers. That is
the old behaviour, about 20x slower, and it makes these values print exactly as CPython does:

<!-- sample: int_exact exact -->
```python
print(9223372036854775808)
print(1 << 100)
print(10 ** 30)
```

```output
9223372036854775808
1267650600228229401496703205376
1000000000000000000000000000000
```

## 5. Lists, dicts and strings

<!-- sample: text -->
```python
def main() -> None:
    words: list[str] = "the quick brown fox jumps over the lazy dog the end".split()
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    for w in sorted(counts):
        print(w, counts[w])

    s: str = "  AIL compiles Python to C  "
    print(s.strip().upper(), len(s))

    parts: list[str] = []
    for w in words[:4]:
        parts.append(w.upper())
    print("-".join(parts))
    print(words[1:4], words[-1])

    squares: list[int] = [n * n for n in range(1, 6) if n != 3]
    print(squares, sum(squares))


main()
```

```output
brown 1
dog 1
end 1
fox 1
jumps 1
lazy 1
over 1
quick 1
the 3
AIL COMPILES PYTHON TO C 28
THE-QUICK-BROWN-FOX
['quick', 'brown', 'fox'] end
[1, 4, 16, 25] 46
```

This whole program is on the typed path (it builds with `--strict`). Rules of thumb: declare the
element type of an empty list or dict (`list[str]`, `dict[str, int]`), keep each list to one
element type, and print numbers and strings, or loop over a container, instead of printing a
container with a mixed type. When something falls off the fast path, the note or `--strict`
tells you which line and what to write instead (section 3).

## 6. Calling C (FFI)

`ail_ffi` declares C functions as Python stubs. Under CPython the stubs run through `ctypes`, and
`ail build` compiles them to direct C calls, so the same file runs both ways. `ffi.py`:

<!-- sample: ffi -->
```python
from ail_ffi import *

link("m")                                   # -lm


@extern(header="math.h", symbol="hypot")
def c_hypot(x: c_double, y: c_double) -> c_double: ...


@extern(header="stdlib.h", symbol="abs")
def c_abs(x: c_int) -> c_int: ...


print(c_hypot(3.0, 4.0))
print(c_abs(-42))
```

```output
5.0
42
```

The compiler checks each declaration against the C header, so a wrong prototype is a compile-time
error. Out-parameters, byte buffers, error codes turned into exceptions, and opaque handles are
described in "Native libraries" in `AIL_CURRENT/AIL_REFERENCE_MORE.md`. In the other direction,
`ail build --lib NAME prog.py` builds the `@export` functions of a file as a C library
(`libNAME.so`, `libNAME.a`, `NAME.h`).

## 7. Typed arrays and the GPU (briefly)

`ail_array` gives arrays with a declared element type (`f64`, `f32`, `f16`, `int8`, `int32`).
Operations are element-wise, floats are IEEE, `int` arrays raise on overflow, and sums use one
fixed order, so the result is the same everywhere. `arr.py`:

<!-- sample: arr -->
```python
import ail_array as ta

a = ta.array([1.0, 2.5, 4.0], ta.f64)
b = a * 2.0 + a
print(ta.sum(b))
print(b[1])
```

```output
22.5
7.5
```

A loop marked with the comment `# ail: gpu` is a candidate for the GPU. Build with `--gpu`. At
run time the kernel runs on a Vulkan device that has the needed features; with no such device, or
for any input where the GPU could differ from the CPU, the loop runs on the CPU, so the program
always prints what CPython prints. `gpu.py`:

<!-- sample: gpu gpu -->
```python
def main() -> None:
    n: int = 1000
    a: list[float] = [i * 0.5 for i in range(n)]
    b: list[float] = [1.0] * n
    out: list[float] = [0.0] * n
    # ail: gpu
    for i in range(n):
        out[i] = a[i] * 2.0 + b[i]
    print(out[0], out[10], out[999])


main()
```

```output
1.0 11.0 1000.0
```

The GPU path is opt-in and still young: only loops that fit the rules in
`AIL_CURRENT/AIL_REFERENCE_MORE.md` are offloaded, and the compiler explains each one it refuses.

## Where to read more

- [INSTALL.md](INSTALL.md): setup on Linux, macOS and Windows (WSL), and troubleshooting.
- `AIL_CURRENT/AIL_REFERENCE.md`: the short core reference.
- `AIL_CURRENT/AIL_REFERENCE_MORE.md`: the longer sections, including strict mode, the standard
  library modules, FFI and export.
- [`DIFFERENCES.md`](../DIFFERENCES.md): known differences from CPython.
- `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md`: many small examples, in Japanese.
