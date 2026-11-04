# 3. Errors and exit status

Errors are ordinary Python exceptions. Name the kinds you catch; there is no bare `except`.
Uncaught errors print a message on stderr and exit with status 1.

## try, except, else and finally

`else` runs when no exception was raised, and `finally` always runs:

<!-- sample: c3_try -->
```python
def parse(text: str) -> int:
    return int(text)


def main() -> None:
    try:
        value: int = parse("12")
    except ValueError:
        print("bad")
    else:
        print("ok", value)
    finally:
        print("done")


main()
```

```output
ok 12
done
```

`finally` also runs after a caught error:

<!-- sample: c3_finally -->
```python
def main() -> None:
    try:
        raise ValueError("stop")
    except ValueError:
        print("caught")
    finally:
        print("cleanup")


main()
```

```output
caught
cleanup
```

## Raising and catching

Raise a `ValueError` with a message, and catch it by name:

<!-- sample: c3_raise -->
```python
def check(n: int) -> None:
    if n < 0:
        raise ValueError("negative")
    print("ok", n)


def main() -> None:
    check(5)
    try:
        check(-1)
    except ValueError as e:
        print(e)


main()
```

```output
ok 5
negative
```

`int("x")` raises `ValueError`, and the message is CPython's:

<!-- sample: c3_valueerror -->
```python
def main() -> None:
    try:
        n: int = int("x")
        print(n)
    except ValueError as e:
        print("ValueError:", e)


main()
```

```output
ValueError: invalid literal for int() with base 10: 'x'
```

A missing dictionary key raises `KeyError`:

<!-- sample: c3_keyerror -->
```python
def main() -> None:
    ages: dict[str, int] = {"ann": 30}
    try:
        print(ages["bob"])
    except KeyError as e:
        print("missing", e)


main()
```

```output
missing 'bob'
```

Division by zero raises `ZeroDivisionError`:

<!-- sample: c3_divzero -->
```python
def main() -> None:
    try:
        print(10 // 0)
    except ZeroDivisionError as e:
        print("ZeroDivisionError:", e)


main()
```

```output
ZeroDivisionError: integer division or modulo by zero
```

`except Exception` catches every kind. `type(e).__name__` and `str(e)` read like CPython's:

<!-- sample: c3_exception -->
```python
def main() -> None:
    try:
        raise RuntimeError("boom")
    except Exception as e:
        print(type(e).__name__, str(e))


main()
```

```output
RuntimeError boom
```

## A user exception class

A class that derives from `ValueError` can add a field and a `__str__`:

<!-- sample: c3_custom -->
```python
class BadRecord(ValueError):

    def __init__(self, line: str):
        super().__init__(line)
        self.line = line

    def __str__(self) -> str:
        return "bad record: " + self.line


def main() -> None:
    try:
        raise BadRecord("x|y")
    except BadRecord as e:
        print(e.line)
        print(e)


main()
```

```output
x|y
bad record: x|y
```

## Exit status

`sys.exit(n)` stops the program with status `n`. The test compares this status with CPython's:

<!-- sample: c3_exit -->
```python
import sys


def main() -> int:
    print("before")
    return 3


sys.exit(main())
```

```output
before
```

## An uncaught error

An uncaught error prints the exception and the source line, then exits with status 1. Output
written before the error is kept:

<!-- sample: c3_uncaught stop -->
```python
def f(n: int) -> int:
    return 10 // n


print("before")
print(f(0))
```

```stdout
before
```

```stderr
ZeroDivisionError: integer division or modulo by zero
  raised near c3_uncaught.py:2
```

The second line names the source file and line. This is the text the default build prints today;
the test removes its temporary directory prefix before it checks the line.
