"""Round two of the corpus findings, each compared with CPython (AIL_IR=0 and 1), also under ASan/UBSan.

1. a user method named like a built-in one (`total`, `count`, `get`, `append`, ...) called on a receiver
   whose class is not known statically (`rows[1].total()`) ran the built-in (Counter.total: segfault);
   the receiver's class is now tested at run time.
2. a user __repr__ / __str__ is used inside lists, dicts, tuples, f-strings, %r and str().
3. dataclass field(repr=False) and dataclass inheritance (inherited fields, in order).
4. a subclass without its own __init__ uses the base class's.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

METHOD_NAMED_LIKE_BUILTIN_MIN = r"""class Row:
    def __init__(self, a: int, word: str) -> None:
        self.a = a
        self.word = word

    def total(self) -> int:
        return self.a + len(self.word)


def main() -> None:
    rows = [Row(i, "w") for i in range(4)]
    print(rows[1].total())


main()
"""

METHOD_DISPATCH = r"""class Row:
    def __init__(self, a: int, word: str) -> None:
        self.a = a
        self.word = word
        self.items = []

    def total(self) -> int:
        return self.a + len(self.word)

    def count(self, c: str) -> int:
        return self.word.count(c) + self.a

    def get(self, k: int, d: int = 7) -> int:
        return self.a * k + d

    def append(self, x: int) -> None:
        self.items.append(x)

    def pop(self) -> int:
        return self.items.pop()

    def update(self, n: int) -> None:
        self.a += n

    def index(self, w: str) -> int:
        return self.word.index(w)


class Fancy(Row):
    def total(self) -> int:
        return 1000 + self.a


def show(x) -> int:
    return x.total()


def main() -> None:
    rows = [Row(i, "w" * i) for i in range(4)]
    print(rows[1].total(), rows[2].count("w"), rows[3].get(2), rows[3].get(2, 1))
    rows[1].append(5)
    rows[1].append(6)
    print(rows[1].pop(), rows[1].items)
    rows[2].update(10)
    print(rows[2].a, rows[2].index("w"))
    d = {i: Row(i, "z" * i) for i in range(3)}
    print(d[2].total(), sum(r.total() for r in d.values()))
    s = {Row(1, "a").total(), Row(2, "b").total()}
    print(sorted(s))
    print(sum(r.total() for r in rows), max(r.total() for r in rows))
    print(sorted(r.count("w") for r in rows))
    fs = [Fancy(i, "q") for i in range(3)]
    print([f.total() for f in fs], show(fs[1]), show(rows[3]))
    mixed = [rows[0], fs[0]]
    print([m.total() for m in mixed])
    ls = [[1, 2], [3]]
    print(ls[0].count(1), ls[1].index(3))
    ls[0].append(9)
    print(ls, ls[0].pop(), {1: 2}.get(1, 5))
    dd = [{"a": 1}, {"b": 2}]
    print(dd[0].get("a"), dd[1].get("z", 0))


main()
"""

REPR_STR_HOOKS = r"""from dataclasses import dataclass


class A:
    def __init__(self, n: int) -> None:
        self.n = n

    def __str__(self) -> str:
        return "A#" + str(self.n)


class B:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return "B<" + str(self.n) + ">"


class C:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return "C-repr"

    def __str__(self) -> str:
        return "C-str"


class D(B):
    def __init__(self, n: int) -> None:
        self.n = n * 2


@dataclass
class E:
    x: int

    def __str__(self) -> str:
        return "E!" + str(self.x)


def main() -> None:
    xs = [A(1), B(2), C(3), D(4), E(5)]
    print(xs[1:])
    print(xs[0], xs[1], xs[2], xs[3], xs[4])
    print([str(x) for x in xs])
    print([repr(x) for x in xs[1:]])
    print([f"{x}" for x in xs])
    print([f"{x!r}" for x in xs[1:]])
    print([f"{x!s}" for x in xs])
    print(["%s" % x for x in xs])
    print(["%r" % x for x in xs[1:]])
    print({"k": xs[2], "j": xs[1]})
    print((xs[1], xs[2]))
    print({1: [B(7)]})
    print("-".join(str(x) for x in xs))
    print(str(xs[1:]), repr(xs[1:]))
    print(xs[3], [D(1)])


main()
"""

DATACLASS_INHERIT_HIDE = r"""from dataclasses import dataclass, field


@dataclass
class Base:
    a: int
    name: str = "n"


@dataclass
class Child(Base):
    b: float = 1.5
    tags: list = field(default_factory=list)


@dataclass
class Third(Child):
    c: bool = True
    name: str = "over"


@dataclass
class Hid:
    x: int
    secret: str = field(default="s", repr=False)
    y: int = 3
    z: int = field(default=4, repr=False)


@dataclass
class Plain:
    k: int


def main() -> None:
    print(Base(1))
    print(Base(2, "q"))
    c = Child(3, "z", 2.5)
    print(c, c.a, c.name, c.b)
    print(Child(4))
    c.tags.append("t")
    print(c)
    print(Third(5))
    print(Third(6, "m", 0.5, [1], False))
    print([Child(7), Base(8)])
    h = Hid(1, "top", 2, 9)
    print(h, h.secret, h.z)
    print(Hid(5))
    print([Hid(6)], repr(Hid(7, y=8)))
    print(Plain(1))
    print(Child(a=1, b=9.5))


main()
"""

SUBCLASS_NO_INIT = r"""class Count:
    def __init__(self, n: int) -> None:
        self.n = n
        self.i = 0

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.i >= self.n:
            raise StopIteration
        self.i += 1
        return self.i


class Sub(Count):
    pass


class Twice(Count):
    def double(self) -> int:
        return self.n * 2


for x in Sub(3):
    print(x)
t = Twice(2)
print(t.double(), list(t), Sub(1).n)
"""


CASES = [
    ('method_total_in_comprehension', METHOD_NAMED_LIKE_BUILTIN_MIN),
    ('method_dispatch_unknown_receiver', METHOD_DISPATCH),
    ('user_repr_str_in_containers', REPR_STR_HOOKS),
    ('dataclass_inheritance_repr_false', DATACLASS_INHERIT_HIDE),
    ('subclass_without_init', SUBCLASS_NO_INIT),
]


def build_and_run(directory, text, name, ir):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0')
    debug = Path(directory, name + '_dbg')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name, '--debug-dir', str(debug)], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected, debug
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected, debug


class CorpusFindings2(unittest.TestCase):
    def check(self, slug, text, ir, sanitize):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected, debug = build_and_run(directory, text, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)
            if sanitize and shutil.which('gcc') and (debug / 'program.c').exists():
                exe = Path(directory, 'asan')
                cc = subprocess.run(['gcc', '-O1', '-g', '-fsanitize=address,undefined', '-fno-sanitize-recover=undefined',
                                     '-o', str(exe), str(debug / 'program.c'), '-lm'], capture_output=True, text=True)
                if cc.returncode != 0:
                    self.skipTest('no sanitizer runtime')
                run = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'))
                self.assertEqual(run.returncode, 0, run.stderr.decode(errors='replace')[-2000:])
                self.assertEqual(run.stdout, expected.stdout)

    def test_cases_default(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, False, False)

    def test_cases_ir(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug, text, True, False)

    def test_cases_under_sanitizers(self):
        for slug, text in CASES:
            with self.subTest(slug):
                self.check(slug + '_san', text, False, True)


if __name__ == '__main__':
    unittest.main()
