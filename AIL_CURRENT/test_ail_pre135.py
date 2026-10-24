"""pre135: a class name is not bound while its own class body runs.

CPython evaluates a class body before binding the class name, so `class C: x = (lambda: C)()`
raises NameError (the general path used to recurse in the compiler).  A lambda that only reads C
later, after the class statement, still works.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SELF_NAME = """class C:
    x = C
print(C.x)
"""

LAMBDA_CALL = """class C:
    x = (lambda: C)()
print(C.x)
"""

CLASS_CALL = """class C:
    x = C()
print(C.x)
"""

THROUGH_FUNCTION = """def f():
    return C

class C:
    x = f()
print(C.x)
"""

COLLECTION = """class C:
    x = [C]
print(C.x)
"""

DEFERRED = """class C:
    x = lambda: C
f = C.x
print(f() is C)
"""

FAIL = [SELF_NAME, LAMBDA_CALL, CLASS_CALL, THROUGH_FUNCTION, COLLECTION]


def build_and_run(directory, text, name, ir):
    source, exe = Path(directory, name + '.py'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_IR='1' if ir else '0', AIL_NO_CACHE='1')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class Pre135(unittest.TestCase):
    def run_case(self, slug, text, ir):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = build_and_run(directory, text, slug + ('_ir' if ir else ''), ir)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertNotEqual(expected.returncode, 0)
            self.assertEqual(ran.returncode, expected.returncode, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)
            self.assertIn(b"NameError: name 'C' is not defined", ran.stderr)

    def test_self_reference_is_a_name_error(self):
        for ir in (False, True):
            for i, text in enumerate(FAIL):
                with self.subTest(ir=ir, case=i):
                    self.run_case('self%d' % i, text, ir)

    def test_deferred_lambda_still_works(self):
        for ir in (False, True):
            with self.subTest(ir=ir):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = build_and_run(directory, DEFERRED, 'deferred' + ('_ir' if ir else ''), ir)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual(expected.returncode, 0, expected.stderr)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                                     ran.stderr)


if __name__ == '__main__':
    unittest.main()
