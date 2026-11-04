# 1. Typed code, the general path, and integers

AIL compiles a subset of Python 3.12. Annotate function parameters and results, and annotate empty
containers. Those annotations keep a program on the **typed path**, the fast plain-C path. The
samples below are built with `--strict`, which means "the typed path or a refusal".

## Annotated functions and the basic types

An `int` function takes and returns `int` values:

<!-- sample: c1_int -->
```python
def add(a: int, b: int) -> int:
    return a + b


def main() -> None:
    print(add(20, 22))


main()
```

```output
42
```

A `float` result is a C `double`:

<!-- sample: c1_float -->
```python
def average(a: float, b: float) -> float:
    return (a + b) / 2.0


def main() -> None:
    print(f"{average(2.0, 5.0):.2f}")


main()
```

```output
3.50
```

A `str` is UTF-8 text. The string methods used here are built on the typed path:

<!-- sample: c1_str -->
```python
def shout(text: str) -> str:
    return text.strip().upper() + "!"


def main() -> None:
    print(shout("  hello  "))


main()
```

```output
HELLO!
```

A `list[int]` is a list of int64 values:

<!-- sample: c1_list -->
```python
def total(xs: list[int]) -> int:
    s: int = 0
    for x in xs:
        s += x
    return s


def main() -> None:
    values: list[int] = [3, 1, 4, 1, 5]
    print(total(values), len(values))


main()
```

```output
14 5
```

A `dict[str, int]` is a dictionary from text to int64. Read it key by key:

<!-- sample: c1_dict -->
```python
def main() -> None:
    scores: dict[str, int] = {"ann": 30, "bob": 25}
    for name in sorted(scores):
        print(name, scores[name])


main()
```

```output
ann 30
bob 25
```

A small class with annotated fields and a method is also on the typed path:

<!-- sample: c1_class -->
```python
from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int

    def total(self) -> int:
        return self.x + self.y


def main() -> None:
    p = Point(2, 3)
    print(p.x, p.total())


main()
```

```output
2 5
```

## The general path and the note

Some programs are valid Python but are not on the typed path. Printing a whole `dict` is one
example. The compiler builds the program on the slower **general path** and prints a note:

<!-- sample: c1_general_dict general -->
```python
def main() -> None:
    counts: dict[str, int] = {"b": 1, "a": 2}
    print(counts)


main()
```

```output
{'b': 1, 'a': 2}
```

```note
note: c1_general_dict.py:3:5: built on the general path (about 20x slower) because print() given a dict[str, int], not a number or a str. write instead: print an element or a measurement (`print(xs[0])`, `print(len(xs))`), or one line per element (`for x in xs: print(x)`); run with --strict to see why
```

Read the note from left to right: `c1_general_dict.py:3:5` is the first blocker (file, line,
column); "built on the general path" says this build is not typed-fast; the text after "because"
is the reason; and "write instead" is a rewrite that stays typed. The note is on stderr.

`--strict` turns the note into an error. It lists the blockers and builds nothing, with exit status
3:

```strict
strict: 1 typed-path blocker; nothing was built (ranked by the code each one keeps off the typed path)
why not typed: print() given a dict[str, int], not a number or a str.
```

Follow the hint and print one line per element. This version builds with `--strict`:

<!-- sample: c1_strict -->
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

Use `--strict` in CI and in speed-critical projects. Leave it off while you are getting a program
to work.

## Integers

`int` is a signed 64-bit integer by default. `//` and `%` floor like Python, and `/` gives a float:

<!-- sample: c1_ints -->
```python
def main() -> None:
    print(-7 // 2, -7 % 2, 2 ** 40)
    print(7 / 2, 7 // 2, 7 % 2)


main()
```

```output
-4 1 1099511627776
3.5 3 1
```

A result that leaves int64 stops the program. It never wraps silently. Output written before the
stop is kept, the exit status is 1, and the error names the operation and the opt-in:

<!-- sample: c1_overflow stop args=9223372036854775807 -->
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

When a program needs values beyond int64, build with `--exact-int` (or set `AIL_EXACT_INT=1`).
Then integers are exact, as in CPython, at a slower speed:

<!-- sample: c1_exact exact -->
```python
print(9223372036854775808)
print(1 << 100)
```

```output
9223372036854775808
1267650600228229401496703205376
```

## A refusal

Some programs neither path can build. They are refused at compile time, by name, with a
`file:line:col` and a `write instead:` hint. Nothing is built, and the exit status is 3:

<!-- sample: c1_refuse_eval refuse -->
```python
def main() -> None:
    x = 5
    print(eval("x * 2"))


main()
```

```refusal
c1_refuse_eval.py:3:5: not in the subset: call to eval()
write instead: define `eval` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str)
```

Other refused constructs include `exec`, `locals()`, `async def`, and imports of third-party
packages such as `numpy`. The built constructs are listed in `AIL_CURRENT/AIL_REFERENCE.md` and
`AIL_CURRENT/AIL_REFERENCE_MORE.md`.
