"""The fuzz52 r52_ovf boundary: constant arithmetic that cancels an out-of-int64 power.

`2**63 - 1` and `-(2**63)` used to abort at the intermediate 2**63 even though the value the
program keeps is an int64. The constant folder now evaluates such an expression exactly and only
writes a literal when the final value is in range; a constant that really is outside int64 is
refused by name instead of ending at run time.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPILER = ROOT / 'ail_chatgpt.py'

VALUES = '''def show(v: int) -> None:
    print(v)


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def main() -> None:
    show(2**63 - 1)
    show(-(2**63))
    print((-2)**63, 2**62, -(2**62))
    print((2**63 - 1) - 1, 2**63 - 2**63)
    print(2**63 // 2, 2**63 % 3)
    xs = [2**63 - 1, -(2**63)]
    print(xs[0], xs[1])
    box = Box(2**63 - 1)
    print(box.v)
    table = {"max": 2**63 - 1, "min": -(2**63)}
    print(table["max"], table["min"])


main()
'''

REFUSED = '''def main() -> None:
    print(2**63)


main()
'''

MODULE_ASSIGNMENTS = '''MAX = (2**63 - 1)
MIN = -(2**63)
KNOWN = 9223372036854775807
CANCELLED = KNOWN - 2**63
TEXT = "x" * (2**63 - 2**63)
BYTES = b"ab" * (2**63 - 2**63)
RATIO = (2**63) / 2
NESTED = (1 + (2**63 - 1)) - 2**63


def show(v: int) -> None:
    print(v)


def main() -> None:
    print(KNOWN, CANCELLED, MIN, MAX)
    print(repr(TEXT), repr(BYTES), RATIO)
    print(NESTED)
    show(CANCELLED)


main()
'''

OVERLAP_REFUSED = '''MAX = 9223372036854775807
BIG = (MAX + 1) * 2**63


def main() -> None:
    print(BIG)


main()
'''


def cpython(directory, text):
    src = Path(directory) / 'probe.py'
    src.write_text(text, encoding='utf-8')
    return subprocess.run([sys.executable, '-B', str(src)], capture_output=True, text=True, timeout=120)


def build(directory, text, unified):
    src = Path(directory) / ('probe_%s.py' % ('general' if unified else 'default'))
    exe = Path(directory) / ('probe_%s' % ('general' if unified else 'default'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return subprocess.run([sys.executable, '-B', str(COMPILER), 'compile', src.name, '--syntax', 'python',
                           '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env), exe


class Pre32(unittest.TestCase):
    def test_boundary_values_match_cpython_in_both_builds(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre32-') as directory:
            expected = cpython(directory, VALUES)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for unified in (True, False):
                with self.subTest(build='general' if unified else 'default'):
                    built, exe = build(directory, VALUES, unified)
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_module_assignments_overlapping_a_power_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre32-') as directory:
            expected = cpython(directory, MODULE_ASSIGNMENTS)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            for unified in (True, False):
                with self.subTest(build='general' if unified else 'default'):
                    built, exe = build(directory, MODULE_ASSIGNMENTS, unified)
                    self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-2000:])
                    ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120)
                    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_an_uncancelled_out_of_range_power_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre32-') as directory:
            for unified in (True, False):
                with self.subTest(build='general' if unified else 'default'):
                    built, _ = build(directory, REFUSED, unified)
                    self.assertNotEqual(built.returncode, 0)
                    self.assertIn('int64 literal out of range', built.stdout + built.stderr)

    def test_a_module_ancestor_that_overflows_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre32-') as directory:
            for unified in (True, False):
                with self.subTest(build='general' if unified else 'default'):
                    built, _ = build(directory, OVERLAP_REFUSED, unified)
                    self.assertNotEqual(built.returncode, 0)
                    text = built.stdout + built.stderr
                    self.assertTrue('int64 literal out of range' in text
                                    or 'int64 constant expression out of range' in text, text)


if __name__ == '__main__':
    unittest.main()
