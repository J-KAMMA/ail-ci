"""fuzz11: silent differences in generators and closures, against CPython 3.12.

* A generator's return value is carried by the StopIteration that ends it: `e.value` and
  `e.args` are the returned value (or its first argument), `next(g)` keeps that exception
  instead of replacing it with an empty one, `next(g, default)` still returns the default,
  and an exhausted generator raises an empty StopIteration afterwards. A user object's own
  `.value` attribute is unchanged.
* `g.close()` throws GeneratorExit at the suspended `yield`, so `finally` blocks run and a
  generator that catches `Exception` around the yield does not swallow the close, as in
  CPython. Closing a fresh generator runs no body; closing an exhausted one is a no-op.
* A nested function's own `global` declaration names module storage even when the enclosing
  function has a local of the same name. Before, the nested name was lifted as a local of
  that function, so `global n; n += 1` read an unbound local (UnboundLocalError).

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print
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


GEN_VALUES = r"""def g_int():
    yield 1
    return -7

def g_big():
    yield 1
    return 4611686018427387904

def g_str():
    yield 1
    return "done"

def g_list():
    yield 1
    return [2, 3]

def g_none():
    yield 1

def g_dict():
    yield 1
    return {"a": 1}

class C:
    def __init__(self):
        self.value = 5

def main():
    for g in (g_int(), g_big(), g_str(), g_list(), g_none(), g_dict()):
        print(next(g))
        try:
            next(g)
        except StopIteration as e:
            print(e.value, e.args)
        try:
            next(g)
        except StopIteration as e:
            print("again", e.value, e.args)
    x = g_int()
    next(x)
    print(next(x, "default"))
    try:
        raise StopIteration(99)
    except StopIteration as e:
        print(e.value, e.args)
        e.value = 100
        print(e.value, e.args)
    print(C().value)

main()
"""

GEN_CLOSE = r"""def g(n):
    try:
        for i in range(n):
            print("before", i)
            yield i
            print("after", i)
    finally:
        print("fin", n)

def main():
    a = g(3)
    print(next(a))
    a.close()
    print("closed a")
    try:
        next(a)
    except StopIteration:
        print("a stopped")
    b = g(5)
    b.close()
    print("closed fresh b")
    c = g(1)
    print(list(c))
    c.close()
    print("closed done c")
    a.close()
    print("closed a twice")
    d = g(2)
    print(next(d))
    d.close()
    print("closed d")

main()
"""

GEN_CLOSE_CATCH = r"""def g():
    try:
        yield 1
    except Exception:
        print("caught Exception")
        yield 2
    finally:
        print("fin")

def main():
    x = g()
    print(next(x))
    x.close()
    print("closed")
    y = g()
    next(y)
    y.close()
    print("done")

main()
"""

NESTED_GLOBAL = r"""n = 10
items = [1]
d = {"k": 1}

def main():
    n = 5
    items = [2]

    def bump():
        global n
        n += 1
        return n

    def add():
        global items
        items.append(9)
        return len(items)

    def dset():
        global d
        d["k"] = d["k"] + 1
        return d["k"]

    print(n, items, d["k"])
    print(bump(), bump(), n)
    print(add(), items)
    print(dset(), d)

    def nested():
        def inner():
            global n
            n = n * 2
            return n
        return inner

    f = nested()
    print(f(), f(), n)

main()
print(n, items, d["k"])
"""

NESTED_GLOBAL_REC = r"""total = 0

def main():
    total = 100

    def add(k):
        global total
        if k == 0:
            return total
        total += k
        return add(k - 1)

    print(add(4), total)

    def read():
        return total

    print(read())

main()
print(total)
"""

GEN_SEND = r"""def echo():
    total = 0
    while True:
        x = yield total
        if x is None:
            return total
        total += x

def main():
    g = echo()
    print(next(g), g.send(5), g.send(7))
    try:
        g.send(None)
    except StopIteration as e:
        print("ret", e.value, e.args)
    print(list(echo()))

main()
"""


def run_py(path):
    return subprocess.run([sys.executable, "-B", str(path)], capture_output=True, timeout=60)


class Fuzz11(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz11-")
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
        want = run_py(path)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(got.stdout, want.stdout, "general" if general else "default")
            self.assertEqual(got.returncode, want.returncode)

    def test_generator_return_value_and_StopIteration(self):
        self.same(GEN_VALUES)

    def test_close_runs_finally(self):
        self.same(GEN_CLOSE)

    def test_close_is_not_caught_by_except_Exception(self):
        self.same(GEN_CLOSE_CATCH)

    def test_nested_function_global_is_module_storage(self):
        self.same(NESTED_GLOBAL)

    def test_nested_function_global_recursion(self):
        self.same(NESTED_GLOBAL_REC)

    def test_send_and_return_value(self):
        self.same(GEN_SEND)


if __name__ == "__main__":
    unittest.main()
