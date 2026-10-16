"""The Python syntax (`--syntax python`) spells built-ins the way Python does, on the typed path.

Each program below is ordinary Python: CPython runs it as the oracle, and the compiled program
(built with AIL_NO_GENERAL=1, so the fast typed path must take it) prints the same bytes.

* Return annotations are result contracts, as `-> T` is in the block syntax: `-> str`,
  `-> list[str]`, `-> list[float]`, `-> dict[str, int]`, `-> bool`, `-> Node`,
  `-> Optional[Node]`, typing's `List`/`Dict`, a string forward reference; `-> None` (and a method
  that returns nothing, annotated or not) is void, `return None` in it a bare return. A body that
  disagrees with its annotation is refused by naming the annotation.
* `import heapq` / `from heapq import ...` / `import bisect` are the built-in heappush, bisect_left,
  ...; `import math` gives math.sqrt (ValueError below zero, -0.0 kept), floor, ceil, isqrt, gcd,
  fabs, pi, e, tau, inf, nan; `from typing ...`, `import typing`, `from __future__ import
  annotations` are accepted and ignored; `@dataclass` expands to the `__init__` it generates
  (defaults and `field(default_factory=...)` are filled in at each constructor call).
* I/O: `sys.stdin.buffer.read()`, `sys.stdout.write(s)` (also through `write = sys.stdout.write`),
  `sys.stdout.buffer.write(b)`, `flush()`, `with open(p) as f` read whole or line by line, `f =
  open(p, "rb")` / `f.read()` / `f.close()`, `open(p, "rb").read()`, a missing file's OSError.
* `self.items: list[str] = []` in `__init__` types the empty field; `sorted(range(n), key=...)` and
  `key=xs.__getitem__` sort; module constants may be constant arithmetic (`(1 << 40) - 1`, also
  `const` in the block syntax).
* A refusal in the Python syntax quotes Python (no `let ...;`), and a construct the front end left
  as written (heapq.nsmallest, math.log) is named, with its line, in a note.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RESULTS = '''from __future__ import annotations
from typing import List, Dict, Optional
import typing


class Node:
    def __init__(self, key: int, label: str):
        self.key = key
        self.label = label
        self.hits = 0

    def bump(self) -> None:
        self.hits += 1

    def touch(self, n: int):
        self.hits += n

    def reset(self) -> None:
        if self.hits > 100:
            return None
        self.hits = 0

    def name(self) -> str:
        return self.label + "#" + str(self.key)


def label(i: int) -> str:
    if i == 0:
        return "zero"
    return "n" + str(i)


def words(n: int) -> List[str]:
    out = []
    for i in range(n):
        out.append(label(i))
    return out


def squares(n: int) -> list[int]:
    return [i * i for i in range(n)]


def halves(n: int) -> typing.List[float]:
    return [i / 2 for i in range(n)]


def counts(ws: list[str]) -> Dict[str, int]:
    d: dict[str, int] = {}
    for w in ws:
        d[w] = d.get(w, 0) + len(w)
    return d


def small(x: int) -> bool:
    return x < 3


def mean(xs: list[int]) -> float:
    return sum(xs) / len(xs)


def make(k: int) -> Node:
    return Node(k, "k")


def find(nodes: list[Node], k: int) -> Optional[Node]:
    for n in nodes:
        if n.key == k:
            return n
    return None


def later(k: int) -> "Node":
    return Node(k, "later")


def show(n: Node) -> None:
    print(n.name(), n.hits)


def main() -> int:
    ws = words(4)
    print(" ".join(ws), squares(5)[4], halves(3)[1])
    c = counts(ws)
    print(c["zero"], c["n3"], small(2), small(5), mean([1, 2, 4]))
    nodes = [make(1), make(2), later(3)]
    nodes[0].bump()
    nodes[0].touch(4)
    show(nodes[0])
    nodes[0].reset()
    show(nodes[0])
    f = find(nodes, 3)
    if f is not None:
        show(f)
    if find(nodes, 9) is None:
        print("none")
    return 0


if __name__ == "__main__":
    main()
'''

IMPORTS = '''import sys
import heapq
import bisect
import math
from math import sqrt, inf
from heapq import heappush as push
from bisect import insort

MASK = (1 << 40) - 1
MOD = 10 ** 9 + 7
HALF = MOD // 2
NAME = "ab" * 3


def main():
    h = []
    for x in [5, 1, 4, 2]:
        heapq.heappush(h, x)
    push(h, 3)
    heapq.heapify(h)
    a = heapq.heappop(h)
    b = heapq.heappushpop(h, 0)
    print(a, b, len(h))
    xs = [1, 3, 5]
    print(bisect.bisect_left(xs, 3), bisect.bisect_right(xs, 3), bisect.bisect(xs, 4))
    bisect.insort(xs, 4)
    insort(xs, 0)
    print(xs[0], xs[3], len(xs))
    print(math.sqrt(2), sqrt(16), math.sqrt(-0.0), math.floor(-2.5), math.ceil(-2.5), math.floor(7), math.ceil(2.1))
    print(math.isqrt(10 ** 18 - 1), math.isqrt(99), math.isqrt(0), math.gcd(12, -18), math.gcd(0, 0), math.fabs(-3))
    print(math.pi, math.e, math.tau, inf > 1e300, -math.inf < 0)
    print(MASK, MOD, HALF, NAME)
    order = sorted(range(4), key=lambda i: -xs[i])
    keys = [3, 1, 2]
    by = sorted(range(3), key=keys.__getitem__)
    print(order[0], order[3], by[0], by[2])
    try:
        print(math.sqrt(-1))
    except ValueError:
        print("domain")
    return 0


sys.exit(main())
'''

DATACLASS = '''from dataclasses import dataclass, field
import dataclasses


@dataclass
class Item:
    name: str
    price: int
    qty: int = 1
    tags: list[str] = field(default_factory=list)

    def total(self) -> int:
        return self.price * self.qty


@dataclasses.dataclass(frozen=True)
class Pt:
    x: float
    y: float


class Bag:
    def __init__(self, cap: int):
        self.cap = cap
        self.items: list[int] = []
        self.names: list[str] = []
        self.index: dict[str, int] = {}
        self.total: int = 0

    def add(self, name: str, v: int):
        self.index[name] = len(self.items)
        self.items.append(v)
        self.names.append(name)
        self.total += v


def main():
    a = Item("pen", 3)
    b = Item("ink", 5, 4)
    c = Item(name="pad", price=2, qty=7)
    a.tags.append("blue")
    items = [a, b, c]
    t = 0
    for i in items:
        t += i.total()
    print(t, a.tags[0], len(b.tags), c.qty)
    p = Pt(1.5, y=2.0)
    print(p.x + p.y)
    g = Bag(10)
    g.add("a", 3)
    g.add("b", 4)
    print(g.total, len(g.items), g.names[1], g.index["b"])


main()
'''

IO = '''import sys

write = sys.stdout.write


def load(path: str) -> str:
    with open(path) as f:
        text = f.read()
    return text


def count_lines(path: str) -> int:
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def raw(path: str) -> bytes:
    f = open(path, "rb")
    data = f.read()
    f.close()
    return data


def main() -> int:
    data = sys.stdin.buffer.read()
    words = data.split()
    sys.stdout.write("words %d\\n" % len(words))
    text = load(sys.argv[1])
    print(len(text), count_lines(sys.argv[1]))
    b = raw(sys.argv[1])
    print(len(b), len(open(sys.argv[1], "rb").read()))
    write("alias ok\\n")
    try:
        with open(sys.argv[2], "rb") as g:
            missing = g.read()
        print(len(missing))
    except OSError:
        print("missing file")
    sys.stdout.flush()
    out = bytearray()
    for i in range(min(3, len(words))):
        out.extend(words[i])
        out.append(10)
    sys.stdout.buffer.write(bytes(out))
    sys.stdout.buffer.flush()
    print("end")
    return 0


sys.exit(main())
'''

BRACE_CONSTANTS = '''const M = (1 << 40) - 1;
const K = M * 2 + 1;
fn main() {
    let xs = [5, 1, 3, 1];
    let o = sorted(range(4), key=lambda i: xs[i]);
    print(M, K, o[0], o[3]);
}
'''

# (source, text the refusal must contain, text it must not contain)
REFUSED = [
    ('def f(x: int) -> str:\n    return x + 1\n\n\ndef main():\n    print(f(2))\n\n\nmain()\n',
     'return annotation str disagrees', None),
    ('def main():\n    xs = ["1", "2", "3"]\n    t = 0\n    for x in map(int, xs[0:3:2]):\n        t += x\n'
     '    print(t)\n\n\nmain()\n', 'prog.ail:4:5:', 'let '),
    ('def main():\n    xs = ["1", "2", "3"]\n    t = 0\n    for x in map(int, xs[0:3:2]):\n        t += x\n'
     '    print(t)\n\n\nmain()\n', '(`for x in part: ...`)', '{'),
    ('import heapq\nimport math\n\n\ndef main():\n    h = [3, 1, 2]\n    heapq.heapify(h)\n'
     '    print(heapq.nsmallest(2, h)[0], math.log(2.0))\n\n\nmain()\n',
     'prog.ail:1:1: not in the subset: import of \'heapq\' with a function that is not built in', None),
    ('import heapq\nimport math\n\n\ndef main():\n    h = [3, 1, 2]\n    heapq.heapify(h)\n'
     '    print(heapq.nsmallest(2, h)[0], math.log(2.0))\n\n\nmain()\n',
     'note: prog.ail:8: math.log() with these arguments is not built', None),
]


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, source, exe


class PythonSyntaxTests(unittest.TestCase):
    def same_as_cpython(self, text, name, args=(), stdin=b""):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_python(directory, text, name)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            argv = [str(source) if arg == "SELF" else arg for arg in args]
            ran = subprocess.run([str(exe), *argv], input=stdin, capture_output=True, timeout=60)
            expected = subprocess.run([sys.executable, str(source), *argv], input=stdin,
                                      capture_output=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (0, expected.stdout), ran.stderr)

    def test_return_annotations_are_contracts(self):
        self.same_as_cpython(RESULTS, "results")

    def test_imports_map_to_builtins(self):
        self.same_as_cpython(IMPORTS, "imports")

    def test_dataclass_and_annotated_fields(self):
        self.same_as_cpython(DATACLASS, "fields")

    def test_io_spellings(self):
        self.same_as_cpython(IO, "io", ("SELF", "/nonexistent/ail-missing"), b"alpha beta\ngamma  delta\n\nzeta\n")

    def test_block_syntax_constant_arithmetic_and_range_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, "consts.ail"), Path(directory, "consts")
            source.write_text(BRACE_CONSTANTS, encoding="utf-8")
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "-o", str(exe)], capture_output=True, text=True, timeout=600,
                                   env=dict(os.environ, AIL_NO_GENERAL="1"))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.stdout, "1099511627775 2199023255551 1 0\n")

    def test_refusals_speak_python(self):
        for text, wanted, unwanted in REFUSED:
            with self.subTest(wanted=wanted), tempfile.TemporaryDirectory() as directory:
                built, _, exe = compile_python(directory, text, "prog")
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stderr)
                if unwanted is not None:
                    self.assertNotIn(unwanted, built.stderr)
                self.assertFalse(exe.exists())

    def test_main_calls_run_once_like_cpython(self):
        body = "import sys\n\ndef main() -> int:\n    t = 0\n    for line in sys.stdin:\n        t += int(line)\n    print(t)\n    return 0\n\n"
        for name, tail in (("plain", "main()\n"),
                           ("guard", 'if __name__ == "__main__":\n    main()\n'),
                           ("exit", "sys.exit(main())\n")):
            with self.subTest(name):
                self.same_as_cpython(body + tail, "main_" + name, (), b"1\n2\n3\n")

    def test_main_never_called_is_refused_not_run(self):
        text = "def main() -> int:\n    print(7)\n    return 0\n"
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "uncalled")
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("main() is defined but never called", built.stdout + built.stderr)
            self.assertFalse(exe.exists())
        # CPython prints nothing for it, which is what the refusal says
        self.assertEqual(subprocess.run([sys.executable, "-c", text], capture_output=True, text=True).stdout, "")

    def test_block_syntax_main_is_still_called_for_you(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, "auto.ail"), Path(directory, "auto")
            source.write_text("fn main() -> int { print(7); return 0; }\n", encoding="utf-8")
            built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "-o", str(exe)], capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual(subprocess.run([str(exe)], capture_output=True, text=True).stdout, "7\n")

    def test_wording_respells_block_snippets(self):
        sys.path.insert(0, str(ROOT))
        from ail_syntax import python_wording
        self.assertEqual(python_wording('keep a counter: `let i = 0; for c in s { ...; i += 1; }`'),
                         'keep a counter: `i = 0; for c in s: ...; i += 1`')
        self.assertEqual(python_wording('`struct G { items: list[str]; }` `let idx: dict[str, int] = {};`'),
                         '`@dataclass class G: items: list[str]` `idx: dict[str, int] = {}`')
        self.assertEqual(python_wording('a list of structs, with a let'), 'a list of class instances, with an assignment')


if __name__ == "__main__":
    unittest.main()
