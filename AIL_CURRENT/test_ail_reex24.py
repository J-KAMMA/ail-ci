"""reex24: a Python-syntax module of definitions builds and runs like CPython does.

`language_examples/math.ail` is a module (`LIMIT` and `sum_to`), not a program: CPython
evaluates its definitions and prints nothing. `integer_series.ail` has the same shape. Both are
built on the default build and on the general path, and their stdout and exit status must equal
CPython's.

A definitions-only file is effect free when every top-level function has literal defaults and
annotations built from builtin names, literals, subscripts and `|` unions (`list[int]`,
`dict[str, int]`, `int | None`); literal module constants, docstrings, `pass`, imports and classes
with effect-free bodies are allowed. A decorator, a non-literal default, a non-builtin annotation
or a class-body statement that runs code runs code while CPython loads the module, so the compiler
refuses it by name instead of silently building a no-op or falling into the file-reading tool shape
(`usage: tool FILE`, exit 2). Imports are part of the definitions-only shape, so a decorated def in
a module that also imports is refused the same way.

Also checks `ail_testenv.rustc()`: under a task-local HOME the rustup proxy is on PATH but has no
toolchain, so the helper must report no usable rustc rather than a path whose every call fails.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import ail_testenv  # noqa: E402

MODULES = {
    'math': '''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'integer_series': '''def above(values: list, minimum: int) -> list:
    return sorted([value for value in values if value >= minimum])

def differences(values: list) -> list:
    return [values[i] - values[i - 1] for i in range(1, len(values))]

def bounds(values: list) -> list:
    if len(values) == 0:
        return []
    return [min(values), max(values)]
''',
    'annotations': '''"""Builtin subscripts, unions and literal defaults are effect free."""

def first(xs: list[int], n: int = 1) -> list[int]:
    return xs[0:n]

def maybe(flag: bool = False) -> int | None:
    if flag:
        return 1
    return None

def table(mapping: dict[str, int] = {}, row: tuple[str, int] = ("x", -1)) -> int:
    return len(mapping) + row[1]
''',
    'constants': '''I = 7
F = 1.5
S = "x"
B = b"y"
MIN = -9223372036854775808
MAX = 9223372036854775807
ZERO = -0.0
VALUES = [1, 2]
PAIR = (3, 4)

def touch(n: int, text: bytes, rows: list) -> int:
    return n
''',
    'class_module': '''class Point:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def norm1(self) -> int:
        return abs(self.x) + abs(self.y)
''',
    'print_top': '''def helper(n):
    return n

print("top", helper(2))
''',
    'main_called': '''def main():
    print("main ran")

main()
''',
    'imports': '''import os
from functools import cache

def first(xs: list[int]) -> int:
    return xs[0]
''',
}

REFUSED = {
    'effectful_default': '''def make():
    print("made")
    return 3

def f(x=make()):
    return x
''',
    'effectful_annotation': '''def make():
    print("made")
    return int

def f(x: make()):
    return x
''',
    'decorator': '''def deco(fn):
    print("deco")
    return fn

@deco
def f():
    return 1
''',
    'list_item_default': '''def make():
    print("made")
    return 3

def f(x=[make()][0]):
    return x
''',
    'dict_value_default': '''def make():
    print("made")
    return 3

def f(x={"f": make}["f"]()):
    return x
''',
    # imports are part of the definitions-only shape: a decorated def in a module that also
    # imports is refused, not built as a file-reading tool (exit 2 where CPython exits 0)
    'decorator_imported_from': '''from functools import cache

@cache
def f(x: int = 1) -> int:
    return x
''',
    'decorator_imported_module': '''import functools

@functools.cache
def f(x: int = 1) -> int:
    return x
''',
    # a class whose body or method decorator runs code is refused instead of falling into
    # entry-point selection (which used to fail with an unrelated no-parameter refusal)
    'class_property': '''class P:
    def __init__(self):
        self._v = 0

    @property
    def v(self):
        return self._v
''',
    'class_body_call': '''def make():
    return 4

class C:
    x = make()
''',
}


def _cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, source, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(source, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            str(src), '--syntax', 'python', '-o', str(exe)],
                           cwd=directory, capture_output=True, text=True, timeout=1200, env=env)
    return built, exe


class ModuleOnlyTests(unittest.TestCase):
    def same_as_cpython(self, slug, source):
        with tempfile.TemporaryDirectory(prefix='ail-reex24-') as directory:
            want, want_rc = _cpython(directory, slug, source)
            self.assertEqual((want, want_rc), (b'', 0), slug)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, source, general)
                self.assertEqual(built.returncode, 0, slug + ': ' + built.stdout + built.stderr)
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, slug)
                self.assertEqual(got.returncode, want_rc, slug)

    def test_language_example_modules_match_cpython(self):
        for name in ('math', 'integer_series'):
            self.same_as_cpython(name, (ROOT / 'language_examples' / (name + '.ail')).read_text(
                encoding='utf-8'))

    def test_effect_free_modules_match_cpython(self):
        for slug in ('annotations', 'constants', 'class_module', 'imports'):
            self.same_as_cpython(slug, MODULES[slug])

    def test_top_level_code_still_runs(self):
        for slug in ('print_top', 'main_called'):
            source = MODULES[slug]
            with tempfile.TemporaryDirectory(prefix='ail-reex24-') as directory:
                want, want_rc = _cpython(directory, slug, source)
                self.assertNotEqual(want, b'', slug)
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, source, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, slug)
                    self.assertEqual(got.returncode, want_rc, slug)

    def test_load_time_effects_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-reex24-') as directory:
            for slug, source in REFUSED.items():
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, _ = _build(directory, name, source, general)
                    text = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, slug)
                    self.assertIn('runs code at load time', text, slug)
                    self.assertNotIn('Traceback', text, slug)
                    self.assertNotIn('C compiler rejected', text, slug)


class RustcHelperTests(unittest.TestCase):
    def test_rustc_matches_a_version_probe(self):
        found = shutil.which('rustc')
        usable = None
        if found is not None:
            try:
                probe = subprocess.run([found, '--version'], capture_output=True, text=True, timeout=60)
            except (OSError, subprocess.SubprocessError):
                probe = None
            if probe is not None and probe.returncode == 0:
                usable = found
        self.assertEqual(ail_testenv.rustc(), usable)


if __name__ == '__main__':
    unittest.main()
