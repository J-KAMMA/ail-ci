"""fuzz19: control-flow silent differences found by small random programs compared with CPython 3.12.

1. Rich ordering of class instances on the general path (DIFFERENCES C?-job-fuzz19-10220951-1).
   The runtime only knew __lt__ and __gt__; `<=`, `>`, `>=` fell through to a `<`-based compare
   (`a > b` called `a.__lt__(b)` and `b.__lt__(a)`), so a class defining __le__/__gt__/__ge__ printed
   the wrong answers on any build that took the general path.  It also printed the reflected `<`
   calls instead of the methods.  Rich comparisons now call the left operator, then the right
   operand's reflected operator (== != already did); a chain gets the same per-link dispatch.
   The values reach the code as locals, tuple assignments, function arguments, list items,
   attributes and dict values.

2. any()/all() over a generator expression were not lazy on the general path (DIFFERENCES
   C?-job-fuzz19-10220951-2): the fused generator loop evaluated every element before looking at
   the answer.  A later element's side effect (and a walrus binding it reads) was visible, and an
   exception after the decisive element was raised where CPython never reaches it.  The loop now
   stops at the first decisive element, at every nesting level.

Each program is built twice (default build and AIL_UNIFIED_FORCE=1 general path) and must print
what CPython prints with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")


def run_py(path):
    r = subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)
    return r.returncode, r.stdout


RICH = r'''class V:
    def __init__(self, n):
        self.n = n
    def __lt__(self, o):
        print("lt", self.n, o.n)
        return self.n < o.n
    def __le__(self, o):
        print("le", self.n, o.n)
        return self.n <= o.n
    def __gt__(self, o):
        print("gt", self.n, o.n)
        return self.n > o.n
    def __ge__(self, o):
        print("ge", self.n, o.n)
        return self.n >= o.n
    def __eq__(self, o):
        print("eq", self.n, o.n)
        return self.n == o.n
    def __ne__(self, o):
        print("ne", self.n, o.n)
        return self.n != o.n


class H:
    def __init__(self, v):
        self.v = v


def direct(a, b):
    return (a < b, a <= b, a > b, a >= b, a == b, a != b)


def chain(a, b, c):
    return (a < b <= c, a <= b < c, a < b >= c, a >= b > c, a != b != c, a == b != c)


def main():
    a, b, c = V(1), V(2), V(3)
    print(direct(a, b))
    print(chain(a, b, c))
    xs = [V(1), V(2), V(3)]
    h = H(V(2))
    d = {"k": V(3)}
    print(direct(xs[0], xs[1]))
    print(direct(h.v, d["k"]))
    print(chain(xs[0], h.v, d["k"]))
    print(chain(xs[2], xs[1], xs[0]))
    print(direct(a, c), direct(c, a))


class L:
    def __init__(self, n):
        self.n = n
    def __lt__(self, o):
        print("L.lt", self.n, o.n)
        return self.n < o.n


class G:
    def __init__(self, n):
        self.n = n
    def __gt__(self, o):
        print("G.gt", self.n, o.n)
        return self.n > o.n


def main2():
    a, b = L(1), L(2)
    print(a < b, b > a, a > b, b < a)
    x, y = G(3), G(1)
    print(x < y, y > x, x > y, y < x)
    try:
        print(a <= b)
    except TypeError:
        print("TypeError le")
    try:
        print(x >= y)
    except TypeError:
        print("TypeError ge")
main()
main2()
'''

LAZY = r'''def gen(n, log):
    for x in range(n):
        log.append(("gen", x))
        yield x


def boom(n, log):
    for x in range(n):
        log.append(("boom", x))
        if x == 5:
            raise ValueError("late")
        yield x


def main():
    log = []
    print(any(x > 3 for x in gen(7, log)), log)
    log.clear()
    print(all(x < 3 for x in gen(7, log)), log)
    log.clear()
    print(any(x > 9 for x in gen(4, log)), log)
    log.clear()
    print(all(x < 9 for x in gen(4, log)), log)
    log.clear()
    print(any(x > 3 for x in boom(7, log)), log)
    log.clear()
    print(all(x > 3 for x in boom(7, log)), log)
    log.clear()
    print(any(x for x in []), log)
    print(all(x for x in []), log)
    xs = [1, 2, 3, 4, 5]
    print(any((y := x) > 3 for x in xs), y)
    print(all((z := x) < 3 for x in xs), z)
    print(any((w := x) > 9 for x in xs), w)
    out = []
    print(any((out.append((a, b)) or a + b == 2) for a in range(3) for b in range(3)), out)
    out = []
    print(all((out.append((a, b)) or a + b < 3) for a in range(3) for b in range(3)), out)
main()
'''

EVENTS = r'''def main():
    for n in [0, 1, 2, 3]:
        for i in range(n):
            if i == 1:
                break
        else:
            print("for else", n)
    i = 0
    while i < 3:
        i += 1
        if i == 2:
            continue
        if i == 3:
            break
    else:
        print("while else")
    print("after", i)
main()
'''


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz19-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, src, general):
        path = self.dir / "p.py"
        path.write_text(src, encoding="utf-8")
        env = dict(os.environ, AIL_NO_CACHE="1", AIL_QUIET_FALLBACK="1")
        env.pop("AIL_UNIFIED_FORCE", None)
        if general:
            env["AIL_UNIFIED_FORCE"] = "1"
        exe = self.dir / ("exe_g" if general else "exe_d")
        built = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "--syntax", "python",
                                "-o", str(exe)], cwd=self.dir, capture_output=True, text=True, env=env)
        return built, exe

    def same(self, src):
        path = self.dir / "ref.py"
        path.write_text(src, encoding="utf-8")
        code, out = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=120)
            self.assertEqual(ran.stdout.decode("utf-8", "replace"), out.decode("utf-8", "replace"),
                             "general" if general else "default")
            self.assertEqual(ran.returncode, code, "general" if general else "default")
        return out


class ControlFlow(Base):
    def test_rich_comparisons(self):
        out = self.same(RICH)
        self.assertIn(b"gt 2 3", out)
        self.assertIn(b"le 1 2", out)
        self.assertIn(b"ge 3 2", out)

    def test_any_all_are_lazy(self):
        out = self.same(LAZY)
        self.assertIn(b'True [(\'gen\', 0), (\'gen\', 1), (\'gen\', 2), (\'gen\', 3), (\'gen\', 4)]', out)
        self.assertIn(b"True 4", out)
        self.assertIn(b"False 3", out)
        self.assertNotIn(b"late", out)

    def test_loop_else_still_matches(self):
        self.same(EVENTS)


if __name__ == "__main__":
    unittest.main()
