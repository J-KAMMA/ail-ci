"""pre381: a class body cannot read its own name.

The pre362 review recorded as pre-existing the probes rp22/rp27 (``class C: y = (lambda: C)()``
and the comprehension form) and rp28 (``class C: y = C``): CPython raises NameError because the
class name is bound only after the class body runs, while both builds printed the class.  Class
objects here are all created at startup, so each class now carries a compile-time-driven
"body being evaluated" flag; a read of the class's own name while that flag is set raises
NameError, exactly as CPython does.

Every route that reads the class name is covered: a plain name, a lambda called in the body, a
comprehension, ``C.attr``, a list item, a dict value, an argument, ``isinstance``, a
classmethod call, and a class raised or matched in an exception handler inside a function called
from the body.  A binding made before the class is visible, and a later read (a method body, a
stored instance) still works.  A generator expression is materialised eagerly here, so one in a
class body that reads its own class name is refused by name instead of keeping CPython's late
binding.  Programs are built with the general path forced and with the default build; stdout and
the exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

NAME_ERROR = '''
class C:
    y = %s
print(C.y)
'''

MATCHING = {
    'direct': 'class C:\n    y = C\nprint(C.y)\n',
    'lambda_call': NAME_ERROR % '(lambda: C)()',
    'list_comp': NAME_ERROR % '[C for _ in range(2)]',
    'set_comp': NAME_ERROR % '{C for _ in range(2)}',
    'dict_comp': NAME_ERROR % '{i: C for i in range(2)}',
    'attribute': NAME_ERROR % 'C.__name__',
    'self_attribute': 'class C:\n    a = 1\n    b = C.a\nprint(C.b)\n',
    'list_item': NAME_ERROR % '[C][0]',
    'dict_value': NAME_ERROR % '{"k": C}',
    'argument': 'def f(v):\n    return v\nclass C:\n    y = f(C)\nprint(C.y)\n',
    'lambda_argument': NAME_ERROR % '(lambda v: v)(C)',
    'nested_lambda': NAME_ERROR % '(lambda: (lambda: C)())()',
    'isinstance': NAME_ERROR % 'isinstance(1, C)',
    'classmethod': '''
class C:
    @classmethod
    def m(cls):
        return cls.__name__
    x = C.m()
print(C.x)
''',
    'raise_in_body': '''
class E(Exception):
    pass
def f():
    raise C
class C(Exception):
    x = f()
print(C.x)
''',
    'except_in_body': '''
def f():
    try:
        raise ValueError
    except C:
        return 1
class C(Exception):
    x = f()
print(C.x)
''',
    'prior_binding': 'C = 5\nclass C:\n    y = C\nprint(C.y)\n',
    'other_class': 'class D:\n    pass\nclass C:\n    y = D\nprint(C.y)\n',
    'class_value_after': 'class C:\n    pass\nx = C\nprint(x.__name__)\n',
    'deferred_method': '''
class C:
    def m(self):
        return C
print(C().m().__name__)
''',
    'deferred_instance': '''
class Box:
    def get(self):
        return C
class C:
    box = Box()
print(C().box.get().__name__)
''',
    # Regression: a handler whose type is a class name opens its own `if (bound)` check.  An
    # earlier handler catching the exception must not then fall into that check's `else`, and a
    # later handler's class name must not be evaluated once an earlier handler matched.
    'loop_second_handler': '''
class Base(Exception):
    pass
class Child(Base):
    pass
for n in ("bad", "nope"):
    try:
        if n == "bad":
            raise Child(n)
        raise Base("unknown " + n)
    except Child as e:
        print("child", e)
    except Base as e:
        print("base", e)
print("after")
''',
    'later_handler_not_evaluated': '''
def f():
    try:
        raise ValueError("x")
    except ValueError as e:
        print("caught", e)
    except C as e:
        print("wrong")
    print("after")
class C(Exception):
    x = f()
print(C.x)
''',
}

REFUSALS = {
    'default': ('class C:\n    def m(self, x=C):\n        return x\nprint(C().m())\n',
                'which is defined after the def'),
    'call_in_body': ('class A:\n    x = A()\nprint("done")\n', 'not in the subset'),
    'genexp_lazy': ('class C:\n    g = (C for _ in range(2))\nprint(list(C.g))\n',
                    'a generator expression in the class body reads the class name C'),
    'genexp_consumed': ('class C:\n    g = list(C for _ in range(2))\nprint(C.g)\n',
                        'a generator expression in the class body reads the class name C'),
}


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


class Pre381Tests(unittest.TestCase):
    def test_class_name_read_in_own_body_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre381-') as directory:
            for slug, text in MATCHING.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))
                    if want[1] != 0:
                        self.assertIn('NameError', build_err or '', '%s (general=%s)' %
                                      (slug, general))

    def test_shadowed_class_name_is_not_a_self_read(self):
        # A parameter or local of the same name is what the read resolves to, so the class-body
        # check must not fire: the pre381 review found both shapes raising a false NameError.
        cases = {
            'shadowed_isinstance': '''
class D:
    pass
class C:
    x = (lambda C: isinstance(1, C))(D)
print(C.x)
''',
            'shadowed_except': '''
class D(Exception):
    pass
def f(C):
    try:
        raise ValueError("x")
    except C:
        pass
class C(Exception):
    x = f(D)
print(C.x)
''',
        }
        with tempfile.TemporaryDirectory(prefix='ail-pre381-') as directory:
            for slug, text in cases.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertNotIn('NameError', build_err or '', '%s (general=%s)' %
                                     (slug, general))

    def test_unsupported_routes_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre381-') as directory:
            for slug, (text, wording) in REFUSALS.items():
                _run_cpython(directory, slug, text)
                for general in (True, False):
                    _, built = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                      text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' %
                                        (slug, general, output))
                    self.assertIn(wording, output, '%s (general=%s)\n%s' %
                                  (slug, general, output))
                    self.assertIn('not in the subset', output, '%s (general=%s)\n%s' %
                                  (slug, general, output))
                    self.assertNotIn('RecursionError', output, '%s (general=%s)\n%s' %
                                     (slug, general, output))


if __name__ == '__main__':
    unittest.main()
