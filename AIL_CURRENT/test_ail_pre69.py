"""A constant integer `**` whose exact result leaves int64 is refused by name at compile time.

CPython answers `10 ** 100` because its int is unbounded.  This compiler's int is 64-bit, so the
expression used to compile and then stop the program at run time with `integer overflow`.  The
value is known while compiling, so both builds now refuse the construct by name instead.  A float
operand, a negative constant exponent and every power that fits are untouched.

The current tree's generic constant folder makes that refusal on the default and general-v2
paths (``int64 constant out of range`` / ``int64 constant expression out of range`` / ``outside
the signed 64-bit range``); the older v1 general emitter now shares the accepted
``does not fit in a 64-bit signed integer`` refusal, so an assignment there is refused too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = (
    ('top_level', 'print(10 ** 100)\n'),
    ('argument', 'def take(v):\n    return v\n\n\ndef main():\n    print(take(10 ** 100))\n\n\nmain()\n'),
    ('list_item', 'def main():\n    xs = [2 ** 63, 3]\n    print(xs[0])\n\n\nmain()\n'),
    ('attribute', 'class C:\n    def __init__(self):\n        self.v = 10 ** 100\n\n\ndef main():\n'
                  '    c = C()\n    print(c.v)\n\n\nmain()\n'),
    ('huge_exponent', 'print(2 ** 100000000)\n'),
    ('assignment', 'def main():\n    x = 10 ** 100\n    print(x)\n\n\nmain()\n'),
    ('nested', 'def main():\n    x = (2 ** 32) ** 2\n    print(x)\n\n\nmain()\n'),
)

# The v1 general emitter (AIL_GENERAL=v1) used to let an assignment through where the default and
# general-v2 paths refused it, then stopped at run time with `integer overflow`.
V1_REFUSED = (
    ('v1_assignment', 'def main():\n    x = 10 ** 100\n    print(x)\n\n\nmain()\n'),
    ('v1_assignment_expr', 'def main():\n    x = (10 ** 100) + 1\n    print(x)\n\n\nmain()\n'),
    ('v1_assignment_63', 'def main():\n    x = 2 ** 63\n    print(x)\n\n\nmain()\n'),
    ('v1_nested', 'def main():\n    x = (2 ** 32) ** 2\n    print(x)\n\n\nmain()\n'),
    ('v1_attribute', 'class C:\n    def __init__(self):\n        self.v = 10 ** 100\n\n\ndef main():\n'
                     '    c = C()\n    print(c.v)\n\n\nmain()\n'),
)

# Every wording a compile-time out-of-int64 constant currently uses on this tree.
NAMED = ('int64 constant out of range',
         'int64 constant expression out of range',
         'outside the signed 64-bit range',
         'does not fit in a 64-bit signed integer')

ACCEPTED = r'''def main():
    print(2 ** 62)
    print((-2) ** 62)
    print((-2) ** 63)
    print(-(2 ** 63))
    print(2 ** 63 - 1)
    print(0 ** 0, 0 ** 100)
    print(1 ** 1000000)
    print((-1) ** 1000001)
    print(10 ** 18)
    print(9 ** 19)
    print(3037000499 ** 2)
    print((-3) ** 38)
    print(2 ** True)
    print(2 ** False)
    print(10 ** 100.0)
    print(10.0 ** 100)
    print(2 ** -1)
    print(10 ** -100)
    print((2 ** 31) ** 2)
    n = 62
    print(2 ** n)


main()
'''


def build_run(directory, text, name, general, v1=False):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s%s' % (name, 'g' if general else 'd', '_v1' if v1 else ''))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    elif v1:
        env['AIL_GENERAL'] = 'v1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


class Pre69(unittest.TestCase):
    def test_overflowing_constant_power_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre69-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertTrue(any(marker in output for marker in NAMED), output)
                        self.assertNotIn('integer overflow', output)
                        self.assertNotIn('Traceback', output)

    def test_v1_assignment_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre69-') as directory:
            for name, text in V1_REFUSED:
                with self.subTest(case=name):
                    status, _, output = build_run(directory, text, name, False, v1=True)
                    self.assertNotEqual(status, 0, output)
                    self.assertTrue(any(marker in output for marker in NAMED), output)
                    self.assertNotIn('integer overflow', output)
                    self.assertNotIn('Traceback', output)

    def test_powers_that_fit_and_float_powers_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre69-') as directory:
            want = subprocess.run([sys.executable, '-B', '-c', ACCEPTED], capture_output=True, timeout=120)
            for general in (False, True):
                with self.subTest(general=general):
                    status, got, output = build_run(directory, ACCEPTED, 'accepted', general)
                    self.assertEqual(status, 0, output)
                    self.assertEqual(got, want.stdout.replace(b'\r\n', b'\n'), output)


if __name__ == '__main__':
    unittest.main()
