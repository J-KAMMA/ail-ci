"""pre279: an instance attribute shadows a class method of the same name.

The pre260 review recorded this method/field collision as a pre-existing difference (its p02
probe): a class with a method ``f`` and an instance field ``f`` printed the method's result,
while CPython looks the instance table up first (a function is a non-data descriptor) and calls
the field.  Both general paths now test the instance table before the static method dispatch;
the field wins when present, and the method still applies when the field was never assigned or
has been deleted.  The field value reaches the call as a literal, through an argument, a list
item, a dict value, an attribute, an alias, an inherited method and an external assignment.
A call with keyword or starred arguments is refused by name when a field may shadow it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

PROGRAMS = {
    'basic': '''class C:
    def __init__(self):
        self.f = lambda x: x + 100
    def f(self, x):
        return x + 101
c = C()
print(c.f(1), c.f(2))
''',
    'routes': '''class Adder:
    def __init__(self, k):
        self.k = k
        self.f = lambda x: self.k + x
    def f(self, x):
        return self.k - x

def call(o):
    return o.f(5)

class Box:
    def __init__(self, o):
        self.o = o

a = Adder(10)
alias = a
xs = [a]
d = {"a": a}
b = Box(a)
print(a.f(1), call(a), alias.f(2), xs[0].f(3), d["a"].f(4), b.o.f(6))
''',
    'external': '''class C:
    def f(self, x):
        return x + 1
c = C()
c.f = lambda x: x + 10
print(c.f(1))
''',
    'conditional': '''class C:
    def __init__(self, flag):
        if flag:
            self.f = lambda x: x + 100
    def f(self, x):
        return x + 101
print(C(True).f(1), C(False).f(1))
''',
    'types': '''class C:
    def __init__(self, value):
        self.f = lambda x: x + value
    def f(self, x):
        return 0
for v in (0, -1, 9223372036854775807, -9223372036854775808):
    print(C(v).f(0))
class D:
    def __init__(self, value):
        self.f = lambda x: x
    def f(self, x):
        return None
print(D(True).f(True), D("").f(""), D([]).f([1]), D(0).f(-5))
''',
    'noncallable': '''class C:
    def __init__(self):
        self.f = 5
    def f(self, x):
        return x + 1
try:
    print(C().f(1))
except TypeError as e:
    print("TypeError", e)
''',
    'inherit': '''class B:
    def f(self, x):
        return x + 1
class D(B):
    def __init__(self):
        self.f = lambda x: x + 10
print(D().f(1))
''',
    'static_classmethod': '''class C:
    @staticmethod
    def f(x):
        return x + 1
    @classmethod
    def g(cls, x):
        return x + 2
c = C()
c.f = lambda x: x + 10
c.g = lambda x: x + 20
print(c.f(1), c.g(1))
''',
    'alias_value': '''def make(v):
    return v
class C:
    def __init__(self, v):
        g = make(v)
        self.f = g
    def f(self, x):
        return x + 101
c = C(lambda x: x + 100)
print(c.f(1))
''',
    'control': '''class C:
    def add(self, x):
        return x + 1
    def run(self):
        return self.add(2)
print(C().add(1), C().run())
''',
}

REFUSED = '''class C:
    def __init__(self):
        self.f = lambda x=0: x + 10
    def f(self, x=0):
        return x + 1
print(C().f(x=5))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
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
    ran = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), ran.stderr.decode('utf-8', 'replace')[-1500:]


class Pre279Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre279-') as directory:
            want, want_rc = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0)
            for general in (True, False):
                got, build_err = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                        text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s'
                                 % (slug, general, build_err))

    def test_field_shadows_method(self):
        for slug in ('basic', 'external', 'conditional', 'inherit', 'static_classmethod',
                     'alias_value'):
            self.check(slug, PROGRAMS[slug])

    def test_field_value_routes(self):
        self.check('routes', PROGRAMS['routes'])

    def test_field_types_and_errors(self):
        for slug in ('types', 'noncallable'):
            self.check(slug, PROGRAMS[slug])

    def test_control_method_call_without_collision(self):
        self.check('control', PROGRAMS['control'])

    def test_keyword_call_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre279-') as directory:
            for general in (True, False):
                got, build_err = _build(directory, 'keyword_%s' % ('g' if general else 'd'),
                                        REFUSED, general)
                self.assertIsNone(got)
                self.assertIn('not in the subset', build_err)
                self.assertIn('instance attribute of the same name may shadow it', build_err)


if __name__ == '__main__':
    unittest.main()
