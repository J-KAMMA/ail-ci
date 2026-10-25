"""A constant shift outside int64 is refused by name, including a bool operand.

CPython's ints are unbounded, so ``True << 64`` prints a bignum and an in-range expression
such as ``(1 << 64) >> 64`` prints 1.  AIL integers are fixed width: a constant shift whose
value leaves int64 used to compile and then stop with ``integer overflow``.  The front end now
refuses the outermost constant expression by name when its final value does not fit, on both
builds.  Shifts whose final value fits (even when an intermediate leaves int64) keep their
CPython behaviour when the code generator can fold that intermediate; a larger one is refused,
so an in-range shift cannot hide an out-of-range power.  Zero shifts by any count and negative
counts are unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OUT_OF_RANGE = {
    'bool_literal': '''print(True << 64)
''',
    'int_literal': '''print(1 << 64)
''',
    'bool_negative_result': '''print(-(True << 64))
''',
    'argument': '''def take(x):
    print(x)


take(True << 64)
''',
    'list_item': '''print([True << 64])
''',
    'class_attribute': '''class C:
    x = True << 64


print(C.x)
''',
    'dict_value': '''print({"k": True << 64})
''',
    'assignment': '''X = True << 64
print(X)
''',
    'nested_power_under_shift': '''print(((10 ** 64) ** 64) >> 100001)
''',
    'nested_power_under_shift_100000': '''print(((10 ** 64) ** 64) >> 100000)
''',
}

IN_RANGE = '''print(True << 0)
print(True << 62)
print((True << 62) - 1)
print(False << 64)
print(0 << 64)
print(0 << 1000)
print(True >> 64)
print(False >> 64)
print((1 << 64) >> 64)
print(1 << 64 >> 64)
print((10 ** 64) >> 100000)
print((1 << 63) - 1)
print(2 ** 62 << 1 >> 1)
try:
    print(1 << -1)
except ValueError as e:
    print(type(e).__name__, e)
'''


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


class Pre201Tests(unittest.TestCase):
    def test_out_of_int64_shifts_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre201-') as directory:
            for label, text in OUT_OF_RANGE.items():
                for general in (True, False):
                    with self.subTest(label + ('_g' if general else '_d')):
                        built, _ = _build(directory, '%s_%s' % (label, 'g' if general else 'd'),
                                          text, general)
                        self.assertNotEqual(built.returncode, 0, label)
                        message = built.stdout + built.stderr
                        self.assertIn('int64 constant out of range', message, label)
                        self.assertNotIn('integer overflow', message, label)
                        self.assertNotIn('Traceback', message, label)

    def test_in_range_shifts_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre201-') as directory:
            want, want_rc, err = _cpython(directory, 'in_range', IN_RANGE)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                with self.subTest('in_range_' + ('g' if general else 'd')):
                    got, build_err = _run(directory, 'in_range_' + ('g' if general else 'd'),
                                          IN_RANGE, general)
                    self.assertIsNotNone(got, build_err)
                    self.assertEqual(got, (want, want_rc), build_err)


if __name__ == '__main__':
    unittest.main()
