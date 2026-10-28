"""pre410: a class body annotation that reads the class name is refused by name.

The pre403 review recorded as pre-existing that a binding in an unrelated function or in a
constant-false branch hid the class-name read: ``def f(): C = 5`` / ``if False: C = 5`` followed
by ``class C: x: C = 1`` printed ``1`` on both builds where CPython evaluates the annotation
while the class body runs and raises ``NameError``.  A class body annotation that reads the class
name is now refused by name at compile time on both builds unless the name is bound in the class
body before the read, or in an enclosing module or function scope before the class.  A type
parameter with the class name, a comprehension target or lambda parameter inside the annotation,
a same-line binding, a string annotation and ``from __future__ import annotations`` keep
CPython's result.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'a class body annotation reads the class name C before it is bound'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


REFUSED = {
    'unrelated_function_binding': '''
def f():
    C = 5
class C:
    x: C = 1
print(C.x)
''',
    'constant_false_binding': '''
if False:
    C = 5
class C:
    x: C = 1
print(C.x)
''',
    'empty_for_binding': '''
for i in []:
    C = 5
class C:
    x: C = 1
print(C.x)
''',
    'direct': '''
class C:
    x: C = 1
print(C.x)
''',
    'annotation_only': '''
class C:
    x: C
print("ok")
''',
    'method_parameter': '''
class C:
    def m(self, x: C):
        return x
print("ok")
''',
    'method_return': '''
class C:
    def m(self) -> C:
        return self
print("ok")
''',
    'later_binding': '''
class C:
    x: C = 1
    C = 5
print(C.x)
''',
    'comprehension_iterable': '''
class C:
    x: [v for v in C] = 1
print(C.x)
''',
    'lambda_default': '''
class C:
    x: (lambda v=C: v)() = 1
print(C.x)
''',
}

MATCHING = {
    'prior_module_binding': '''
C = 5
class C:
    x: C = 1
print(C.x)
''',
    'module_if_true_binding': '''
if True:
    C = 5
class C:
    x: C = 1
print(C.x)
''',
    'earlier_class_binding': '''
class C:
    C = 5
    x: C = 1
print(C.x)
''',
    'same_line_binding': '''
class C:
    C = 5; x: C = 1
print(C.x)
''',
    'walrus_binding': '''
class C:
    x: ((C := 1), C)[1] = 5
print(C.x)
''',
    'type_parameter': '''
class C[C]:
    x: C = 1
print(C.x)
''',
    'comprehension_target_shadow': '''
class C:
    x: [C for C in range(3)][0] = 1
print(C.x)
''',
    'lambda_parameter_shadow': '''
class C:
    x: (lambda C: C)(7) = 1
print(C.x)
''',
    'string_annotation': '''
class C:
    x: "C" = 1
print(C.x)
''',
    'future_annotations': '''
from __future__ import annotations
class C:
    x: C = 1
print(C.x)
''',
    'no_class_name_read': '''
class C:
    x: int = 1
print(C.x)
''',
}


class Pre410Tests(unittest.TestCase):
    def test_class_name_read_in_annotation_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre410-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))

    def test_visible_bindings_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre410-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
