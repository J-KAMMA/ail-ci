"""pre415: a power routed through a starred call argument is refused by name.

The pre400 review recorded as pre-existing that ``def power(b, e): return b ** e`` called as
``power(*args)`` with a constant tuple or list still compiled on both builds and then stopped
with ``integer overflow``, where CPython prints the bignum.  The routed-power pass now binds
the values a starred argument unpacks (a literal, a module or local tuple/list, an alias, a
list item, a class attribute, a dict value or a wrapper argument) as well as ordinary keyword
and positional arguments, so an out-of-int64 constant result is refused by name.

In-range starred calls, int64 boundaries, float/bool/negative exponents, safe bases, a mutation
before the call, a callee that stores to its parameter before the power and a non-power call
still match CPython.  The review's first item, a ``**kwargs`` call, is already refused by name
on both builds and is pinned here.
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
    ('direct_literal', 'def power(b, e):\n    return b ** e\n\n\n'
                       'print(power(*(2, 100)))\n'),
    ('module_tuple', 'def power(b, e):\n    return b ** e\n\n\n'
                     'args = (2, 100)\nprint(power(*args))\n'),
    ('module_list', 'def power(b, e):\n    return b ** e\n\n\n'
                    'args = [2, 100]\nprint(power(*args))\n'),
    ('alias', 'def power(b, e):\n    return b ** e\n\n\n'
              'args = (2, 100)\nalias = args\nprint(power(*alias))\n'),
    ('list_item', 'def power(b, e):\n    return b ** e\n\n\n'
                  'holder = [(2, 100)]\nprint(power(*holder[0]))\n'),
    ('class_attribute', 'def power(b, e):\n    return b ** e\n\n\n'
                        'class Box:\n    args = (2, 100)\n\n\n'
                        'print(power(*Box.args))\n'),
    ('dict_value', 'def power(b, e):\n    return b ** e\n\n\n'
                   'settings = {"args": (2, 100)}\n'
                   'print(power(*settings["args"]))\n'),
    ('wrapper_argument', 'def power(b, e):\n    return b ** e\n\n\n'
                         'def go(a):\n    return power(*a)\n\n\n'
                         'print(go((2, 100)))\n'),
    ('local_tuple', 'def go():\n    args = (2, 100)\n    return power(*args)\n\n\n'
                    'def power(b, e):\n    return b ** e\n\n\n'
                    'print(go())\n'),
    ('pow_builtin', 'def power(b, e):\n    return pow(b, e)\n\n\n'
                    'args = (2, 100)\nprint(power(*args))\n'),
    ('mixed_star_keyword', 'def power(b, e):\n    return b ** e\n\n\n'
                           'args = (2,)\nprint(power(*args, e=100))\n'),
    ('negative', 'def power(b, e):\n    return b ** e\n\n\n'
                 'args = (-2, 100)\nprint(power(*args))\n'),
)

SAFE = r'''def power(b, e):
    return b ** e


def go(a):
    return power(*a)


def assign(b, e):
    b = 1
    return b ** e


def loop(b, e):
    for b in (1,):
        pass
    return b ** e


def stored(a):
    a = (1, 10)
    return power(*a)


class Box:
    args = (2, 10)


args = (2, 10)
values = [2, 10]
holder = [(2, 10)]
settings = {'args': (2, 10)}
mutated = [2, 100]
mutated[1] = 10

print(power(*args), power(*values), power(*holder[0]), power(*Box.args))
print(power(*settings['args']), go((2, 10)), go([2, 10]))
print(power(*(-2, 63)))
print(power(*(2.0, 100)), power(*(True, 100)), power(*(2, -3)))
print(power(*(0, 10 ** 6)), power(*(1, 10 ** 6)), power(*(-1, 10 ** 6)))
print(power(*mutated))
print(power(b=2, e=10), power(2, e=10))
print(assign(2, 100), loop(2, 100), stored((2, 100)))
'''


class Pre415(unittest.TestCase):
    def test_starred_routed_power_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre415-') as directory:
            for name, text in REFUSED:
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertIn('int64 constant expression out of range', output)
                        self.assertIn('through a call', output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('integer overflow', output)

    def test_in_range_starred_calls_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre415-') as directory:
            want = run_cpython(directory, SAFE, 'safe')
            for general in (False, True):
                with self.subTest(general=general):
                    got = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual((got[1].decode('utf-8'), got[0]), want, got[2])

    def test_kwargs_is_refused_by_name(self):
        text = ('def power(b, e):\n    return b ** e\n\n\n'
                'kw = {"b": 2, "e": 100}\nprint(power(**kw))\n')
        with tempfile.TemporaryDirectory(prefix='ail-pre415-') as directory:
            for general in (False, True):
                with self.subTest(general=general):
                    status, _, output = build_run(directory, text, 'kwargs', general)
                    self.assertNotEqual(status, 0, output)
                    self.assertIn('a **kwargs call argument', output)
                    self.assertNotIn('integer overflow', output)


if __name__ == '__main__':
    unittest.main()
