# AIL-N: an AI-oriented surface

AIL-N is a small typed language; it translates mechanically to AIL (Python syntax) and then to a
native binary. One statement per line, two spaces per indent, no tabs. Expressions are Python
expressions (`+ - * // % **`, comparisons, `and or not`, indexing, slicing, `len`, `min`, `max`,
`sum`, `abs`, `sorted`, `range`, `enumerate`, `zip`, list/dict/set literals). No f-strings.
`int` is signed 64-bit and stops loudly on overflow.

## Bindings (a type is required)

    let name: Type = expr      # immutable: assigning to it again is an error
    var name: Type = expr      # mutable: `name = expr` keeps the declared Type
    let xs: list[int] = []     # a container literal needs its type in the binding

Every binding, parameter and return has a type. No implicit conversion: use `int(s)`, `float(x)`,
`str(n)`.
## Types

    int  bool  float  str  bytes
    list[T]  dict[K, V]  set[T]  tuple[A, B]      (fixed arity, no "...")
    Result[T]                                      (present value or error)

No `None`, `Optional`, `Any` or unions. An absent value is a sentinel (`-1`, `""`) or a `Result[T]`.
## Functions

    fn name(a: int, b: list[int]) -> int:
      let total: int = 0
      return total

No `class`, `lambda`, decorator, `import`, `global`/`nonlocal`, nested function, `*args`/`**kwargs`,
generator or `yield`.
## Control flow (one form per construct)

    if cond: / elif cond: / else:
    while cond:                (with `break` and `continue`)
    for x: T in iterable:
    return expr

    match subject:
      case 0: ...             case "add": ...
      case Ok(v): ...         case Err(e): ...
      case _:                 # last arm only

An arm is a literal (`0`, `-1`, `"text"`, `True`, `False`, `1.5`), `Ok(v)`, `Err(e)`, or the final
`_`. A `Result` match has one `Ok` and one `Err` arm. Nothing falls through; there is no `switch`.
## Errors

A function that can fail returns `Result[T]` and returns `Ok(value)` or `Err("message")`. A caller
must `match` the result and handle both arms. There is no `try`, `except`, `raise` or `assert`.
Errors are values; the program chooses the exit status with `exit(code)`.
## Input, output, files, math

    read_stdin() -> str          read_stdin_bytes() -> bytes     read_line() -> str
    read_file_bytes(path: str) -> bytes                          read_file_text(path: str) -> str
    arg_count() -> int           arg(i: int) -> str              (0-based)
    write(s: str)                write_bytes(b: bytes)           exit(code: int)
    div_ceil(a: int, b: int) -> int     sqrt(x: float) -> float
    floor(x: float) -> int              ceil(x: float) -> int

No other builtin exists: `print`, `open`, `input`, `eval`, `exec`, `type`, `getattr` are not in the
surface. Top-level statements run in order; there is no `main` entry point and no automatic call.

## Complete example

    fn parse(text: str) -> Result[list[int]]:
      let out: list[int] = []
      for part: str in text.split():
        let n: int = int(part)
        if n > 0:
          out.append(n)
      if len(out) == 0:
        return Err("empty")
      return Ok(out)

    match parse(read_stdin()):
      case Ok(xs):
        write(str(len(xs)) + "\n")
      case Err(e):
        write(e + "\n")
        exit(1)
