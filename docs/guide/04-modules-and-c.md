# 4. Modules and C

The standard modules below build today. Each sample is built and run by the test; only modules
whose sample passes are kept here. `csv` and `shlex` build on the general path and print the note
described in [chapter 1](01-typed-and-general.md); the other samples build with `--strict`.

## math

`math` gives the usual C-backed functions:

<!-- sample: c4_math -->
```python
import math


def main() -> None:
    print(math.sqrt(81.0))
    print(math.gcd(48, 18))
    print(math.floor(3.9), math.ceil(3.1))


main()
```

```output
9.0
6
3 4
```

## re

`import re` uses a pattern written as a literal. Groups, `findall` and `search` follow CPython's
leftmost-first order:

<!-- sample: c4_re -->
```python
import re


def main() -> None:
    m = re.search(r"([a-z]+)@([a-z.]+)", "mail me@example.com now")
    if m:
        print(m.group(1), m.group(2))
    print(re.findall(r"[0-9]+", "a1 b22 c333"))


main()
```

```output
me example.com
['1', '22', '333']
```

## json

`json.loads` needs the type it produces, written down. Here it is `dict[str, int]`:

<!-- sample: c4_json -->
```python
import json


def main() -> None:
    data: dict[str, int] = json.loads('{"a": 1, "b": 2}')
    print(data["a"] + data["b"])
    print(json.dumps({"ok": True, "n": 3}, sort_keys=True))


main()
```

```output
3
{"n": 3, "ok": true}
```

## csv

`csv.reader` reads rows from an open file. This sample writes a small file first, then reads it
back:

<!-- sample: c4_csv general -->
```python
import csv


def main() -> None:
    with open("guide.csv", "w") as f:
        f.write("name,qty\napple,3\npear,5\n")
    n: int = 0
    with open("guide.csv") as f:
        for row in csv.reader(f):
            if n == 0:
                print(row[0], row[1])
            n += 1
    print(n)


main()
```

```output
name qty
3
```

## collections

`Counter`, `defaultdict` and `deque` are built from the `collections` module:

<!-- sample: c4_collections -->
```python
from collections import Counter, defaultdict, deque


def main() -> None:
    c = Counter("abracadabra")
    print(c["a"], c["z"])
    d: dict[str, int] = defaultdict(int)
    for w in ["a", "b", "a"]:
        d[w] += 1
    print(d["a"], d["b"])
    q = deque([1, 2, 3])
    q.append(4)
    print(q.popleft(), len(q))


main()
```

```output
5 0
2 1
1 3
```

## heapq

`heapq` keeps a list as a heap. `heappush` and `heappop` return the smallest item first:

<!-- sample: c4_heapq -->
```python
import heapq


def main() -> None:
    h: list[int] = [5, 1, 3]
    heapq.heapify(h)
    heapq.heappush(h, 2)
    print(heapq.heappop(h), heapq.heappop(h))


main()
```

```output
1 2
```

## bisect

`bisect` finds an insertion point in a sorted list, and `insort` inserts there:

<!-- sample: c4_bisect -->
```python
import bisect


def main() -> None:
    xs: list[int] = [1, 3, 5, 7]
    print(bisect.bisect_left(xs, 5), bisect.bisect_right(xs, 5))
    bisect.insort(xs, 4)
    print(xs)


main()
```

```output
2 3
[1, 3, 4, 5, 7]
```

## statistics

`statistics.fmean` and `statistics.median` are built for a list of floats:

<!-- sample: c4_statistics -->
```python
import statistics


def main() -> None:
    xs: list[float] = [1.0, 2.0, 3.0, 4.0]
    print(statistics.fmean(xs))
    print(statistics.median(xs))


main()
```

```output
2.5
2.5
```

## shlex

`shlex` ships as AIL source in `AIL_CURRENT/stdlib/shlex.py`. Its `split` and `join` parse and
rebuild a command line:

<!-- sample: c4_shlex general -->
```python
import shlex


def main() -> None:
    print(shlex.split("one 'two three' four"))
    print(shlex.join(["a b", "c"]))


main()
```

```output
['one', 'two three', 'four']
'a b' c
```

## Calling C with ail_ffi

`ail_ffi` declares a C function as a Python stub. Under CPython the stub runs through `ctypes`;
`ail build` compiles it to a direct C call. This sample calls libm's `cbrt`:

<!-- sample: c4_ffi -->
```python
from ail_ffi import *

link("m")


@extern(header="math.h", symbol="cbrt")
def c_cbrt(x: c_double) -> c_double: ...


print(c_cbrt(27.0))
```

```output
3.0000000000000004
```

The same file runs both ways: the test builds it and also runs it under CPython. More C examples
are in [`FFI.md`](../FFI.md).
