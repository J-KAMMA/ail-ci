"""pre400: a power routed through keyword call arguments is refused by name.

The pre385 review recorded as pre-existing that ``def power(b, e): return b ** e`` called as
``power(b=2, e=100)`` still compiled on both builds and then stopped with ``integer overflow``,
where CPython prints the bignum.  The routed-power pass now binds keyword arguments (including
mixed positional/keyword calls, keyword-only parameters and a keyword call nested inside another
function) as well as positional ones, so an out-of-int64 constant result is refused by name.

In-range keyword calls, a parameter the callee stores to before the power, a non-power call and
values that are not statically known still match CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def build_run(directory, text, name, general):
    src = Path(directory) / ('%s.py' % name)
    exe = Path(directory) / ('%s_%s' % (name, 'g' if general else 'd'))
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    env.pop('AIL_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


def run_cpython(directory, text, name):
    src = Path(directory) / ('%s_cpython.py' % name)
    src.write_text(text, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', src.name], cwd=directory,
                         capture_output=True, text=True,
                         env=dict(os.environ, PYTHONUTF8='1'), timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


REFUSED = (
    ('both_keywords', 'def power(b, e):\n    return b ** e\n\n\n'
                      'print(power(b=2, e=100))\n'),
    ('reversed_keywords', 'def power(b, e):\n    return b ** e\n\n\n'
                          'print(power(e=100, b=2))\n'),
    ('mixed', 'def power(b, e):\n    return b ** e\n\n\n'
              'print(power(2, e=100))\n'),
    ('keyword_only', 'def power(*, b, e):\n    return b ** e\n\n\n'
                     'print(power(b=2, e=100))\n'),
    ('keyword_wrapper', 'def power(b, e):\n    return b ** e\n\n\n'
                        'def go(a, c):\n    return power(b=a, e=c)\n\n\n'
                        'print(go(a=2, c=100))\n'),
    ('keyword_pow', 'def power(b, e):\n    return pow(b, e)\n\n\n'
                    'print(power(b=2, e=100))\n'),
    ('keyword_exponent_63', 'def power(b, e):\n    return b ** e\n\n\n'
                            'print(power(b=2, e=63))\n'),
    ('keyword_store_after', 'def power(b, e):\n    v = b ** e\n    b = 1\n'
                            '    return v\n\n\nprint(power(b=2, e=100))\n'),
)

SAFE = r'''def power(b, e):
    return b ** e


def add(b, e):
    return b + e


def assign(b, e):
    b = 1
    return b ** e


def main(n):
    print(power(b=2, e=10), power(e=10, b=2), power(2, e=10))
    print(power(b=2, e=62), power(b=-2, e=63), power(b=0, e=100))
    print(power(b=2.0, e=100), power(b=True, e=100), power(b=2, e=-3))
    print(add(b=2, e=100), assign(b=2, e=100))
    print(power(b=2, e=n))


main(10)
'''


class Pre400(unittest.TestCase):
    def test_keyword_routed_power_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre400-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertIn('int64 constant expression out of range', output)
                        if name != 'keyword_pow':
                            self.assertIn('through a call', output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('integer overflow', output)

    def test_in_range_keyword_calls_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre400-') as directory:
            want = run_cpython(directory, SAFE, 'safe')
            for general in (False, True):
                with self.subTest(general=general):
                    got = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual((got[1].decode('utf-8'), got[0]), want, got[2])


if __name__ == '__main__':
    unittest.main()
