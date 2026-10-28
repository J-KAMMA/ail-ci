"""`__file__` of Python-syntax programs and of the modules they import matches CPython 3.12.

The entry program sees the absolute path it was built from, as CPython does for a script; an imported
module sees its own path, both as a bare name and as `module.__file__`; a function that returns
`__file__` returns its module's path.  Each program is built with the default build and with the
general path forced (`AIL_UNIFIED_FORCE=1`), and both must print what CPython prints and exit the same.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def run(command, directory):
    return subprocess.run(command, cwd=directory, capture_output=True, timeout=120)


def cpython(directory, source):
    done = run([sys.executable, '-B', str(source)], directory)
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, mode, argument=None):
    source = Path(directory, name + '.py')
    exe = Path(directory, 'exe_' + name.replace('/', '_') + ('_g' if mode == 'general' else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', argument or source.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, done


class FilePathTests(unittest.TestCase):
    def check(self, name, text, files=()):
        with tempfile.TemporaryDirectory() as directory:
            for filename, content in files:
                path = Path(directory, filename)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding='utf-8')
            source = Path(directory, name + '.py')
            source.write_text(text, encoding='utf-8')
            want, want_status = cpython(directory, source)
            for mode in ('default', 'general'):
                with self.subTest(mode=mode):
                    exe, built = build(directory, name, mode)
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                    got = run([str(exe)], directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)
                    self.assertEqual(got.returncode, want_status)

    def test_language_example(self):
        example = ROOT / 'language_examples' / 'file_path.py'
        self.check('file_path', example.read_text(encoding='utf-8'))

    def test_entry_path(self):
        self.check('entry', '''from pathlib import Path

SOURCE = Path(__file__)
print(SOURCE.name)
print(SOURCE.suffix)
print(SOURCE.resolve().name)
print(__file__ == str(SOURCE))
''')

    def test_argument_spelling(self):
        for argument in ('./sub/main.py', 'sub//main.py'):
            with self.subTest(argument=argument), tempfile.TemporaryDirectory() as directory:
                path = Path(directory, 'sub', 'main.py')
                path.parent.mkdir()
                path.write_text('print(__file__)\n', encoding='utf-8')
                want, want_status = cpython(directory, argument)
                for mode in ('default', 'general'):
                    with self.subTest(mode=mode):
                        exe, built = build(directory, 'sub/main', mode, argument=argument)
                        self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                        got = run([str(exe)], directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)
                        self.assertEqual(got.returncode, want_status)

    def test_shadowed_name(self):
        self.check('shadow', '''def show(__file__):
    print(__file__)
show("argument")
''')

    def test_assigned_entry_name(self):
        main = '''from pathlib import Path
import helper
__file__ = "saved"
print(__file__)
print(Path(helper.where()).name)
'''
        self.check('assigned', main, (('helper.py', 'def where():\n    return __file__\n'),))

    def test_imported_modules(self):
        main = '''from pathlib import Path
import helper
from pkg import tool

print(Path(__file__).name)
print(Path(__file__).resolve().name)
print(Path(helper.where()).name)
print(Path(helper.__file__).name)
print(tool.NAME)
print(Path(tool.__file__).name)
'''
        files = (
            ('helper.py', 'def where():\n    return __file__\n'),
            ('pkg/__init__.py', ''),
            ('pkg/tool.py', 'from pathlib import Path\nSOURCE = __file__\nNAME = Path(SOURCE).name\n'),
        )
        self.check('main', main, files)


if __name__ == '__main__':
    unittest.main()
