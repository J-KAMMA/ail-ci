"""A field/method collision reached through a function-return receiver (job pre288).

The pre278 review recorded a pre-existing difference: with ``self.f = lambda: 101`` and a method
``def f`` in the same class, ``make(4).f()`` where ``make`` returns that class printed ``-1`` (the
method) where CPython prints ``40`` (the stored field).  The collision refusal now resolves a
function-return (and constructor) receiver, so this route is refused by name on both builds; the
direct constructor, an alias, a branch, a pass-through argument, an inherited method and a method
return are covered too.  Calls on unrelated classes, other method names, non-colliding classes and
the class-level spelling ``C.f(c)`` keep their old behaviour.  Function and name resolution stays in
the receiver's lexical scope, so a same-named method or a local/annotation in another function is
not attributed to it, while a call made inside a function still follows that function's return.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'also stores an instance field named'


COLLISION = r'''class C:
    def __init__(self, k):
        self.k = k
        self.f = lambda: self.k * 10
    def f(self):
        return -1
'''

RETURN_CALL = COLLISION + r'''def make(k):
    return C(k)
print(make(4).f())
'''

RETURN_ALIAS = COLLISION + r'''def make(k):
    c = C(k)
    return c
print(make(4).f())
'''

RETURN_IF = COLLISION + r'''def make(k, flag):
    if flag:
        return C(k)
    return C(k + 1)
print(make(4, True).f())
'''

RETURN_PASSTHROUGH = COLLISION + r'''def passthrough(c):
    return c
def make(k):
    return passthrough(C(k))
print(make(4).f())
'''

RETURN_INHERITED = r'''class B:
    def f(self):
        return 1
class C(B):
    def __init__(self):
        self.f = lambda: 2
def make():
    return C()
print(make().f())
'''

RETURN_METHOD = COLLISION + r'''class Factory:
    def make(self, k):
        return C(k)
print(Factory().make(4).f())
'''

RETURN_ATTRIBUTE = r'''class C:
    def __init__(self):
        self.f = lambda: 19
    def f(self):
        return 20
class H:
    def __init__(self):
        self.c = C()
def make():
    return H()
print(make().c.f())
'''

DIRECT_CONSTRUCTOR = COLLISION + r'''print(C(4).f())
'''

UNRELATED = COLLISION + r'''class D:
    def f(self):
        return 7
def make(k):
    return D()
print(make(1).f())
'''

OTHER_METHOD = COLLISION + r'''    def g(self):
        return 9
def make():
    return C(4)
print(make().g())
'''

NO_COLLISION = r'''class C:
    def __init__(self):
        self.g = 3
    def f(self):
        return 8
def make():
    return C()
print(make().f())
'''

CLASS_CALL = COLLISION + r'''c = C(4)
print(C.f(c))
'''

SAME_NAME_METHOD = r'''class C:
    def __init__(self):
        self.f = lambda: 1
    def f(self):
        return 2
class D:
    def f(self):
        return 3
class F:
    def make(self):
        return C()
def make():
    return D()
print(make().f())
'''

LOCAL_SCOPE = r'''class C:
    def __init__(self):
        self.f = lambda: 1
    def f(self):
        return 2
class D:
    def f(self):
        return 3
def b():
    x = C()
    return 0
def a():
    x = D()
    return x.f()
print(a())
'''

ANNOTATION_SCOPE = r'''class C:
    def __init__(self):
        self.f = lambda: 1
    def f(self):
        return 2
class D:
    def f(self):
        return 3
def a(x: C):
    return 0
def b():
    x = D()
    return x.f()
print(b())
'''

CALL_INSIDE_FUNCTION = COLLISION + r'''def make(k):
    return C(k)
def a():
    return make(4).f()
print(a())
'''

LOCAL_SHADOW = COLLISION + r'''class D:
    def f(self):
        return 5
def make():
    return C(4)
def a():
    def make():
        return D()
    return make().f()
print(a())
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


class Pre288Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre288-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre288-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNone(got, '%s was built (general=%s)' % (slug, general))
                self.assertIn(REFUSAL, build_err, 'general=%s\n%s' % (general, build_err))

    def test_return_route_is_refused(self):
        self.refused('return_call', RETURN_CALL)

    def test_other_return_shapes_are_refused(self):
        for slug, text in (('alias', RETURN_ALIAS), ('if', RETURN_IF),
                           ('passthrough', RETURN_PASSTHROUGH),
                           ('inherited', RETURN_INHERITED), ('method', RETURN_METHOD),
                           ('attribute', RETURN_ATTRIBUTE),
                           ('constructor', DIRECT_CONSTRUCTOR)):
            with self.subTest(slug=slug):
                self.refused(slug, text)

    def test_unrelated_receivers_match_cpython(self):
        self.check('unrelated', UNRELATED)
        self.check('other_method', OTHER_METHOD)
        self.check('no_collision', NO_COLLISION)
        self.check('class_call', CLASS_CALL)

    def test_name_resolution_stays_in_scope(self):
        self.check('samename', SAME_NAME_METHOD)
        self.check('local_scope', LOCAL_SCOPE)
        self.check('annotation_scope', ANNOTATION_SCOPE)
        self.check('local_shadow', LOCAL_SHADOW)

    def test_call_inside_function_still_refused(self):
        self.refused('call_inside', CALL_INSIDE_FUNCTION)


if __name__ == '__main__':
    unittest.main()
