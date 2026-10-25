"""A statically known unary integer constant outside int64 is refused by name.

AIL integers are fixed width.  ``-MIN`` (and the same value spelled through nested unary
minus or a module constant assigned from an expression) used to compile on the default build
and then stop at run time with ``integer overflow`` while CPython printed a bignum.  The
compiler now evaluates unary constant expressions and refuses them before emitting C, on the
general and the default build.  In-range unary expressions, and values that only reach the
operation as variables, keep their previous behaviour.
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

OUT_OF_RANGE = {
    'module_constant': '''MIN = %d


def main() -> None:
    print(-MIN)


main()
''' % MIN,
    'nested_literal': '''def main() -> None:
    print(-(-9223372036854775808))


main()
''',
    'assigned_expression': '''MAX = %d
N = -MAX - 1


def main() -> None:
    print(-N)


main()
''' % MAX,
}

IN_RANGE = '''MAX = %d


def main() -> None:
    print(-MAX, -(-MAX), -(-9223372036854775807), -0, -(-1))


main()
''' % MAX

PARAMETER = '''MIN = %d


def neg(MIN: int) -> int:
    return -MIN


def main() -> None:
    print(neg(3))


main()
''' % MIN


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


class Pre172Tests(unittest.TestCase):
    def test_statically_known_unary_overflow_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre172-') as directory:
            for label, text in OUT_OF_RANGE.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        self.assertIn('int64 constant expression out of range', message, label)
                        self.assertNotIn('integer overflow', message, label)
                        self.assertNotIn('Traceback', message, label)

    def test_in_range_unary_expressions_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre172-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)

    def test_parameter_with_the_constant_name_is_not_folded(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre172-') as directory:
            want, want_rc, err = _cpython(directory, 'parameter', PARAMETER)
            self.assertEqual(want_rc, 0, err)
            got, build_err = _run(directory, 'parameter_d', PARAMETER, False)
            self.assertIsNotNone(got, build_err)
            self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()
