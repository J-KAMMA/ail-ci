"""Deleting a top-level function name (job-pre256).

The pre-existing difference recorded by the pre244 review: `global side; del side; side(1)`
printed the function's result instead of raising `NameError`, because a top-level function is
resolved statically at every call and read site.  The del fix also made a plain module-level
`del side` compile, but the name still resolved to the function (the base build stopped with
`KeyError: 'side'`).  Both shapes are now refused by name at compile time on the general path;
the typed path already refused them.  Deleting a name that an ordinary module-level assignment
(or a local/parameter binding) gives a real slot still matches CPython.
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


class Pre256Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre256-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def refuse(self, slug, text, message):
        with tempfile.TemporaryDirectory(prefix='ail-pre256-') as directory:
            for general in (True, False):
                built, _exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                output = built.stdout + built.stderr
                self.assertNotEqual(built.returncode, 0, '%s (general=%s)\n%s' % (text[:2000], general, output))
                self.assertIn(message, output, '%s (general=%s)\n%s' % (text[:2000], general, output))
                self.assertNotIn('KeyError', output, '%s (general=%s)\n%s' % (text[:2000], general, output))

    def test_global_delete_function_is_refused(self):
        self.refuse('del_global_function', r'''def side(x):
    return x


def f():
    global side
    del side
    print(side(1))


f()
''', 'del on the function name side')

    def test_module_delete_function_is_refused(self):
        self.refuse('del_module_function', r'''def side(x):
    return x


print(side(1))
del side
print(side(2))
''', 'del on the function name side')

    def test_module_delete_function_without_use_is_refused(self):
        self.refuse('del_module_function_only', r'''def side(x):
    return x


del side
print("done")
''', 'del on the function name side')

    def test_function_name_rebound_by_value_can_be_deleted(self):
        self.check('del_rebound_function', r'''def side(x):
    return x


side = 5
del side
print("done")
''')

    def test_local_and_parameter_shadow_can_be_deleted(self):
        self.check('del_local_shadow_function', r'''def side(x):
    return x


def local():
    side = 1
    del side
    try:
        print(side)
    except NameError:
        print("NE local")


def parameter(side):
    del side
    try:
        print(side)
    except NameError:
        print("NE parameter")


local()
parameter(5)
''')


if __name__ == '__main__':
    unittest.main()
