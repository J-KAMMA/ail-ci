"""A str method fetched as a value, against CPython 3.12.

`f = "ab".upper` is a bound method in CPython. Both builds used to compile it and
then raise `AttributeError: 'str' object has no attribute 'upper'` at run time.
The general path now refuses the construct by name (DIFFERENCES
C?-job-pre45-10241007-1) instead of emitting code that fails at run time. Calls
such as `"ab".upper()` and instance fields named like a str method still work. A class
attribute with such a name (`class C: title = "hi"`, read through a list item, a dict value
or an argument) is a real attribute, not a str method value, and still builds.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None
MARKER = 'C?-job-pre45-10241007-1'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre45-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre45-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(MARKER, message, (name, general, message[-1200:]))
            test.assertIn('str method upper used as a value', message, (name, general, message[-1200:]))


REFUSED = {
    'direct': 'def main():\n    f = "ab".upper\n    print(f())\n\n\nmain()\n',
    'empty': 'def main():\n    f = "".upper\n    print(f())\n\n\nmain()\n',
    'alias': 'def main():\n    s = "ab"\n    t = s\n    f = t.upper\n    print(f())\n\n\nmain()\n',
    'through_argument': ('def take(s):\n    f = s.upper\n    return f()\n\n\ndef main():\n'
                          '    print(take("ab"))\n\n\nmain()\n'),
    'through_list_item': 'def main():\n    xs = ["ab"]\n    f = xs[0].upper\n    print(f())\n\n\nmain()\n',
    'through_dict_value': 'def main():\n    d = {"k": "ab"}\n    f = d["k"].upper\n    print(f())\n\n\nmain()\n',
    'through_attribute': ('class Box:\n    def __init__(self, s: str) -> None:\n        self.s = s\n\n\n'
                           'def main():\n    b = Box("ab")\n    f = b.s.upper\n    print(f())\n\n\nmain()\n'),
}

VALID = {
    'method_calls': ('def main():\n    s = "ab"\n    print("ab".upper())\n    print("".lower())\n'
                     '    print(s.upper(), s.title())\n    words = ["Banana", "apple"]\n'
                     '    print(sorted(words, key=str.lower))\n\n\nmain()\n'),
    'field_named_title': ('class Box:\n    def __init__(self, title: str) -> None:\n        self.title = title\n\n\n'
                           'def main():\n    b = Box("ab")\n    print(b.title)\n    print(b.title.upper())\n\n\nmain()\n'),
    'user_method_upper': ('class C:\n    def __init__(self, s: str) -> None:\n        self.s = s\n\n'
                           '    def upper(self) -> str:\n        return self.s + "!"\n\n\n'
                           'def main():\n    c = C("ab")\n    print(c.upper())\n\n\nmain()\n'),
    'class_attr_dict': ('class C:\n    title = "hi"\n\n\ndef main():\n'
                         '    d = {"k": C()}\n    print(d["k"].title)\n\n\nmain()\n'),
    'class_attr_list': ('class C:\n    title = "hi"\n\n\ndef main():\n'
                         '    xs = [C()]\n    print(xs[0].title)\n\n\nmain()\n'),
    'class_attr_argument': ('class C:\n    format = "hi"\n\n\ndef show(c):\n    print(c.format)\n\n\n'
                             'def main():\n    show(C())\n\n\nmain()\n'),
    'class_attr_inherited': ('class B:\n    title = "hi"\n\n\nclass C(B):\n    pass\n\n\n'
                              'def main():\n    d = {"k": C()}\n    xs = [C()]\n'
                              '    print(d["k"].title, xs[0].title)\n\n\nmain()\n'),
    'class_attr_annotated': ('class C:\n    title: str = "hi"\n    format: str = "fmt"\n\n\n'
                              'def show(c):\n    print(c.title, c.format)\n\n\n'
                              'def main():\n    show(C())\n    print(C.title)\n\n\nmain()\n'),
    'field_named_upper': ('class C:\n    def __init__(self, upper: str) -> None:\n        self.upper = upper\n\n\n'
                           'def show(c):\n    print(c.upper)\n\n\n'
                           'def main():\n    show(C("field"))\n    xs = [C("list")]\n'
                           '    print(xs[0].upper)\n\n\nmain()\n'),
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Pre45Tests(unittest.TestCase):
    def test_str_method_value_refused(self):
        for name, text in REFUSED.items():
            with self.subTest(name):
                check_refused(self, name, text)

    def test_calls_and_fields_still_work(self):
        for name, text in VALID.items():
            with self.subTest(name):
                check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
