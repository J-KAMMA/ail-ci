"""A Python source that is only definitions plus module constants runs no code, like CPython.

`language_examples/math.ail` is such a file (`LIMIT = 6` and `def sum_to(n)`): CPython prints
nothing and exits 0, and the general path already built the same no-op. The typed path compiled
the functions and then tried to synthesize the array-entry "tool" wrapper, which refused because
the entry function's first parameter is not a sequence. It now emits a no-op `main` for a source
whose top level is definitions plus at least one module constant, with no `main` and no executable
statement. A top-level statement still runs as a script, and a `main` is still the entry point.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

MODULES = {
    'int_entry': '''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'print_entry': '''LIMIT = 6

def show(n):
    print(n)
''',
    'list_entry': '''LIMIT = 6

def count(xs):
    return len(xs)
''',
    'types': '''A = -3
B = 2.5
S = "x"
D = b"y"
L = []
T = ()
M = {}

def f(n):
    return n
''',
    'constant_after': '''def f(n):
    return n + 1

X = 3
''',
    'array_entry': '''X = 0

def f(xs):
    return xs[0]
''',
    'import_and_class': '''import sys
LIMIT = 6

class C:
    x = 1

def f(n):
    return n + 1
''',
}

SCRIPTS = {
    'top_statement': 'LIMIT = 6\nprint(LIMIT)\n',
    'main_entry': 'LIMIT = 6\n\ndef main():\n    print(LIMIT)\n\nmain()\n',
    'side_effect_assignment': 'X = print("side")\n',
}


def cpython(directory, text, name):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(source)], cwd=directory,
                          capture_output=True, timeout=60)


def ail(directory, text, name, general):
    source = Path(directory) / (name + '.ail')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-2000:]
    return subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=60), ''


class ModuleConstantSource(unittest.TestCase):
    def check(self, text, name):
        with tempfile.TemporaryDirectory() as directory:
            expected = cpython(directory, text, name)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for general in (False, True):
                with self.subTest(name=name, general=general):
                    ran, refusal = ail(directory, text, name, general)
                    self.assertIsNotNone(ran, refusal)
                    self.assertEqual((ran.returncode, ran.stdout),
                                     (expected.returncode, expected.stdout), ran.stderr)

    def test_definition_and_constant_only_is_a_no_op(self):
        for name, text in MODULES.items():
            with self.subTest(name=name):
                self.check(text, name)

    def test_scripts_still_run(self):
        for name, text in SCRIPTS.items():
            with self.subTest(name=name):
                self.check(text, name)


if __name__ == '__main__':
    unittest.main()
