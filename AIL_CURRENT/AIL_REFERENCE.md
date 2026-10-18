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
- Top level: imports, constants, read-only tables (`N = 10`, `STOP = {"a"}`, `T = {"k": 1}`),
  `@dataclass` classes (methods, no inheritance), functions, `sys.exit(main())`. No globals you
  change, nested `def`, own exception classes (MORE).
- `int` is 64-bit (`OverflowError`, no big ints). Types: int, float, str, bool, bytes, `list`,
  `dict`, `set`, `tuple[int, str]` (`return a, b`; `a, b = f()`), dataclasses. `None` only for a
  class (`nxt: Optional["Node"]`); else a sentinel (-1, "").
- A list, dict or set parameter is read-only: change a dataclass field (`acc.keys.append`) or
  return a new one.
- `print` takes numbers, str, bool, tuples, never a list, dict or `*xs`: `" ".join([str(x) for x
  in xs])`. A dict literal only as `d: dict[str, int] = {...}`.
- Exceptions: kinds by name (`except (ValueError, KeyError) as e:`, no bare `except`);
  `print(e)`, `str(e)`, `e.args` read like CPython's.
- Bind before use: `words = s.split()`, `x = heapq.heappop(h)` (not inside another call). Sort
  with `xs.sort(key=lambda ...)`; `min`/`max` take no `key=`.
- Text: `for line in sys.stdin` (keeps `\n`), `input()`, `sys.stdin.read()`, `int(s)`
  (`ValueError`). Bytes: `sys.stdin.buffer.read()`, `data[i]` is an int, `data[a:b]` an O(1)
  view, `.decode()`, `sys.stdout.buffer.write(bytearray)`.
- Modules: `sys re math heapq bisect json`, `collections` (Counter, defaultdict, deque),
  `itertools`, `functools`, `random` (after `random.seed(n)`).
- Speed: fix `slow:` hints (`x in list`, `.pop(0)`: set, deque).

MORE (`sed -n A,Bp AIL_REFERENCE_MORE.md`): Commands 8-20, Text I/O 22-56, Bytes 58-121, Syntax 123-134, Local names 136-161, Numbers 163-177, Structs 179-212, Trees 214-256, Lists 258-270, Sort keys 272-279, Nested lists 281-298, Dicts 300-309, Sets 311-329, Strings 331-356, Regular expressions 358-414, Collections 416-496, Tuples, lambdas (Python syntax) 498-557, Libraries 559-662, Heaps 664-679, Loops 681-688, Exceptions 690-705, Refused 707-748, Word count 750-782, Dijkstra 784-826, BFS 828-872, Modules 874-902, Speed 904-923, Parallel 925-1008.
