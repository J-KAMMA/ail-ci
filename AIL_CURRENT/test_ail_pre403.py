"""pre403: a class body annotation that reads the class name is refused by name.

The pre381 review recorded as pre-existing that ``class C: x: C = 1`` printed ``1`` on both
builds where CPython evaluates the annotation while the class body runs and raises ``NameError``
(the class name is bound only after the body).  AIL does not read annotations, so the read was
lost.  A class body annotation that reads the class name before any earlier binding of that name
is now refused by name at compile time on both builds, including a method parameter or return
annotation and a read reached through a subscript, a list item, a dict value, an argument or an
attribute.  A plain/type annotation, a string annotation, ``from __future__ import
annotations`` and an earlier module or class-body binding of the name keep CPython's result; a
later binding after the read still leaves the read refused.
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
    'subscript': '''
class C:
    x: list[C] = []
print(C.x)
''',
    'list_item': '''
class C:
    x: [C][0] = 1
print(C.x)
''',
    'dict_value': '''
class C:
    x: {"k": C}["k"] = 1
print(C.x)
''',
    'argument': '''
def f(v):
    return v
class C:
    x: f(C) = 1
print(C.x)
''',
    'attribute': '''
class C:
    x: C.__name__ = 1
print(C.x)
''',
    'later_binding': '''
class C:
    x: C = 1
    C = 5
print(C.x)
''',
}

MATCHING = {
    'plain': '''
class C:
    x: int = 1
print(C.x)
''',
    'other_class': '''
class D:
    pass
class C:
    x: D = 1
print(C.x)
''',
    'string': '''
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
    'prior_module_binding': '''
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
    'other_route': '''
class C:
    A = 1
    x: list[int] = [A]
print(C.x)
''',
    'constant_annotations': '''
class C:
    x: () = 1
    y: -1 = 2
print(C.x, C.y)
''',
}


class Pre403Tests(unittest.TestCase):
    def test_class_name_read_in_annotation_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre403-') as directory:
            for slug, text in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(MESSAGE, output, (slug, general, output[-1200:]))

    def test_annotations_without_a_self_read_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre403-') as directory:
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
