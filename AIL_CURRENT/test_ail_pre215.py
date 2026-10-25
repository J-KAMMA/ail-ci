"""pre215: a constant abs() whose exact value leaves int64 is refused by name.

`abs(-(1 << 63))` -- and the literal spelling `abs(-9223372036854775808)` -- used to build and
then stop with ``integer overflow`` at run time, while CPython prints 9223372036854775808.  AIL
ints are 64-bit, so the compiler now folds the constant argument exactly and refuses the
construct before emitting C, on the general and the default build.  In-range abs() values,
floats, values that only reach abs() as run-time variables, and a program that binds its own
``abs`` keep their previous behaviour.  The other pre-existing cases from the same review
(``-(1<<63) * -1``, ``// -1`` and ``-(1<<63) - 1``) are already refused by name and are checked
here too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / 'ail_chatgpt.py')

OUT_OF_RANGE = {
    'direct': '''def main() -> None:
    print(abs(-(1 << 63)))


main()
''',
    'literal': '''def main() -> None:
    print(abs(-9223372036854775808))


main()
''',
    'module_constant': '''M = -(1 << 63)


def main() -> None:
    print(abs(M))


main()
''',
    'argument': '''def through(x: int) -> int:
    return x


def main() -> None:
    print(through(abs(-(1 << 63))))


main()
''',
    'list_item': '''def main() -> None:
    print([abs(-(1 << 63))][0])


main()
''',
    'attribute': '''class Box:
    pass


def main() -> None:
    box = Box()
    box.value = abs(-(1 << 63))
    print(box.value)


main()
''',
    'dict_value': '''def main() -> None:
    print({'k': abs(-(1 << 63))}['k'])


main()
''',
    'nested': '''def main() -> None:
    print(abs(abs(-(1 << 63))))


main()
''',
}

OTHER_REFUSED = {
    'multiply': 'print(-(1 << 63) * -1)\n',
    'floor_div': 'print(-(1 << 63) // -1)\n',
    'subtract': 'print(-(1 << 63) - 1)\n',
}

IN_RANGE = '''MAX = 9223372036854775807
MIN = -9223372036854775808


class Box:
    def __init__(self, n: int) -> None:
        self.n = n


def through(x: int) -> int:
    return abs(x)


def main() -> None:
    print(abs(-5), abs(5), abs(0), abs(-0))
    print(abs(MIN + 1), abs(MAX), abs(-MAX))
    print(through(-7))
    print(abs([-8][0]))
    print(abs(Box(-9).n))
    print(abs({'k': -10}['k']))
    print(abs(-0.0), abs(-2.5), abs(2.5))


main()
'''

SHADOWED = '''def abs(x: int) -> int:
    return 42


def main() -> None:
    print(abs(-(1 << 63)))


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, built.stdout + built.stderr
    done = subprocess.run([str(exe)], cwd=directory, capture_output=True, text=True, timeout=120)
    return done, ''


class Pre215Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ail-pre215-')
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_constant_abs_outside_int64_is_refused_by_name(self):
        for label, text in OUT_OF_RANGE.items():
            for general in (False, True):
                with self.subTest(label + ('_g' if general else '_d')):
                    built, _ = _build(self.dir, '%s_%s' % (label, 'g' if general else 'd'),
                                      text, general)
                    self.assertNotEqual(built.returncode, 0, label)
                    message = built.stdout + built.stderr
                    self.assertIn('int64 constant expression out of range', message, label)
                    self.assertNotIn('integer overflow', message, label)
                    self.assertNotIn('Traceback', message, label)

    def test_other_review_cases_are_refused_by_name(self):
        for label, text in OTHER_REFUSED.items():
            for general in (False, True):
                with self.subTest(label + ('_g' if general else '_d')):
                    built, _ = _build(self.dir, 'other_%s_%s' % (label, 'g' if general else 'd'),
                                      text, general)
                    self.assertNotEqual(built.returncode, 0, label)
                    message = built.stdout + built.stderr
                    self.assertIn('outside the signed 64-bit range', message, label)
                    self.assertNotIn('integer overflow', message, label)
                    self.assertNotIn('Traceback', message, label)

    def test_in_range_abs_matches_cpython(self):
        want = _cpython(self.dir, 'in_range', IN_RANGE)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            with self.subTest('g' if general else 'd'):
                got, err = _run(self.dir, 'in_range_' + ('g' if general else 'd'), IN_RANGE,
                                general)
                self.assertIsNotNone(got, err)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), err)

    def test_a_user_defined_abs_is_not_refused(self):
        want = _cpython(self.dir, 'shadowed', SHADOWED)
        self.assertEqual(want.returncode, 0, want.stderr)
        for general in (False, True):
            with self.subTest('g' if general else 'd'):
                got, err = _run(self.dir, 'shadowed_' + ('g' if general else 'd'), SHADOWED,
                                general)
                self.assertIsNotNone(got, err)
                self.assertEqual((got.returncode, got.stdout), (0, want.stdout), err)


if __name__ == '__main__':
    unittest.main()
