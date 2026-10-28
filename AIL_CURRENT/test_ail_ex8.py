"""ex8: `__file__` is the module's absolute source path, as CPython binds it.

The Python front end refused every read of `__file__` ("name '__file__' is not defined"),
which was the first blocker for five programs in `language_examples` (the row research scripts
locate their sibling files with `Path(__file__)`).  Each module text now replaces a read of
`__file__` by the absolute path of the file it came from; an imported module and a package get
their own path, and `m.__file__` follows the same rule.  A module that binds the name itself
(an assignment, a parameter, an import alias, a loop or `except` target, `global`/`nonlocal`)
is left exactly as written, so its own binding still wins.

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

ROUTES = '''from pathlib import Path

print(__file__)
print(Path(__file__).is_absolute())
print(Path(__file__).name)
print(Path(__file__).parent.name)
print(Path(__file__).resolve() == Path(__file__))


def show():
    return __file__


def show_arg(value):
    print(value)


print(show())
show_arg(__file__)
items = [__file__]
print(items[0])


class Box:
    pass


box = Box()
box.path = __file__
print(box.path)
values = {"path": __file__}
print(values["path"])
alias = __file__
print(alias)
print(f"{Path(__file__).suffix}")
'''

IMPORTED = '''import helper
from helper import where
import pkg
import pkg.mod

print(helper.__file__)
print(helper.VALUE)
print(helper.where())
print(where())
print(pkg.__file__)
print(pkg.PKG)
print(pkg.mod.__file__)
print(pkg.mod.mod_where())
print(__file__)
'''

HELPER = '''def where():
    return __file__


VALUE = __file__
'''

PACKAGE = '''PKG = __file__
'''

PACKAGE_MODULE = '''def mod_where():
    return __file__
'''

OWN_BINDING = '''__file__ = "custom"
print(__file__)


def local(__file__):
    return __file__


print(local("parameter"))
'''


def cpython(directory, source):
    return subprocess.run([sys.executable, '-B', source.name], capture_output=True, timeout=120,
                          cwd=directory, env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, source, general):
    exe = Path(directory) / ('exe_' + source.stem + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', source.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


def last_line(data):
    lines = [line for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
    return lines[-1] if lines else ''


class Ex8Tests(unittest.TestCase):
    def check(self, files):
        with tempfile.TemporaryDirectory(prefix='ail-ex8-') as directory:
            root = Path(directory)
            for name, text in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding='utf-8')
            source = root / 'main.py'
            want = cpython(root, source)
            for general in (True, False):
                exe, built = build(root, source, general)
                self.assertEqual(built.returncode, 0, (files.keys(), general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=root)
                self.assertEqual(got.stdout, want.stdout, (files.keys(), general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (files.keys(), general, got.stderr[-800:]))
                self.assertEqual(last_line(got.stderr), last_line(want.stderr),
                                 (files.keys(), general, got.stderr[-800:]))

    def test_file_routes_match_cpython(self):
        self.check({'main.py': ROUTES})

    def test_imported_module_and_package_match_cpython(self):
        self.check({'main.py': IMPORTED, 'helper.py': HELPER,
                    'pkg/__init__.py': PACKAGE, 'pkg/mod.py': PACKAGE_MODULE})

    def test_own_binding_keeps_python_semantics(self):
        self.check({'main.py': OWN_BINDING})


if __name__ == '__main__':
    unittest.main()
