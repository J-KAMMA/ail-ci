# AIL reference (core)

AIL compiles typed Python 3.12 to C. It prints what CPython would, or the compiler refuses a construct
with `file:line:col` and what to write instead. This card is enough for most
programs: compile, and open MORE only for a refusal or a missing feature.
In AIL_CURRENT/: `python3 ail_chatgpt.py compile p.ail -o p` (`check p.ail`: types only).

```python
# exit: 1
import sys
from dataclasses import dataclass

@dataclass
class Acc:
    total: int
    keys: list[str]

def parse(acc: Acc, line: str) -> None:
    f = line.split("|")
    if len(f) != 2 or not f[0].isupper():
        raise ValueError("bad")
    acc.keys.append(f[0])
    acc.total += int(f[1])

def main() -> int:
    acc = Acc(0, [])
    for line in sys.stdin:
        parse(acc, line)
    parse(acc, "B|5")
    w = [3, 9, 3]
    idx = list(range(3))
    idx.sort(key=lambda i: (-w[i], i))
    seen: dict[int, int] = {}
    for i in idx:
        seen[w[i]] = seen.get(w[i], 0) + 1
        print(f"{i:<2}{w[i]:>3}")
    q, r = divmod(acc.total, 2)
    print(",".join(acc.keys), q, r, len(seen), b"xy"[1:].decode())
    try:
        parse(acc, "b|1")
    except ValueError:
        print("error: bad record", file=sys.stderr)
        return 1
    return 0

sys.exit(main())
```

- Annotate parameters, results and empty containers (`xs: list[int] = []`). A name keeps one
  type in its function: give a new type a new name.
- Top level: imports, constants, read-only tables (`N = 10`, `STOP = {"a"}`),
  `@dataclass` classes (methods; inheritance on the general path), functions, `sys.exit(main())`.
  No other globals you change (an int/float `global` works), nested `def`, own exception classes (MORE).
- `int` is 64-bit (`OverflowError`, no big ints). Types: int, float, str, bool, bytes, `list`,
  `dict`, `set`, `tuple[int, str]` (`return a, b`; `a, b = f()`), dataclasses. `None` for a class
  or int/float/str (`int | None`; `Optional["Node"]`); else a sentinel (-1, "").
- List/dict/set params are read-only (typed): change a dataclass field
  (`acc.keys.append`) or return one.
- `print` takes numbers, str, bool, tuples, lists, `*xs` (dict: general path):
  `" ".join([str(x) for x in xs])`.
- Exceptions: kinds by name (`except (ValueError, KeyError) as e:`, no bare `except`);
  `print(e)`, `str(e)`, `e.args` read like CPython's.
- Bind before use: `words = s.split()`, `x = heapq.heappop(h)` (not inside another call). Sort
  with `xs.sort(key=...)`; `min`/`max` take `key=`.
- Text: `for line in sys.stdin` (keeps `\n`), `input()`, `sys.stdin.read()`, `int(s)`
  (`ValueError`). Bytes: `sys.stdin.buffer.read()`, `data[i]` is an int, `data[a:b]` an O(1)
  view, `.decode()`, `sys.stdout.buffer.write(bytearray)`.
- Modules: `sys re math heapq bisect json csv`, `collections` (Counter, defaultdict, deque),
  `itertools`, `functools`, `random` (after `random.seed(n)`).
- Speed: fix `slow:` hints (`x in list`, `.pop(0)`: set, deque).

MORE (`sed -n A,Bp AIL_REFERENCE_MORE.md`): Commands 8-48, Text I/O 50-88, Bytes 90-153, Syntax 155-169, Local names 171-196, Numbers 198-212, Structs 214-249, Trees 251-294, Lists 296-309, Sort keys 311-318, Nested lists 320-337, Dicts 339-348, Sets 350-368, Strings 370-396, Regex 398-455, Collections 457-537, Tuples, lambdas (Python syntax) 539-598, Libraries 600-703, Heaps 705-720, Loops 722-730, Exceptions 732-747, Refused 749-790, Word count 792-824, Dijkstra 826-868, BFS 870-914, Modules 916-944, Speed 946-965, Parallel 967-1130, Export 1133-1165.
