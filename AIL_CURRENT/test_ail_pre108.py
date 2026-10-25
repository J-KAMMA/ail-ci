"""A statically known integer constant expression outside int64 is refused by name.

AIL integers are fixed width, so an expression such as ``MAX * 2`` used to compile and
then stop at run time with ``integer overflow`` while CPython printed a bignum.  The
compiler now evaluates the constant expression and refuses it before emitting C, on both
the general and the default build.  Values that only reach the operation at run time keep
the documented fixed-width trap, and a module constant shadowed by a local or a parameter
is not folded.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAX = 9223372036854775807
MIN = -9223372036854775808

EXPRESSIONS = {
    'argument': '''MAX = %d


def take(v: int) -> None:
    print(v)


def main() -> None:
    take(MAX * 2)


main()
''' % MAX,
    'list_item': '''MAX = %d


def main() -> None:
    print([MAX + 1])


main()
''' % MAX,
    'tuple_item': '''MIN = %d


def main() -> None:
    print((MIN - 1, 0))


main()
''' % MIN,
    'attribute': '''class Box:
    def __init__(self) -> None:
        self.v = 0


def main() -> None:
    box = Box()
    box.v = 2 ** 63
    print(box.v)


main()
''',
    'dict_value': '''MAX = %d


def main() -> None:
    print({"value": MAX * MAX})


main()
''' % MAX,
    'module_constant': '''MAX = %d
BIG = MAX * 2


def main() -> None:
    print(BIG)


main()
''' % MAX,
    'unary_boundary': '''def main() -> None:
    print(-(2 ** 63) - 1)


main()
''',
    'large_power': '''def main() -> None:
    print(2 ** 100)


main()
''',
}

IN_RANGE = '''MAX = %d


def main() -> None:
    print(MAX - 1, MAX - 2, 2 ** 62, -(-MAX))


main()
''' % MAX

SHADOWED = '''MAX = %d


def local() -> int:
    MAX = 3
    return MAX * 2


def parameter(MAX: int) -> int:
    return MAX * 2


def main() -> None:
    print(local(), parameter(3))


main()
''' % MAX

RUNTIME = '''MAX = %d


def main() -> None:
    values = [MAX]
    v = values[0]
    print(v * 2)


main()
''' % MAX


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre108Tests(unittest.TestCase):
    def test_constant_expressions_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre108-') as directory:
            for label, text in EXPRESSIONS.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        self.assertIn('int64 constant expression out of range', message, label)
                        self.assertNotIn('integer overflow', message, label)

    def test_in_range_constant_expressions_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre108-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_shadowed_module_constant_is_not_folded(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre108-') as directory:
            want, want_rc, err = _cpython(directory, 'shadowed', SHADOWED)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('shadowed_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'shadowed_' + ('g' if general else 'd'),
                                          SHADOWED, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_runtime_overflow_keeps_the_fixed_width_trap(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre108-') as directory:
            for general in (True, False):
                with self.subTest('runtime_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'runtime_' + ('g' if general else 'd'),
                                          RUNTIME, general)
                    self.assertIsNotNone(got, build_err)
                    stdout, rc = got
                    self.assertEqual((stdout, rc), (b'', 1), build_err)
                    self.assertIn('integer overflow', build_err)


if __name__ == '__main__':
    unittest.main()
