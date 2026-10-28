"""ex17: `__file__` and the valid `@export` marker in Python-syntax examples.

`__file__` is the absolute path CPython gives a script (and an imported module), so a Python
program can locate a file beside itself; the general path and the typed path both carry it now.
`@export` from `ail_ffi` returns the function unchanged on CPython, so a valid export marker does
not stop the ordinary Python program from being compiled and run.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text, pythonpath=None):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore')
    if pythonpath is not None:
        env['PYTHONPATH'] = str(pythonpath)
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          cwd=directory, env=env)
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + Path(name).stem + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


FILE_PROGRAMS = {
    'file_routes': """from pathlib import Path


def show(value):
    print(value)


a = __file__
print(a == __file__)
print((__file__,)[0])
print([__file__][0])
d = {'k': __file__}
print(d['k'])


class Box:
    pass


b = Box()
b.where = __file__
print(b.where)
show(__file__)
print(Path(__file__).name, Path(__file__).parent == Path(a).parent)
""",
    'file_shadow': "__file__ = 'custom'\nprint(__file__)\n",
    'file_argument': "def show(__file__):\n    print(__file__)\n\nshow('argument')\n",
}

EXPORT_PROGRAMS = {
    'export_basic': """from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def halves(values: list[float]) -> list[float]:
    out = []
    for value in values:
        out.append(value / 2.0)
    return out


print(add(2, 3), halves([1.0, 2.0]))
""",
    'export_alias': """import ail_ffi


@ail_ffi.export
def shout(text: str) -> str:
    return text.upper() + '!'


print(shout('hello'))
""",
}


class Ex17Tests(unittest.TestCase):
    def check_programs(self, programs, pythonpath=None):
        with tempfile.TemporaryDirectory(prefix='ail-ex17-') as directory:
            for slug, text in programs.items():
                want = cpython(directory, slug + '.py', text, pythonpath)
                for general in (True, False):
                    exe, built = build(directory, slug + '.py', text, general)
                    self.assertEqual(built.returncode, 0,
                                     (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1],
                                     (slug, general, got.stderr[-800:]))

    def test_file_constant_matches_cpython(self):
        self.check_programs(FILE_PROGRAMS)

    def test_export_decorator_matches_cpython(self):
        self.check_programs(EXPORT_PROGRAMS, pythonpath=ROOT)

    def test_file_constant_in_imported_module(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex17-import-') as directory:
            helper = """FILE = __file__


def where():
    return __file__
"""
            main = """import helper

print(helper.FILE == helper.where())
print(helper.where().endswith('helper.py'))
print(helper.__file__ == helper.FILE)
print(helper.FILE == __file__)
"""
            Path(directory, 'helper.py').write_text(helper, encoding='utf-8')
            want = cpython(directory, 'main.py', main)
            for general in (True, False):
                exe, built = build(directory, 'main.py', main, general)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 got.stderr[-800:])
                self.assertEqual(got.returncode, want[1], got.stderr[-800:])


if __name__ == '__main__':
    unittest.main()
