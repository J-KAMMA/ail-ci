SYNTAX NOTES (AIL, brace style):
- Blocks use braces. Every statement ends with `;` but never after a closing `}`. Comments start with `#`. Use `and`, `or`, `not`, `elif` (not `else if`).
- Top level holds only `const`, `struct`, `impl`, `fn`. No global variables, no nested functions, no classes, no tuples.
- Declare functions as `fn name(a: int, b: str) -> int { ... }`; use `-> void` for no result. Annotate all parameters and results.
- Declare variables with `let`: `let n = 0;` or `let xs: list[int] = [];`. A name keeps one type for the whole function.
- Types: `int` (64-bit), `float`, `str`, `bool`, `list[T]`, `dict[str, T]` / `dict[int, T]`, `set[int]`. T is int, float, str or bool for containers.
- Entry point: `fn main() -> int { ...; return 0; }`.
- Records: `struct P { x: int; name: str; }`, build with `P(1, "a")`, read `p.x`. Methods: `impl P { fn m(self, d: int) -> int { return self.x + d; } }`. Structs are shared references and may be changed through a function parameter. Flat lists, dicts and sets passed as parameters are read-only: return a new one or keep it in a struct field.
- Input: `for line in sys.stdin { ... }` yields lines with the trailing newline kept; use `line.strip()`, `line.split()`, `int(s)`. `print(a, b)` joins with spaces; `print(xs)` of a list is not allowed, use `" ".join(list_of_str)`. f-strings work: `f"{n} {s}"`.
- Strings: `len`, indexing `s[i]` gives a str, slices, `lower`, `upper`, `isalpha`, `isdigit`, `isalnum`, `join`, `split`, `strip`, `replace`. `+` never mixes str and numbers: use `str(n)`. There is no `ord`/`chr` conversion between a str and a number: to shift letters, look a letter up with `ABC.find(ch)` in a str constant and index it again with `ABC[i]`.
- Lists: `append`, `pop`, `sort()`, `sorted(xs)`, `sort(key=lambda i: (-w[i], i))` (a lambda is only allowed as a sort key). Dicts: `d[k]`, `k in d`, `d.get(k, default)`, `for k in d`, `for k, v in d.items()`, `sorted(d)`. No `math`, `re`, `collections`, `zip`.
- Errors: `try { ... } except ValueError as e { ... }`; name the exception kinds (ValueError, KeyError, IndexError, ZeroDivisionError); no bare `except`. `raise ValueError("message");`. `int("abc")` raises ValueError.
- Example:
```
struct Acc { total: int; names: list[str]; }
fn add(acc: Acc, name: str, v: int) -> void {
    acc.names.append(name);
    acc.total += v;
}
fn main() -> int {
    let acc = Acc(0, []);
    for line in sys.stdin {
        let f = line.split();
        try { add(acc, f[0], int(f[1])); }
        except ValueError as err { print("bad", err.message); }
    }
    print(acc.total, len(acc.names));
    return 0;
}
```
