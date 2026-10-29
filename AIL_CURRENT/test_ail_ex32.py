"""ex32: a print-only script of an integer constant expression runs on the typed path.

`language_examples/hello.ail` is `print(40 + 2)`.  The typed path refused it with
"a script that is only print(<expression>) needs general object semantics" although 40 + 2 is a
proven int constant expression, so the default build had to take the general path.  The print
gate now accepts integer constant expressions (an out-of-int64 result is left to the big-int
check to name) while bool, float, text and container arguments keep the old fallback.  Every
result is compared with CPython on the general, default and typed-only builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / 'language_examples'
CHATGPT = str(ROOT / 'ail_chatgpt.py')
MESSAGE = 'a script that is only print(<expression>) needs general object semantics'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, mode):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 't':
        env['AIL_NO_GENERAL'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


MATCHING = {
    'add': 'print(40 + 2)\n',
    'negative': 'print(-5)\n',
    'zero': 'print(0)\n',
    'subtract': 'print(40 - 50)\n',
    'multiply': 'print(6 * 7)\n',
    'floor_divide': 'print(7 // 2)\nprint(-7 // 2)\n',
    'modulo': 'print(-7 % 3)\n',
    'shift': 'print(1 << 10)\nprint(-8 >> 1)\n',
    'power': 'print(2 ** 10)\n',
    'int64_bounds': 'print(2 ** 63 - 1)\nprint(-(2 ** 63))\n',
    'bool_leaf': 'print(1 + True)\n',
    'keyword_sep': 'print(40 + 2, sep=",")\n',
    'keyword_end': 'print(40 + 2, end="!\\n")\n',
    'several_arguments': 'print(40 + 2, 7 // 2)\n',
}

REFUSED_TYPED = {
    'bare_bool': 'print(True)\n',
    'float_expression': 'print(1.5 + 2.5)\n',
    'text_expression': 'print("a" + "b")\n',
    'list_literal': 'print([1, 2])\n',
}


class Ex32Tests(unittest.TestCase):
    def test_hello_and_integer_constant_expressions_match(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex32-') as directory:
            cases = dict(MATCHING)
            cases['hello'] = (EXAMPLES / 'hello.ail').read_text(encoding='utf-8')
            for slug, text in cases.items():
                want = cpython(directory, slug, text)
                for mode in ('g', 'd', 't'):
                    exe, built = build(directory, '%s_%s' % (slug, mode), text, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, mode, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, mode, got.stderr[-800:]))

    def test_non_integer_print_arguments_keep_the_typed_refusal_and_match(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex32-refused-') as directory:
            for slug, text in REFUSED_TYPED.items():
                _, typed = build(directory, slug + '_t', text, 't')
                output = typed.stdout + typed.stderr
                self.assertNotEqual(typed.returncode, 0, (slug, output[-1200:]))
                self.assertIn(MESSAGE, output, (slug, output[-1200:]))
                want = cpython(directory, slug, text)
                for mode in ('g', 'd'):
                    exe, built = build(directory, '%s_%s' % (slug, mode), text, mode)
                    self.assertEqual(built.returncode, 0, (slug, mode, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, mode, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, mode, got.stderr[-800:]))

    def test_out_of_int64_constant_expression_is_refused_by_the_big_int_check(self):
        text = 'print(2 ** 100)\n'
        with tempfile.TemporaryDirectory(prefix='ail-ex32-big-') as directory:
            _, typed = build(directory, 'big_t', text, 't')
            self.assertNotEqual(typed.returncode, 0)
            self.assertIn('can need an int beyond int64', typed.stdout + typed.stderr)
            want = cpython(directory, 'big', text)
            for mode in ('g', 'd'):
                exe, built = build(directory, 'big_' + mode, text, mode)
                self.assertEqual(built.returncode, 0, (mode, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (mode, got.stderr[-800:]))
                self.assertEqual(got.returncode, want[1], (mode, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
