"""Pre-240: `float()` on a non-number names a "real number" and the value's class.

The review of job rbrbrbmemsafe2 recorded this pre-existing difference: `float(None)` and
`float([1])` raised `TypeError: float() argument must be a string or a number, ...` where
CPython 3.12 says `... a string or a real number, ...`.  A user-class instance was also named
`instance` instead of its class, and the 80-byte message buffer cut a long type name such as
`builtin_function_or_method`.

Both builds now use CPython's wording and class-aware type name for the wrong-type branch; the
buffer is large enough for the longest builtin type name.  Valid int/bool/float/str conversions
are unchanged.  The cases below are direct calls and values reaching the conversion through an
argument, a list item, an attribute, a dict value, an alias, a function/class value and classes
that define `__float__`, `__index__`, `__int__` or an operator hook (which turns on the dunder
dispatch), on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

BASIC = r'''class Box:
    def __init__(self):
        self.n = None
        self.l = [1]
        self.d = {"x": {}}
        self.b = b"1"


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def conv(v):
    return float(v)


def f():
    return 1


def main():
    values = [None, [1], [], (), {}, set(), frozenset(), b"", bytearray(), (1,),
              {"a": 1}, {1}, frozenset([1]), b"1", bytearray(b"1"),
              0, -1, True, False, 1.5, -0.0, -2.5, "1.5", " 2 ", "-3",
              "inf", "nan", "", "x", 9223372036854775807, -9223372036854775808]
    for i in range(len(values)):
        v = values[i]
        show("v" + str(i) + "-direct", lambda v=v: float(v))
        show("v" + str(i) + "-arg", lambda v=v: conv(v))
        show("v" + str(i) + "-list", lambda v=v, i=i: float(values[i]))
    d = {"none": None, "empty": [], "good": "1.25", "bad": "1.2.3"}
    for k in ("none", "empty", "good", "bad"):
        show("dict-" + k, lambda k=k: float(d[k]))
    b = Box()
    show("attr-none", lambda: float(b.n))
    show("attr-list", lambda: float(b.l))
    show("attr-dict", lambda: float(b.d))
    show("attr-bytes", lambda: float(b.b))
    alias = [1]
    alias2 = alias
    alias.append(2)
    show("alias", lambda: float(alias2))
    show("builtin-len", lambda: float(len))
    show("user-func", lambda: float(f))
    show("class", lambda: float(Box))
    show("class-arg", lambda: float([Box][0]))


main()
'''

HOOKS = r'''class F:
    def __float__(self):
        return 2.5

    def __add__(self, other):
        return 7


class Ix:
    def __index__(self):
        return 3

    def __add__(self, other):
        return 8


class It:
    def __int__(self):
        return 4

    def __add__(self, other):
        return 9


class Box:
    def __init__(self):
        self.v = 1

    def __add__(self, other):
        return 10


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def conv(v):
    return float(v)


def main():
    b = Box()
    show("float-hook", lambda: float(F()))
    show("index-hook", lambda: float(Ix()))
    show("int-hook", lambda: float(It()))
    show("no-hook", lambda: float(b))
    show("no-hook-arg", lambda: conv(b))
    show("float-hook-arg", lambda: conv(F()))
    show("list-hook", lambda: float([F()][0]))
    show("list-no-hook", lambda: float([b][0]))
    show("none", lambda: float(None))
    show("none-arg", lambda: conv(None))
    show("list", lambda: float([1]))
    show("dict", lambda: float({}))
    show("tuple", lambda: float((1,)))
    show("builtin", lambda: float(len))
    show("good-str", lambda: float("2.25"))
    show("good-int", lambda: float(5))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre240Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre240-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_float_wrong_type_message(self):
        self.check('basic', BASIC)

    def test_float_wrong_type_with_dunder_dispatch(self):
        self.check('hooks', HOOKS)


if __name__ == '__main__':
    unittest.main()
