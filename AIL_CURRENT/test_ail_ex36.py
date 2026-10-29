# -*- coding: utf-8 -*-
"""ex36: `@export` from ail_ffi is the identity on CPython and no longer refused.

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
GEOMETRY = ROOT / 'language_examples' / 'c_export' / 'geometry.py'
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

FUTURE = '''from __future__ import annotations
from dataclasses import dataclass
from ail_ffi import export

@dataclass
class P:
    x: int

@export
def add(a: int, b: int) -> int:
    return a + b

@export
def total(xs: list[int]) -> int:
    return sum(xs)

print(add(2, 3), total([1, 2, 3]), P(4).x)
'''

REBIND_AFTER = '''from ail_ffi import export

@export
def f(x: int) -> int:
    return x

export = 5
print(f(2), export)
'''

ANNOTATION_ONLY = '''from ail_ffi import export
export: int
@export
def f(x: int) -> int:
    return x
print(f(2))
'''

INIT_FALSE_OK = '''from dataclasses import dataclass, field
from ail_ffi import export

@dataclass
class P:
    x: int
    flag: bool = field(init=False, default=True)

@export
def f(p: P) -> int:
    return p.x if p.flag else -p.x

print(f(P(3)))
'''

EXPORT_INSIDE_CACHE = '''from functools import lru_cache
from ail_ffi import export

@lru_cache(maxsize=None)
@export
def f(x: int) -> int:
    return x * x

print(f(3))
'''

UNUSED_IMPORTS = (
    'from ail_ffi import export\n\ndef main() -> None:\n    xs = [3, 1, 2]\n    xs.sort()\n    print(xs[0] + xs[-1])\n\nmain()\n',
    'import ail_ffi\n\ndef main() -> None:\n    xs = [3, 1, 2]\n    xs.sort()\n    print(xs[0] + xs[-1])\n\nmain()\n',
)

INVALID = (
    'from ail_ffi import export\n\n@export\ndef add(a: int, b: int):\n    return a + b\n\nprint(add(2, 3))\n',
    'from ail_ffi import export\n\n@export\ndef inc(x: int = 1) -> int:\n    return x + 1\n\nprint(inc())\n',
    'from ail_ffi import export\n\n@export\ndef keys(d: dict) -> int:\n    return len(d)\n\nprint(keys({"a": 1}))\n',
    'from __future__ import annotations\nfrom dataclasses import dataclass\nfrom ail_ffi import export\n\n@dataclass\nclass P:\n    x: int\n\n@export\ndef w(p: P) -> int:\n    return p.x\n\nprint(w(P(2)))\n',
    'from ail_ffi import export\n\nexport = 5\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from ail_ffi import export\n\nexport: int = 5\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from ail_ffi import export\n\nfor export in [5]:\n    pass\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'import ail_ffi as ffi\n\nffi = 5\n\n@ffi.export\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from ail_ffi import export\n\n(export := 5)\n\n@export\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from functools import lru_cache\nfrom ail_ffi import export\n\n@export\n@lru_cache(maxsize=None)\ndef f(x: int) -> int:\n    return x * x\n\nprint(f(3))\n',
    'from functools import cache\nfrom ail_ffi import export\n\n@export\n@cache\ndef f(x: int) -> int:\n    return x * x\n\nprint(f(2))\n',
    'from ail_ffi import export\n\n@export(123)\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from ail_ffi import export\n\n@export(name="f")\ndef f(x: int) -> int:\n    return x\n\nprint(f(2))\n',
    'from dataclasses import dataclass, field\nfrom ail_ffi import export\n\n@dataclass\nclass P:\n    x: int\n    label: str = field(init=False, default="z")\n\n@export\ndef f(p: P) -> int:\n    return p.x\n\nprint(f(P(1)))\n',
    'from dataclasses import dataclass, field\nfrom ail_ffi import export\n\n@dataclass\nclass P:\n    x: int\n    label: list[str] = field(init=False, default_factory=list)\n\n@export\ndef f(p: P) -> int:\n    return p.x\n\nprint(f(P(1)))\n',
)


def python_path():
    old = os.environ.get('PYTHONPATH')
    return str(ROOT) if not old else str(ROOT) + os.pathsep + old


def build(directory, source, general, quiet=True, name='p.py'):
    path = Path(directory, name)
    path.write_text(source, encoding='utf-8')
    exe = Path(directory, 'exe_g' if general else 'exe_d')
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_QUIET_FALLBACK', None)
    if quiet:
        env['AIL_QUIET_FALLBACK'] = '1'
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    done = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(path),
                           '--syntax', 'python', '-o', str(exe)],
                          cwd=directory, capture_output=True, text=True, timeout=300, env=env)
    return done, exe


def cpython(directory, source, name='ref.py'):
    path = Path(directory, name)
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, PYTHONPATH=python_path())
    return subprocess.run([sys.executable, str(path)], cwd=directory,
                          capture_output=True, text=True, timeout=120, env=env)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class ExportDecorator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-ex36-')
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

    def test_init_false_dataclass_field_of_allowed_type_matches_cpython(self):
        self.run_both(INIT_FALSE_OK)

    def test_export_below_lru_cache_matches_cpython(self):
        self.run_both(EXPORT_INSIDE_CACHE)

    def test_future_annotations_matches_cpython(self):
        self.run_both(FUTURE)

    def test_rebound_after_the_decorator_matches_cpython(self):
        self.run_both(REBIND_AFTER)

    def test_annotation_without_a_value_does_not_rebind(self):
        self.run_both(ANNOTATION_ONLY)

    def test_unused_export_import_keeps_the_typed_path(self):
        for source in UNUSED_IMPORTS:
            expected = cpython(self.dir, source)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for general in (False, True):
                (self.dir / ('exe_g' if general else 'exe_d')).unlink(missing_ok=True)
                built, exe = build(self.dir, source, general, quiet=False)
                where = 'general' if general else 'default'
                self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
                self.assertNotIn('built on the general path', built.stdout + built.stderr, where)
                ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
                self.assertEqual(ran.stdout, expected.stdout, where)

    def test_invalid_export_is_refused_named(self):
        for source in INVALID:
            expected = cpython(self.dir, source)
            self.assertNotEqual(expected.returncode, 0)
            for general in (False, True):
                built, exe = build(self.dir, source, general)
                where = 'general' if general else 'default'
                self.assertNotEqual(built.returncode, 0, where + ':\n' + source)
                self.assertIn('@export', built.stdout + built.stderr, where)

    def test_geometry_example_matches_cpython(self):
        source = GEOMETRY.read_text(encoding='utf-8')
        expected = cpython(self.dir, source, name='geometry.py')
        self.assertEqual(expected.returncode, 0, expected.stderr)
        for general in (False, True):
            built, exe = build(self.dir, source, general, name='geometry.py')
            where = 'general' if general else 'default'
            self.assertEqual(built.returncode, 0, where + ':\n' + built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
            self.assertEqual(ran.returncode, expected.returncode, where + ':\n' + ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, where)


if __name__ == '__main__':
    unittest.main()
