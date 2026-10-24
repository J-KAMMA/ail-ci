"""Deleting a class name (fuzz67, pre-existing difference recorded before job pre24).

`class C: pass; del C` made both builds fail with the compiler's own `KeyError: 'C'`:
a class name is read from its dedicated class slot, not from an ordinary frame/global
slot, so `del` cannot clear the binding. The construct is now refused by name at
compile time instead. Deleting ordinary globals, locals, list/dict items and slices is
unchanged and still matches CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env), exe


def _build_and_run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre134Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre134-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refuse(self, slug, text, message):
        with tempfile.TemporaryDirectory(prefix='ail-pre134-') as directory:
            for general in (True, False):
                built, _exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' % (text[:2000], general, output))
                self.assertIn(message, output, '%s (general=%s)\n%s' % (text[:2000], general, output))
                self.assertNotIn('KeyError', output, '%s (general=%s)\n%s' % (text[:2000], general, output))

    def test_delete_class_name_is_refused(self):
        self.refuse('del_class_name', r'''class C:
    pass


del C
print(C)
''', 'del on the class name C')

    def test_delete_class_name_without_use_is_refused(self):
        self.refuse('del_class_only', r'''class C:
    pass


del C
print("done")
''', 'del on the class name C')

    def test_delete_several_class_names_is_refused(self):
        self.refuse('del_two_classes', r'''class C:
    pass


class D(C):
    pass


del C, D
print("done")
''', 'del on the class name C')

    def test_delete_rebound_class_name_is_refused(self):
        self.refuse('del_rebound_class', r'''class C:
    pass


C = 5
del C
print("done")
''', 'del on the class name C')

    def test_delete_class_name_with_global_declaration_is_refused(self):
        self.refuse('del_global_class', r'''class C:
    pass


def drop():
    global C
    del C


drop()
print("done")
''', 'del on the class name C')

    def test_delete_plain_names_and_items(self):
        self.check('del_plain', r'''def local():
    x = 1
    del x
    try:
        print(x)
    except NameError:
        print("NE local")


x = 2
del x
try:
    print(x)
except NameError:
    print("NE global")

xs = [1, 2, 3, 4]
del xs[0]
del xs[1:3]
print(xs)

d = {"a": 1, "b": 2}
del d["a"]
print(d)

local()
''')

    def test_local_shadow_of_a_class_name_can_be_deleted(self):
        self.check('del_local_shadow', r'''class C:
    pass


def local():
    C = 3
    del C


def parameter(C):
    del C


local()
parameter(5)
print("ok")
''')


if __name__ == '__main__':
    unittest.main()
