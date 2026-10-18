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
  `input()` (`EOFError` at the end), `open(path).read()` (only this form).
- Output: `print(*values, sep=, end=, file=sys.stderr)` (ints, floats, strs, bools). stdout is
  buffered and still flushed by `sys.exit` or an uncaught exception: when a program must print
  nothing on error, collect the lines and print them at the end.
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
Only structs can be None (`int | None` is refused: use a sentinel such as -1). Test with `is None`,
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
- A flat list parameter is read-only (Structs). `print(xs)` is refused: `", ".join(xs)`.
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
  `d[str(r.id)]`). `dict[str, Struct]` and `dict[str, list[T]]` are refused: map the key to an
  index into a `list[Struct]` or a `list[list[T]]` (Word count).
- `d[k]` (`KeyError`), `get(k, default)` (one-argument `get(k)` is refused: there is no None for a
  value; use `d.get(k, -1)` or `if k in d`), `setdefault`, `pop(k[, default])`, `del d[k]`, `in`,
  `len`, `keys()`, `values()`, `items()`, `update`, `copy`, `clear`; `for k in d`,
  `for k, v in d.items()`, `sorted(d)`, `list(d)` / `list(d.keys())` (keys in insertion order),
  `list(d.values())`. No dict comprehensions. A dict parameter is read-only.

## Sets: `set[int]`, `set[str]`

`let s: set[int] = set();` (or `{1, 2}`, `set(xs)`): `add discard remove clear update copy`,
`x in s`, `len`, `for`, `sorted`, `list(s)`, `sum/min/max` (int), `| & - ^` and `|= &= -= ^=`
(also `union intersection difference symmetric_difference`, `*_update`), `== != <= < >= >`
(`issubset`, `issuperset`), `isdisjoint`. Insertion ordered; `s.pop()` removes the newest element
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
  `hex(int)`. Missing: `partition`, `title`, `capitalize`, `zfill`, `ljust`, `translate`,
  `removeprefix`. `+` never mixes str and a number: `"n=" + str(n)`.
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

## Regular expressions: re (Python syntax)

`import re` with the pattern spelled as a literal: a str or bytes literal, or a name bound once to one
(`WORD = r"[a-z]+"`), or `P = re.compile(literal[, flags])` bound once and used as `P.search(s)` and so
on. The pattern is parsed when the program is built and matched by a linear-time engine written in the
language itself (leftmost-first, CPython's priority), so groups and spans equal CPython's.

- Functions and methods: `match fullmatch search findall finditer split sub escape`; `flags=` or the
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
  a non-literal `repl` must have no backslash; a function is not built. Empty matches follow CPython 3.7+.
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
  (tuples, None), `subn`, `m.groups()` / `m.groupdict()` / `m.span()` as values, a pattern that is not a
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
- Refused by name (`note:` lines): `namedtuple` (use a `@dataclass`), `ChainMap` and the rest of the module,
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
  a seed that is a str / float / None, `random.Random(...)`, `choices`, `triangular`, `getrandbits`... are refused by
  name. Ranges wider than 64 bits are a RuntimeError. Only the module-level functions share state, as in CPython.
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
`x if c else y`, list comprehensions (also nested `for`). `parallel for` (Parallel).
No `for ... else`, `zip`, tuple unpacking except `for k, v in d.items()`, `enumerate(str)`, dict
comprehensions, `global`, `isinstance`.

## Exceptions

`ValueError`, `KeyError`, `IndexError`, `ZeroDivisionError`, `OverflowError`, `OSError`
(= `FileNotFoundError`), `EOFError`, `RuntimeError`, `AssertionError`, `UnicodeDecodeError`.
Name the kinds: `except (ValueError, KeyError) as e` (no bare `except`, no `except Exception`, no
user classes); `e.kind`, `e.message` are strs. `raise ValueError("m");`, `raise;`,
`assert c, "m";`. Uncaught: message on stderr, exit 1. A function whose body only raises still
needs a final `return`. Handler names: Local names.

## Refused: what to write instead

| Python | AIL |
|---|---|
| tuples beyond the Tuples section, `zip` over non-lists | a struct; index loops |
| a lambda that escapes, nested `def` | a top-level `fn` passed as `Callable[[A], R]` |
| global variables you change | a struct holding the state, passed to each function (a literal read-only table is fine) |
| `dict[str, Struct]`, `dict[str, list[T]]` | a `dict[str, int]` index into a `list[Struct]` (or a `list[list[T]]`) |
| `None` for int, str, list | a sentinel (-1, ""), or raise. A struct may be `Node \| None` |
| `xs[i] = v` or `xs.append(v)` on a list parameter | a struct field `s.xs`, or return a new list |
| one name holding an int, later a str | a second name |
| `str(b)` of bytes | `b.decode()` |
| `print(xs)`, `p1 == p2` on structs | print or compare fields; `", ".join(xs)` |
| `d.get(k)` (None when missing) | `d.get(k, -1)` with a sentinel, or `if k in d { ... d[k] ... }` |
| `int(s)` on text that may overflow | `parse_int64_decimal(s)` from `checked_integer` (`ValueError`) |
| `with open(p) as f`, `f.write` | `read_bytes`, `write_text`, `file_chunks` |
| `namedtuple`, big integers | a `@dataclass` class; limbs in a `list[int]` |

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
  per side, stop once the two tops add up to at least the best meeting found): on a route-search program
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
token first: 2.2 s, 1.1 GB. Whole programs written this way (three record- and log-processing
programs) were 23 to 58% shorter than byte-scanner versions; 2.8M log lines each split into
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
- `statistics` on `list[int]`: `mean median median_low median_high mode multimode variance pvariance stdev pstdev`; `fmean` also on floats. `StatisticsError` is `ValueError`. Mixed int/float results only where printed or used as floats.
- Small forms: `int.bit_length()`, `int.bit_count()`, `max/min(..., default=)`, `max(d, key=d.get)` (and over a generator), `x in (constants)`, `itertools.product(x, repeat=n)` with a runtime `n`, unpacking a `tuple | None` after a None test.
- Refused by name with a "write instead" hint: `decimal`, `fractions`, `textwrap`, `unicodedata`, `enum`, `string.Template`.
