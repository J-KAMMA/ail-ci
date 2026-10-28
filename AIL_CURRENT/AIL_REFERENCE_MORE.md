# AIL reference: the rest

Look-up sections behind AIL_REFERENCE.md, whose last line gives each section's line range here:
read only the slice you need (`sed -n A,Bp AIL_REFERENCE_MORE.md`). A refusal names the construct,
the rewrite and `file:line:col`. Most examples use the brace surface (`fn`, `let`, `;`, braces);
write them in Python as usual (`struct` is a `@dataclass`, `impl` its methods; brace `let ys = xs;` copies).

## Commands

```text
python3 ail_chatgpt.py compile prog.ail -o prog    # from AIL_CURRENT/; fails if prog already exists
python3 ail_chatgpt.py check prog.ail              # type check only, JSON diagnostics
python3 ail_chatgpt.py api csv_stream              # signatures of a bundled module
```

Both `compile` (stderr) and `check` (`slow_patterns` in the JSON) name at most 3 commonly O(n²)
loops as `file:line: slow: ...; fix`: `x in xs` / `.index` / `.count` / `.remove` on a list, `.pop(0)`
/ `.insert(0, x)`, `min`/`max`/`sort` of a list the loop keeps changing, a scan of all rows for the
current key, nested loops over one list, a struct heap keyed by a computed value. They never
fail the build; fix them when n can be large. `s += t` on a str is linear (no hint).
Projects (`ail new`, `ail.toml`), `ail lsp` and `ail build --debug`: see Tooling at the end.

### Strict mode: the typed path or a refusal

A program the typed path cannot take is built on the general path, about 20x slower, and `compile`
prints one `note: ... built on the general path (about 20x slower) because ...; run with --strict to see
why` line (`AIL_QUIET_FALLBACK=1` silences it). Strict mode never falls back:

```text
python3 ail_chatgpt.py compile prog.py --strict -o prog          # also AIL_STRICT=1, ail build --strict, ail run --strict
python3 ail_chatgpt.py compile prog.py --strict --json -o prog   # blockers as ail.strict/1 JSON on stdout
```

A typed program builds exactly as without the flag (same C, same executable). Otherwise exit status 3 and
every blocker the compiler can find in one pass, not only the first: `file:line:col`, the code, the
construct, why it is not typed and a `write instead:` rewrite, the one that keeps the most code off the
typed path first (`blocks N lines (f, main)`: the function and every caller). Fix them all, run again.
The JSON has `schema`, `status`, `blocker_count`, `incomplete` (null, or why the list may be short) and
`blockers[]` with `rank path line column function statement construct why write_instead blocks_lines
blocks_functions message`. `AIL_NO_GENERAL=1` alone still stops at the first refusal.

### The general path's unboxing: `AIL_UNIFIED` (default on since 2026-10-21)

On the general path the compiler infers int / float / bool locals, parameters and results and keeps them as C
values (about 1.7x faster on general-only programs; same output, stderr and exit status, same RSS within 0.5%).
It is on by default. `AIL_UNIFIED=0` (also `off`, `no`, `false`) builds the general path with every value boxed, as
before; `AIL_UNIFIED=1` is still accepted. The size-class free list under the collector is a separate switch and
stays off unless `AIL_UNIFIED_POOL=1` (it costs RSS). Typed-path programs are not affected.

## Text I/O: main, arguments, stdin lines, print, files

```ail
# args: 2
fn main() {
    if len(sys.argv) != 2 { print("usage: prog N", file=sys.stderr); return 2; }
    let n = int(sys.argv[1]);
    let total = 0;
    let rows = 0;
    for line in sys.stdin {                 # one str per line, "\n" kept
        let f = line.split();
        if len(f) == 0 { continue; }
        total += int(f[0]);
        rows += 1;
    }
    for i in range(n) { print(f"row {i}: {rows} {total}"); }
}
```

```text
row 0: 0 0
row 1: 0 0
```

- `fn main()` takes no parameters and returns the exit code (falling off the end is 0); `sys.argv`
  is a `list[str]` with the program name first; `sys.exit(n)` works anywhere.
- Input: `for line in sys.stdin` (keeps `\n`; input that is not UTF-8 exits 1: read bytes instead),
  `input()` (`EOFError` at the end), `open(path).read()` and `for line in open(path)`.
- Files: `with open(p, "w") as f: f.write(text)` and the same for read; modes `r w a x` with `b` / `+`,
  `encoding=`, `errors=`, `newline=`, `read/readline/readlines/write/seek/tell/close` (typed path too).
- Output: `print(*values, sep=, end=, file=sys.stderr)` (ints, floats, strs, bools; a list or
  tuple prints as its repr, `print(*xs)` walks a list / tuple / generator, and `Cls(*xs)` and `f(*xs)`
  are built, binding like a plain call). stdout is buffered and still flushed by
  `sys.exit` or an uncaught exception: when a program must print nothing on error, collect the lines
  and print them at the end.
- Files: `read_bytes(path)`, `file_chunks(path, 65536)` (bytes chunks, constant memory),
  `write_text(path, s)`, `write_bytes`, `append_bytes`, `path_exists`, `file_size`, `list_dir`.
- `for line in sys.stdin` with `split`/`int`/`isdigit` and one `print(f"...")` per output line is
  as fast as hand-written byte scanning and keeps memory flat (Speed).

## Bytes: binary input, views, decode, bytearray

```ail
fn main() {
    let data = b"7 42\n";                   # all of stdin: read_stdin_bytes(1 << 40)
    let lines = 0;
    for b in data { if b == b"\n"[0] { lines += 1; } }   # items are ints 0..255
    let out = bytearray();
    out.extend(data[0:1]);
    out.append(ord(" "));
    write_stdout_bytes(out);
    print(lines, int(data[2:4]) + 1, data[2:4].decode() + "!");
}
```

```text
7 1 43 42!
```

- `read_stdin_bytes(max)` reads until `max` bytes or EOF (like `sys.stdin.buffer.read(max)`);
  `read_bytes(path)`; `file_chunks(path, 65536)`.
- `b[i]` is an int; `for b in data` (also `data[i:j]`, `b"acgt"`, `s.encode()`) walks ints;
  `b[a:b]` is an O(1) view; `int(b[a:b])` parses it without copying (`ValueError` on bad text).
  Compare with `ord("a")` or `b"a"[0]`, not 97.
- Methods: `len`, slices, `find/rfind/count/startswith/endswith/split/join/replace`, `hex()`,
  `bytes.fromhex(s)`, `bytes(list[int])`, `bytes(bytearray)`.
- bytes to str: `b.decode()` (strict UTF-8, `UnicodeDecodeError`, also caught by
  `except ValueError`); `str(b)` is refused. str to bytes: `s.encode()`.
- `bytearray()`, `bytearray(n)` (zeros): `append(int)`, `extend(bytes)`, `ba[i] = v`, `ba[i] += v`
  (0..255 or `ValueError`), `pop`, `clear`. A bytearray parameter is writable.
  `write_stdout_bytes(bytes|bytearray)` and `print` mix in order.
- Use bytes for binary formats, non-UTF-8 input and one huge line of tokens. `bytes.split()`
  builds a list of every token: avoid it on large input.
- Python syntax: a bytes-keyed dict or set (`ids: dict[bytes, int] = {}`, `stop = {b"an"}`) and a list
  of bytes are locals, not parameters or fields; a bytes sort key is `terms[i].hex()`;
  `ba[a:b].decode()` works on a bytearray; a tuple cannot hold a bytearray (pass it in, return the
  number). A module-level set or dict literal is a read-only table (next section).

```python
import sys

def main() -> int:
    ids: dict[bytes, int] = {}
    stop = {b"an", b"the"}
    terms = []
    for w in b"the cat an ox cat".split():
        t = bytes(w)
        if t in stop:
            continue
        if t not in ids:
            ids[t] = len(terms)
            terms.append(t)
    order = list(range(len(terms)))
    order.sort(key=lambda i: terms[i].hex())
    ba = bytearray(b"xyz")
    print(len(terms), order[0], ids[b"ox"], ba[1:3].decode())
    return 0

sys.exit(main())
```

```text
2 0 1 yz
```

## Syntax: top level, functions, statements, let, const

- Top level holds only `use NAME;`, `const`, `struct`, `impl`, `fn`. No top-level `let` (pass
  state in a struct), no nested `fn`, no `class`, no `lambda` value (only as a sort key).
- `fn f(a: int, b: str = "x") -> int { ... }`: parameters and result annotated; `-> void` or no
  arrow returns nothing. Keyword arguments work. Recursion works. Pass a top-level `fn` by name as
  a `Callable[[int], int]` value (also a field type).
- Every statement ends with `;`, never after `}`. Blocks use braces: `if c { } elif d { } else { }`
  (no `else if`), `while c { }`, `for x in xs { }`, `try { } except E as e { } finally { }`.
  Comments start with `#`. Logic is `and or not`.
- `with expr as name:` / `with a as x, b as y:` is built: `with open(...)` on the typed path, and on
  the general path user `__enter__` / `__exit__` (a true result suppresses) and `contextlib.contextmanager`,
  `suppress`, `closing`, `nullcontext` (the default build falls back).
- `let x = 1;` or `let x: list[str] = [];`: an initializer is required and fixes the type.
  `const N = 3;` takes a number, str, bytes or numeric-list literal.

## Local names: one type per name, loop and except names

- `let` is function-scoped: a name has one type in the whole function, also across blocks. Give a
  value of another type a new name (`let x = 1;` then `let x = "a";` in another block is refused).
- A `for` variable belongs to its loop, and a lambda parameter to its lambda: two loops may reuse
  `t` with different types, and `idx.sort(key=lambda i: ...)` next to `for i in` is fine.
- `except E as e` binds `e` inside the handler only. If the function also has a local `e` that is
  read after the handler, the binding is refused: pick a fresh name (`as err`).
- A top-level `fn`, `struct` or `const` named like a built-in (`abs`, `min`, `sorted`, `print`,
  `heappush`, `read_bytes`, ...) wins everywhere, as in Python. Type names (`int`, `str`, `list`,
  ...), exception names, `math`, `sys`, `os` are refused when used: rename the definition.

```ail
fn main() {
    let e = 3;
    for t in ["a", "b"] { print(t); }
    for t in [1, 2] { e += t; }
    try { raise KeyError("k"); } except KeyError as err { print(err.kind, e); }
}
```

```text
a
b
KeyError 6
```

## Numbers: int, float, bool

- `int` is 64-bit; overflow in `+ - * // << -x` raises `OverflowError`. `wrapping_add/sub/mul(a, b)`
  wrap modulo 2**64 (hashes, PRNGs). `/` gives float; `//` and `%` floor like Python. `**`,
  `& | ^ ~ << >>`. No big ints: limbs in a `list[int]`.
- `int(str)`, `int(bytes)` (`ValueError` on bad text), `int(float)`, `float(str)`, `round(x)` (half
  to even, int), `round(x, n)`, `abs`, `max(a, b)`, `min(a, b)`, `sum/min/max/any/all(list)`.
  No `math` module: `x ** 0.5`. For text that may overflow: `parse_int64_decimal(s)` (Modules).
- `bool` is Python's: `True`/`False` (also `true/false`), comparisons, `not`, `and`/`or` of bools,
  `bool(x)`, `any/all`, the `is...()`/`startswith`/`issubset`... predicates, a `-> bool` result, a
  `bool` field or a local only ever given bools all print `True`/`False` (also `str(b)`, `f"{b}"`,
  `"%s" % b`); a spec'd field formats the number (`f"{b:>3}"` is `  1`, as CPython). In
  arithmetic a bool is 1/0 (`total += x > 0`). A declared bool slot (parameter, result, field,
  `let ok: bool`, `list[bool]`) takes only bools: write `n != 0`, not `n`. A function declared
  `-> int` returns an int (`print` shows `1`). `0 or 5` is `1` (an int `and`/`or` gives 1/0).

## Structs: fields, methods, aliasing, writable parameters

- `struct P { x: int; name: str; }` is built `P(1, "a")` or `P(name="a", x=1)`; every field needs
  a value (list/dict/set fields take `[]`/`{}`/`set()`). Methods: `impl P { fn m(self, d: int) ->
  int { ... } }`. A field may be any type, the struct's own type only as `P | None` or `list[P]`.
  A Python `@dataclass` class may derive from one `@dataclass` base on the general path (the default
  build falls back): inherited fields, `==` and printing work there.
- A struct is a shared reference (assignment, list elements and arguments alias it), as are nested
  lists and their rows; `let ys = xs;` copies a flat list. No tuples: return a struct.
- Flat `list`, `dict` and `set` parameters are read-only: to modify one in a helper, keep it in a
  struct field and pass the struct (or return a new list). Struct, `bytearray` and
  `list[list[T]]` parameters are writable. `print(p)` and `p1 == p2` on structs: use the fields.

```ail
struct Point { x: int; y: int; }
struct Bag { xs: list[int]; }
impl Point { fn shift(self, d: int) -> void { self.x += d; } }
fn bump(p: Point, b: Bag) -> void { p.y += 100; b.xs.append(p.y); }
fn main() {
    let p = Point(1, -2);
    let q = p;                       # the same object
    q.shift(3);
    let b = Bag([]);
    bump(p, b);
    let xs = [0] * 3;
    let ys = xs;                     # a copy
    ys.append(3);
    let a = 1; let c = 2;
    a, c = c, a;
    print(p.x, p.y, b.xs[0], len(xs), len(ys), a, c);
}
```

```text
4 98 98 3 4 2 1
```

## Trees: linked lists, `Node | None`

A struct field, parameter, result or `let` written `Node | None` (or `Optional[Node]`) may be `None`.
On the typed path `int | None`, `float | None` and `str | None` are built too; `bool`, `bytes` and
`list[T]` with `| None` need the general path (the default build falls back). Test with `is None`,
`is not None`, `if x`; `a is b` compares identity. Reading or writing a field (or calling a method)
through None raises `RuntimeError` (message `field access on None`), catchable. Structs are
reference counted: trees and lists are freed when unreferenced, a reference cycle (parent pointer,
doubly linked list) is never freed. `let x = None;` alone is not a struct: write
`let x: Node | None = None;`. `a if c else None` is refused: use if/else.

```ail
struct Node { val: int; next: Node | None; }
struct Tree { key: int; left: Tree | None; right: Tree | None; }
fn total(head: Node | None) -> int {
    let s = 0;
    let cur = head;
    while cur is not None { s += cur.val; cur = cur.next; }
    return s;
}
fn insert(t: Tree | None, k: int) -> Tree {
    if t is None { return Tree(k, None, None); }
    if k < t.key { t.left = insert(t.left, k); } else { t.right = insert(t.right, k); }
    return t;
}
fn depth(t: Tree | None) -> int {
    if t is None { return 0; }
    return 1 + max(depth(t.left), depth(t.right));
}
fn main() {
    let list: Node | None = None;
    for i in range(4) { list = Node(i, list); }
    let root: Tree | None = None;
    for k in [5, 2, 8, 1, 9, 7] { root = insert(root, k); }
    print(total(list), depth(root), root.left.key, root.left.right is None);
    try { print(root.left.right.key); }
    except RuntimeError as e { print(e.message); }
}
```

```text
6 3 2 True
field access on None
```

## Lists: methods, copying, list()

- `list[T]`, T: int, float, str, bytes, bytearray, bool, a struct, or a row (Nested lists).
  `[0] * n`, `[0.0] * n`, `[False] * n` allocate; `[f(i) for i in range(n) if c]` builds.
- `append extend insert pop([i]) remove index count clear copy reverse`, `sort(key=, reverse=)`,
  `del xs[i]`, slices with steps, `+`, `+=`, `in`, `len`, `reversed(xs)`, `enumerate(xs)`,
  `sorted(xs, key=, reverse=True)` (a float list: `xs.sort()`, not `sorted`). A bad index raises
  `IndexError`; `xs[-1]` works.
- `list(x)` copies any list, set, dict (its keys), `d.keys()`, `d.values()`, str (its characters)
  or range into a new list. On a list field, `x in st.xs` and `st.xs.count(x)` read it in place.
- A flat list parameter is read-only on the typed path (Structs). `print(xs)` is the list's repr;
  `print` of a dict needs the general path (the default build falls back).
- `x in xs`, `index`, `count`, `remove`, `pop(0)`, `insert(0, x)` are O(n), as in Python: in a
  loop use a set or `[False] * n`, a queue as list + head index (BFS), a heap (Heaps).

## Sort keys

A `lambda` (or a function name such as `len`) giving an int, float or str, or a tuple of 2 to 4
of them: `key=lambda g: (-g.total, g.key)` (negate the numeric part; a str cannot be negated).
The key may read other lists: sort indexes with `idx.sort(key=lambda i: (-w[i], names[i]))`
instead of writing a merge sort. `reverse=` is literally `True` or `False`.
`sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))` works only as the iterable of `for k, v in`
(Word count).

## Nested lists: `list[list[T]]`

Nested lists (T int, float, str or a struct) work as locals, struct fields, parameters and
results, with Python's meaning:
- Build rows with `[[] for _ in range(n)]`, `[[0] * w for _ in range(h)]`, `[[1, 2], [3]]`,
  `[[i * j for j in range(w)] for i in range(h)]` or `g.append(row)`; annotate an empty one
  (`let g: list[list[str]] = [];`). `[[0] * w] * h` is refused: every row would be one list.
- `g[i][j]` read, write and `+=` (O(1), nothing copied), `g[i].append(x)`, `len(g[i])`,
  `for row in g`, `for x in g[i]`, `x in g[i]`, `sum/min/max(g[i])`, `g[i][a:b]`,
  `g[i].sort()` / `.sort(reverse=True)`, `pop insert extend remove clear reverse index count`,
  `g.sort(key=lambda r: len(r))`, `[x for row in g for x in row]`. A bad index raises `IndexError`.
- Aliasing is Python's: `let r = g[i];`, `for r in g` and `g[j] = g[i]` share the row, so
  `r.append(x)` is seen in `g`; `let h = g;` and a `list[list[T]]` parameter share the whole list
  (a callee's `g[i].append(x)`, `g.append(row)` and `g[i] = row` are seen by the caller);
  `g.copy()` copies the outer list only. Storing a plain list (`g.append(xs)`, `g[i] = xs`), and
  reading a row into a `list[T]` (`let r: list[int] = g[i];`, an argument or result of type
  `list[T]`), copies it. `for x in g[i]` sees appends made in the loop, as Python does.
- Not built: deeper nesting, rows of bytes, `key=` on a row's `sort`, `print(g)`.

## Dicts: `dict[str, T]`, `dict[int, T]`

- T: int, float, str, bytes. Insertion ordered. Key an int id as an int (`d[r.id]`, never
  `d[str(r.id)]`). `dict[str, Struct]` and `dict[str, list[T]]` need the general path (the default
  build falls back); the typed path maps the key to an index into a `list[Struct]` or a `list[list[T]]`.
- `d[k]` (`KeyError`), `get(k, default)` (one-argument `get(k)` is refused: there is no None for a
  value; use `d.get(k, -1)` or `if k in d`), `setdefault`, `pop(k[, default])`, `del d[k]`, `in`,
  `len`, `keys()`, `values()`, `items()`, `update`, `copy`, `clear`; `for k in d`,
  `for k, v in d.items()`, `sorted(d)`, `list(d)` / `list(d.keys())` (keys in insertion order),
  `list(d.values())`, dict comprehensions. A dict parameter is read-only on the typed path.

## Sets: `set[int]`, `set[str]`

`let s: set[int] = set();` (or `{1, 2}`, `set(xs)`): `add discard remove clear update copy`,
`x in s`, `len`, `for`, `sorted`, `list(s)`, `sum/min/max` (int), `| & - ^` and `|= &= -= ^=`
(also `union intersection difference symmetric_difference`, `*_update`), `== != <= < >= >`
(`issubset`, `issuperset`), `isdisjoint`. Insertion ordered; `s.pop()` removes the first element in that order
(`KeyError` when empty). A set parameter is read-only.

Module-level tables (Python syntax): `STOP = {"a", "the"}`, `STOP: set[str] = {...}`, `TABLE = {"x": 1}`,
`NAMES = {1: "one"}`, `PAIRS = {(0, 1), (2, 3)}`, `STOP = {b"a"}`: a non-empty literal, every element of one
kind (int, str, bytes, or a tuple of ints / strs; a dict: one key kind, one value kind, int / float / str /
bytes / tuple), bound once and not changed. Any function reads it in place: `w in STOP`, `TABLE[k]`,
`TABLE.get(k, 0)`, `for k, v in TABLE.items()`, `len`, `sorted`, `min`, `max`, `sum`, `any`, `all`. It is built
once in the entry function and passed down (a bytes table is rebuilt by each function that reads it).
Refused by name: `STOP.add(x)`, `T[k] = v`, `global STOP`, `xs = STOP`, `return STOP`, `f(STOP)`, `[STOP]`
(CPython would share the one object; write `set(STOP)` for a copy), and a set of ints walked by `for` /
`list(...)` (CPython walks it in hash order, this compiler in insertion order; write `sorted(PRIMES)`). A
computed, empty, mixed-kind, bool or float table is refused too: build it in `main` and pass it in. A library
module (`compile-library`) takes no table.

## Strings: methods, formatting

- `str` is UTF-8; `len`, index, slice, `for c in s` count code points; `s[i]` is a str.
- `strip/lstrip/rstrip([chars])`, `split([sep[, maxsplit]])`, `rsplit`, `splitlines()`, `join`,
  `find/rfind/index/rindex/count(sub[, start[, end]])`, `startswith/endswith`, `replace`,
  `lower/upper`, `isdigit/isalpha/isalnum/isspace/isupper/islower/isdecimal/isnumeric/istitle`,
  `encode()`; `in`, `+`, `*`, `<`, slices with steps, `ord`, `chr`, `str(int|float|bool)`,
  `hex(int)`, `partition`, `rpartition`, `ljust`, `rjust`, `center`. Missing on the typed path:
  `title`, `capitalize`, `zfill`, `removeprefix`, `removesuffix` (the default build falls back and
  runs them); `translate` is refused on every path. `+` never mixes str and a number: `"n=" + str(n)`.
- f-strings `{expr}`, `{n:5d}`, `{n:05d}`, `{x:.2f}`, `{x:8.3f}`, `{s:>6}` (`<`, `^`);
  `"%d %5s %-5s %.9f" % (...)`; `"{} {:.2f}".format(...)`. Specs follow CPython: `[[fill]align][sign][#][0]
  [width][, or _][.precision][type]` with int types d x X o b (and e f g %), float types f F e E g G %
  or none (the repr), `!r`; refused by name: n, c, z, a nested `{w}`, grouping with zero padding.

```ail
fn main() {
    let n = 7; let x = 3.14159; let name = "ab";
    print(f"{n:03d}|{n:>4}|{x:.2f}|{name:<4}|{n + 1}", "%5d|%.1f" % (n, x), "{}!".format(n));
    print(3 > 2, 0 or 5, 7 / 2, 7 // 2, -7 % 3, 2 ** 10);
}
```

```text
007|   7|3.14|ab  |8     7|3.1 7!
True 1 3.5 3 2 1024
```

## Regex: re (Python syntax)

`import re` with the pattern spelled as a literal: a str or bytes literal, or a name bound once to one
(`WORD = r"[a-z]+"`), or `P = re.compile(literal[, flags])` bound once and used as `P.search(s)` and so
on. The pattern is parsed when the program is built and matched by a linear-time engine written in the
language itself (leftmost-first, CPython's priority), so groups and spans equal CPython's.

- Functions and methods: `match fullmatch search findall finditer split sub subn escape`; `flags=` or the
  last positional flags (`re.I re.M re.S re.X re.A`, joined with `|`), `count=`, `maxsplit=`.
  `finditer` returns a list of matches, not an iterator (use it in a `for` or with `len`).
- Pattern syntax: literals, `.`, classes (`[a-z]`, `[^...]`, ranges, `\d \w \s` and their
  negations; Unicode-aware for str as in CPython, ASCII for bytes and `re.A`), `^ $ \A \Z \b \B`,
  `* + ? {m} {m,} {,n} {m,n}` and the lazy forms, `|`, `(...)`, `(?:...)`, `(?P<name>...)`, `(?#...)`,
  a leading `(?imsxa)`, `\n \t \xhh \uhhhh` escapes, lookahead `(?=..) (?!..)` and fixed-width lookbehind
  `(?<=..) (?<!..)` (no groups inside).
- Match: `m.group(i)`, `m.group("name")`, `m.group()`, `m.start(i)`, `m.end(i)`, `a, b = m.span()`,
  `x, y = m.groups()`, `if m:`, `m is None`. A group that did not take part gives `start == -1`; reading it
  with `m.group(i)` raises `ValueError` (there is no None str), so test `m.start(i) >= 0` first.
  `findall` with one group returns that group ('' when it did not take part).
- `sub(pattern, repl, s[, count])`: a literal `repl` may use `\1`, `\g<1>`, `\g<name>`, `\n`;
  a non-literal `repl` must have no backslash. `subn` and a function `repl` run on the general path
  (the default build falls back; the typed path needs a literal repl). Empty matches follow CPython 3.7+.
- Cost: matching is O(len(pattern) x len(text)). On an ASCII str or a bytes subject (and a pattern without
  lookaround) a DFA built with the program finds the spans, so scans over megabytes (`findall`, `finditer`,
  `sub`, `split`, `search`) and short `fullmatch` calls run at or below CPython's time, with 2 to 5 times
  fewer CPU cycles; groups are then read by the Pike VM on the matched span only. A non-ASCII str, a
  lookaround, or a `$` before a final newline uses the slower Pike VM (a few times slower than CPython on
  megabytes). The result lists of `findall`/`split` cost about 650 instructions per element in the
  runtime's list-of-str return, whatever the engine.
- `for k, v in re.findall(P, s):` with several groups is a loop over the matches (the names may not be used
  outside the loop); `m.group(k) or d` and `m.group(k) is None` read the group as CPython's None would.
- Refused by name (the compiler prints a `note:` line): backreferences, groups inside lookaround,
  atomic groups, possessive quantifiers, conditionals, scoped flags `(?i:...)`, a repeated group that
  can match the empty string (`(a*)*`), `re.IGNORECASE` with a non-ASCII pattern character (a non-ASCII
  subject with `re.I` raises `ValueError`), `findall` with several groups and `split` with groups
  (tuples, None), `m.groups()` / `m.groupdict()` / `m.span()` as values, a pattern that is not a
  literal, `pos` / `endpos`.

```python
import re

DATE = re.compile(r"(?P<y>[0-9]{4})-(?P<m>[0-9]{2})")


def main() -> int:
    if re.fullmatch(r"[0-9]+", "123"):
        print("digits")
    m = DATE.search("on 2026-10 ok")
    if m:
        print(m.group("y"), m.group(2), m.start(0))
    print(re.sub(r"(\w+)@(\w+)", r"\2 at \1", "me@home"))
    for word in re.findall(r"[a-z]+", "ab, cd"):
        print(word)
    return 0


main()
```

## Collections: Counter, defaultdict, OrderedDict, deque (Python syntax)

`from collections import Counter, defaultdict, deque, OrderedDict` (or `import collections`). Each is built
into the ordinary dict / list / class the compiler already has, before the rest runs (collib.py), so a
program that does not import collections is unchanged. Keys are `str` or `int`; values `int`, `float` or
`str`; deque elements `int`, `float`, `str` or `bool`. The type comes from an annotation
(`c: Counter[str] = Counter()`, `d: DefaultDict[int, List[int]]`, a parameter `q: Deque[int]`) or from the
first uses (`Counter(words)`, `d[w].append(i)`, `q.append(x)`).

- `Counter`: `Counter()`, `Counter(list | str | set | range | comprehension | another Counter or dict)`;
  `c[k]` is 0 for a missing key and does not insert; `c[k] += n`, `c[k] = n`, `del c[k]` (silent when
  missing), `c.get(k, d)`, `pop`, `keys / values / items`, `len`, `in`, `sum(c.values())`, `total()`,
  `update(iterable | Counter)`, `elements()`, `+ - & |` (and `+=` ...) with CPython's rules (keep
  positive counts), `print(c)` as `Counter({'a': 3, 'b': 2})`. `most_common([n])` (ties in insertion order,
  as CPython) is built in `for word, n in c.most_common(10):`, in comprehensions of that form,
  as `c.most_common(1)[0][0]` / `[i][1]`, in `len()`, `dict()` and `print()`; the loop body may not change `c`.
- `defaultdict(int | float | str | lambda: <constant>)`: a `dict`. `d[k]` inserts the default, as CPython
  (so `len(d)` and the order of the keys show it); `d.get(k, x)`, `in`, `pop`, `setdefault` do not;
  `d[k] += v`, `dict(d)`, `d.copy()`, `for k in d`, `items()` work. `OrderedDict()` is an insertion-ordered
  dict with `move_to_end(k)` and `popitem(last=True | False)` (a statement or `k, v = d.popitem(...)`).
- `defaultdict(list)`: a class with the keys in order and the rows (`list[list[T]]`, T int, float or str):
  `d[k].append / extend / pop / sort / insert`, `d[k] += [..]`, `d[k][i]`, `len(d[k])`, `for x in d[k]`,
  `d[k] = [..]` (a fresh list), `d.get(k, [])` where the result is only read, `k in d`, `len(d)`,
  `for k in d`, `d.keys() / values()`, `for k, v in d.items()`, `d.clear()`. Pass it to a function with a
  parameter annotated `defaultdict[K, list[T]]` (or `Dict[K, List[T]]`); the callee may change it.
  `defaultdict(set)` (elements int or str): `d[k].add / discard / remove / update(xs)`, `x in d[k]`,
  `len`, `sorted / sum / min / max / any / all` of a row; looping over a row is refused (CPython's set order is
  unspecified) -- write `for x in sorted(d[k])`.
- `deque` (ring buffer, O(1) at both ends): `deque()`, `deque(iterable)`, `maxlen=n` (drops from the other
  end), `append appendleft pop popleft extend extendleft rotate([n]) clear count index remove insert
  reverse copy`, `len(q)`, `q[i]` / `q[i] = x` / `del q[i]` (negative too), `x in q`, `for x in q`, `while q:`,
  `list(q)`, `sum / min / max / sorted(q)`, `print(q)`; `IndexError` / `ValueError` as CPython.
- A collection passed to a function needs the same annotation on the parameter. A `Counter` or a defaultdict
  of numbers is a dict there (read-only: return new values instead of changing it); `d[k]` on a defaultdict
  parameter is refused because it would insert into the caller's dict.
- Tuples inside collections (tuples of `int` / `float` / `bool` / `str`, see Tuples): `deque([(r, c)])` with
  `r, c = q.popleft()`, `deque` of `(node, dist)`, `Counter` of coordinate tuples (`most_common`, `+`, `update`,
  `Counter(zip(a, b))`), `defaultdict(int | float | str)` and `OrderedDict` with tuple keys,
  `defaultdict(list)` / `defaultdict(set)` with tuple rows and/or keys (`adj[u].append((v, w))` then
  `for v, w in adj[u]`). The collections pass runs first and writes its helpers with `tuple[...]`
  annotations, which the tuple pass lowers to classes and tables, so the C runtime gets nothing new.
  Printing is CPython's repr: `deque([(1, 2)])`, `Counter({(0, 1): 2})`, `defaultdict(<class 'int'>, {...})`,
  `defaultdict(<class 'list'>, {...})`, `OrderedDict({...})` (also for str / int keys).
- Refused by name (`note:` lines): `namedtuple(rename=)` (namedtuple, ChainMap: batch 5) and the rest of the module,
  `defaultdict(bool | dict | Counter | lambda: <expression>)`, float keys, nested tuples,
  `print` of a `defaultdict(set)` or of `defaultdict(lambda: ...)`, `==` / `<` on collections, `q.maxlen`, `d.default_factory`, deque slices, `OrderedDict(items)`, a collection
  in a class field or at module level, `top = c.most_common(3)` as a value, `d[k] = xs` with an existing list,
  `del d[k]` on `defaultdict(list)`, `Counter.subtract`, a loop that adds to or
  deletes from the collection it walks (CPython raises `RuntimeError`).

```python
from collections import Counter, defaultdict, deque


def main() -> int:
    words = "to be or not to be".split()
    counts = Counter(words)
    for word, n in counts.most_common(2):
        print(word, n)
    groups = defaultdict(list)
    for i, w in enumerate(words):
        groups[len(w)].append(i)
    for k in sorted(groups):
        print(k, len(groups[k]))
    window = deque(maxlen=3)
    for w in words:
        window.append(w)
    print(len(window), window[0], counts["zzz"], len(counts))
    return 0


main()
```

```text
to 2
be 2
2 5
3 1
3 not 0 4
```

## Tuples, lambdas (Python syntax)

Tuples and lambdas are lowered before the rest runs (tuplib.py): a tuple type is a class `_AilT_<types>` with
fields f0, f1, ..., a tuple expression its constructor, `t[k]` a field read, a dict or set that mentions a
tuple a generated insertion-ordered hash table. Tuples are immutable, so sharing is CPython's behaviour. A
program whose tuple uses the compiler already builds (literal swaps, sort-key tuples, `%` operands, lists of
number tuples) is returned as written. Element types: int, float, bool, str, tuples, lists of those.

- Functions: `return a, b`, `-> tuple[int, str]` (or `Tuple`), `q, r = f(x)`, nested `(a, b), c = ...`,
  `divmod(a, b)`, `k, sep, v = s.partition(":")`, tuple parameters, class fields, `Optional[tuple[...]]`.
- `t[k]` with a constant k (negative too), `len(t)`, `== != < <= > >=` (lexicographic, CPython's rules;
  a nan field raises), `print(t)` / `str(t)` / f-strings give CPython's repr: `(1, 'a')`, `(1,)`, quotes and
  escapes. `print(xs)` of a list is its repr too.
- Loops: `for a, b in pairs`, `for i, (a, b) in enumerate(pairs)`, `for x, y in zip(xs, ys)`,
  `for (r, c), v in d.items()`, comprehensions over or producing tuples (built as statements).
- `list[tuple[...]]`: `append`, `sort()` (lexicographic), `sort(key=...)`, `sorted`, `min`, `max`, `in`,
  `index`, `count`, `pop`, `insert`, slices, `reverse`. Sorting tuples of more than 4 scalar fields is done
  by successive stable sorts in `list.sort()`.
- `heapq`: `heappush(h, (d, v))`, `heappop`, `heapify`, `heappushpop`, `heapreplace` on lists of tuples.
- `dict[tuple, V]`, `dict[str, tuple]`, `set[tuple]`, V int, float, str, bool, a tuple, or a list (a row is
  read in place, `d[k].append(x)` changes it; `d[k] = xs` stores a copy): `d[k]`, `d[k] = v`, `d[k] += v`,
  `get`, `setdefault`, `pop`, `del`, `in`, `len`, `update`, `copy`, `keys / values / items`, `popitem`;
  sets `add discard remove pop clear update`, `| & - ^`, `<= < >= >`, `==`. Iteration is in insertion order
  (a set too, unlike CPython: sort before printing). A float is not a key. A loop may not change the
  dict or set it walks.
- A module-level list of number tuples (`DIRS = [(0, 1), (1, 0)]`) is kept as columns; `for dr, dc in DIRS`
  allocates nothing.
- Lambdas: `f = lambda x: x * k` and then `f(3)`, `apply(f, xs)`; a lambda passed to a parameter typed
  `Callable[[int], int]` (lifted to a top-level function; with captured locals the callee is cloned and
  gets the captures as leading parameters); `map / filter` with a lambda (fused into loops and
  comprehensions); `functools.reduce` with a lambda. A captured name must not be assigned after the lambda
  is made (CPython reads it when the lambda is called); a lambda that is returned or stored in a list,
  dict or field is refused by name.
- Refused by name: tuple concatenation / repetition / slices, a variable index, `tuple(x)`, `tuple[int, ...]`,
  iterating a tuple, float keys, dict values that are sets or
  dicts, `max(xs, key=...)` over tuples.

```python
import heapq


def main() -> int:
    q, r = divmod(17, 5)
    pq = [(3, "c"), (1, "a")]
    heapq.heapify(pq)
    heapq.heappush(pq, (2, "b"))
    seen = {(0, 0)}
    seen.add((0, 1))
    k = 10
    scale = lambda x: x * k
    print(q, r, heapq.heappop(pq), (1, "a") < (1, "b"), len(seen), scale(4))
    return 0


main()
```

```text
3 2 (1, 'a') True 2 40
```

## Libraries

`import random`, `import itertools`, `import functools`, `import json` (or `from m import name`). Each use is
lowered before the rest of the compiler runs (stdlib3.py, itlib.py, funclib.py, jsonlib.py), so a program that
imports none of them is unchanged. A use that is not built is refused by name (`module.name ...`), never
passed on to the generic import refusal. Positions: a call that needs statements (sample, reduce, a
comprehension over itertools, list(chain(...))) is built where it is the first thing a statement evaluates
(`x = ...`, `return ...`, `print(...)` past names and constants, an `if` test, a `for` iterable); bind it to a
variable first when it sits behind another call.

- `random`: CPython 3.12's MT19937, bit for bit after `random.seed(<int>)`: `random()`, `randint`,
  `randrange(stop | start, stop[, step])`, `uniform`, `gauss(mu, sigma)`, `choice(list)`, `shuffle(list)`,
  `sample(list, k)` (same draws, same ValueError / IndexError). The state is one generator per program. A
  program without `random.seed(<int>)` is refused (an unseeded run is not reproducible);
  a seed that is a str / float / None, `choices`, `triangular`, `getrandbits`... are refused by name (`random.Random(seed)`:
  batch 5). Ranges wider than 64 bits are a RuntimeError. Only the module-level functions share state, as in CPython.
- `itertools`: `count`, `repeat` (a number or str), `chain`, `chain.from_iterable` (list of lists), `islice`
  (None, 1 to 3 integers, CPython's ValueErrors), `accumulate` (default `+`, `func=` a two-parameter lambda,
  a function name, `max`, `min`, `operator.mul`..., `initial=`), `pairwise`, `zip_longest(..., fillvalue=)`,
  `groupby(list[, key])` (a pure key: lambda over len / abs / str / int / indexing or a name), `product`
  (`repeat=` a literal), `permutations`, `combinations`, `combinations_with_replacement`. They are loops, so they appear in
  `for` statements, comprehensions / generator expressions, and as the argument of `list`, `sum`, `min`, `max`,
  `sorted`, `set`, `any`, `all`, `"".join` (`any` / `all` stop early). The items come out in CPython's order. Arguments are
  lists / strs held in a variable the compiler knows to be one, slices, literals, comprehensions or `range(...)`
  (anything else: `list(...)` it first). Lists are walked live (a list the body grows is walked on); the
  pools of `product` / `permutations` / `combinations` are snapshots, as CPython's are. Tuples are not a
  type: a tuple item is unpacked (`for a, b in product(x, y)`; `permutations(xs)` with a variable r needs the
  item bound to one name), or bound to one name that is only indexed, iterated, summed or measured (it is a
  list; `print(p)`, `p == q`, `d[p]` are refused). `zip(count(1), xs)` works too. Not built: `cycle`, `tee`,
  `takewhile`, `dropwhile`, `filterfalse`, `starmap`, `compress`, `batched`, iterators held in variables, a
  loop's `else:`, rebinding the walked list inside the loop.
- `functools.reduce(f, iterable[, initial])` with a two-parameter lambda, a function name, `max` / `min`,
  `operator.add` / `mul`..., `math.gcd` (these now also work as values: `key=operator.neg`). An empty iterable without
  an initial value raises RuntimeError with CPython's text (there is no TypeError here).
  `@lru_cache` / `@lru_cache(maxsize=N)` / `@cache` on a top-level pure function (int / str / bool parameters,
  int / float / str / bool result; no print, input, files, sys, random, time, global): one memo dict per function,
  shared by every call of the program (the dict travels as an extra parameter of the functions that can reach
  it; `main` creates it). The size bound is ignored (the result of a pure function does not depend on eviction).
  `cache_info()` / `cache_clear()` and passing the function as a value are refused.
  `sorted(xs, key=cmp_to_key(f), reverse=)` and `xs.sort(key=cmp_to_key(f))` with a pure `f(a, b) -> int`: a
  stable merge sort calling `f(a, b) < 0`, the same order as CPython for every consistent comparator.
- `json.loads(s)` needs the type it produces, written down: `data: dict[str, int] = json.loads(s)`, a
  function's return annotation, an annotated variable, or an annotated parameter of the function it is passed to.
  Types: `int`, `float`, `str`, `bool`, `list[T]`, `list[list[T]]` (T int / float / str), `dict[str, T]` (T int / float /
  str); `list[dict[...]]`, `dict[str, list[...]]`, `dict[str, bool]` are not types the compiler holds, so they are
  refused. `json.load(sys.stdin)` is `json.loads(sys.stdin.read())`. The text is checked by a scanner with CPython's
  messages, so every malformed document raises the same ValueError (`json.JSONDecodeError` in an `except` is
  ValueError) with the same `line L column C (char P)`. A valid document that does not fit the declared type
  (1 where float is declared, 1.5 for int, null, another container, an int beyond 64 bits, a lone surrogate)
  is a RuntimeError naming what was found: CPython would hand back another type and a silent conversion would print
  differently. `json.dumps(x, indent=, sort_keys=, separators=, ensure_ascii=, allow_nan=)` (literal options)
  prints CPython's bytes for dict / list / str / int / float / bool / None literals (nested, mixed) and for variables of
  the types above, whose type comes from an annotation or the first assignment; `json.dump(x, sys.stdout)` works.
  `default=`, `cls=`, `skipkeys=` and a value of unknown type are refused by name.
  Speed: a plain document (strict syntax, every value of the declared type, ints within 64 bits) is parsed in one
  pass by the C runtime straight into the declared list / dict, with no intermediate strings, and `json.dumps` of a
  list, a nested list or a str-keyed dict is written by C appenders into one buffer; on the 12 MB benchmark documents
  both are 2-6 times faster than CPython 3.12 with about half its peak memory. Whatever the fast path does not take
  (a syntax error, a value of another type, NaN, an integer beyond 64 bits) runs the scanner and the typed parsers
  described above, so errors and results are the same. `data: dict[str, int] = json.loads(s)` (or an assignment to an
  annotated local) fills the local in place; a `return json.loads(s)` or a call argument goes through a loader
  function and copies the result once more.
- `pathlib` (`from pathlib import Path`, POSIX paths): `Path(a, b)`, `Path.cwd()`, `p / "x"`, `p /= "x"`, `str(p)`, `print(p)`,
  `f"{p}"`, `repr(p)`, `p == q`, `p.name stem suffix suffixes parent root anchor`, `p.parts` (iterate it, index it with one number,
  `len` or `list(p.parts)`), `joinpath with_name with_stem with_suffix resolve absolute is_absolute as_posix`, `exists is_file
  is_dir`, `mkdir(parents=, exist_ok=)`, `unlink(missing_ok=)`, `rmdir`, `rename`, `replace`, `read_text write_text read_bytes
  write_bytes open` (UTF-8), `iterdir() glob(pat) rglob(pat)` in a `for` loop or inside `list()` / `sorted()`; `sorted(paths)`
  orders as CPython. A path is known from the program text, so annotate: `def f(p: Path) -> Path:`, `xs: list[Path] = []`, a
  dataclass field `root: Path`; a path passed to an unannotated parameter or returned without `-> Path` is refused. Also
  refused, with the line to write instead: `stat touch chmod relative_to parents is_symlink`, `Pure*` classes, a path as a dict
  key or set member, `<` on paths, `p.iterdir()` kept in a variable. The typed path does not build a comprehension over a
  `list[Path]` that produces strs: write the loop (the default build falls back to the slower general path). Differences:
  DIFFERENCES A31-A35.
- `urllib` (`import urllib.request`, `urllib.error`, `urllib.parse`; `http://` and `https://` over libcurl, which is linked only into
  a program that uses `urllib.request`; typed path only): `urlopen(url, data=, timeout=)`, `urlopen(request)`, `Request(url, data=,
  headers={...}, method=)` and `add_header get_method has_header get_header(k, d) full_url`; the response `r.read() r.read(n) r.status
  r.reason r.url r.getcode() r.geturl() r.headers.get(name, "") name in r.headers r.getheader(name, "") r.close()` and `with
  urlopen(url) as r:`; `except urllib.error.HTTPError as e:` (`e.code e.reason e.url e.read() e.headers.get(n, "") print(e)`) and
  `except urllib.error.URLError as e:` (`e.reason`), both caught by `except OSError`; `urllib.parse.urlencode(d) quote(s, safe=)
  quote_plus unquote unquote_plus urljoin`. It does what CPython 3.12 does: `Python-urllib/3.12`, POST when `data` is given, redirects
  followed (10 at most), a status outside 200-299 is an `HTTPError`, certificates checked (`SSL_CERT_FILE`). Print a body as
  `r.read().decode()`. Refused with the line to write instead: openers and handlers, `ftp:` / `file:` URLs, `headers.get(name)` with
  no default (there is no `None` str), `r.info()`, iterating a response, the `urlparse` family, passing a response to a function.
  Differences: DIFFERENCES A46-A50.
- Threads (`threading`, `queue`, `concurrent.futures`): one interpreter lock as in CPython, so threads overlap waiting
  (`sleep`, `join`, `Queue.get`, locks), not computing. `threading.Thread(target=worker, args=(a, b))` where `worker` is a
  module-level `def` or `obj.method` (not a lambda or a nested def), `start join is_alive name daemon`, subclasses with
  `run()`; `Lock RLock Condition Semaphore BoundedSemaphore Event` with `with`; `queue.Queue(maxsize)` `LifoQueue`
  `SimpleQueue` with `task_done/join`, `queue.Empty/Full`; `ThreadPoolExecutor` `submit map shutdown as_completed`,
  `Future.result()` raising the worker's exception. Built on the general path only (the program falls back to it, several
  times slower than typed code). Print results after `join()`, sorted, or from one consumer: thread order is not
  deterministic in CPython either. Refused with the line to write instead: `threading.local Timer Barrier`,
  `PriorityQueue`, `ProcessPoolExecutor`, `wait_for`, `add_done_callback`. Differences: DIFFERENCES A36-A38.
- `sqlite3` (the system libsqlite3; only a program that imports it links it): `conn = sqlite3.connect(path or ":memory:")`,
  `conn.execute(sql, params)` / `executemany(sql, rows)` / `executescript` / `cursor()` / `commit()` / `rollback()` / `close()`,
  `with conn:`, `cur.fetchone()` / `fetchall()` / `for row in cur`, `rowcount`, `lastrowid`, `conn.in_transaction`,
  `except sqlite3.IntegrityError` (and the other classes), 3.12's implicit BEGIN before insert / update / delete / replace.
  `?` / `:name` parameters (tuple, list or dict display, or a name beside a literal SQL text) of int, float, str, bytes, bool, None.
  Rows are plain tuples whose shape YOU declare in an annotation CPython ignores: `rows: list[tuple[int, str]] = cur.fetchall()`,
  `row: tuple[int, str] | None = cur.fetchone()`, `n = cast(tuple[int], cur.fetchone())[0]`, `pk: int` and `name: Optional[str]` on
  lines of their own before `for pk, name in cur.execute(...)`. A nullable (`Optional[T]`) or `bytes` column makes the row a
  generated class (index with a constant, unpack, `is None`, print). A value of another type than declared is a `RuntimeError`.
  `print(e)` / `str(e)` of an error is CPython's text. Refused with the line to write instead: `row_factory`,
  adapters, `create_function`, `fetchmany`, `description`, `connect(timeout=...)`. Differences: DIFFERENCES A41-A44.

## Heaps: heapq, bisect

No import, on a list of int, float, str or structs: `heappush(h, x)`, `heappop(h)` (`IndexError`
when empty), `heapify(h)`, `heappushpop(h, x)`, `heapreplace(h, x)`;
`bisect_left/bisect_right/bisect(xs, x[, lo[, hi]])`, `insort/insort_left/insort_right(xs, x[, lo[,
hi]])`. Same results and heap layout as CPython, O(log n), the list changed in place.
- The list that changes must be a local or a struct field (`heappush(self.h, x)`), not a list
  parameter.
- A heap of structs takes a sort key on every call: `heappush(h, n, key=lambda n: (n.dist, n.id))`,
  `heappop(h, key=lambda n: (n.dist, n.id))` (the same key each time; Python would use a tuple).
  A key of 1-4 int/float fields read as they are (`(n.dist, n.id)`) is sifted in C over the list's
  pointers, no reference count per step; any other key (negated, computed, str) is slower, so there
  prefer a heap of ints: push `(d << 20) | v`, pop `p >> 20` and `p & 1048575`.
  `bisect_left(xs, x, key=lambda n: n.t)` compares `x` with `key(xs[i])`.
- A call that pops inside a larger expression must come before any other read of that list in it;
  otherwise bind it first: `let x = heappop(h);`. A function you define with the same name wins.

## Loops: for, comprehensions

`for` walks a list, str, bytes (also `data[i:j]`, `s.encode()`), bytearray, a dict,
`range(a, b, step)`, `enumerate(list)`, `reversed(list)`, `sorted(...)`, `s.split(...)`,
`s.splitlines()`, a call returning a list, `sys.stdin`. `break`, `continue`, `pass`,
`x if c else y`, list and dict comprehensions (also nested `for`), `zip(a, b)` as the iterable of
`for a, b in`, `isinstance(x, int)` (and str / float / bool). `parallel for` (Parallel).
No `for ... else`, `list(zip(...))`, `enumerate(zip(...))`, `enumerate(str)`, tuple unpacking
beyond `for a, b in zip(...)` / `enumerate(...)` / `d.items()`, or `isinstance` of a struct.

## Exceptions

`ValueError`, `KeyError`, `IndexError`, `ZeroDivisionError`, `OverflowError`, `OSError`
(= `FileNotFoundError`), `EOFError`, `RuntimeError`, `AssertionError`, `UnicodeDecodeError`.
Name the kinds: `except (ValueError, KeyError) as e` (no bare `except`); `except Exception` takes every kind. On the
Python surface `print(e)`, `str(e)`, `repr(e)`, `f"{e}"`, `"%s" % e`, `e.args`, `e.args[i]`, `len(e.args)`,
`type(e).__name__`, `isinstance(e, K)` read like CPython's (`ValueError('x')`, `('x',)`, `[Errno 2] No such file or
directory: 'f'`; a KeyError prints its key's repr); `raise K(a, b)` takes up to 8 str, int, float, bool or None
arguments. Own classes: `class E(Base)` where Base is `Exception`, `ValueError`, `RuntimeError`, `IndexError`,
`ZeroDivisionError`, `EOFError`, `AssertionError`, `OverflowError` or such a class; the body is `pass`, an `__init__`
with one `super().__init__(..)` and `self.x = <expression of the parameters>` (annotate the parameters or let the
calls show their kinds), constants in the body (`status = 404`) and a `__str__` returning an expression of `self.x`;
read `e.x` under `except E as e`.
On the brace surface: `e.kind`, `e.message` are strs. `raise ValueError("m");`, `raise;`,
`assert c, "m";`. Uncaught: message on stderr, exit 1. A function whose body only raises still
needs a final `return`. Handler names: Local names.

## Refused: what to write instead

| Python | AIL |
|---|---|
| tuples beyond the Tuples section, `zip` over non-lists | a struct; index loops |
| a lambda that escapes, nested `def` | a top-level `fn` passed as `Callable[[A], R]` |
| changing a global list / str / dict | a struct holding the state, passed to each function; a module-level int / float may use `global` |
| `dict[str, Struct]`, `dict[str, list[T]]` on the typed path | a `dict[str, int]` index into a `list[Struct]` (or a `list[list[T]]`); the default build falls back |
| `None` for a list on the typed path | a sentinel (-1, ""), or raise; int / float / str may be `int \| None` |
| `xs[i] = v` or `xs.append(v)` on a list parameter (typed path) | a struct field `s.xs`, or return a new list; the default build falls back |
| one name holding an int, later a str | a second name |
| `str(b)` of bytes on the typed path | `b.decode()`; the default build prints the repr |
| `print` of a dict on the typed path | `sorted(d.items())`; a list and a tuple print as their repr |
| `d.get(k)` (None when missing) | `d.get(k, -1)` with a sentinel, or `if k in d { ... d[k] ... }` |
| `int(s)` on text that may overflow | `parse_int64_decimal(s)` from `checked_integer` (`ValueError`) |
| a file mode, encoding or `os` call that is not built | `read_bytes`, `write_text`, `file_chunks` |
| big integers (`Fraction` has 64-bit parts) | limbs in a `list[int]`; a `@dataclass` class |

```ail-refused
fn main() { let t = (1, 2); print(t[0]); }

let counter = 0;
fn main() { counter += 1; }

fn main() { let x: int | None = None; print(1); }

fn push(xs: list[int]) -> void { xs.append(1); }
fn main() { let a: list[int] = []; push(a); }

fn main() { let x = 1; if x == 1 { print(1); } else if x == 2 { print(2); } }

fn main() { if true { print(1); }; }

struct N { v: int; next: N; }
fn main() { print(1); }

fn main() { if 1 > 0 { let x = 1; print(x); } else { let x = "a"; print(x); } }

fn main() { let d = b"ab"; print(str(d)); }

fn main() { let e = 5; try { raise ValueError("x"); } except ValueError as e { print(1); } print(e); }
```

## Word count: top-N, grouping by key (example)

```ail
struct Group { key: str; count: int; total: int; }
fn main() {
    let counts: dict[str, int] = {};
    for w in "b a b c b d d a e".split() { counts[w] = counts.get(w, 0) + 1; }
    let shown = 0;
    for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) {
        if shown == 3 { break; }
        print(str(v) + "\t" + k);
        shown += 1;
    }
    let slot: dict[str, int] = {};
    let groups: list[Group] = [];
    for row in ["b,2", "a,5", "b,3"] {
        let f = row.split(",");
        let i = slot.get(f[0], -1);
        if i < 0 { slot[f[0]] = len(groups); groups.append(Group(f[0], 1, int(f[1]))); }
        else { groups[i].count += 1; groups[i].total += int(f[1]); }
    }
    groups.sort(key=lambda g: (-g.total, g.key));
    for g in groups { print(f"{g.key}\t{g.count}\t{g.total}"); }
}
```

```text
3	b
2	a
2	d
a	1	5
b	2	5
```

## Dijkstra: int heap, adjacency, insort (example)

```ail
struct Step { dist: int; node: int; }
fn main() {
    let n = 4;
    let src = [0, 0, 1, 2];
    let dst = [1, 2, 3, 3];
    let w = [4, 1, 1, 5];
    let out: list[list[int]] = [[] for _ in range(n)];
    for e in range(len(src)) { out[src[e]].append(e); }
    let best = [1 << 60] * n;
    best[0] = 0;
    let h = [(0 << 20) | 0];
    while len(h) > 0 {
        let p = heappop(h);
        let d = p >> 20;
        let u = p & 1048575;
        if d > best[u] { continue; }
        for e in out[u] {
            if d + w[e] < best[dst[e]] {
                best[dst[e]] = d + w[e];
                heappush(h, (best[dst[e]] << 20) | dst[e]);
            }
        }
    }
    let sh: list[Step] = [];
    for v in range(n) { heappush(sh, Step(best[v], v), key=lambda s: (s.dist, s.node)); }
    let s = heappop(sh, key=lambda s: (s.dist, s.node));
    let seen: list[int] = [];
    for x in [5, 1, 4] { insort(seen, x); }
    print(best[3], s.dist, s.node, seen[0], bisect_left(seen, 4));
}
```

```text
5 0 0 1 1
```

- Group edges by source once (`out`); never scan every edge for each popped node (O(V*E)).
- Many S-to-T queries on one big graph: stop when T is popped, and search from both ends (a heap
  per side, stop once the two tops add up to at least the best meeting found): on rail_transfer
  175x fewer relaxations than a one-sided search, which made AIL 40x slower than C there.

## BFS: graph, grid DP, buckets (example)

```ail
struct Graph { adj: list[list[int]]; }
impl Graph {
    fn add(self, u: int, v: int) -> void { self.adj[u].append(v); self.adj[v].append(u); }
}
fn bfs(adj: list[list[int]], src: int) -> list[int] {
    let dist = [-1] * len(adj);
    dist[src] = 0;
    let q = [src];
    let head = 0;
    while head < len(q) {
        let u = q[head];
        head += 1;
        for v in adj[u] {
            if dist[v] < 0 { dist[v] = dist[u] + 1; q.append(v); }
        }
    }
    return dist;
}
fn main() {
    let n = 5;
    let g = Graph([[] for _ in range(n)]);
    g.add(0, 1); g.add(1, 2); g.add(0, 3); g.add(3, 2);
    let d = bfs(g.adj, 0);
    print(d[2], d[4], len(g.adj[2]));
    let h = 3; let w = 4;
    let paths = [[1] * w for _ in range(h)];
    for i in range(1, h) {
        for j in range(1, w) { paths[i][j] = paths[i - 1][j] + paths[i][j - 1]; }
    }
    let buckets: list[list[str]] = [[] for _ in range(3)];
    for word in "pear fig apple kiwi plum".split() { buckets[len(word) % 3].append(word); }
    for b in buckets { b.sort(); }
    let row = paths[2];
    row.append(0);
    print(paths[h - 1][w - 1], len(paths[2]), ",".join(buckets[1]));
}
```

```text
2 -1 2
10 5 kiwi,pear,plum
```

## Modules: csv, json, checked ints

`use NAME;` at the top; exact signatures: `python3 ail_chatgpt.py api NAME`.

| module | use |
|---|---|
| `checked_integer` | `parse_int64_decimal(s) -> int` (`[+-]?[0-9]+` within int64, else `ValueError`), `checked_int64_add(a, b)` |
| `csv_stream` | `dec = csv_decoder_new(); rows = csv_decode_feed(dec, text); rows.extend(csv_decode_finish(dec));` gives `list[CsvRow]`, `CsvRow{number; fields: list[str]}`; RFC 4180, empty lines skipped, bad quote `ValueError` |
| `json_pointer_scan` | `json_pointer_scan_bytes(data, pointers: list[str]) -> JsonPointerValues{error; values: list[str]}`: values as compact JSON; `error != 0` or `ValueError` if invalid or not found |
| `json_pointer` | `json_parse_document(text) -> list[JsonValue]`, `JsonValue{kind; parent; key; text}` (kind 0 null, 1 bool, 2 number, 3 string, 4 array, 5 object), `json_quote(s)` |
| `utf8_stream`, `cli_args`, `path_posix`, `base64_codec`, `csv_writer`, `binary_cursor` | see `api NAME` |

```ail
use csv_stream;
use json_pointer_scan;
fn main() {
    let dec = csv_decoder_new();
    let rows = csv_decode_feed(dec, "name,qty\n\n\"x,\"\"y\",-5\r\nb,2");
    rows.extend(csv_decode_finish(dec));
    print(len(rows), rows[1].fields[0], rows[2].fields[1]);
    let found = json_pointer_scan_bytes(b"{\"a\": {\"b\": [10, \"t\\u00e9\"]}}", ["/a/b/1", "/a"]);
    print(found.error, found.values[0], found.values[1]);
}
```

```text
3 x,"y 2
0 "té" {"b":[10,"té"]}
```

## Speed: lines versus bytes, measured

Line-oriented input and output (best wall time of several runs, peak RSS, instructions):

| task | `for line in sys.stdin`, `split`, `int`, `print(f"...")` | hand-written bytes |
|---|---|---|
| 2M lines of 6 ints (118 MB) | 0.44 s, 1.5 MB, 6.6 G | `read_stdin_bytes` scanner 0.59 s, 233 MB, 4.2 G |
| 2M `S\|ev\|seat\|buyer` records, validate, count | `split("\|")`, `isdigit` 0.73 s, 156 MB, 3.9 G | offsets 0.78 s, 295 MB, 3.8 G |
| 3M output lines | `print(f"...")` 0.63 s, 1.4 MB, 3.6 G | `bytearray` + itoa 0.94 s, 107 MB, 9.2 G |
| the 12M ints on one line | 0.73 s, 411 MB, 5.2 G | scanner 0.47 s, 233 MB, 4.2 G |

`"\n".join(out)` of the 3M lines: 0.56 s but 366 MB. `for w in data.split()` on bytes builds every
token first: 2.2 s, 1.1 GB. Whole programs written this way (berth_sim, ticket_audit, term_rank
of tasks-novel) were 23 to 58% shorter than byte-scanner versions; 2.8M log lines each split into
fields and checked one field kind at a time took 3.3x the instructions of a byte scanner (22 G
versus 6.8 G), a 3M-line simulation 1.2x. So: lines and `split` for text; a byte scanner for
binary data, one huge line, or when per-field checks of a huge file dominate and speed matters
more than length. On 8 MB of text: `for b in data` over bytes 29 ms (C: 27); `for c in s` 55; `while`
with `s[i]` on a str 190; `out += line + "\n"` 148 versus `out += line; out += "\n";` 87.
`for line in s.splitlines()` builds no list.

## Parallel: `parallel for` loops

`parallel for i in range(a, b) { ... }` runs iterations on all cores and gives exactly the result of
the plain `for` (`AIL_THREADS=n` fixes the thread count). The compiler refuses, by name, a body whose
iterations could see each other:
- The body computes int/float values and may read anything. It writes only (a) locals it creates
  itself, private to one iteration and unusable after the loop, and (b) elements `xs[i]`,
  `xs[i * K + j]` (`j` from an inner `for j in range(0, K)`) or `xs[i * 4 + 1]` of a list or
  bytearray sized before the loop (`[0.0] * n`, `bytearray(n)`), touched nowhere else in the body.
- Refused: a total carried between iterations (`t += x`: write `out[i]`, add up after the loop),
  append/pop, str, bytes, print, try, return, a nested `parallel for`, any call except
  int/float/abs/min/max/round/len and top-level `fn`s that take and return only int/float.
- An error in the body (IndexError, OverflowError) is raised after the loop, the same one a
  sequential run hits first. Not allowed in a function that has try/except: put the loop in its own `fn`.

```ail
fn row_sums(n: int) -> list[float] {
    let out = [0.0] * n;
    parallel for i in range(0, n) {
        let s = 0.0;
        for j in range(0, n) { s += 1.0 / float(i + j + 1); }
        out[i] = s;
    }
    return out;
}
fn main() {
    let r = row_sums(1000);
    let total = 0.0;
    for x in r { total += x; }
    print(r[0], r[999], total);
}
```

```text
7.485470860550343 0.6933972430599376 1385.7944861198737
```

### Library batch 4 (csv, datetime, statistics, small forms)

Lowered in the front end like batches 1 to 3 (stdlib4.py, csvlib.py, dtlib.py, statlib.py, smalllib.py); a program that does not use them is unchanged.

- `csv`: `reader`, `DictReader`, `writer`, `DictWriter` on `sys.stdin`, a file opened for reading, or a list of lines, with `delimiter quotechar doublequote escapechar skipinitialspace quoting lineterminator strict`. CPython's state machine (QUOTE_MINIMAL default, `lineterminator '
'`). A parse error is raised when the reader reaches it, so earlier rows are processed first. `csv.Error` is `ValueError`. Declared difference: `DictReader` rows with too few or too many fields raise `RuntimeError`.
- `datetime`: `date`, `datetime` (naive), `time`, `timedelta` with arithmetic, comparison, `replace`, `isoformat`, `strftime`, `strptime`, `fromisoformat`, `fromordinal`, `weekday`, `isocalendar` parts. `now() utcnow() today() date.today() fromtimestamp() utcfromtimestamp() timestamp()` read the wall clock and the OS time zone (`time`, below). Fixed-offset time zones are built: `timezone.utc`, `UTC`, `timezone(timedelta(...)[, name])`, `tzinfo=` / `replace(tzinfo=)`, `astimezone([tz])`, `utcoffset()`, `tzname()`, `now(tz)`, `fromtimestamp(t, tz)`, `fromisoformat` with `Z` or an offset, `%z %Z`; test `d.tzinfo is None`. Refused by name: `zoneinfo`, `tzinfo` subclasses, `dst()`, `timezone.min/max`, an aware `time`. Limit: `timedelta` beyond about 53 million days raises `OverflowError`.
- `time`: `perf_counter() monotonic() time() time_ns() sleep(x) localtime([t]) gmtime([t]) strftime(fmt[, t]) mktime(t)`. The wall clock is a program input: `AIL_CLOCK=<seconds>[.<fraction>]` pins it for tests (every read returns that value, `sleep(x)` advances it without sleeping); local time is the OS time zone (`TZ` is respected). `localtime` and `gmtime` give an object with `tm_year tm_mon tm_mday tm_hour tm_min tm_sec tm_wday tm_yday tm_isdst tm_zone tm_gmtoff` only. Refused by name: `asctime ctime tzset altzone daylight timezone tzname struct_time(...)` and `strftime` of a tuple.
- `statistics` on `list[int]`: `mean median median_low median_high mode multimode variance pvariance stdev pstdev`; `fmean`, `median`, `median_low`, `median_high`, `mode`, `multimode` also on `list[float]`. `StatisticsError` is `ValueError`. Mixed int/float results only where printed or used as floats.
- Small forms: `int.bit_length()`, `int.bit_count()`, `max/min(..., default=)`, `max(d, key=d.get)` (and over a generator), `x in (constants)`, `itertools.product(x, repeat=n)` with a runtime `n`, unpacking a `tuple | None` after a None test.
- `unicodedata.category(ch)` from the generated `stdlib/unicodedata.py` (CPython 3.12's Unicode 15.0 data): the General_Category of one character, with CPython's `TypeError` for an empty or longer string and for a non-str value. `name`, `normalize`, `lookup` and the rest are refused by name.
- Refused by name with a "write instead" hint: `decimal`, `string.Template`.

### Library batch 5 (fractions, enum, namedtuple, random.Random, keyword, calendar, abc, array, io.StringIO)

Lowered in the front end (stdlib5.py, enumlib.py, ntlib.py, randlib.py, smalllib5.py; the classes are Python source in `prelude_*.py`); a program that
imports none of them is unchanged. They are classes with operator methods, so a program using them is built on the general path (several times
slower than typed code), where operator methods dispatch on the run-time class (dunderrt.py). `int` is still 64 bits: a numerator beyond it is an `OverflowError`.

- `fractions.Fraction`: `Fraction(a, b)`, `Fraction("3/4")`, `Fraction("0.125")`, `Fraction(0.75)`, `Fraction(other)`; `+ - * / // % **` with ints, Fractions and
  floats (a float gives a float), `== < <= > >=`, `abs round(x[, n]) int float math.floor math.ceil`, `limit_denominator`, `numerator`, `denominator`,
  `is_integer`, `as_integer_ratio`, `Fraction.from_float`, `sum / min / max / sorted`, dict keys and set members. `str`/`repr` as CPython (`3/4`, `Fraction(3, 4)`).
  Not built: `Fraction.from_decimal`, `format` specs, `divmod`, `decimal` (refused by name).
- `enum`: `Enum`, `IntEnum`, `StrEnum`, `Flag`, `IntFlag`, `auto()`, `@unique`. Members print as `Color.RED`, repr `<Color.RED: 1>`; `Color(1)` (ValueError `1 is not a valid Color`),
  `Color["RED"]` (KeyError), `for c in Color`, `list(Color)`, `len(Color)`, `Color.__members__`, aliases, `.name`, `.value`, methods, members as dict keys and set
  members, `==` / `is`. An `IntEnum` member compares, adds and indexes like its value (`int(m)`, `m + 1`, `lst[m]`). `Flag` / `IntFlag` compose with `| & ^ ~ << >>`,
  test with `in`, iterate `list(m)` and format; a member past 63 bits is refused. Refused by name: the functional API, mixed-in bases (`class C(str, Enum)`),
  `__init__`/`__new__` in an enum, class methods. `isinstance(m, int)` is False.
- `contextlib`: `contextmanager`, `suppress`, `closing`, `nullcontext` and user `with` classes on the general path (the default build falls back);
  `with a as x, b as y:`, `return` / `break` / `continue` / an exception inside, and an `__exit__` returning True suppressing. Not built: `ExitStack`.
- `collections.namedtuple("P", "x y", defaults=[..])`, `class P(NamedTuple)` (annotations, defaults, methods) and `class P(namedtuple(..))`: fields, indexing, unpacking,
  iteration, `==` with tuples, ordering, hashing, `repr` `P(x=1, y=2)`, `_asdict()`, `_replace(x=..)`, `P._make(xs)`, `P._fields`, `count`, `index`. Refused:
  `rename=`, `module=`, `__new__`, `_field_defaults`. Slices `p[1:]` and `isinstance(p, tuple)` are not built. `collections.ChainMap(*maps)`: lookups, `get`, `in`,
  `len`, iteration, `keys values items`, writes to the first map, `new_child`, `.parents`, `.maps`, `update`, `pop`, `setdefault`, `copy`. An `OrderedDict` kept in a class
  field or at module level (not built by the typed collections pass above) is a class with `move_to_end`, `popitem(last=)`, `pop`, `get`, `setdefault`, `update`, `copy`, `repr`.
- `random.Random(seed)`: its own MT19937 state, bit for bit with CPython 3.12 for an int seed: `random randint randrange choice shuffle sample uniform gauss
  getrandbits choices expovariate triangular seed`, with the same exceptions. Any number of generators, in fields or passed to functions. In a program that also calls
  `random.randint(..)` the module functions run on a hidden generator, seeded by `random.seed(<int>)`. Refused: no seed, a str/float/None seed, `SystemRandom`,
  `getstate`, `randbytes`, other distributions; `getrandbits(k)` beyond 62 bits is a RuntimeError.
- `keyword`: `iskeyword`, `issoftkeyword`, `kwlist`, `softkwlist`. `calendar`: `isleap leapdays weekday monthrange monthcalendar`, `month_name month_abbr day_name day_abbr`,
  `MONDAY`..`SUNDAY`, `month(y, m[, w, l])`, `prmonth(y, m)` (`weekday` and `monthrange` give `calendar.Day` members, which print as ints and as `calendar.TUESDAY` in a tuple;
  `monthrange(y, m)[1]` is a plain int and stays on the typed path). Refused: `calendar.calendar`, the Calendar classes, `setfirstweekday`.
- `abc`: `ABC`, `ABCMeta`, `abstractmethod` are dropped (an abstract class can be instantiated). `array.array(tc, it)` for `b B h H i I l L q Q d`: `append extend insert pop
  remove index count reverse tolist byteswap`, indexing, `len`, iteration, range-checked values, `repr`; refused: `f`, `u`, `tobytes`, `frombytes`, `tofile`.
- `io.StringIO(text)`: `write writelines getvalue read readline readlines seek tell truncate close`, iteration, `print(.., file=buf)`. `csv.reader(io.StringIO(text))` and
  `csv.DictReader(io.StringIO(text))` read the text; `csv.writer(buf)` / `csv.DictWriter(buf, ..)` write into a StringIO; `list(csv.DictReader(..))` gives
  `list[dict[str, str]]` (general path); `json.load(io.StringIO(text))` is `json.loads(text)`.
  `io.BytesIO` and the rest of `io` are refused by name.
- Also: user classes may define `__add__ __sub__ __mul__ __truediv__ __floordiv__ __mod__ __pow__` (and the `__r..__` forms), `__neg__ __pos__ __abs__ __bool__ __int__ __float__
  __round__ __floor__ __ceil__ __trunc__ __index__ __hash__ __eq__ __len__ __getitem__ __setitem__ __delitem__ __contains__`; instances hash and compare by identity unless the
  class says otherwise. `d1 | d2` on dicts, `type(x).__name__`, `x.__class__.__name__`, `Cls(*xs)` for a class with a fixed `__init__`.

### Tooling: projects, language server, debugging (last section of this file)

`ail` (packaging/ail_lang/cli.py) is the command; `python -m ail_lang` is the same. With `AIL_SDK_DIR=<AIL_CURRENT>` it runs from a source checkout.

- **Project.** `ail new NAME` creates `NAME/ail.toml`, `NAME/src/main.py` and `NAME/.gitignore`. `ail build`, `ail run` and `ail check` with no source
  file use the project found from the current directory upwards: `ail.toml` (top-level keys) or `[tool.ail]` in pyproject.toml, `ail.toml` first.
  Keys: `name` (default: the directory name), `entry` (required, .py or .ail), `link` (plain library names, passed as `--link LIB`, i.e. `-lLIB`),
  `strict` (default false), `module_path` (directories, passed as `-I`). Unknown keys, wrong types, a missing entry, and a bad name or link are refused
  by name. `ail build` writes `build/NAME` (`build/NAME-debug` with `--debug`), replacing the previous one; `-o` overrides. There is no package registry.
- **strict.** `strict = true` adds `--strict` to the build: a program the typed path refuses is not built on the slow general path; every blocker is listed with its `write instead:` (exit 3, ail.strict/1 with `--json`). The language server shows those as errors. `link` and `compile --link LIB` are `link("LIB")` of the source (cratebridge), one code path (`Session.extra_libs`).
- **Language server.** `ail lsp` (stdio, JSON-RPC 2.0, standard library only). Capabilities: open/close sync, `didSave`, hover. On didOpen and didSave it
  runs `ail check` (schema `ail.check/1`) on the file on disk (a file that does not exist yet is checked from the buffer text). Severity: a source that
  does not load or parse, or that the build refuses, is an Error; a typed-path blocker that the general path builds is a Warning `runs on the slow general
  path because <reason>`; `slow_patterns` are Information. The Warning/Error split costs one build of the program (needs a C compiler; remembered per source
  hash; without a compiler the Warning says it cannot tell). Messages keep the `write instead:` text; hover on a diagnostic shows it as **write instead:**.
  The blocker list is `compile --strict --json` (no C compiler needed); the Warning/Error split is the one build. A problem in an imported module is published on that module's file. Classification lives in `lsp.Diagnoser.classify`; when `ail check --strict`
  reports blockers and refusals itself, that is the only place to change.
- **Debugging.** `ail build --debug` (`compile --debug`, environment `AIL_DEBUG=1`) compiles with `-g -O0`, and writes `#line N "file"` before every C line of every
  statement (the combined-source line is mapped back through the loader's source map, so imported modules point at their own files). It uses the same code generator as
  a release build: the IR path (`AIL_IR` is no longer forced to 0), the legacy emitter for what the IR refuses, and the general path (pyboxed2) for a program built there.
  A debug build's C differs from the release C by `#line` and `AIL_DBG_SITE` lines alone, and a release build's C has none (`test_ail_debug_lines`). gdb, `addr2line`
  and `assert` name the user's `.py` line. The typed paths also record `file:line` of the statement being run: an uncaught exception or runtime trap prints its usual
  message, then `  raised near file:line`; a normal build's stderr is unchanged (DIFFERENCES A4). The line is the last statement that began to run, so for an
  exception raised after a call returns within one statement it can name the callee's last statement, and for one that a `finally` lets through, the last statement of
  the `finally` (C121). The general path has `#line` but no `raised near` (a note says so; C123); `--separate` and linked objects have no line mapping.
  A function the legacy emitter writes puts one `#line` per statement, so a debugger stepping inside a long one shows the next lines (C122). The build cache
  keeps debug and normal builds apart. `-O0` uses more stack per call than `-O2`, so very deep recursion fails sooner.
### Native libraries: C and Rust (`ail_ffi`, `link`, `ail_cbuf`)

```python
from ail_ffi import *
from ail_cbuf import get_i32, get_i64, put_i64      # copy ail_cbuf.py beside the program

link("m", "z")                                       # -lm -lz; the CPython shim loads the same libraries

@extern(header="math.h", symbol="frexp")
def c_frexp(x: c_double, e: ptr(c_int)) -> c_double: ...            # out-parameter: a bytearray(4)
@extern(header="zlib.h", symbol="compress")
def z_compress(dest: bytearray, dest_len: ptr(c_ulong), src: bytes, n: length("src", c_ulong)) -> c_int: ...
@extern(header="zlib.h", symbol="uncompress", check="nonzero", exc=ValueError)   # error code -> exception
def z_uncompress(dest: bytearray, dest_len: ptr(c_ulong), src: bytes, n: length("src", c_ulong)) -> c_int: ...
@extern(header="sqlite3.h", trust=True)              # the prototype names `sqlite3 **`: not compared
def sqlite3_open(path: c_char_p, db: ptr(c_void_p)) -> c_int: ...    # void ** out-parameter: read with get_i64

e = bytearray(4)
m = c_frexp(48.0, e)
print(m, get_i32(e, 0))                              # 0.75 6
```

- `link("name", ...)` once per file; `pkg_config="x"` for pkg-config flags; a path links that file. Stubs without `lib=` search the C
  library, then the linked libraries.
- Out-parameters and structs are byte buffers: `ptr(T)` (writable) / `cptr(T)` (read only) over a `bytearray` / `bytes`, element types are
  ints, `c_float`, `c_double`, `c_bool`, `c_void_p`; `c_mut_void_p` / `c_const_void_p` for a struct; fields are read and written at the C
  offsets with `get_i32 get_u32 get_i64 get_f64 put_i32 put_i64 put_f64 ...`.
- `trust=True` for a prototype that names a struct (`struct tm *`, `sqlite3 *`): the header is included, its prototype is not compared.
- Callbacks (AIL functions called from C) are not supported.
- Rust: export `#[no_mangle] pub extern "C"` functions from a `cdylib` / `staticlib` crate (`panic = "abort"`), generate a header with
  cbindgen, and `python3 AIL_CURRENT/ail_bindgen.py crate.h --lib ./libcrate.so --check fn=nonzero:ValueError` writes the stubs.
  Recipe: `docs/design/NATIVE_LIBRARIES.md`.


## Export

`@export` marks the top-level typed functions of a Python-syntax file as the C API of a library. The same
file runs on CPython (`from ail_ffi import export` is a checking no-op there) and builds with

    ail build --lib NAME prog.py [-o DIR]        # or: ail_chatgpt.py compile --lib NAME prog.py -o DIR

into `DIR/libNAME.so` (`.dylib` on macOS), `DIR/libNAME.a` and `DIR/NAME.h` (DIR must exist, default `.`; an
existing file is never overwritten; Linux and macOS). Only the `@export` functions are public; every other
function, class and literal constant of the file is private and may use any typed AIL. `@dataclass` classes
and the `ail_ffi` / `dataclasses` imports are consumed by the build; `if __name__ == "__main__":` blocks
are dropped.

| annotation | C parameter | C result (out-parameter) |
|---|---|---|
| `int` / `float` / `bool` | `int64_t` / `double` / `bool` | `int64_t *` / `double *` / `bool *` |
| `str` | `const char *` (UTF-8, NUL terminated) | `char **`, malloc'd, NUL terminated |
| `bytes` | `const uint8_t *p, size_t p_len` | `uint8_t **, size_t *`, malloc'd |
| `list[int]` / `list[float]` | `const int64_t *` / `const double *` + `size_t` count | `T **, size_t *`, malloc'd |
| dataclass of `int`/`float`/`bool` | `const NAME_Type *` (C struct, same field order) | not allowed |
| `None` | | none |

Every function returns `int`: 0 on success, otherwise `NAME_ERR_VALUE` 1, `_ZERO_DIVISION` 2, `_INDEX` 3,
`_KEY` 4, `_EOF` 5, `_OS` 6, `_RUNTIME` 7, `_INTERNAL` 8 (allocation failure, invalid result), `_ARGUMENT` 9
(NULL where a pointer is required, a NUL in a str result). Results are written only on success.
`const char *NAME_last_error(void)` returns `"ValueError: text"` for the calling thread's last call (empty after
a success; valid until that thread's next call). An exception that escapes an exported function never ends the
process. `NAME_free(void *)` releases every str, bytes and list result (once; NULL is fine; an empty bytes or
list result may be NULL). No init or teardown function exists because no state survives a call. Calls from any
number of threads are allowed: one internal mutex serializes them (no calls from signal handlers; link the
static library with `-lm -lpthread`). Differences from CPython: `int` is 64 bit, `str` results containing a
NUL are refused, and a dataclass cannot be returned. A file without `@export` and the existing
`compile-library` (view structs, `NAME_error`) are unchanged.
