# AIL reference (core)

AIL is statically typed Python with braces, compiled via C. Write Python, with these rules.
Build in AIL_CURRENT/: `python3 ail_chatgpt.py compile p.ail -o p`; fix its `slow:` (O(n²)) hints.

```ail
# args: 3
# exit: 1
struct Acc { total: int; keys: list[str]; }
impl Acc { fn add(self, k: str, v: int) -> void { self.keys.append(k); self.total += v; } }
fn parse(acc: Acc, line: str) -> void {
    let f = line.split("|");
    if len(f) != 2 or not f[0].isupper() { raise ValueError(f"bad: {line.strip()}"); }
    acc.add(f[0], int(f[1]));
}
fn main() {
    let acc = Acc(0, []);
    for line in sys.stdin { parse(acc, line); }
    parse(acc, "B|5"); parse(acc, "A| 7");
    let w = [3, 9, 3];
    let idx = [i for i in range(3)];
    idx.sort(key=lambda i: (-w[i], i));
    for i in idx { print(f"{i:<2}{w[i]:>3}"); }
    acc.keys.sort();
    print(",".join(acc.keys), acc.total, int(sys.argv[1]), 3 > 2, b"xy"[1:].decode());
    try { parse(acc, "b|1"); }
    except ValueError as err { print(err.message, file=sys.stderr); return 1; }
    return 0;
}
```

- `;` ends every statement, never a `}`; `elif`; `#` comments; `and or not`. `except` names the
  kinds (no bare `except`); an uncaught error exits 1.
- Top level: only `use`, `const`, `struct`, `impl`, `fn`; no globals (pass a struct), nested
  `fn`, `class`. A lambda is only a sort key and may read other lists (`idx.sort`): never
  hand-write a sort.
- `let x = 1;`, `let xs: list[str] = [];` fix the type. A name keeps one type in the whole
  function, also across blocks: give another type a new name. Loop variables are per loop; name
  `except` bindings freshly (`as err`). Annotate parameters and results (`-> void`).
- `int` is 64-bit (overflow raises `OverflowError`). `bool` prints `True`/`False`, adds as 1/0; a
  bool slot takes only bools (`n != 0`). `None`
  only for structs typed `Node | None`.
- `list[T]`, `dict[int|str, T]`, `set[int|str]`, T int, float, str, bytes; lists also bool,
  structs, rows (`[[0] * w for _ in range(h)]`). Structs and rows are shared references; `let ys =
  xs;` copies a flat list. Flat list/dict/set parameters are read-only: change a struct field
  `s.xs` or return a new list.
- `print` takes int, float, str, bool; `+` never mixes str and number (`str(n)`). f-strings, `%`,
  `.format`: `d f s`, width, precision, `<>^`.
- Text: `for line in sys.stdin` (keeps `\n`), `input()`, `split()`, `int(s)`, a print per line.
  Bytes for binary, non-UTF-8 (str input exits 1) or one huge line: `read_stdin_bytes(1 << 40)`;
  `data[i]` is an int (`ord("a")`, not 97); `data[a:b]` an O(1) view, `int(data[a:b])`; to str
  only by `.decode()`; `write_stdout_bytes(bytearray)`. To print nothing on error, collect output.
- No big ints: `x ** 0.5`, loops. Libs: `re`, `collections`, `random`,
  `itertools`, `functools`, `json`; tuples/lambda: MORE. Built in: `heappush`, `heappop(h)` (`key=`), `bisect_left`, `insort`.

MORE (`sed -n A,Bp AIL_REFERENCE_MORE.md`): Commands 7-19, Text I/O 21-55, Bytes 57-89, Syntax 91-102, Local names 104-129, Numbers 131-145, Structs 147-180, Trees 182-224, Lists 226-238, Sort keys 240-247, Nested lists 249-266, Dicts 268-277, Sets 279-285, Strings 287-312, Regular expressions 314-370, Collections 372-444, Tuples, lambdas (Python syntax) 446-505, Libraries 507-560, Heaps 562-577, Loops 579-586, Exceptions 588-595, Refused 597-638, Word count 640-672, Dijkstra 674-716, BFS 718-762, Modules 764-792, Speed 794-813, Parallel 815-850.
