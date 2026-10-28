"""ex12: a definitions-only Python module builds and matches CPython.

The most common refusal left in `language_examples` was `the first parameter must be the sequence
read from the file`: `math.ail` defines `LIMIT` and `sum_to()` and nothing else, so CPython runs
nothing, but the compiler treated the last function as the program entry and demanded an input
file.  A Python-surface entry whose top level is effect-free definitions, side-effect-free imports, a
docstring and literal module constants now builds with an empty entry point (no output, exit 0).
A class body, a decorator, an annotation or a non-constant default can run code while the module
loads, so those keep the old path rather than dropping the effect.  An import outside the known
side-effect-free modules (for example `this`, which prints the Zen of Python) is refused by name
instead of silently losing its load-time effect.  A script with top-level statements, and the
existing refusal of an uncalled `main()`, are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULES = {
    'sums': '''
LIMIT = 6


def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'docstring_default': '''
"""A module: a docstring, a constant and a constant default."""
LIMIT = 6


def sum_to(n, start=0):
    total = start
    for i in range(n + 1):
        total += i
    return total
''',
    'stdlib_import': '''
import math


def volume(radius):
    return 4.0 / 3.0 * math.pi * radius ** 3
''',
    'safe_imports_alias': '''
import math as m
from collections import Counter
import os.path


def area(radius):
    return m.pi * radius ** 2
''',
}

SCRIPTS = {
    'top_level_call': '''
def bump(value):
    return value + 1


print(bump(2))
''',
}

REFUSED = {
    'uncalled_main': ('''
def main():
    print(7)
''', 'main() is defined but never called'),
    'import_this': ('''
import this


def noop():
    pass
''', "import of 'this' can run code when the module loads"),
    'from_this': ('''
from this import d


def noop():
    pass
''', "import of 'this' can run code when the module loads"),
}


def _run_cpython(directory, source):
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          cwd=directory, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, source, exe, general):
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                           '--syntax', 'python', '-o', str(exe)], cwd=directory, capture_output=True,
                          text=True, timeout=1200, env=env)


def _build_and_run(directory, source, exe, general):
    built = _build(directory, source, exe, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Ex12Tests(unittest.TestCase):
    def test_definitions_only_modules_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex12-') as directory:
            directory = Path(directory)
            for slug, text in {**MODULES, **SCRIPTS}.items():
                source = directory / (slug + '.py')
                source.write_text(text, encoding='utf-8')
                want = _run_cpython(directory, source)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, source, directory / ('exe_%s_%s' % (slug, 'g' if general else 'd')), general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_unsupported_shapes_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex12-main-') as directory:
            directory = Path(directory)
            for slug, (text, expected) in REFUSED.items():
                source = directory / (slug + '.py')
                source.write_text(text, encoding='utf-8')
                for general in (True, False):
                    built = _build(directory, source, directory / ('%s_%s' % (slug, 'g' if general else 'd')), general)
                    self.assertNotEqual(built.returncode, 0, 'general=%s' % general)
                    self.assertIn(expected, built.stdout + built.stderr, 'general=%s' % general)


if __name__ == '__main__':
    unittest.main()
