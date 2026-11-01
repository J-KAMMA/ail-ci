"""The default int64 mode at the power and round boundaries, with values taken at run time.

The pre425/pre429/pre433 rewrites test the routes and the compile-time refusals.  This module
adds the other half: a value that only arrives at run time (from ``sys.argv``) is not seen by
the constant folder, so the int64 default reaches its checked operator instead of refusing the
program.  A widened ``b **= e`` stops loudly on the typed and forced general paths, while an
in-range one matches CPython (including the 2**62 / -2**63 boundaries, 0**0, negative
exponents, bases 0/1/-1 and bool-free integer work).  ``round(float)`` matches CPython just
inside and just outside int64; a wide finite value is a loud typed stop and a catchable
OverflowError on the general path (the declared C74/A1 difference).  ``--exact-int`` /
``AIL_EXACT_INT=1`` computes every case exactly, so it matches CPython on both paths.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

POWER = '''import sys


def power(b, e):
    b **= e
    return b


try:
    print(power(int(sys.argv[1]), int(sys.argv[2])))
except OverflowError:
    print("caught")
print("after")
'''

ROUND = '''import sys


v = float(sys.argv[1])
try:
    print(round(v))
except OverflowError:
    print("caught")
print("after")
'''

INT64_MODES = (
    ('int64_default', {}),
    ('int64_default_ir', {'AIL_IR': '1'}),
    ('int64_general', {'AIL_UNIFIED_FORCE': '1'}),
)

INT64_TYPED = tuple(mode for mode in INT64_MODES if 'AIL_UNIFIED_FORCE' not in mode[1])

EXACT_MODES = (
    ('exact', {'AIL_EXACT_INT': '1'}),
    ('exact_general', {'AIL_EXACT_INT': '1', 'AIL_UNIFIED_FORCE': '1'}),
)

ALL_MODES = INT64_MODES + EXACT_MODES


def cpython(directory, name, text, args):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', src.name, *args], cwd=directory,
                          capture_output=True, timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build_run(directory, name, text, args, extra):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_EXACT_INT'):
        env.pop(key, None)
    env.update(extra)
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True,
                           timeout=900, env=env)
    if built.returncode:
        return None, built.returncode, built.stdout + built.stderr
    ran = subprocess.run([str(exe), *args], cwd=directory, capture_output=True, timeout=120)
    return ran, 0, ''


class Int64Edges(unittest.TestCase):
    def same(self, name, text, args, modes=ALL_MODES):
        with tempfile.TemporaryDirectory(prefix='ail-i64edges-') as directory:
            want, want_rc = cpython(directory, name, text, args)
            for mode, extra in modes:
                with self.subTest(name=name, args=args, mode=mode):
                    got, build_rc, err = build_run(directory, name + '_' + mode, text, args, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, args, mode))
                    self.assertEqual(got.returncode, want_rc, (name, args, mode, got.stderr[-1500:]))

    def stopped(self, name, text, args, modes=INT64_MODES, stdout=b''):
        with tempfile.TemporaryDirectory(prefix='ail-i64edges-') as directory:
            for mode, extra in modes:
                with self.subTest(name=name, args=args, mode=mode):
                    got, build_rc, err = build_run(directory, name + '_' + mode, text, args, extra)
                    self.assertIsNotNone(got, '%s %s\n%s' % (name, mode, err[-3000:]))
                    self.assertEqual(build_rc, 0, err[-3000:])
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), stdout, (name, args, mode))
                    self.assertEqual(got.returncode, 1, (name, args, mode, got.stderr[-1500:]))
                    self.assertIn(b'integer overflow', got.stderr, (name, args, mode))
                    self.assertNotIn(b'AIL limit', got.stderr, (name, args, mode))

    def test_in_range_power_boundaries_match_cpython(self):
        for args in (('2', '62'), ('-2', '63'), ('0', '0'), ('2', '-3'), ('1', '100000'),
                     ('-1', '100001'), ('3', '39')):
            self.same('power_safe', POWER, args)

    def test_runtime_wide_power_is_a_loud_stop_in_int64(self):
        for args in (('2', '63'), ('-2', '64'), ('10', '19')):
            self.stopped('power_wide', POWER, args)

    def test_runtime_wide_power_matches_cpython_with_exact_ints(self):
        for args in (('2', '63'), ('-2', '64'), ('10', '19')):
            self.same('power_wide_exact', POWER, args, EXACT_MODES)

    def test_round_boundaries_just_inside_and_outside_int64(self):
        for value in ('9223372036854774784.0', '-9223372036854774784.0', '2.5', '-2.5',
                      '0.5', '-0.5', 'nan', 'inf', '-inf'):
            self.same('round_safe', ROUND, (value,))

    def test_typed_round_just_outside_int64_is_a_loud_stop(self):
        for value in ('9300000000000000000.0', '-9300000000000000000.0', '1e20'):
            self.stopped('round_wide', ROUND, (value,), INT64_TYPED)

    def test_general_round_just_outside_int64_is_catchable(self):
        expected = b'caught\nafter\n'
        for value in ('9300000000000000000.0', '-9300000000000000000.0', '1e20'):
            with tempfile.TemporaryDirectory(prefix='ail-i64edges-') as directory:
                for mode, extra in (('int64_general', {'AIL_UNIFIED_FORCE': '1'}),
                                    ('int64_general_ir', {'AIL_UNIFIED_FORCE': '1', 'AIL_IR': '1'})):
                    with self.subTest(value=value, mode=mode):
                        got, build_rc, err = build_run(directory, 'round_wide_' + mode, ROUND,
                                                       (value,), extra)
                        self.assertIsNotNone(got, err[-3000:])
                        self.assertEqual(build_rc, 0, err[-3000:])
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), expected, (value, mode))
                        self.assertEqual(got.returncode, 0, (value, mode, got.stderr[-1500:]))
                        self.assertEqual(got.stderr, b'', (value, mode))

    def test_wide_round_matches_cpython_with_exact_ints(self):
        for value in ('9300000000000000000.0', '-9300000000000000000.0', '1e20'):
            self.same('round_wide_exact', ROUND, (value,), EXACT_MODES)


if __name__ == '__main__':
    unittest.main()
