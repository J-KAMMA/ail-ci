"""A constant integer `**` whose exact result leaves int64 is refused by name at compile time.

CPython answers `10 ** 100` because its int is unbounded.  This compiler's int is 64-bit, so the
expression used to compile and then stop the program at run time with `integer overflow`.  The
value is known while compiling, so both builds now refuse the construct by name instead.  A float
operand, a negative constant exponent and every power that fits are untouched.
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
)

ACCEPTED = r'''def main():
    print(2 ** 62)
    print((-2) ** 62)
    print((-2) ** 63)
    print(0 ** 0, 0 ** 100)
    print(1 ** 1000000)
    print((-1) ** 1000001)
    print(10 ** 18)
    print(9 ** 19)
    print(3037000499 ** 2)
    print((-3) ** 38)
    print(2 ** True)
    print(10 ** 100.0)
    print(10.0 ** 100)
    print(2 ** -1)
    print(10 ** -100)


main()
'''


def build_run(directory, text, name, general):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s' % (name, 'g' if general else 'd'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
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
                        self.assertEqual(status, 3, output)
                        self.assertIn('does not fit in a 64-bit signed integer', output)
                        self.assertIn('not in the subset:', output)

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
