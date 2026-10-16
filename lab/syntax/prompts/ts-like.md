SYNTAX NOTES (AIL, brace style with TypeScript-like annotations) -- MOCK-UP, NOT ACCEPTED BY THE COMPILER TODAY:
- Same as the brace style (`fn`, `let`, `struct`, `impl`, `;` after statements, braces for blocks), except that result types follow the parameter list after a colon and `void` is written the same way: `fn name(a: int, b: str): int { ... }`, `fn main(): int { ...; return 0; }`.
- Variables: `let n: int = 0;` and `let xs: list[int] = [];`.
- Everything else (types, `struct` / `impl`, `for line in sys.stdin`, `try { } except ValueError as e { }`, no tuples, no classes, no globals) is as in the brace style.
- Input: `for line in sys.stdin { ... }` with `line.strip()`, `line.split()`, `int(s)`; output with `print(...)` and f-strings; `" ".join(list_of_str)` to print a list.
- Example:
```
struct Acc { total: int; names: list[str]; }
fn add(acc: Acc, name: str, v: int): void {
    acc.names.append(name);
    acc.total += v;
}
fn main(): int {
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
