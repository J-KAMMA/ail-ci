"""pre28: any()/all() propagate an exception from a user __bool__ (or __len__).

On the general path the truth test used by any() and all() was the int-returning
``ail_truthy_u``, whose no-status form counts a raising __bool__ as true.  The
deciding element therefore did not raise: ``any([B(False), B(False, True)])``
printed True instead of raising ValueError, and the same happened through a
generator expression, an argument, a list item, an attribute and a dict value.

The fused generator path now also stops at the deciding element, as CPython does,
so an error after the result is decided is not evaluated.  Both builds must match
CPython's stdout and exit status; the remaining pre13 differences (the inner
generator expression in p7, the unclosed generator in r8/r9 and tuple
destructuring in r15) are outside this job.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROGRAM = r'''class B:
    def __init__(self, v, boom):
        self.v = v
        self.boom = boom

    def __bool__(self):
        if self.boom:
            raise ValueError("bad bool")
        return self.v


class L:
    def __init__(self, n, boom):
        self.n = n
        self.boom = boom

    def __len__(self):
        if self.boom:
            raise RuntimeError("bad len")
        return self.n


class Box:
    def __init__(self, b):
        self.b = b


def first(xs):
    return xs[0]


def take_any(xs):
    return any(xs)


def take_all(xs):
    return all(xs)


def gen_any(xs):
    return any(x for x in xs)


def gen_all(xs):
    return all(x for x in xs)


def main():
    a = B(True, False)
    f = B(False, False)
    r = B(False, True)
    print("any plain", any([f, a]))
    print("all plain", all([a, f]))
    try:
        print("any decide", any([f, r]))
    except ValueError as e:
        print("any decide", e)
    try:
        print("all decide", all([a, r]))
    except ValueError as e:
        print("all decide", e)
    try:
        print("any after", any([a, r]))
    except ValueError as e:
        print("any after", e)
    try:
        print("all after", all([f, r]))
    except ValueError as e:
        print("all after", e)
    try:
        print("gen any decide", gen_any([f, r]))
    except ValueError as e:
        print("gen any decide", e)
    try:
        print("gen all decide", gen_all([a, r]))
    except ValueError as e:
        print("gen all decide", e)
    try:
        print("gen any after", gen_any([a, r]))
    except ValueError as e:
        print("gen any after", e)
    try:
        print("gen all after", gen_all([f, r]))
    except ValueError as e:
        print("gen all after", e)
    xs = [f, r]
    try:
        print("arg any", take_any(xs))
    except ValueError as e:
        print("arg any", e)
    try:
        print("arg all", take_all([a, r]))
    except ValueError as e:
        print("arg all", e)
    try:
        print("item any", any([first(xs), first([r])]))
    except ValueError as e:
        print("item any", e)
    box = Box(r)
    try:
        print("attr any", any([f, box.b]))
    except ValueError as e:
        print("attr any", e)
    d = {"x": f, "y": r}
    try:
        print("dict any", any([d["x"], d["y"]]))
    except ValueError as e:
        print("dict any", e)
    ln = L(0, False)
    lt = L(1, False)
    lb = L(1, True)
    print("len fallback", any([ln, lt]), all([lt, ln]))
    try:
        print("len raising any", any([ln, lb]))
    except RuntimeError as e:
        print("len raising any", e)
    try:
        print("len raising all", all([lt, lb]))
    except RuntimeError as e:
        print("len raising all", e)
    print("empty", any([]), all([]))
    print("plain values", any([0, "", [], None]), all([1, "x", [0]]))
    print("mixed", any([0, "", [], None, a]))


main()
'''


def cpython(directory, text):
    src = Path(directory) / 'p_cpython.py'
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, text, general):
    src = Path(directory) / 'p.ail'
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                src.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class AnyAllTruthTests(unittest.TestCase):
    def test_raising_bool_propagates(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre28-') as directory:
            want = cpython(directory, PROGRAM)
            for general in (True, False):
                exe, built = build(directory, PROGRAM, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 'general=%s\n%s' % (general, got.stderr.decode('utf-8', 'replace')[-1500:]))
                self.assertEqual(got.returncode, want[1], 'general=%s' % general)


if __name__ == '__main__':
    unittest.main()
