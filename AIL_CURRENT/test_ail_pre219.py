"""pre219: combinations()/combinations_with_replacement() convert r before the pool.

CPython converts the r argument with its index rules before it materializes the iterable, so
`combinations(5, 1.0)` raises TypeError for the float (and accepts an object with __index__),
while AIL materialized the pool first and raised "'int' object is not iterable".  Both builds now
convert r first: an int, a bool or an instance with __index__ is an index; a float, a str, None
and anything else raise CPython's "'<type>' object cannot be interpreted as an integer", and a
bad __index__ return is "__index__ returned non-int (type ...)".  The value may reach the call
through a variable, a function argument, a list item, an attribute or a dict value.  A successful
conversion still materializes the pool before the negative-r ValueError, as CPython does.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


ORDER = r'''import itertools


class Box:
    def __init__(self, r):
        self.r = r


def from_arg(v):
    return v


def call(label, which, xs, r):
    try:
        if which == 0:
            out = list(itertools.combinations(xs, r))
        else:
            out = list(itertools.combinations_with_replacement(xs, r))
        print(label, out)
    except Exception as e:
        print(label, type(e).__name__, str(e))


def run():
    d = {"r": "x"}
    b = Box(None)
    for which in (0, 1):
        for label, r in (("float", 1.0), ("str", "x"), ("none", None)):
            call("noniter-" + label, which, 5, r)
            call("list-" + label, which, [1, 2, 3], r)
        call("local-float", which, [1, 2, 3], 1.0)
        call("arg-float", which, [1, 2, 3], from_arg(1.0))
        call("listitem-float", which, [1, 2, 3], [1.0][0])
        call("attr-none", which, [1, 2, 3], b.r)
        call("dict-str", which, [1, 2, 3], d["r"])
        call("noniter-neg", which, 5, -1)
        call("list-neg", which, [1, 2, 3], -1)
        call("zero-empty", which, [], 0)
        call("true", which, [1, 2, 3], True)
        call("false", which, [1, 2, 3], False)


run()
'''

INDEX = r'''import itertools


class Ix:
    def __init__(self, v):
        self.v = v

    def __index__(self):
        return self.v


class Bad:
    def __index__(self):
        return 1.0


class Plain:
    pass


class KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK:
    pass


class LongReturn:
    pass


class BadLong:
    def __index__(self):
        return LongReturn()


class Box:
    def __init__(self, r):
        self.r = r


def from_arg(v):
    return v


def call(label, which, xs, r):
    try:
        if which == 0:
            out = list(itertools.combinations(xs, r))
        else:
            out = list(itertools.combinations_with_replacement(xs, r))
        print(label, out)
    except Exception as e:
        print(label, type(e).__name__, str(e))


def run():
    d = {"r": Ix(2)}
    b = Box(Ix(2))
    for which in (0, 1):
        for label, r in (("I0", Ix(0)), ("I2", Ix(2)), ("I3", Ix(3)),
                         ("Ineg", Ix(-1)), ("bad", Bad()), ("plain", Plain()),
                         ("longplain", KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK()), ("longbad", BadLong())):
            call("literal-" + label, which, [1, 2, 3], r)
        call("local-I2", which, [1, 2, 3], Ix(2))
        call("arg-Ineg", which, [1, 2, 3], from_arg(Ix(-1)))
        call("listitem-I2", which, [1, 2, 3], [Ix(2)][0])
        call("attr-I2", which, [1, 2, 3], b.r)
        call("dict-I2", which, [1, 2, 3], d["r"])
        call("empty-I0", which, [], Ix(0))
        call("empty-I2", which, [], Ix(2))


run()
'''

UNCAUGHT = r'''import itertools


def gen():
    yield 1
    yield 2


print("before")
print(list(itertools.combinations(gen(), 1.0)))
print("after")
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr.decode('utf-8', 'replace')


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


class Pre219Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, stderr=None):
        with tempfile.TemporaryDirectory(prefix='ail-pre219-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[0], want, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got[1], rc, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                if stderr is not None:
                    self.assertIn(stderr, build_err)

    def test_order(self):
        self.check('order', ORDER)

    def test_index(self):
        self.check('index', INDEX)

    def test_uncaught(self):
        self.check('uncaught', UNCAUGHT, rc=1,
                   stderr="TypeError: 'float' object cannot be interpreted as an integer")


if __name__ == '__main__':
    unittest.main()
