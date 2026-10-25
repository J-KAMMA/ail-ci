"""pre187: boxed `//` and `%` name both operand types on a type error.

The fuzz45 review recorded that the general path's unsupported-operand TypeError
for the divmod family omitted the operand types: `1 // "a"` printed
`unsupported operand type(s) for //`, where CPython prints
`unsupported operand type(s) for //: 'int' and 'str'` (and likewise for `%`).
The boxed and unified operators now fill the message from the operand types,
including a user class name; `divmod()` itself already matched CPython.

The programs cover both operators with int, float, str, bytes, None, list, dict,
set, tuple and bool operands, a user class with and without the dunders, and
values reaching the operator through an argument, a list item, an attribute, a
dict value and an alias.  Exception operands name their exception class and
iterator operands their concrete CPython iterator type (a deque iterator keeps
its `collections.` prefix), on either side of the operator.  Zero-error wording
and valid/dunder operations are kept as neighbours.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TYPE_MESSAGES = r'''class A:
    def __init__(self, x: int) -> None:
        self.x = x


class B:
    def __init__(self) -> None:
        self.x = 0

    def __floordiv__(self, o):
        return ("B//", self.x, o)

    def __mod__(self, o):
        return ("B%", self.x, o)


class C:
    def __init__(self) -> None:
        self.x = 0

    def __rfloordiv__(self, o):
        return ("C//", o, self.x)

    def __rmod__(self, o):
        return ("C%", o, self.x)


class Box:
    def __init__(self, v: str) -> None:
        self.v = v


def op(tag, a, b, kind):
    try:
        if kind == "//":
            print(tag, repr(a // b))
        else:
            print(tag, repr(a % b))
    except Exception as e:
        print(tag, type(e).__name__, str(e))


def route(a, b):
    op("arg", a, b, "//")
    op("arg", a, b, "%")


def main():
    vals = [(1, "a"), ("a", 1), (1.0, "a"), ("a", 1.0),
            (None, 1), (1, None), ([], 1), (1, []), ({}, 1), (1, {}),
            ({1}, 2), (2, {1}), ((1,), 2), (2, (1,)), (True, "a"), ("a", False),
            (0, "a"), ("a", 0)]
    for a, b in vals:
        op("lit", a, b, "//")
        op("lit", a, b, "%")
    op("bytes", b"a", 1, "//")
    op("bytes", 1, b"a", "//")
    a = A(1)
    for b in (2, "a", None):
        op("inst", a, b, "//")
        op("inst", a, b, "%")
        op("inst", b, a, "//")
        op("inst", b, a, "%")
    b = B()
    c = C()
    print(b // 2, b % 2)
    print(2 // c, 2 % c)
    route("a", 1)
    route(1, "a")
    xs = ["a", 1]
    op("list", xs[0], xs[1], "//")
    op("list", xs[0], xs[1], "%")
    box = Box("a")
    op("attr", box.v, 1, "//")
    op("attr", box.v, 1, "%")
    d = {"x": "a", "y": 1}
    op("dict", d["x"], d["y"], "//")
    op("dict", d["x"], d["y"], "%")
    x = "a"
    y = x
    x = 1
    op("alias", y, x, "//")
    op("alias", y, x, "%")


main()
'''

NEIGHBOURS = r'''def main():
    z = 0
    for a, b in [(7, z), (7.0, z), (0, z), (0.0, z), (-7, z), (-7.0, z)]:
        for kind in ("//", "%"):
            try:
                if kind == "//":
                    print("zero", repr(a // b))
                else:
                    print("zero", repr(a % b))
            except ZeroDivisionError as e:
                print("zero ZeroDivisionError", str(e))
    print("ok", 7 // 2, 7 % 2, -7 // 2, -7 % 2, 7.5 // 2.0, 7.5 % 2.0)
    print("ok", divmod(7, 2), divmod(-7, 2), divmod(7.5, 2.0))
    try:
        print("dm", divmod(1, "a"))
    except TypeError as e:
        print("dm TypeError", str(e))


main()
'''


EXCEPTION_ITERATOR_MESSAGES = r'''import collections


class Hook:
    def __floordiv__(self, other):
        return 0


class UserError(Exception):
    pass


class It:
    def __init__(self):
        self.done = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.done:
            raise StopIteration
        self.done = True
        return 1


_DQ = collections.deque([1])
_DQ_ITER = iter(_DQ)
_DQ_REV = reversed(_DQ)


def caught(f):
    try:
        f()
    except Exception as x:
        return x


def op(tag, a, b):
    for kind in ("//", "%"):
        try:
            if kind == "//":
                print(tag, kind, repr(a // b))
            else:
                print(tag, kind, repr(a % b))
        except Exception as y:
            print(tag, kind, type(y).__name__, str(y))


def main():
    z = caught(lambda: 1 // 0)
    op("exc_left", z, 1)
    op("exc_right", 1, z)
    i = caught(lambda: [][0])
    op("index_left", i, 1)
    op("index_right", 1, i)
    u = UserError("boom")
    op("user_left", u, 1)
    op("user_right", 1, u)
    def itop(name, v):
        op(name + "_left", v, 1)
        op(name + "_right", 1, v)

    d = {"a": 1, "b": 2}
    itop("list", iter([1]))
    itop("tuple", iter((1,)))
    itop("str_ascii", iter("a"))
    itop("str_wide", iter("\u00e9"))
    itop("keys", iter(d.keys()))
    itop("values", iter(d.values()))
    itop("items", iter(d.items()))
    itop("set", iter({1}))
    itop("range", iter(range(3)))
    itop("enumerate", enumerate([1]))
    itop("zip", zip([1], [2]))
    itop("rev_list", reversed([1]))
    itop("rev_tuple", reversed((1,)))
    itop("rev_str", reversed("a"))
    itop("rev_range", reversed(range(3)))
    itop("map", map(str, [1]))
    itop("filter", filter(None, [1]))
    itop("genexpr", (x for x in [1]))
    itop("user_iter", iter(It()))
    itop("deque", _DQ_ITER)
    itop("deque_rev", _DQ_REV)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre187Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre187-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_unsupported_operand_type_names(self):
        self.check('type_messages', TYPE_MESSAGES)

    def test_exception_and_iterator_type_names(self):
        self.check('exception_iterator', EXCEPTION_ITERATOR_MESSAGES)

    def test_division_neighbours_unchanged(self):
        self.check('neighbours', NEIGHBOURS)


if __name__ == '__main__':
    unittest.main()
