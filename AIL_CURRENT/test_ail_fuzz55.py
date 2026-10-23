"""Differential fuzz round 55: generators with send / close and their finally blocks, against CPython 3.12.

Found with small programs compared on both builds:

1. `g.close()` on a suspended generator finished it without running its `try/finally` blocks: the
   general path's `ail2g_close` (safetyrt.py) marked the generator DONE and freed its stack. A close now
   resumes the generator with GeneratorExit at its suspension point, so `finally` (and `except`) run as
   in CPython. A generator that yields during that cleanup still gives CPython's RuntimeError
   "generator ignored GeneratorExit" and stays suspended after the yield; a completed close (GeneratorExit
   or StopIteration) returns None, another exception propagates, an unstarted generator is finished
   without running its body, and a finished one is a no-op.

The programs below keep the close shapes (empty / negative / nested / wrong-state / contained generator)
compared with CPython on both builds. `yield from` with a non-statement value and `except GeneratorExit`
are still refused by name by the compiler (the general path lowers a `yield from` statement to a loop, so
closing an outer generator does not close a delegated one -- left as a pre-existing difference).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

CLOSE_FINALLY = r"""def gen(n):
    print("start", n)
    try:
        for i in range(n):
            print("yield", i)
            yield i
    finally:
        print("finally", n)


def main():
    g = gen(5)
    print(next(g))
    print(next(g))
    print("closing")
    g.close()
    print("after close")
    try:
        next(g)
    except StopIteration:
        print("stopped")
    h = gen(0)
    print(list(h))
    k = gen(3)
    k.close()
    print("closed before start")
    try:
        next(k)
    except StopIteration:
        print("stopped unstarted")


main()
"""

CLOSE_STATES = r"""def g(tag):
    print("body", tag)
    try:
        yield 1
        yield 2
    finally:
        print("fin", tag)


def main():
    a = g("new")
    a.close()
    try:
        next(a)
    except StopIteration:
        print("unstarted stopped")
    b = g("done")
    print(next(b), next(b))
    b.close()
    b.close()
    print("done closed twice")
    c = g("suspended")
    print(next(c))
    c.close()
    c.close()
    print("suspended closed twice")
    d = g("negative")
    print(next(d))
    d.close()
    print("end")


main()
"""

CLOSE_IGNORED = r"""def g():
    try:
        yield 1
    finally:
        print("fin")
        yield 2
        print("after yield")


def main():
    a = g()
    print(next(a))
    for n in range(2):
        try:
            a.close()
        except RuntimeError as e:
            print("runtime", n, e)
    a.close()
    print("done")


main()
"""

CLOSE_EXCEPTION = r"""def bad():
    try:
        yield 1
    finally:
        print("fin bad")
        raise ValueError("cleanup failed")


def stop():
    try:
        yield 1
    finally:
        print("fin stop")
        raise StopIteration("explicit")


def main():
    a = bad()
    print(next(a))
    try:
        a.close()
    except ValueError as e:
        print("ValueError", e)
    b = stop()
    print(next(b))
    try:
        b.close()
    except RuntimeError as e:
        print("RuntimeError", e)


main()
"""

CLOSE_CONTAINERS = r"""class Box:
    def __init__(self):
        self.g = None


def make(tag):
    try:
        yield tag
    finally:
        print("fin", tag)


def close_it(obj):
    obj.close()


def main():
    gs = [make("list0"), make("list1")]
    print(next(gs[0]), next(gs[1]))
    close_it(gs[0])
    close_it(gs[1])
    d = {"g": make("dict")}
    print(next(d["g"]))
    close_it(d["g"])
    box = Box()
    box.g = make("attr")
    print(next(box.g))
    box.g.close()
    fn = make(-1)
    print(next(fn))
    close_it(fn)


main()
"""


class GeneratorClose(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ail-fuzz55-")
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
        ref = self.dir / "ref.py"
        ref.write_text(src, encoding="utf-8")
        want = subprocess.run([sys.executable, str(ref)], cwd=self.dir, capture_output=True, timeout=120)
        for general in (False, True):
            built, exe = self.build(src, general)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], cwd=self.dir, capture_output=True, timeout=120)
            self.assertEqual(got.stdout, want.stdout, "general" if general else "default")
            self.assertEqual(got.returncode, want.returncode, "general" if general else "default")

    def test_close_runs_finally(self):
        self.same(CLOSE_FINALLY)

    def test_close_in_every_state(self):
        self.same(CLOSE_STATES)

    def test_close_yield_runtime_error(self):
        self.same(CLOSE_IGNORED)

    def test_close_propagates_and_swallows(self):
        self.same(CLOSE_EXCEPTION)

    def test_close_through_containers(self):
        self.same(CLOSE_CONTAINERS)


if __name__ == "__main__":
    unittest.main()
