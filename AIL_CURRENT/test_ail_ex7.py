"""ex7: `__file__` is the source path CPython 3.12 reports, on both builds.

CPython 3.12 makes the main script's `__file__` absolute, and an imported module's `__file__` is
the file found on the search path.  The compiler used to refuse the name ("the program is built
into one executable, so a module has no file ..."), which stopped five Python-syntax examples
under `language_examples` before their real blocker.  A module that never rebinds `__file__` now
gets its absolute source path as a string constant, in the entry file and in every merged local
module; a module that both rebinds and reads it is refused by name, since the compiler cannot
follow the rebinding (CPython keeps the assigned value, and the compiler's constant would not).
`lib.__file__` stays refused: a merged module is not a module object.

The reproducer is ordinary Python: CPython runs it as the oracle, and each build prints the same
bytes and exits with the same code.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REBIND = 'both rebinds __file__'
ATTRIBUTE = '__file__ is not available'

SINGLE = '''
def show(value):
    print(value)
show(__file__)
print([__file__][0])
print({"k": __file__}["k"])
class Box:
    pass
box = Box()
box.p = __file__
print(box.p)
class Holder:
    p = __file__
    tail = __file__.rsplit("/", 1)[-1]
print(Holder.p)
print(Holder.tail)
def here():
    return __file__
print(here() == __file__)
print((lambda: __file__)())
print(type(__file__).__name__, __file__.endswith(".py"))
print(f"{__file__!r}")
'''

LIB = '''
def where():
    return __file__
NAME = __name__
'''

PACKAGE = 'ROOT = __file__\n'
PACKAGE_MOD = '''
def where():
    return __file__
'''

ENTRY = '''
import lib
from pkg import mod as nested
import pkg
print(__file__)
print(lib.where())
print(lib.NAME)
print(nested.where())
print(pkg.ROOT)
'''

REBOUND = '''
__file__ = "x"
print(__file__)
'''


def cpython(directory, entry):
    done = subprocess.run([sys.executable, '-B', entry], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, entry, general):
    name = 'exe_' + entry.replace('.py', '') + ('_g' if general else '_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', CHATGPT, 'compile', entry, '--syntax', 'python',
                           '-o', name], cwd=directory, capture_output=True, text=True,
                          timeout=900, env=env), name


class FilePathTests(unittest.TestCase):
    def check_matching(self, files, entry):
        with tempfile.TemporaryDirectory(prefix='ail-ex7-') as directory:
            base = Path(directory)
            for name, text in files.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            expected, code = cpython(directory, entry)
            self.assertEqual(code, 0)
            for general in (True, False):
                built, name = build(directory, entry, general)
                self.assertEqual(built.returncode, 0, built.stderr[-2000:])
                done = subprocess.run([str(base / name)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(done.returncode, code, done.stderr[-2000:])
                self.assertEqual(done.stdout, expected)

    def check_refused(self, files, entry, needle):
        with tempfile.TemporaryDirectory(prefix='ail-ex7-') as directory:
            base = Path(directory)
            for name, text in files.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            for general in (True, False):
                built, _ = build(directory, entry, general)
                self.assertEqual(built.returncode, 2, built.stdout + built.stderr)
                self.assertIn(needle, built.stderr)

    def test_single_file(self):
        self.check_matching({'single.py': SINGLE}, 'single.py')

    def test_local_modules(self):
        self.check_matching({'lib.py': LIB, 'pkg/__init__.py': PACKAGE,
                             'pkg/mod.py': PACKAGE_MOD, 'entry.py': ENTRY}, 'entry.py')

    def test_rebinding_is_refused_by_name(self):
        self.check_refused({'rebound.py': REBOUND}, 'rebound.py', REBIND)

    def test_module_attribute_stays_refused(self):
        self.check_refused({'lib.py': LIB, 'entry.py': 'import lib\nprint(lib.__file__)\n'},
                           'entry.py', ATTRIBUTE)


if __name__ == '__main__':
    unittest.main()
