"""ex42: `@export` in a normal executable is CPython's identity check, not a library build.

The Python-syntax example ``language_examples/c_export/geometry.py`` was refused by a plain
``compile`` ("a decorator on def add"), although CPython runs the same file and the ``--lib``
build already accepts it.  In an executable the decorator only checks the annotations and
returns the function unchanged, so the compiler now removes the marker after the same checks
and keeps the definitions.  A signature CPython's decorator rejects is still refused by name.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
EXAMPLE = ROOT / 'language_examples' / 'c_export' / 'geometry.py'


def environment():
    env = dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore')
    env['PYTHONPATH'] = str(ROOT) + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    return env


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=environment())


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


PROGRAM = '''from dataclasses import dataclass
from ail_ffi import export


@dataclass
class Point:
    x: int
    y: float
    visible: bool


def square(n: int) -> int:
    return n * n


@export
def weight(p: Point) -> float:
    if p.visible:
        return p.x * p.y
    return 0.0


@export
def squares(values: list[int]) -> list[int]:
    return [square(v) for v in values]


@export
def shout(text: str) -> str:
    return text.upper() + "!"


print(weight(Point(2, 1.5, True)), weight(Point(2, 1.5, False)),
      squares([1, 2, 3]), shout("héllo"))
'''

ALIASED = '''import ail_ffi


@ail_ffi.export()
def negate(flag: bool) -> bool:
    return not flag


print(negate(True), negate(False))
'''

FUTURE_SCALARS = '''from __future__ import annotations
from ail_ffi import export


@export
def add(a: int, b: int) -> int:
    return a + b


@export
def total(values: list[int]) -> int:
    return sum(values)


print(add(2, 3), total([1, 2, 3]))
'''

REFUSED = {
    'unsupported_type': ('from ail_ffi import export\n\n@export\ndef f(x: list[str]) -> int:\n'
                         '    return 1\n\nprint(f([]))\n', 'unsupported type list[str]'),
    'missing_parameter_annotation': ('from ail_ffi import export\n\n@export\ndef f(x) -> int:\n'
                                     '    return 1\n\nprint(f(1))\n', 'parameter x needs a type annotation'),
    'missing_result': ('from ail_ffi import export\n\n@export\ndef f(x: int):\n'
                       '    return x\n\nprint(f(1))\n', 'annotate the result'),
    'default_parameter': ('from ail_ffi import export\n\n@export\ndef f(x: int = 3) -> int:\n'
                          '    return x\n\nprint(f())\n', 'plain parameters without defaults only'),
    'forward_reference': ('from dataclasses import dataclass\nfrom ail_ffi import export\n\n'
                          '@export\ndef f(p: Point) -> float:\n    return p.x\n\n'
                          '@dataclass\nclass Point:\n    x: float\n\nprint(f(Point(2.0)))\n',
                          "NameError: name 'Point' is not defined"),
    'future_dataclass': ('from __future__ import annotations\nfrom dataclasses import dataclass\n'
                         'from ail_ffi import export\n\n@dataclass\nclass Point:\n    x: int\n    y: int\n\n'
                         '@export\ndef f(p: Point) -> int:\n    return p.x + p.y\n\nprint(f(Point(2, 3)))\n',
                         'a dataclass is only allowed as a parameter whose fields are int, float or bool'),
    'shadowed_builtin': ('from ail_ffi import export\nint = list\n\n'
                         '@export\ndef f(x: int) -> int:\n    return 1\n\nprint("ok")\n',
                         'TypeError: list is not one of int float bool str bytes list[int] list[float]'),
}


class Ex42Tests(unittest.TestCase):
    def compare(self, directory, name, text):
        want = cpython(directory, name, text)
        self.assertEqual(want.returncode, 0, want.stderr[-1200:])
        for general in (True, False):
            exe, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
            self.assertEqual(built.returncode, 0,
                             (name, general, built.stdout[-1500:] + built.stderr[-1500:]))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            self.assertEqual(got.stdout, want.stdout, (name, general, got.stderr[-800:]))
            self.assertEqual(got.returncode, want.returncode, (name, general, got.stderr[-800:]))

    def test_export_is_an_identity_in_an_executable(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex42-') as directory:
            self.compare(directory, 'program', PROGRAM)

    def test_dotted_and_called_export_forms(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex42-') as directory:
            self.compare(directory, 'aliased', ALIASED)

    def test_future_annotations_still_resolve_scalars_and_aliases(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex42-') as directory:
            self.compare(directory, 'future_scalars', FUTURE_SCALARS)

    def test_the_reference_example_builds_and_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex42-') as directory:
            want = subprocess.run([sys.executable, '-B', str(EXAMPLE)], capture_output=True,
                                  timeout=120, env=environment())
            self.assertEqual(want.returncode, 0, want.stderr[-1200:])
            for general in (True, False):
                exe, built = build(directory, 'geometry_%s' % ('g' if general else 'd'),
                                   EXAMPLE.read_text(encoding='utf-8'), general)
                self.assertEqual(built.returncode, 0,
                                 ('geometry', general, built.stdout[-1500:] + built.stderr[-1500:]))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout, want.stdout, ('geometry', general, got.stderr[-800:]))
                self.assertEqual(got.returncode, want.returncode, ('geometry', general, got.stderr[-800:]))

    def test_a_rejected_signature_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex42-') as directory:
            for name, (text, message) in REFUSED.items():
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (name, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (name, general, output[-1200:]))
                    self.assertIn(message, output, (name, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
