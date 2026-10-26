"""A call through a name a class defines as both a method and an instance field (job pre278).

The pre260 review recorded a pre-existing difference: with ``self.f = lambda: 101`` and a method
``def f`` in the same class, CPython's instance attribute wins and ``c.f()`` returns 101, while
both builds silently dispatched to the method and returned 102.  A callable held in an instance
field has no route on either emitter, so such a call is now refused by name at compile time;
the class-level spelling ``C.f(c)``, a plain field read, a class that defines only the method or
only the field, and an unrelated class with the same method name keep their old behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REFUSAL = 'also stores an instance field named'


DIRECT = r'''class C:
    def __init__(self):
        self.f = lambda: 101
    def f(self):
        return 102
c = C()
print(c.f(), C.f(c))
'''

ARGUMENT = r'''class C:
    def __init__(self):
        self.f = lambda x: x + 5
    def f(self, x):
        return x + 500
def call(c, x):
    return c.f(x)
print(call(C(), -3))
'''

LIST_ITEM = r'''class C:
    def __init__(self, k):
        self.k = k
        self.f = lambda: self.k
    def f(self):
        return -1
xs = [C(7)]
print(xs[0].f())
'''

DICT_VALUE = r'''class C:
    def __init__(self):
        self.f = lambda: 11
    def f(self):
        return 22
d = {"c": C()}
print(d["c"].f())
'''

ATTRIBUTE = r'''class C:
    def __init__(self):
        self.f = lambda: 13
    def f(self):
        return 14
class H:
    def __init__(self):
        self.c = C()
print(H().c.f())
'''

ALIAS = r'''class C:
    def __init__(self):
        self.f = lambda: 15
    def f(self):
        return 16
c = C()
a = c
b = a
print(b.f())
'''

NON_CALLABLE = r'''class C:
    def __init__(self):
        self.f = 101
    def f(self):
        return 102
c = C()
print(c.f())
'''

INHERITED_METHOD = r'''class B:
    def f(self):
        return 1
class C(B):
    def __init__(self):
        self.f = lambda: 2
print(C().f())
'''

SELF_RECEIVER = r'''class C:
    def __init__(self):
        self.f = lambda: 21
    def f(self):
        return 22
    def run(self):
        return self.f()
print(C().run())
'''

CLASS_CALL = r'''class C:
    def __init__(self):
        self.f = lambda: 17
    def f(self):
        return 18
c = C()
print(C.f(c))
'''

READ = r'''class C:
    def __init__(self):
        self.f = 19
    def f(self):
        return 20
c = C()
print(c.f)
'''

ONLY_METHOD = r'''class C:
    def f(self, x):
        return x * 3
print(C().f(-2))
'''

OTHER_FIELD = r'''class C:
    def __init__(self):
        self.g = 8
    def f(self):
        return self.g
print(C().f())
'''

UNRELATED = r'''class A:
    def f(self):
        return 1
class B:
    def __init__(self):
        self.f = 9
    def f(self):
        return 2
print(A().f())
'''

UNRELATED_CALL = r'''class C:
    def __init__(self):
        self.f = lambda: 3
    def f(self):
        return 4
class D:
    def f(self):
        return 5
print(D().f())
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


class Pre278Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre278-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre278-') as directory:
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNone(got, '%s was built (general=%s)' % (slug, general))
                self.assertIn(REFUSAL, build_err, 'general=%s\n%s' % (general, build_err))

    def test_direct_collision_is_refused(self):
        self.refused('direct', DIRECT)

    def test_routes_are_refused(self):
        for slug, text in (('arg', ARGUMENT), ('list', LIST_ITEM), ('dict', DICT_VALUE),
                           ('attr', ATTRIBUTE), ('alias', ALIAS), ('noncallable', NON_CALLABLE),
                           ('inherited', INHERITED_METHOD), ('self', SELF_RECEIVER)):
            with self.subTest(slug=slug):
                self.refused(slug, text)

    def test_class_call_and_read_keep_their_behaviour(self):
        self.check('class_call', CLASS_CALL)
        self.check('read', READ)

    def test_classes_without_the_collision_match_cpython(self):
        self.check('only_method', ONLY_METHOD)
        self.check('other_field', OTHER_FIELD)
        self.check('unrelated', UNRELATED)
        self.check('unrelated_call', UNRELATED_CALL)


if __name__ == '__main__':
    unittest.main()
