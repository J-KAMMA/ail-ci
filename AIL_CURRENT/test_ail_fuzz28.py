"""Differential round 28: a class-body comprehension read through the class.

A class-body list/set/dict comprehension is a class attribute, and CPython's `C.ys` reads it.
Since pre304 a class body has its own namespace, so an earlier class attribute is visible to a
comprehension's outermost iterable and the read evaluates the comprehension on both builds. An
instance read of the same attribute, the comprehension variable shadowing the class's name, and
literal class attributes keep behaving as CPython does.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

CLASS_READ = r'''class C:
    x = 3
    ys = [i for i in range(x)]
    zs = {i: i for i in range(x)}
    ws = {i for i in range(x)}


def main():
    print(C.ys, C.zs, C.ws)


main()
'''

CLASS_INSTANCE = r'''class C:
    x = 3
    ys = [i for i in range(3)]
    zs = {i: i for i in range(2)}


def main():
    o = C()
    print(o.ys, o.zs, o.x)


main()
'''

CLASS_SHADOW = r'''class C:
    x = 3
    ys = [x for x in range(4)]
    zs = [i * 2 for i in range(3)]


def main():
    o = C()
    print(o.ys, o.zs, o.x)


main()
'''

LITERAL_READ = r'''class C:
    i = -7
    f = 1.5
    s = "ab"
    b = True
    big = 1000000000000000000


def main():
    print(C.i, C.f, C.s, C.b, C.big)
    o = C()
    print(o.i, o.f, o.s, o.b, o.big)


main()
'''


def cpython(directory, name, text):
    source = Path(directory, name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    run = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                         env=dict(os.environ, PYTHONUTF8='1'))
    return (run.stdout.replace(b'\r\n', b'\n'), run.returncode), run.stderr


def build_and_run(directory, name, text, general):
    source = Path(directory, name + '.ail')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory, 'exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', source.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900,
                           env=env)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')


class Fuzz28Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz28-') as directory:
            want, err = cpython(directory, slug, text)
            self.assertEqual(want[1], 0, err)
            for general in (True, False):
                got, build = build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build[-3000:]))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (text[:2000], general, build[-3000:]))

    def test_class_comprehension_read_through_class(self):
        self.check('class_read', CLASS_READ)

    def test_class_comprehension_read_through_instance(self):
        self.check('class_instance', CLASS_INSTANCE)

    def test_comprehension_variable_shadows_class_name(self):
        self.check('class_shadow', CLASS_SHADOW)

    def test_literal_class_attributes(self):
        self.check('literal_read', LITERAL_READ)


if __name__ == '__main__':
    unittest.main()
