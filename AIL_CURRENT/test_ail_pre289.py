"""A method-call collision reached through a function-return receiver (job pre289).

The pre278 review recorded a pre-existing difference: with a class whose ``__init__`` stores
``self.f = lambda: self.k * 10`` and whose body also defines ``def f``, a call through a
function-return receiver (``make(4).f()``) still printed the method's ``-1`` on both builds,
where CPython calls the stored field and prints ``40``.  The collision refusal now resolves
the classes a user function returns (a ``-> C`` annotation, a constructor in a ``return``, a
chain through another function, and a value assigned first).  A receiver that resolves to an
unrelated class, or to a non-class value, keeps its old behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'also stores an instance field named'

PAIR = '''class C:
    def __init__(self, k):
        self.k = k
        self.f = lambda: self.k * 10
    def f(self):
        return -1
'''

DIRECT = PAIR + '''print(C(4).f())
'''

V1 = PAIR + '''def make(k):
    return C(k)

print(make(4).f())
'''

ANNOTATED = PAIR + '''def make(k) -> C:
    return C(k)

print(make(4).f())
'''

CHAIN = PAIR + '''def make(k):
    return C(k)

def outer(k):
    return make(k)

print(outer(4).f())
'''

ASSIGNED = PAIR + '''def make(k):
    c = C(k)
    return c

print(make(4).f())
'''

ARGUMENT = PAIR + '''def make(k):
    return C(k)

def call(c):
    return c.f()

print(call(make(4)))
'''

LIST_ITEM = PAIR + '''def make(k):
    return C(k)

xs = [make(4)]
print(xs[0].f())
'''

DICT_VALUE = PAIR + '''def make(k):
    return C(k)

d = {"c": make(4)}
print(d["c"].f())
'''

ATTRIBUTE = PAIR + '''def make(k):
    return C(k)

class H:
    def __init__(self):
        self.c = make(4)

print(H().c.f())
'''

ALIAS = PAIR + '''def make(k):
    return C(k)

c = make(4)
a = c
print(a.f())
'''

SUBCLASS = PAIR + '''class B(C):
    pass

def make(k):
    return B(k)

print(make(4).f())
'''

CONDITIONAL = PAIR + '''def make(k):
    if k > 0:
        return C(k)
    return C(0)

print(make(4).f(), make(-1).f())
'''

UNRELATED = '''class A:
    def f(self):
        return 41

class C:
    def __init__(self, k):
        self.k = k
        self.f = lambda: self.k * 10
    def f(self):
        return -1

def make(k):
    return A()

print(make(4).f())
'''

UNRELATED_CONDITIONAL = '''class A:
    def f(self):
        return 41

class C:
    def __init__(self, k):
        self.k = k
        self.f = lambda: self.k * 10
    def f(self):
        return -1

def make(k):
    if k > 0:
        return A()
    return A()

print(make(4).f())
'''

NON_CLASS = '''def make(k):
    return k * 2

print(make(4))
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


class Pre289Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre289-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre289-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNone(got, '%s was built (general=%s)' % (slug, general))
                self.assertIn(REFUSAL, build_err, 'general=%s\n%s' % (general, build_err))

    def test_v1_return_route_is_refused(self):
        self.refused('v1', V1)

    def test_direct_collision_is_refused(self):
        self.refused('direct', DIRECT)

    def test_return_routes_are_refused(self):
        for slug, text in (('annotated', ANNOTATED), ('chain', CHAIN), ('assigned', ASSIGNED),
                           ('argument', ARGUMENT), ('list', LIST_ITEM), ('dict', DICT_VALUE),
                           ('attribute', ATTRIBUTE), ('alias', ALIAS), ('subclass', SUBCLASS),
                           ('conditional', CONDITIONAL)):
            with self.subTest(slug=slug):
                self.refused(slug, text)

    def test_unrelated_function_returns_match_cpython(self):
        self.check('unrelated', UNRELATED)
        self.check('unrelated_conditional', UNRELATED_CONDITIONAL)
        self.check('non_class', NON_CLASS)


if __name__ == '__main__':
    unittest.main()
