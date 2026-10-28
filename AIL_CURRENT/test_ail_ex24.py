"""ex24: a Python-syntax module of definitions builds and runs like CPython does.

`language_examples/math.ail` is a module (`LIMIT` and `sum_to`), not a program: CPython
evaluates its definitions and prints nothing.  The compiler used to call its last function and
refuse `math.ail` ("the first parameter must be the sequence read from the file"), and built
`integer_series.ail` as a file-reading tool that printed `usage: tool FILE` and exited 2.
An effect-free Python module (functions whose annotations and defaults are literals or builtin
types, literal module constants, docstrings/pass) now builds as a no-op entry on both builds.
A definition that would run code at load time (a decorator, a non-constant annotation or
default) is refused by name instead of being dropped or turned into a file tool.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULES = {
    'math': '''LIMIT = 6

def sum_to(n):
    total = 0
    for i in range(n + 1):
        total += i
    return total
''',
    'integer_series': '''def above(values: list, minimum: int) -> list:
    result = sorted([value for value in values if value >= minimum])
    return result

def differences(values: list) -> list:
    return [values[i] - values[i - 1] for i in range(1, len(values))]

def filtered_differences(values: list, minimum: int) -> list:
    return differences(above(values, minimum))

def filtered_change_total(values: list, minimum: int) -> int:
    return sum(filtered_differences(values, minimum))

def bounds(values: list) -> list:
    if len(values) == 0:
        return []
    return [min(values), max(values)]
''',
    'annotations': '''"""Only definitions; the subscript annotations and literal defaults are effect free."""

def first(xs: list[int], n: int = 1) -> list[int]:
    return xs[0:n]

def maybe(flag: bool = False) -> int | None:
    if flag:
        return 1
    return None

def table(mapping: dict[str, int] = {}) -> int:
    return 0
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
    'print_top': '''def helper(n):
    return n

print("top", helper(2))
''',
    'main_called': '''def main():
    print("main ran")

main()
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
}


def _run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(path)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, source, general, target=None):
    src = Path(target) if target is not None else Path(directory) / (name + '.ail')
    if target is None:
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


class Ex24Tests(unittest.TestCase):
    def test_language_example_modules_match_cpython(self):
        for name in ('math', 'integer_series'):
            source = (ROOT / 'language_examples' / (name + '.ail')).read_text(encoding='utf-8')
            with tempfile.TemporaryDirectory(prefix='ail-ex24-') as directory:
                want, want_rc = _run_cpython(directory, name, source)
                self.assertEqual((want, want_rc), (b'', 0))
                for general in (True, False):
                    built, exe = _build(directory, name, source, general,
                                        target=ROOT / 'language_examples' / (name + '.ail'))
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory, input=b'')
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)
                    self.assertEqual(got.returncode, want_rc)

    def test_effect_free_modules_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex24-') as directory:
            for slug, source in MODULES.items():
                want, want_rc = _run_cpython(directory, slug, source)
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, exe = _build(directory, name, source, general)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                         cwd=directory, input=b'')
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, slug)
                    self.assertEqual(got.returncode, want_rc, slug)

    def test_definitions_with_a_load_time_effect_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex24-') as directory:
            for slug, source in REFUSED.items():
                for general in (True, False):
                    name = '%s_%s' % (slug, 'g' if general else 'd')
                    built, _ = _build(directory, name, source, general)
                    text = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, slug)
                    self.assertIn('runs code at load time', text, slug)
                    self.assertNotIn('Traceback', text, slug)
                    self.assertNotIn('C compiler rejected', text, slug)


if __name__ == '__main__':
    unittest.main()
