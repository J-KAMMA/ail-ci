# AIL strict-path brief

AIL reads Python 3.12 and compiles one file to a native binary. The default build works without
these rules, but it then falls back to a slow general path or refuses. Follow every rule here so
the same program builds on the typed path. The syntax is unchanged Python.

## Annotate everything

- Annotate every `def` parameter and the return: `def f(a: int, rows: list[tuple[int, int]]) -> int:`
- Annotate every binding whose type is not obvious from a literal:
  `total: int = 0`, `best: list[int] = []`, `by_id: dict[int, str] = {}`,
  `rows: list[tuple[int, int, str]] = []`.
- A container literal needs enough annotation to know its element type; `xs = []` alone does not.
- Use `list[T]`, `dict[K, V]`, `set[T]`, `tuple[A, B]`, `str`, `bytes`, `int`, `float`, `bool`.
- Do not use `Optional`/`None` in a container: use a sentinel (`-1`, `""`) or a second argument.
- Prefer `d[k]` after proving `k in d` to `d.get(k)`: `get` with one argument needs Optional.

## Keep the typed path

- One consistent type per name and container: do not bind a list of 2-tuples and later a list of
  6-tuples to the same variable; a captured row has one arity everywhere.
- A dict whose values are lists, sets or dicts is a "dict of containers" and falls back: use a
  list of records, or a list of `(key, value)` pairs, instead.
- Do not mix bools and numbers in one value (a dict value, a return that is `bytes` on one path and
  an `int` on another, ...): pick one type for every path.
- `d.items()`, `d.keys()`, `d.values()` only at the use site; never bind a view to a name.
- No class-level comprehensions; build the list in `__init__` or in a helper.

## int64

- `int` is a signed 64-bit integer. `+ - * // % ** abs round int()` overflow stops the program
  loudly with `OverflowError` and exit 1; it never wraps. Keep values in range or use `--exact-int`.
- An integer literal or constant expression outside int64 is refused at build time.
- Do not rely on CPython's arbitrary-precision integers: `1 << 200` is a build error.

## Refused constructs and the rewrite

| refused | write instead |
|---|---|
| a dict view kept in a name/field/item (`x = d.items()`) | call `d.items()` where used, or `list(d.items())` |
| a decorator other than `@staticmethod`, `@classmethod`, `@property`, `@lru_cache`, `@cache` | call the helper explicitly |
| a decorator on a class (it is dropped, not applied) | no class decorator |
| multiple inheritance | one base class, or composition |
| `with` around a `yield` in a generator (builtin `open` is fine) | open the resource outside the loop |
| `open()` with a non-literal mode | write out `"r"` / `"rb"` in each branch |
| a module used as a plain value (`x = sys`, `f(os)`) | use `sys.maxsize`, `os.sep` at the use site |
| `eval`, `exec` | `int()`, `float()`, `json.loads`, or explicit branches |
| `argparse` | read `sys.argv`, `len(sys.argv)`, `int()` directly |
| `tempfile` and most stdlib modules | `os.getenv("TMPDIR")` or `/tmp` plus a counter |
| `os.system`, `os.fork` | `subprocess.run([...])` |

## Stdlib available

`sys`, `math`, `collections`, `heapq`, `functools`, `bisect`, `itertools`, `re`, `io`, `struct`,
`json`, `csv`, `subprocess.run`/`check_output`. Other modules are refused by name at first use.

## Run time

- A build that is refused prints a named message with file, line and usually the rewrite; fix that
  construct and reply with the whole file.
- `note: ... built on the general path` is not an error (about 20x slower, same output). Remove it
  where the message names the cause.
