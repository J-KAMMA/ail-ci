# Porting a Python program to AIL

AIL's rule is simple: a program either prints exactly what CPython 3.12 prints, or it is refused at
compile time with a message that names the construct and, usually, the supported rewrite. A refusal
is never a wrong answer at run time. This page collects the refusals an ordinary Python program
hits most often, each with the program that triggers it and the program to write instead.

A refusal exits non-zero (2 for a syntax or size limit, 3 for a construct outside the subset) and
prints its message on stderr. The location comes first when the compiler knows it:

```text
prog.py:2:5: not in the subset: a caught exception type int (only builtin or user Exception subclasses are supported)
```

Some messages end with a `write instead:` line. `--strict` asks for the typed path or a refusal and
lists every blocker with its rewrite; without it the default build may fall back to the general
path and prints `note: ... built on the general path ...` on stderr (about 20x slower, same
output). Every `after` program below builds in the default mode and prints what CPython prints for
its `before` program.

For each entry, the first block is the refusal message (the path part is shown as `prog.py`), the
second is the program that is refused, and the third is the rewrite.

## 1. A dictionary view kept in a name

```text
not in the subset: a dict view kept in a name, field, item or container (`x = d.items()`, line 3): a view follows its dict in CPython, but here it is a snapshot, so it would show old contents and a loop over it would not raise "dictionary changed size during iteration"; call `d.items()` where it is used, or keep `list(d.items())` for a snapshot
```

Refused:

<!-- example: dict_view_before.py -->
```python
def main() -> None:
    counts = {"a": 1}
    view = counts.items()
    counts["b"] = 2
    print(list(view))


main()
```

Write this instead:

<!-- example: dict_view_after.py -->
```python
def main() -> None:
    counts = {"a": 1}
    counts["b"] = 2
    print(list(counts.items()))


main()
```

A dict view is live in CPython: it shows a later store, and a loop over it raises when the dict changes size. AIL has no view object, so a view kept in a name would be a snapshot; the message names both rewrites (call `d.items()` where it is used, or take `list(d.items())`).

## 2. One `import` line mixing a local module and another module

```text
prog.py:1:1: one `import` statement mixes local modules and others; the compiler needs them apart.
```

Refused:

<!-- example: mixed_import_before.py -->
```python
import shlex, math

print(shlex.split("a b"), math.floor(2.5))
```

Write this instead:

<!-- example: mixed_import_after.py -->
```python
import shlex
import math

print(shlex.split("a b"), math.floor(2.5))
```

A local module is compiled from its source while the program is built, while a standard module is built in; one `import` line cannot take both routes. Split it into one line per module, as the message's `write instead:` line says.

## 3. A name that is imported and then assigned again

```text
prog.py:1:1: 'shlex' is imported and also assigned or defined again in prog.py; this compiler does not guess which binding a reader meant.
```

Refused:

<!-- example: import_assigned_before.py -->
```python
import shlex

shlex = shlex.split("a b")
print(shlex)
```

Write this instead:

<!-- example: import_assigned_after.py -->
```python
import shlex

words = shlex.split("a b")
print(words)
```

The name `shlex` is bound twice, once by the import and once by the assignment, and later code that reads it is ambiguous. AIL refuses rather than guess; give the value its own name (or import the module under another name, as the message suggests).

## 4. A decorator other than the supported ones

```text
not in the subset: the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are supported)
```

Refused:

<!-- example: unsupported_decorator_before.py -->
```python
def twice(function):
    def inner(value: int) -> int:
        return function(function(value))

    return inner


@twice
def bump(value: int) -> int:
    return value + 1


print(bump(3))
```

Write this instead:

<!-- example: unsupported_decorator_after.py -->
```python
def bump(value: int) -> int:
    return value + 1


def bump_twice(value: int) -> int:
    return bump(bump(value))


print(bump_twice(3))
```

A decorator runs arbitrary code when the function is defined, so only the ones named in the message are modelled. Write the wrapping as an ordinary function call instead of decorating.

## 5. A caught type that is not an Exception subclass

```text
prog.py:2:5: not in the subset: a caught exception type int (only builtin or user Exception subclasses are supported)
```

Refused:

<!-- example: caught_non_exception_before.py -->
```python
def parse(text: str) -> int:
    try:
        return int(text)
    except int:
        return 0


print(parse("12"))
```

Write this instead:

<!-- example: caught_non_exception_after.py -->
```python
def parse(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return 0


print(parse("12"))
```

AIL matches an `except` clause by the exception class, so the type there must be a builtin or user Exception subclass. `int` is not one, and CPython would never let it catch anything either; name the exception the code can actually raise.

## 6. A required keyword-only parameter

```text
not in the subset: a required keyword-only parameter name in def greet (this cut requires every keyword-only parameter to have a default)
```

Refused:

<!-- example: keyword_only_before.py -->
```python
def greet(*, name: str) -> None:
    print("hi", name)


greet(name="ada")
```

Write this instead:

<!-- example: keyword_only_after.py -->
```python
def greet(name: str) -> None:
    print("hi", name)


greet(name="ada")
```

The typed cut resolves a call to a fixed argument list, so a keyword-only parameter must have a default there. Pass the value as an ordinary positional parameter (or give the keyword-only one a default, which the default build accepts on the general path).

## 7. A class defined inside a function

```text
prog.py:2:5: not in the subset: a nested class definition (Point)
```

Refused:

<!-- example: nested_class_before.py -->
```python
def make() -> None:
    class Point:
        def __init__(self) -> None:
            self.x = 1

    print("made")


make()
```

Write this instead:

<!-- example: nested_class_after.py -->
```python
class Point:
    def __init__(self) -> None:
        self.x = 1


def make() -> None:
    print("made")


make()
```

A class object is created when the program starts, so a class body inside a function has no place to live; DIFFERENCES `C?-job-pre326-10271918-1` records this refusal. Move the class to module level.

## 8. `open()` with a mode that is not a string literal

```text
prog.py:3:5: not in the subset: open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the program is built (the general path could not build this program either); general path: open() with a mode that is not a string literal: the file kind (text or binary) has to be known when the program is built.
```

Refused:

<!-- example: open_mode_before.py -->
```python
def main() -> None:
    mode = "w"
    with open("out.txt", mode) as handle:
        handle.write("hi")
    print("written")


main()
```

Write this instead:

<!-- example: open_mode_after.py -->
```python
def main() -> None:
    with open("out.txt", "w") as handle:
        handle.write("hi")
    print("written")


main()
```

A text file and a binary file have different types in the generated C, so the mode has to be known at build time. Write the mode out at the `open()` call, as the `write instead:` line says.

## 9. `sys.stdin` kept in a name

```text
prog.py:5:5: not in the subset: sys.stdin: only sys.stdin.read(), sys.stdin.readline() and sys.exit(<int>) are supported, and only as calls; sys.stdin used as a value is not (the general path could not build this program either); general path: sys.stdin used as a plain value
```

Refused:

<!-- example: sys_stdin_before.py -->
```python
import sys


def main() -> None:
    stream = sys.stdin
    line = stream.readline()
    print("got", line.strip())


main()
```

Write this instead:

<!-- example: sys_stdin_after.py -->
```python
import sys


def main() -> None:
    line = sys.stdin.readline()
    print("got", line.strip())


main()
```

`sys.stdin` has no first-class stream value here; the two reading calls are built directly. Name `sys.stdin` at each call instead of storing it in a variable.

## 10. A module used as a plain value

```text
prog.py:3:1: not in the subset: the module math used as a plain value
```

Refused:

<!-- example: module_value_before.py -->
```python
import math

helper = math
print(helper.floor(2.5))
```

Write this instead:

<!-- example: module_value_after.py -->
```python
import math

print(math.floor(2.5))
```

A module is resolved at each use, so it cannot be passed, stored or compared as a value. Use the module name at the call site.

## 11. A builtin kept in a name

```text
prog.py:2:5: not in the subset: 'print' is read before it is assigned (the general path could not build this program either); general path: name 'print' is not defined
```

Refused:

<!-- example: print_value_before.py -->
```python
def main() -> None:
    show = print
    show("hello")


main()
```

Write this instead:

<!-- example: print_value_after.py -->
```python
def main() -> None:
    print("hello")


main()
```

A builtin is not a first-class value here; it is built when it is called by name. Call `print(...)` directly instead of storing it in a variable. The message wording is unclear (see the PR notes).

## 12. `type(x)` used in a test

```text
prog.py:3:5: not in the subset: call to type(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one (the general path could not build this program either); general path: the name 'type' is not a known function/class/builtin; did you mean 'type'?
```

Refused:

<!-- example: type_as_value_before.py -->
```python
def main() -> None:
    value = 1
    kind = type(value)
    print(kind is int)


main()
```

Write this instead:

<!-- example: type_as_value_after.py -->
```python
def main() -> None:
    value = 1
    print(isinstance(value, int))


main()
```

`type` is not in the builtin set that AIL builds (and the hint repeats the name). For the common use, a type test, `isinstance(value, int)` says the same thing and is built.

## 13. `os.stat()` where only the size is needed

```text
prog.py:7:5: not in the subset: os.stat is not built. Built: os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep name curdir, and os.path join exists isfile isdir islink getsize basename dirname split splitext abspath normpath isabs relpath (the general path could not build this program either)
```

Refused:

<!-- example: os_stat_before.py -->
```python
import os


def main() -> None:
    with open("data.txt", "w") as handle:
        handle.write("hello")
    info = os.stat("data.txt")
    print(info.st_size)


main()
```

Write this instead:

<!-- example: os_stat_after.py -->
```python
import os


def main() -> None:
    with open("data.txt", "w") as handle:
        handle.write("hello")
    print(os.path.getsize("data.txt"))


main()
```

AIL builds the `os` functions listed in the message, and `os.stat` is not one of them. When only the size is needed, `os.path.getsize` is built and returns the same number.

## 14. An integer literal beyond int64

```text
prog.py:2:13: int64 literal out of range: 99999999999999999999
```

Refused:

<!-- example: int_beyond_int64_before.py -->
```python
def main() -> None:
    limit = 99999999999999999999
    if limit > 1000000:
        print("limit is large")


main()
```

Write this instead:

<!-- example: int_beyond_int64_after.py -->
```python
def main() -> None:
    limit = 1000001
    if limit > 1000000:
        print("limit is large")


main()
```

AIL's `int` is a signed 64-bit integer, while CPython's is unbounded; DIFFERENCES `C?-job-pre335-10272125-1` records the same refusal for a huge literal base. Keep the value inside int64, or compile with `--exact-int` (about 20x slower).
