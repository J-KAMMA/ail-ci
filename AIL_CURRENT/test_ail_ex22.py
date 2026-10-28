"""ex22: `__file__` names the source file a Python-syntax program was built from.

The Python-syntax examples under `language_examples` that read `__file__` (directly, or through
a sibling module such as `row_locals_compare`) were refused with `__file__ is not available: the
program is built into one executable, so a module has no file`.  A read-only `__file__` now folds
to the module's build-time path: the entry file for a single-file program, and each imported
module's own file for a merged program.  A module that binds or deletes `__file__` itself keeps
the ordinary name rules; an attribute read on such a module stays a named refusal.

Programs are built with the general path forced and with the default build; stdout and the exit
status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, src):
    return subprocess.run([sys.executable, '-B', str(src)], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, src, general, ail_path=None):
    exe = Path(directory) / ('exe_' + src.stem + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_PATH', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    if ail_path is not None:
        env['AIL_PATH'] = str(ail_path)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', str(src), '--syntax', 'python',
                                '-o', str(exe)], cwd=directory, capture_output=True, text=True, timeout=900,
                               env=env)


class Ex22Tests(unittest.TestCase):
    def same(self, files, entry='main.py', ail_path=None, run_dir=None, expect_success=True):
        with tempfile.TemporaryDirectory(prefix='ail-ex22-') as directory:
            directory = Path(directory)
            for name, text in files.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            src = directory / entry
            want = cpython(directory, src)
            if expect_success:
                self.assertEqual(want.returncode, 0, want.stderr.decode())
                self.assertTrue(want.stdout)
            where = directory
            if run_dir is not None:
                where = directory / run_dir
                where.mkdir()
            for general in (True, False):
                exe, built = build(directory, src, general, ail_path=directory / ail_path if ail_path else None)
                self.assertEqual(built.returncode, 0, (entry, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], cwd=where, capture_output=True, timeout=120)
                self.assertEqual(got.returncode, want.returncode, (entry, general, got.stderr[-800:]))
                self.assertEqual(got.stdout, want.stdout, (entry, general, got.stderr[-800:]))
            return want.stdout.decode()

    def refused(self, files, *needles, entry='main.py', ail_path=None):
        with tempfile.TemporaryDirectory(prefix='ail-ex22-') as directory:
            directory = Path(directory)
            for name, text in files.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            for general in (True, False):
                exe, built = build(directory, directory / entry, general,
                                   ail_path=directory / ail_path if ail_path else None)
                self.assertNotEqual(built.returncode, 0, (entry, general, built.stdout + built.stderr))
                self.assertFalse(exe.exists())
                self.assertNotIn('Traceback', built.stderr)
                for needle in needles:
                    self.assertIn(needle, built.stderr)
            return built.stderr

    def test_a_single_file_reads_its_own_path(self):
        out = self.same({'main.py': 'print(__file__)\n'}, run_dir='elsewhere')
        self.assertTrue(out.endswith('/main.py\n'), out)

    def test_path_helpers_and_the_source_text(self):
        out = self.same({'main.py': '''from pathlib import Path
print(Path(__file__).name)
print(Path(__file__).resolve().parent.name)
print(Path(__file__).read_text().splitlines()[0])
'''}, run_dir='elsewhere')
        self.assertIn('from pathlib import Path\n', out)

    def test_values_reach_code_through_a_list_dict_attribute_and_argument(self):
        self.same({'main.py': '''class Box:
    pass
b = Box()
b.f = __file__
d = {'f': __file__}
xs = [__file__]


def echo(x):
    print(x)


echo(__file__)
echo(d['f'])
echo(xs[0])
echo(b.f)
print(f"{__file__}!")
'''})

    def test_an_imported_module_has_its_own_file(self):
        out = self.same({
            'helper.py': '''def where():
    return __file__
''',
            'main.py': '''import helper
print(helper.__file__)
print(helper.where())
print(__file__)
'''}, ail_path='.')
        self.assertIn('/helper.py\n', out)

    def test_a_package_and_a_namespace_package(self):
        out = self.same({
            'pkg/__init__.py': '''def where():
    return __file__
''',
            'nsmod/portion.py': 'VALUE = 1\n',
            'main.py': '''import pkg
import nsmod
print(pkg.__file__)
print(pkg.where())
print(nsmod.__file__)
'''}, ail_path='.')
        self.assertIn('/pkg/__init__.py\n', out)
        self.assertTrue(out.endswith('None\n'), out)

    def test_a_module_that_binds_file_keeps_the_ordinary_rules(self):
        self.same({'main.py': "__file__ = 'custom'\nprint(__file__)\n"})
        self.refused({'helper.py': "__file__ = 'custom'\n", 'main.py': 'import helper\nprint(helper.__file__)\n'},
                     'helper.__file__ is not available', ail_path='.')

    def test_deleting_file_after_a_read(self):
        out = self.same({'main.py': 'x = __file__\ndel __file__\nprint(x)\n'})
        self.assertTrue(out.endswith('/main.py\n'), out)

    def test_a_parameter_or_lambda_argument_shadows_the_path(self):
        self.same({'main.py': '''def f(__file__):
    return __file__
print(f('arg-value'))
print(__file__)
g = lambda __file__: __file__
print(g('lambda-value'))
print(__file__)
'''})

    def test_an_except_alias_keeps_the_ordinary_name_rules(self):
        self.same({'main.py': '''try:
    raise ValueError('boom')
except ValueError as __file__:
    print(__file__)
print(__file__)
'''}, expect_success=False)

    def test_a_read_before_a_later_assignment_sees_the_path(self):
        self.same({'main.py': '''def f():
    return __file__
print(f())
__file__ = 'custom'
print(__file__)
'''})
        self.same({'main.py': '''def g():
    global __file__
    __file__ = 'custom'
print(__file__)
g()
print(__file__)
'''})

    def test_an_imported_module_reads_before_rebinding_file(self):
        self.same({
            'helper.py': '''def f():
    return __file__
print(f())
__file__ = 'custom'
print(__file__)
''',
            'main.py': 'import helper\n'}, ail_path='.')

    def test_a_local_binding_does_not_hide_the_module_path(self):
        self.same({
            'helper.py': '''def f():
    __file__ = 'local'
    return __file__
print(f())
print(__file__)
''',
            'main.py': 'import helper\n'}, ail_path='.')

    def test_from_an_imported_module_file_when_it_binds_one(self):
        self.same({'helper.py': "__file__ = 'custom'\n",
                   'main.py': 'from helper import __file__\nprint(__file__)\n'}, ail_path='.')

    def test_assigning_a_module_file_attribute_is_refused_by_name(self):
        self.refused({'helper.py': 'X = 1\n',
                      'main.py': "import helper\nhelper.__file__ = 'Z'\nprint(helper.__file__)\n"},
                     'helper.__file__` is assigned', ail_path='.')


if __name__ == '__main__':
    unittest.main()
