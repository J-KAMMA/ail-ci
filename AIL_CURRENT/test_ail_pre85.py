"""pre85: negative shift counts name CPython's message on the typed path.

A negative shift count is a ValueError in Python.  The general path already
raised it with the message "negative shift count", but the typed path's ck_shl
and ck_shr guards used a code-only raise, so

    try:
        print(1 << -1)
    except ValueError as e:
        print(str(e))

printed an empty line where CPython prints "negative shift count".  Both guards
now carry the message.  The programs keep valid shifts, right shifts of 64 or
more (which are defined in Python), and counts reaching the operator through an
argument, a list item, an attribute and a dict value.  Each is built on both
builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SHIFT_MESSAGE = r'''class Box:
    def __init__(self, n):
        self.n = n


box = Box(-2)
xs = [4, -3]
d = {"a": 6, "b": -1}


def report(tag, value):
    print(tag, value)


try:
    report("left-const", 1 << -1)
except ValueError as e:
    report("left-const", (type(e).__name__, str(e), e.args))
try:
    report("right-const", 8 >> -1)
except ValueError as e:
    report("right-const", (type(e).__name__, str(e), e.args))
try:
    report("left-const2", -5 << -3)
except ValueError as e:
    report("left-const2", (type(e).__name__, str(e), e.args))
try:
    report("right-const2", -5 >> -2)
except ValueError as e:
    report("right-const2", (type(e).__name__, str(e), e.args))
try:
    report("left-list", xs[0] << xs[1])
except ValueError as e:
    report("left-list", (type(e).__name__, str(e), e.args))
try:
    report("right-list", xs[0] >> xs[1])
except ValueError as e:
    report("right-list", (type(e).__name__, str(e), e.args))
try:
    report("left-attr", d["a"] << box.n)
except ValueError as e:
    report("left-attr", (type(e).__name__, str(e), e.args))
try:
    report("right-attr", d["a"] >> box.n)
except ValueError as e:
    report("right-attr", (type(e).__name__, str(e), e.args))
try:
    report("left-dict", d["a"] << d["b"])
except ValueError as e:
    report("left-dict", (type(e).__name__, str(e), e.args))
try:
    report("right-dict", d["a"] >> d["b"])
except ValueError as e:
    report("right-dict", (type(e).__name__, str(e), e.args))
try:
    report("left-zero", 0 << -9)
except ValueError as e:
    report("left-zero", (type(e).__name__, str(e), e.args))
try:
    report("right-zero", 0 >> -9)
except ValueError as e:
    report("right-zero", (type(e).__name__, str(e), e.args))
print("done")
'''

SHIFT_ARGUMENT = r'''class Box:
    def __init__(self, n):
        self.n = n


def by_argument(a, b):
    return a << b


def by_argument_right(a, b):
    return a >> b


def main():
    box = Box(-2)
    xs = [4, -3]
    d = {"a": 6, "b": -1}
    try:
        print("left-arg", by_argument(3, -4))
    except ValueError as e:
        print("left-arg", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-arg", by_argument_right(16, -4))
    except ValueError as e:
        print("right-arg", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("left-list", by_argument(xs[0], xs[1]))
    except ValueError as e:
        print("left-list", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-list", by_argument_right(xs[0], xs[1]))
    except ValueError as e:
        print("right-list", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("left-attr", by_argument(d["a"], box.n))
    except ValueError as e:
        print("left-attr", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-attr", by_argument_right(d["a"], box.n))
    except ValueError as e:
        print("right-attr", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("left-dict", by_argument(d["a"], d["b"]))
    except ValueError as e:
        print("left-dict", type(e).__name__, repr(str(e)), repr(e.args))
    try:
        print("right-dict", by_argument_right(d["a"], d["b"]))
    except ValueError as e:
        print("right-dict", type(e).__name__, repr(str(e)), repr(e.args))
    print("done")


main()
'''

SHIFT_VALID = r'''class Box:
    def __init__(self, n):
        self.n = n


def shift(a, b):
    return a << b, a >> b


def shr(a, b):
    return a >> b


def main():
    box = Box(3)
    xs = [5, 2]
    d = {"a": 7, "b": 1}
    print(shift(1, 0), shift(1, 1), shift(1, 62))
    print(shift(-1, 1), shift(-1, 62))
    print(shr(8, 63), shr(-8, 63), shr(8, 64), shr(-8, 64), shr(8, 1000), shr(-8, 1000))
    print(xs[0] << xs[1], xs[0] >> xs[1])
    print(d["a"] << box.n, d["a"] >> box.n)
    print(0 << 64, 0 << 1000)
    print("done")


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


class Pre85Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre85-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_negative_shift_message(self):
        self.check('shift_message', SHIFT_MESSAGE)

    def test_negative_shift_through_calls(self):
        self.check('shift_argument', SHIFT_ARGUMENT)

    def test_valid_shifts(self):
        self.check('shift_valid', SHIFT_VALID)


if __name__ == '__main__':
    unittest.main()
