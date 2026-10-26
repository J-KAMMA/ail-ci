"""float() of an int constant outside int64 (job pre302).

The reviewer of job rbrbpre33 recorded that ``float(10 ** 40)`` was refused, although
CPython converts the unbounded int to the nearest double and prints 1e+40.  The source
rewrite now folds a direct, unshadowed ``float(<exact int constant outside int64>)``
whose conversion is finite to a float literal, so both builds match CPython.  A folded
negative value is parenthesized, so a following ``**`` still applies to the call result
rather than binding tighter than the unary minus.  A value
that reaches ``float()`` through an argument, a list item, an attribute, a dict value,
a local or a module constant is still refused by name (the int itself does not fit
int64), as is a conversion that overflows a double.  The second recorded item,
out-of-range intermediates that reduce to an in-range value, already matches CPython,
including a 2**20-bit intermediate shifted back down.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REFUSALS = (
    'int64 constant out of range',
    'int64 constant expression out of range',
    'outside the signed 64-bit range',
    'outside the signed 64 bit range',
)

FLOAT_MATCH = '''def main() -> None:
    print(float(10**40))
    print(float(2**100))
    print(float(-(10**40)))
    print(float(2**63))
    print(float(2**63 - 1))
    print(float(2**100 + 1))
    print(float(-(2**100) - 1))
    print(float(10**18), float(10**19), float(0))
    print(float(10**40) / 2.0)
    print(float(2.5), float(-0.0))
    print(float(-(10**40)) ** 2)
    print(float(-(2**70)) ** 2)
    print(float(-(10**40)) ** 0)
    print(float(-(10**40)) ** -1)
    print(float(-(2**100)) ** -1)
    print(float(10**40) ** 2)


main()
'''

INTERMEDIATE_MATCH = '''def main() -> None:
    print((10**40) >> 100)
    print((10**40) - (10**40))
    print((10**40) // (10**40))
    print((2**63) * 0)
    print((10**40) % 3)
    print(((10**64)**64) >> 100001)
    print((1 << 1048576) >> 1048576)


main()
'''

REFUSED = {
    'argument': '''def show(v) -> None:
    print(float(v))


def main() -> None:
    show(10**40)


main()
''',
    'list_item': '''def main() -> None:
    xs = [10**40]
    print(float(xs[0]))


main()
''',
    'attribute': '''class Box:
    def __init__(self, v) -> None:
        self.v = v


def main() -> None:
    b = Box(10**40)
    print(float(b.v))


main()
''',
    'dict_value': '''def main() -> None:
    d = {"k": 10**40}
    print(float(d["k"]))


main()
''',
    'local': '''def main() -> None:
    x = 10**40
    print(float(x))


main()
''',
    'module_constant': '''X = 10**40


def main() -> None:
    print(float(X))


main()
''',
    'overflow': '''def main() -> None:
    print(float(10**400))


main()
''',
}


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, mode):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_GENERAL', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Pre302Tests(unittest.TestCase):
    def check_match(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre302-') as directory:
            want, want_rc = cpython(directory, name, text)
            self.assertEqual(want_rc, 0)
            for mode in ('g', 'd'):
                with self.subTest(name=name, mode=mode):
                    exe, built = build(directory, name + '_' + mode, text, mode)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want)
                    self.assertEqual(got.returncode, want_rc)

    def test_float_of_out_of_int64_constant_matches_cpython(self):
        self.check_match('float_fit', FLOAT_MATCH)

    def test_reducing_intermediates_match_cpython(self):
        self.check_match('intermediate_fit', INTERMEDIATE_MATCH)

    def test_negative_fractional_power_is_refused_by_name(self):
        text = '''def main() -> None:
    print(float(-(10**40)) ** 1.5)


main()
'''
        with tempfile.TemporaryDirectory(prefix='ail-pre302-') as directory:
            for mode in ('g', 'd'):
                with self.subTest(mode=mode):
                    _, built = build(directory, 'negative_fractional_' + mode, text, mode)
                    self.assertNotEqual(built.returncode, 0, mode)
                    self.assertIn('complex number', built.stdout + built.stderr, mode)

    def test_values_that_cannot_be_an_int64_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre302-') as directory:
            for name, text in REFUSED.items():
                for mode in ('g', 'd'):
                    with self.subTest(name=name, mode=mode):
                        _, built = build(directory, name + '_' + mode, text, mode)
                        self.assertNotEqual(built.returncode, 0, (name, mode))
                        message = built.stdout + built.stderr
                        self.assertTrue(any(item in message for item in REFUSALS), (name, mode, message))
                        self.assertNotIn('integer overflow', message, (name, mode))


if __name__ == '__main__':
    unittest.main()
