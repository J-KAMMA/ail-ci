"""pre213: a name read only through two levels of nested def is captured too.

A nested def registered in place captured only the names its own body read, so a list read by
the def inside it was not captured at all (``name 'xs' is not defined``).  The intermediate def
now shares the enclosing activation's cell, so the inner def sees the same object and later
rebinding of the name, and the shared cell is passed on through any further nested defs.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

DEEP = r'''class Box:
    def __init__(self, v):
        self.v = v


def append_arg(xs):
    def middle():
        def inner():
            xs.append(1)
        inner()
    middle()
    return xs


def alias():
    xs = []
    ys = xs
    def middle():
        def inner():
            xs.append(1)
            ys.append(2)
        inner()
    middle()
    return xs


def flows(d, xs, box):
    def middle():
        def inner():
            d["k"].append("d")
            xs[0].append("l")
            box.v.append("a")
        inner()
    middle()
    return d["k"], xs[0], box.v


def read(n, s):
    def middle():
        def inner():
            return s * n
        return inner()
    return middle()


def default_arg():
    xs = []
    def middle():
        def inner(y=xs):
            y.append(1)
        inner()
    middle()
    return xs


def siblings():
    xs = []
    def middle():
        def a():
            xs.append("a")
        def b():
            xs.append("b")
        a()
        b()
    middle()
    return xs


def returned():
    xs = []
    def middle():
        def inner():
            xs.append(1)
            return len(xs)
        return inner
    return middle()


def rebind():
    xs = []
    def middle():
        def inner():
            xs.append(1)
        return inner
    f = middle()
    xs = ["new"]
    f()
    return xs


def three():
    xs = []
    def a():
        def b():
            def c():
                xs.append("c")
            c()
        b()
    a()
    return xs


def main():
    print(append_arg([]))
    print(append_arg([9]))
    print(alias())
    print(flows({"k": []}, [[]], Box([])))
    print(read(3, "ab"))
    print(read(0, "ab"))
    print(read(-1, "ab"))
    print(default_arg())
    print(siblings())
    f = returned()
    print(f())
    print(f())
    print(rebind())
    print(three())


main()
'''

NONLOCAL = r'''def outer():
    n = 0
    def middle():
        def inner():
            nonlocal n
            n += 1
        inner()
        inner()
    middle()
    return n


print(outer())
'''
REFUSAL = 'not in the subset:'


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
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre213Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre213-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, want_rc), 'general=%s\n%s' % (general, build_err))

    def check_refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre213-') as directory:
            _, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNone(got, 'built and ran instead of refusing (general=%s):\n%s\n%s'
                                  % (general, text, build_err))
                self.assertIn(REFUSAL, build_err, 'general=%s\n%s' % (general, build_err))

    def test_two_level_capture(self):
        self.check('deep', DEEP)

    def test_two_level_nonlocal_still_refused(self):
        self.check_refused('nonlocal', NONLOCAL)


if __name__ == '__main__':
    unittest.main()
