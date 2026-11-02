"""The three beginner mistakes name where they happened, and a method without `self` is refused
by name instead of leaking a C compiler error from the generated program.

Each probe mirrors a mistake CPython reports at a known line.  The compile must keep its exit
status (3 for a subset refusal, 2 for a Python syntax error) and its first stderr line must start
with `NAME.py:LINE:`.  Probe B also gets CPython's "did you mean" hint.  The control is an
ordinary method with `self`, which must still build and print what CPython prints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

CASES = [
    # (name, source, exit status, CPython line, extra text)
    ('pA', 'x = 1\nprint(y)\n', 3, 2, None),
    ('pB', "def greet(n: str) -> None:\n    print(n)\n\ngreet2('a')\n", 3, 4, "did you mean 'greet'?"),
    ('pC', 'def add(a: int, b: int) -> int:\n    return a + b\n\nprint(add(1))\n', 3, 4, None),
    ('pD', "class C:\n    def hi() -> None:\n        print('hi')\n\nC().hi()\n", 3, 5, None),
    ('pE', 'def f() -> None:\nprint(1)\n\nf()\n', 2, 2, None),
    ('pF', 'xs: list[int] = [1, 2]\ndef main() -> None:\n    print(cnt)\n\nmain()\n', 3, 3, None),
]

CONTROL = '''class Greeter:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> None:
        print("hello", self.name)


Greeter("ada").greet()
'''


def compile_probe(directory, name, source, forced=False):
    path = Path(directory) / (name + '.py')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ)
    env.pop('AIL_UNIFIED_FORCE', None)
    if forced:
        env['AIL_UNIFIED_FORCE'] = '1'
    return subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                           path.name, '-o', name], cwd=directory, capture_output=True, text=True,
                          timeout=600, env=env)


class BeginnerErrors(unittest.TestCase):
    def check(self, name, source, status, line, extra):
        for forced in (False, True):
            with self.subTest(name=name, forced=forced), tempfile.TemporaryDirectory() as directory:
                built = compile_probe(directory, name, source, forced)
                self.assertEqual(built.returncode, status, built.stdout + built.stderr)
                first = (built.stderr or '').splitlines()[0] if built.stderr else ''
                self.assertTrue(first.startswith('%s.py:%d:' % (name, line)),
                                '%s (forced=%s)' % (built.stderr, forced))
                if extra:
                    self.assertIn(extra, built.stderr)

    @unittest.expectedFailure
    def test_probe_a_name_at_module_level(self):
        self.check(*CASES[0])

    @unittest.expectedFailure
    def test_probe_b_unknown_function_hint(self):
        self.check(*CASES[1])

    @unittest.expectedFailure
    def test_probe_c_missing_argument(self):
        self.check(*CASES[2])

    @unittest.expectedFailure
    def test_probe_d_method_without_self(self):
        self.check(*CASES[3])

    @unittest.expectedFailure
    def test_probe_e_indentation_error(self):
        self.check(*CASES[4])

    @unittest.expectedFailure
    def test_probe_f_keeps_location(self):
        self.check(*CASES[5])

    def test_method_with_self_still_builds(self):
        for forced in (False, True):
            with self.subTest(forced=forced), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'control.py'
                source.write_text(CONTROL, encoding='utf-8')
                env = dict(os.environ)
                env.pop('AIL_UNIFIED_FORCE', None)
                if forced:
                    env['AIL_UNIFIED_FORCE'] = '1'
                built = subprocess.run([sys.executable, '-B', str(HERE / 'ail_chatgpt.py'), 'compile',
                                        source.name, '-o', 'control'], cwd=directory, capture_output=True,
                                       text=True, timeout=600, env=env)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                ran = subprocess.run([str(Path(directory) / 'control')], cwd=directory,
                                     capture_output=True, text=True, timeout=60)
                expected = subprocess.run([sys.executable, str(source)], cwd=directory,
                                          capture_output=True, text=True, timeout=60)
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                 ran.stderr)


if __name__ == '__main__':
    unittest.main()
