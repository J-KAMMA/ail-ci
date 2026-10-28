# -*- coding: utf-8 -*-
"""ex21: `@export` from ail_ffi is the identity on CPython and no longer refused.

`ail build --lib` already lowers the functions marked by ``@export``; a plain ``ail compile``
used to refuse the decorator with "not in the subset".  The decorator now compiles as the
identity it is on CPython, so ``geometry.py`` builds and prints the same line as CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

SOURCE = '''from ail_ffi import export

@export
def add(a: int, b: int) -> int:
    return a + b

@export
def shout(text: str) -> str:
    return text.upper() + "!"

print(add(2, 3), shout("héllo"))
'''

BOUNDARIES = '''from dataclasses import dataclass
from ail_ffi import export

@dataclass
class Pair:
    left: int
    right: float
    flag: bool

@export()
def total(values: list[int]) -> int:
    out = 0
    for value in values:
        out += value
    return out

@export
def halves(values: list[float]) -> list[float]:
    return [value / 2.0 for value in values]

@export
def weight(p: Pair) -> float:
    return p.left * p.right if p.flag else 0.0

@export
def note(n: int) -> None:
    if n < 0:
        raise ValueError("negative")

values = [total([1, 2, 3])]
table = {'h': halves([1.0, 2.0])}
print(values[0], table['h'], weight(Pair(2, 1.5, True)), note(1))
'''

INVALID = (
    'from ail_ffi import export\n\n@export\ndef add(a: int, b: int):\n    return a + b\n\nprint(add(2, 3))\n',
    'from ail_ffi import export\n\n@export\ndef inc(x: int = 1) -> int:\n    return x + 1\n\nprint(inc())\n',
    'from ail_ffi import export\n\n@export\ndef keys(d: dict) -> int:\n    return len(d)\n\nprint(keys({"a": 1}))\n',
)


def python_path():
    old = os.environ.get('PYTHONPATH')
    return str(ROOT) if not old else str(ROOT) + os.pathsep + old


def build(directory, source, general):
    path = Path(directory, 'p.py')
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, 'exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env)
    return done, exe


def cpython(directory, source):
    path = Path(directory, 'ref.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=python_path())
    return subprocess.run([sys.executable, str(path)], cwd=directory,
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class ExportDecorator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex21-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_both(self, source):
        expected = cpython(self.dir, source)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for general in (False, True):
            built, exe = build(self.dir, source, general)
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)

    def test_export_identity_matches_cpython(self):
        self.run_both(SOURCE)

    def test_export_annotation_boundaries_match_cpython(self):
        self.run_both(BOUNDARIES)

    def test_invalid_export_is_refused_named(self):
        for source in INVALID:
            expected = cpython(self.dir, source)
            self.assertNotEqual(expected.returncode, 0)
            for general in (False, True):
                built, exe = build(self.dir, source, general)
                where = 'general' if general else 'default'
                self.assertNotEqual(built.returncode, 0, where + ':\n' + source)
                self.assertIn('@export', built.stdout + built.stderr, where)


if __name__ == '__main__':
    unittest.main()
