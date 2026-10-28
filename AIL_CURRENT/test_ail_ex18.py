"""Ex18: CPython's implicit module-level `__file__` in a Python-syntax program.

`__file__` used to be refused by name ("a module has no file").  It is now the absolute path of
the source file recorded at build time, set before the module body runs exactly as CPython 3.12
sets it: a read before a user assignment sees the path, a later assignment rebinds it, a
function-local parameter shadows it, and an imported module has its own path (None for a
namespace package).  The general path gets a normal module-level assignment, so the typed path
that turns module statements into locals cannot hide it.  Every program is compared with CPython
on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SINGLE = r'''first = __file__
xs = [__file__]
d = {'f': __file__}


class Box:
    pass


b = Box()
b.f = __file__


def show():
    print('fn', __file__)


def local(__file__):
    print('local', __file__)


print('entry', first)
print('routes', xs[0], d['f'], b.f)
__file__ = 'changed'
print('rebound', __file__)
show()
local('arg')
'''

HELPER = r'''print('helper-first', __file__)
FIRST = __file__
__file__ = 'changed'
SECOND = __file__


def show():
    print('helper-fn', __file__)
'''

MULTI = r'''import helper
import helper as h
from helper import __file__ as imported

print('entry', __file__)
print('module', h.__file__)
print('values', helper.FIRST, helper.SECOND, imported)
helper.show()
'''

DELETED = r'''__file__ = 'set'
del __file__
try:
    print(__file__)
except NameError as error:
    print(type(error).__name__, error)
'''

DELETED_HELPER = r'''X = 1
del __file__
'''

DELETED_IMPORT = r'''import helper
print(helper.X)
try:
    print(helper.__file__)
except AttributeError as error:
    print(type(error).__name__, error)
'''

PATH_ONLY = "print(repr(__file__))\n"

FROM_ONLY = r'''from helper import __file__ as f

print('from', f)
'''


def cpython(directory, files, script='main.py'):
    for name, text in files.items():
        (Path(directory) / name).write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', script], cwd=directory,
                          capture_output=True, timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def build_and_run(directory, files, general, script='main.py'):
    for name, text in files.items():
        (Path(directory) / name).write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_g' if general else 'exe_d')
    if exe.exists() or exe.is_symlink():
        exe.unlink()
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', script,
                            '--syntax', 'python', '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class SourceFileDunderTests(unittest.TestCase):
    def check(self, slug, files, script='main.py'):
        with tempfile.TemporaryDirectory(prefix='ail-ex18-') as directory:
            want, want_rc, err = cpython(directory, files, script)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = build_and_run(directory, files, general, script)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (slug, general, build_err))
            return want

    def test_single_file_routes(self):
        out = self.check('single', {'main.py': SINGLE}).decode()
        self.assertIn('entry /', out)
        self.assertIn('rebound changed', out)
        self.assertIn('fn changed', out)
        self.assertIn('local arg', out)

    def test_imported_module_has_its_own_path(self):
        out = self.check('multi', {'main.py': MULTI, 'helper.py': HELPER}).decode()
        self.assertIn('entry /', out)
        self.assertIn('helper-first /', out)
        self.assertIn('values /', out)
        self.assertIn('helper-fn changed', out)

    def test_from_import_of_a_module_that_only_has_the_implicit_binding(self):
        out = self.check('from-only', {'main.py': FROM_ONLY, 'helper.py': 'X = 1\n'}).decode()
        self.assertIn('from /', out)
        self.assertIn('helper.py', out)

    def test_deleted_name(self):
        out = self.check('deleted', {'main.py': DELETED}).decode()
        self.assertIn("NameError name '__file__' is not defined", out)

    def test_imported_module_deleting_its_file_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex18-') as directory:
            for general in (True, False):
                got, build_err = build_and_run(directory, {'main.py': DELETED_IMPORT,
                                                           'helper.py': DELETED_HELPER}, general)
                self.assertIsNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertIn('`del __file__` in an imported module', build_err)

    def test_entry_keeps_the_spelling_it_was_invoked_with(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex18-') as directory:
            os.mkdir(Path(directory) / 'sub')
            os.symlink('.', str(Path(directory) / 'link'))
            for script in ('./main.py', 'sub/../main.py', 'link/main.py'):
                want, want_rc, err = cpython(directory, {'main.py': PATH_ONLY}, script)
                self.assertEqual(want_rc, 0, err)
                for general in (True, False):
                    got, build_err = build_and_run(directory, {'main.py': PATH_ONLY}, general, script)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (script, general, build_err))
                    self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (script, general, build_err))
            # the merge path must use the same spelling for the entry, while the imported module
            # keeps its canonical path
            want, want_rc, err = cpython(directory, {'main.py': MULTI, 'helper.py': HELPER}, './main.py')
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = build_and_run(directory, {'main.py': MULTI, 'helper.py': HELPER},
                                               general, './main.py')
                self.assertIsNotNone(got, 'merge (general=%s)\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'merge (general=%s)\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
