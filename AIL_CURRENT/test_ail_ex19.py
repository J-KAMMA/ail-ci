"""ex19: a Python-syntax module with only definitions runs nothing, like CPython.

`language_examples/math.ail` is a helper module: a module constant and one scalar function
(``def sum_to(n)``).  CPython runs no function when the file is run directly, so it prints
nothing and exits 0.  The typed path treated the last definition as a file-reading program and
refused it ("the first parameter must be the sequence read from the file"); the general path
also invented an array entry for an annotated scalar.  Both builds now leave such a source with
no entry point, while a first parameter that is the input sequence keeps the pipeline entry and
a top-level call still runs.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


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


MODULES = {
    'math_example': (ROOT / 'language_examples' / 'math.ail').read_text(encoding='utf-8'),
    'constant_scalar': 'LIMIT = 6\n\n\ndef sum_to(n):\n    total = 0\n    for i in range(n + 1):\n'
                       '        total += i\n    return total\n',
    'annotated_int': 'def increment(x: int) -> int:\n    return x + 1\n',
    'unannotated_int': 'def increment(n):\n    return n + 1\n',
    'annotated_float': 'def half(x: float) -> float:\n    return x / 2\n',
    'annotated_str': 'def greet(name: str) -> str:\n    return "hi " + name\n',
    'two_scalars': 'def increment(x: int) -> int:\n    return x + 1\n\n\n'
                   'def twice(y: int) -> int:\n    return y * 2\n',
}

RUNS = {
    'top_level_call': 'def increment(x: int) -> int:\n    return x + 1\n\n\nprint(increment(2))\n',
}


class Ex19Tests(unittest.TestCase):
    def test_definition_only_modules_match_cpython_on_both_builds(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex19-') as directory:
            for slug, text in MODULES.items():
                want = cpython(directory, slug, text)
                self.assertEqual(want, (b'', 0), slug)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_a_top_level_call_still_runs(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex19-') as directory:
            for slug, text in RUNS.items():
                want = cpython(directory, slug, text)
                self.assertEqual(want, (b'3\n', 0), slug)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
