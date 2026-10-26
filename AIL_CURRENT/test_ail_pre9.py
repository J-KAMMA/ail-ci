"""f03: `int(1e300)` was the int64-overflow stop instead of CPython's exact big integer.

CPython's int is unbounded, so `int(<float literal>)` can exceed int64. AIL's int is 64-bit
(SEMANTICS section 1), so the conversion is refused at compile time, by name, in both emitters
and on both AIL_IR paths -- the same outcome an out-of-range integer literal already gets.
In-range float literals, including the int64 minimum, and values arriving through an argument,
a list item, a dataclass attribute, a dict value or a variable keep the ordinary conversion.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AIL = str(ROOT / 'ail_chatgpt.py')
MODES = (('default', False, '1'), ('default', False, '0'), ('general', True, '1'), ('general', True, '0'))
REFUSAL = 'does not fit in a 64-bit signed integer'

OUT_OF_RANGE = {
    'positive': 'print(int(1e300))\n',
    'negative': 'print(int(-1e300))\n',
    'two_to_63': 'print(int(9223372036854775808.0))\n',
    'infinity_literal': 'print(int(1e400))\n',
}
IN_RANGE = '''print(int(1e18))
print(int(-1e18))
print(int(1.5), int(-1.5))
print(int(0.0), int(-0.0))
print(int(2.9), int(-2.9))
print(int(9.223372036854775e18))
print(int(-9223372036854775808.0))
print(int(7), int(-7))
'''
FLOWS = '''from dataclasses import dataclass


@dataclass
class Box:
    v: float


def take(x: float) -> int:
    return int(x)


def main():
    vals = [1.5, -2.5, 0.0]
    print(take(3.75))
    print(int(vals[0]), int(vals[1]), int(vals[2]))
    b = Box(-4.25)
    print(int(b.v))
    d = {"k": 6.5}
    print(int(d["k"]))
    x = -7.75
    print(int(x))
    return 0


main()
'''


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))


def build(directory, name, text, ir, general):
    src = Path(directory) / ('%s_%s_%d.py' % (name, ir, general))
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_%s_%s_%d' % (name, ir, general))
    env = dict(os.environ, AIL_SURFACE='python', AIL_IR=ir, AIL_NO_CACHE='1')
    for key in ('AIL_NO_MIX', 'AIL_NO_GENERAL'):
        env.pop(key, None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    cmd = [sys.executable, '-B', AIL, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    return exe, subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)


class Pre9(unittest.TestCase):
    def test_out_of_int64_float_literals_are_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre9-') as directory:
            for name, text in OUT_OF_RANGE.items():
                for mode, general, ir in MODES:
                    with self.subTest(case=name, mode=mode, ir=ir):
                        exe, built = build(directory, name, text, ir, general)
                        self.assertNotEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                        self.assertIn(REFUSAL, built.stdout + built.stderr)
                        self.assertIn('int()', built.stdout + built.stderr)
                        self.assertFalse(exe.exists())

    def test_in_range_values_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre9-') as directory:
            for name, text in (('literals', IN_RANGE), ('flows', FLOWS)):
                want = cpython(directory, name, text)
                self.assertEqual(want.returncode, 0, want.stderr.decode('utf-8', 'replace'))
                for mode, general, ir in MODES:
                    with self.subTest(case=name, mode=mode, ir=ir):
                        exe, built = build(directory, name, text, ir, general)
                        self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-1500:])
                        got = subprocess.run([str(exe)], capture_output=True, timeout=60, cwd=directory)
                        self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want.stdout, got.stderr[-500:])
                        self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])


if __name__ == '__main__':
    unittest.main()
