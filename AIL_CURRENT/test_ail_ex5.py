"""ex5: `__file__` is the module's path, as CPython 3.12 binds it.

A merged program has no file at run time, so each read of `__file__` becomes a string constant:
the entry keeps the command-line spelling made absolute (CPython 3.12 does not normalise `.`/`..`
or resolve symlinks), and an imported module gets the absolute file the search path found (CPython
normalises its `sys.path[0]`).  `module.__file__` gives the same value, and a namespace package's
is `None`.  A program that *binds* `__file__` itself is refused by name: a string constant cannot
carry a rebound module global across the merge.

Each check writes one source file, runs it with CPython, then compiles that same file on both
builds (the general path and the default build) and compares stdout and exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def run_cpython(directory, name, text, args=()):
    src = Path(directory) / name
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(Path(name) if args else src)] + list(args),
                          cwd=directory, capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))


def build(directory, name, general, args=None):
    exe = Path(directory) / ('exe' + ('_g' if general else '_d'))
    if exe.exists():
        exe.unlink()
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', CHATGPT, 'compile', *(args or [name]),
                           '--syntax', 'python', '-o', exe.name], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env), exe


class Ex5Tests(unittest.TestCase):
    def check(self, name, text, files=None, args=None):
        """CPython runs `name`; both builds compile the same file and must print the same bytes and exit."""
        with tempfile.TemporaryDirectory(prefix='ail-ex5-') as directory:
            for extra, body in (files or {}).items():
                (Path(directory) / extra).parent.mkdir(parents=True, exist_ok=True)
                (Path(directory) / extra).write_text(body, encoding='utf-8')
            want = run_cpython(directory, name, text)
            for general in (True, False):
                built, exe = build(directory, name, general)
                self.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_minimal_reproducer(self):
        self.check('probe.py', '''print(__file__)
print(type(__file__).__name__, isinstance(__file__, str), len(__file__) > 0)
import os.path
print(os.path.basename(__file__), os.path.dirname(__file__).startswith('/'))
''')

    def test_differing_command_line_spellings(self):
        # CPython 3.12 keeps the spelling: cwd-prefixed without normalising `.`/`..`; a symlink is
        # not resolved either.  The entry's constant must be that same string.
        with tempfile.TemporaryDirectory(prefix='ail-ex5-spell-') as directory:
            source = Path(directory) / 'probe.py'
            source.write_text('print(__file__)\n', encoding='utf-8')
            (Path(directory) / 'sub').mkdir()
            os.symlink('probe.py', str(Path(directory) / 'link.py'))
            for spelling in ('probe.py', './probe.py', './sub/../probe.py', 'link.py'):
                want = subprocess.run([sys.executable, '-B', spelling], cwd=directory,
                                      capture_output=True, timeout=120)
                for general in (True, False):
                    built, exe = build(directory, 'probe.py', general, args=[spelling])
                    self.assertEqual(built.returncode, 0, (spelling, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
                    self.assertEqual(got.stdout, want.stdout, (spelling, general))

    def test_imported_module_and_routes(self):
        util = 'HERE = __file__\n\ndef where():\n    return __file__\n'
        text = '''import util

print(util.HERE)
print(util.where())
print(util.__file__)
print(util.HERE == util.__file__)
print(__file__ != util.HERE)
print(f"file is {__file__}")
box = [__file__]
table = {"p": __file__}
print(box[0] == __file__, table["p"] == __file__)
class C:
    where = __file__
print(C.where == __file__)
'''
        self.check('main.py', text, files={'util.py': util})

    def test_namespace_package_file_is_none(self):
        self.check('main.py', '''import ns.util

print(ns.util.VALUE, ns.__file__ is None, ns.util.__file__.endswith('/ns/util.py'))
''', files={'ns/util.py': 'VALUE = 1\n'})

    def test_binding_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex5-bind-') as directory:
            source = Path(directory) / 'bind.py'
            source.write_text('__file__ = "changed"\nprint(__file__)\n', encoding='utf-8')
            for general in (True, False):
                built, _ = build(directory, 'bind.py', general)
                self.assertNotEqual(built.returncode, 0, general)
                self.assertIn('`__file__` is assigned or shadowed', built.stdout + built.stderr)


if __name__ == '__main__':
    unittest.main()
