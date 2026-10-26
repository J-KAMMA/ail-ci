"""Callable values stored in instance fields (job pre260).

The reviewer of job bigint-fix04 recorded the general path refusing a Callable held in a class
field (``self.cb(x)`` / ``obj.cb(x)``) while the default build matched CPython.  The general
path now remembers class/instance annotations that name ``Callable[...]`` and calls such a field
through the ordinary function-value path, so the stored function is called instead of being
reported as an unknown method.  Missing fields and non-callable values raise CPython's
``AttributeError`` / ``TypeError``.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FIELD = r'''from typing import Callable

def inc(x: int) -> int:
    return x + 1

class Holder:
    cb: Callable[[int], int]
    def __init__(self, f: Callable[[int], int]) -> None:
        self.cb = f
    def run(self, x: int) -> int:
        return self.cb(x)

def main() -> None:
    h = Holder(inc)
    print(h.cb(3), h.run(4))
main()
'''

ROUTES = r'''from typing import Callable

class Ops:
    f: Callable[[int], int]
    g: Callable[[int], int]

    def __init__(self, f: Callable[[int], int], g: Callable[[int], int]) -> None:
        self.f = f
        self.g = g

    def apply(self, x: int) -> int:
        return self.f(x) + self.g(x)

    def pick(self, n: int) -> Callable[[int], int]:
        if n > 0:
            return self.f
        return self.g

def inc(x: int) -> int:
    return x + 1

def dbl(x: int) -> int:
    return x * 2

def call_it(cb: Callable[[int], int], x: int) -> int:
    return cb(x)

def main() -> None:
    o = Ops(inc, dbl)
    print(o.f(3), o.g(3), o.apply(3), o.pick(1)(4), o.pick(-1)(4))
    h = o.f
    print(h(5), call_it(o.g, 6))
    xs = [o.g]
    d = {"f": o.f}
    print(xs[0](7), d["f"](8), Ops(o.g, o.f).g(9))
    print(o.f(-9223372036854775807), o.g(4611686018427387903))
main()
'''

SELF_ANNOTATION = r'''from typing import Callable

class C:
    def __init__(self, f: Callable[[int], int]) -> None:
        self.f: Callable[[int], int] = f

    def run(self, x: int) -> int:
        return self.f(x)

def triple(x: int) -> int:
    return x * 3

def main() -> None:
    c = C(triple)
    print(c.f(4), c.run(5))
main()
'''

KINDS = r'''from typing import Callable

class F:
    a: Callable[[float], float]
    b: Callable[[str], int]
    c: Callable[[list[int]], int]
    d: Callable[[int], None]

def half(x: float) -> float:
    return x / 2

def length(s: str) -> int:
    return len(s)

def total(xs: list[int]) -> int:
    t = 0
    for x in xs:
        t += x
    return t

def show(x: int) -> None:
    print("show", x)

def main() -> None:
    f = F()
    f.a = half
    f.b = length
    f.c = total
    f.d = show
    print(f.a(-3.5), f.a(0.0), f.b(""), f.b("hello"), f.c([]), f.c([1, 2, 3]))
    f.d(7)
main()
'''

ERRORS = r'''from typing import Callable

class Box:
    f: Callable[[int], int]

def good(x: int) -> int:
    return -x

def main() -> None:
    b = Box()
    b.f = good
    print(b.f(5))
    try:
        Box().f(1)
    except AttributeError as e:
        print("AttributeError", e)
    b.f = 10
    try:
        b.f(1)
    except TypeError as e:
        print("TypeError", e)
    try:
        b.f()
    except TypeError as e:
        print("TypeError", e)
    print(b.f)
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


class Pre260Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre260-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_callable_in_instance_field(self):
        self.check('field', FIELD)

    def test_callable_field_routes(self):
        self.check('routes', ROUTES)

    def test_callable_field_annotation_on_self(self):
        self.check('self_annotation', SELF_ANNOTATION)

    def test_callable_field_kinds(self):
        self.check('kinds', KINDS)

    def test_callable_field_errors(self):
        self.check('errors', ERRORS)


if __name__ == '__main__':
    unittest.main()
