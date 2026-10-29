"""`@export` programs outside `ail build --lib` run like CPython on both compiler builds.

`@export` only checks the signature on CPython and returns the function unchanged, so the decorator
can be dropped before a normal build.  The general path used to refuse it as an unknown decorator,
while the typed path ignored its checks; both now share the CPython checks, and a valid program
builds on the default, typed and general paths.  The example `c_export/geometry.py` is the recorded
case, with a small program below as the minimal reproducer.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLE = ROOT / 'language_examples' / 'c_export' / 'geometry.py'

PROGRAM = r'''from dataclasses import dataclass
from ail_ffi import export
import ail_ffi as ffi


@dataclass
class Point:
    x: int
    y: float
    visible: bool


def helper(n: int) -> int:
    return n * n


@export
def add(a: int, b: int) -> int:
    return helper(a) + b


@export()
def length(p: Point) -> float:
    return float(p.x) + p.y


@ffi.export
def total(values: list[int]) -> int:
    return sum(values)


@export
def ping() -> None:
    print('ping')


print(add(1, 2), length(Point(3, 4.5, True)), total([1, 2, 3]))
ping()
'''

INVALID = [
    ('missing result', 'def f(x: int):\n    return 1\n', 'f'),
    ('missing parameter', 'def f(x) -> int:\n    return 1\n', 'f'),
    ('default', 'def f(x: int = 3) -> int:\n    return x\n', 'f'),
    ('star arguments', 'def f(*xs: int) -> int:\n    return 1\n', 'f'),
    ('str list', 'def f(x: list[str]) -> int:\n    return 1\n', 'f'),
    ('plain class parameter', 'def f(p: P) -> int:\n    return 1\n', 'f'),
]

DATACLASS = ('from ail_ffi import export\nfrom dataclasses import dataclass\n'
             '@dataclass\nclass P:\n    x: int\n\n')


def _env():
    env = dict(os.environ, AIL_NO_CACHE='1', PYTHONUTF8='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    return env


def _cpython(source):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONUTF8='1')
    return subprocess.run([sys.executable, '-B', str(source)], capture_output=True, text=True,
                          timeout=120, env=env)


def _build(directory, source, name, mode):
    env = _env()
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    exe = Path(directory) / (name + '_' + mode)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', str(source),
                            '--syntax', 'python', '-o', str(exe)], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=env)
    return built, exe


class ExportOutsideLibraryTests(unittest.TestCase):
    def check(self, name, source, text=None):
        if text is not None:
            source = Path(source)
            source.write_text(text, encoding='utf-8')
        expected = _cpython(source)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for mode in ('default', 'typed', 'general'):
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory(prefix='ail-ex39-') as directory:
                    built, exe = _build(directory, source, name, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual((got.returncode, got.stdout), (expected.returncode, expected.stdout),
                                     got.stderr)

    def test_export_decorator_runs_like_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex39-src-') as directory:
            source = Path(directory) / 'program.py'
            self.check('program', source, PROGRAM)

    def test_geometry_example_runs_like_cpython(self):
        self.check('geometry', EXAMPLE)

    def test_decorator_above_export(self):
        text = ('import functools\nfrom ail_ffi import export\n\n'
                '@functools.lru_cache\n@export\ndef f(x: int) -> int:\n    return x + 1\n\n'
                'print(f(2), f(2))\n')
        with tempfile.TemporaryDirectory(prefix='ail-ex39-wrapped-') as directory:
            source = Path(directory) / 'wrapped.py'
            self.check('wrapped', source, text)

    def test_bad_export_is_refused_by_both_builds(self):
        header = 'from ail_ffi import export\n\n'
        cases = [(label, header + '@export\n' + body, function) for label, body, function in INVALID]
        cases.append(('dataclass result', DATACLASS + '@export\ndef f(x: int) -> P:\n    return P(x)\n', 'f'))
        cases.append(('future dataclass parameter',
                      'from __future__ import annotations\n' + DATACLASS +
                      '@export\ndef f(p: P) -> int:\n    return p.x\n', 'f'))
        cases.append(('decorator below export',
                      'import functools\nfrom ail_ffi import export\n\n'
                      '@export\n@functools.lru_cache\ndef f(x: int) -> int:\n    return x + 1\n', 'f'))
        cases.append(('dataclass base',
                      'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                      '@dataclass\nclass Base:\n    s: str\n\n'
                      '@dataclass\nclass P(Base):\n    x: int\n\n'
                      '@export\ndef f(p: P) -> int:\n    return p.x\n', 'f'))
        cases.append(('dataclass below the function',
                      'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                      '@export\ndef f(p: P) -> int:\n    return p.x\n\n'
                      '@dataclass\nclass P:\n    x: int\n', 'f'))
        cases.append(('dataclass with another decorator',
                      'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                      'def replace(c):\n    return 5\n\n'
                      '@replace\n@dataclass\nclass P:\n    x: int\n\n'
                      '@export\ndef f(p: P) -> int:\n    return p.x\n', 'f'))
        cases.append(('dataclass rebound before the function',
                      'from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                      '@dataclass\nclass P:\n    x: int\n\nP = 5\n\n'
                      '@export\ndef f(p: P) -> int:\n    return 1\n', 'f'))
        cases.append(('shadowed scalar annotation',
                      'from ail_ffi import export\n\nint = dict\n\n'
                      '@export\ndef f(x: int) -> int:\n    return 1\n', 'f'))
        cases.append(('shadowed list annotation',
                      'from ail_ffi import export\n\nlist = dict\n\n'
                      '@export\ndef f(x: list[int]) -> int:\n    return 1\n', 'f'))
        cases.append(('export with arguments',
                      'from ail_ffi import export\n\n@export(1)\ndef f(x: int) -> int:\n    return x\n', 'f'))
        cases.append(('export on a class',
                      'from ail_ffi import export\n\n@export\nclass C:\n    pass\n', None))
        for label, source_text, function in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory(prefix='ail-ex39-bad-') as directory:
                    source = Path(directory) / 'bad.py'
                    source.write_text(source_text, encoding='utf-8')
                    expected = _cpython(source)
                    self.assertNotEqual(expected.returncode, 0)
                    for mode in ('default', 'typed', 'general'):
                        built, _ = _build(directory, source, 'bad_' + label.replace(' ', '_'), mode)
                        output = built.stdout + built.stderr
                        self.assertNotEqual(built.returncode, 0, output)
                        self.assertIn('@export applies' if function is None else '@export ' + function, output)

    def test_unused_unsupported_dataclass_is_not_refused(self):
        text = ('from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                '@dataclass\nclass Bad:\n    s: str\n\n'
                '@export\ndef add(a: int) -> int:\n    return a\n\nprint(add(2))\n')
        with tempfile.TemporaryDirectory(prefix='ail-ex39-unused-') as directory:
            source = Path(directory) / 'unused.py'
            self.check('unused', source, text)


if __name__ == '__main__':
    unittest.main()
