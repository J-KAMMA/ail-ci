"""pre431: a loop store before a routed power still refuses an out-of-int64 result.

The rbpre400 review recorded that a power reached through a call was still left to the
run-time ``integer overflow`` stop when the callee stored to a parameter in a loop before
the power (``p10``), even though the stored constant was the call-site value.  The routed
power check now follows simple stores: a store that leaves the same value, a loop that
assigns one constant, and an unreachable branch or empty loop no longer hide the power.
A different constant assigned by a loop that runs, and a module loop before the call, are
folded the same way; a conditional or repeated store that may change the value keeps the
pre-existing run-time stop.  Sequential stores to one name are folded in order, so two
stores that undo each other leave an in-range power alone (``sequential``); a store that
reads another tracked name a store may have changed is dropped instead of being folded
against the stale call-site value (``cross_name``, ``cross_expr``).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REFUSAL = 'int64 constant expression out of range'

REFUSED = {
    'loop_self': '''
def power(b, e):
    for i in range(1):
        b = b
    return b ** e
print(power(b=2, e=100))
''',
    'loop_same_constant': '''
def power(b, e):
    for i in range(2):
        b = 2
    return b ** e
print(power(b=2, e=100))
''',
    'loop_other_constant': '''
def power(b, e):
    for i in range(2):
        b = 3
    return b ** e
print(power(b=2, e=100))
''',
    'loop_exponent': '''
def power(b, e):
    for i in range(1):
        e = e
    return b ** e
print(power(b=2, e=100))
''',
    'loop_augmented_zero': '''
def power(b, e):
    for i in range(2):
        b += 0
    return b ** e
print(power(b=2, e=100))
''',
    'empty_loop': '''
def power(b, e):
    for i in []:
        b = 2
    return b ** e
print(power(b=2, e=100))
''',
    'module_loop': '''
def power(b, e):
    return b ** e
for i in range(1):
    b = 2
    e = 100
print(power(b=b, e=e))
''',
    'module_loop_other': '''
def power(b, e):
    return b ** e
for i in range(2):
    b = 3
    e = 100
print(power(b=b, e=e))
''',
    'list_item': '''
def power(b, e):
    return b ** e
vals = [2, 100]
print(power(b=vals[0], e=vals[1]))
''',
    'dict_value': '''
def power(b, e):
    return b ** e
vals = {'b': 2, 'e': 100}
print(power(b=vals['b'], e=vals['e']))
''',
    'attribute': '''
def power(b, e):
    return b ** e
class C:
    b = 2
    e = 100
print(power(b=C.b, e=C.e))
''',
    'alias': '''
def power(b, e):
    return b ** e
base = 2
exponent = 100
print(power(b=base, e=exponent))
''',
    'sequential_stores': '''
def power(b, e):
    b = b - 1
    b = b + 1
    return b ** e
print(power(2, 100))
''',
}

SAFE = r'''
def power(b, e):
    for i in range(2):
        b = 3
    return b ** e


def empty(b, e):
    for i in range(0):
        b = 4000000000
    return b ** e


def conditional(b, e):
    if flag:
        b = 4000000000
    return b ** e


def augmented(b, e):
    for i in range(2):
        b += 1
    return b ** e


def stored_before(b, e):
    b = 1
    return b ** e


def plain(b, e):
    return b ** e


def sequential(b, e):
    b = -b
    b = -b
    return b ** e


def cross_name(b, e):
    b = 1
    e = b
    b = -2
    return b ** e


def cross_expr(b, e):
    b = 1
    e = b + 62
    b = -2
    return b ** e


flag = False
print(power(2, 2), empty(2, 2), conditional(2, 2), augmented(2, 2))
print(stored_before(2, 100))
print(sequential(-2, 63))
print(cross_name(2000, 0), cross_expr(2, 0))
print(plain(b=2, e=62), plain(b=-2, e=63), plain(b=0, e=100))
print(plain(b=2.0, e=100), plain(b=True, e=100), plain(b=2, e=-3))
print(plain(b=2, e=10), plain(e=10, b=2), plain(2, e=10))
'''


def run_cpython(directory, text, name):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.returncode, done.stdout.replace(b'\r\n', b'\n')


def build_run(directory, text, name, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                            '--syntax', 'python', '-o', str(exe)], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode:
        return built.returncode, b'', built.stdout + built.stderr
    ran = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return ran.returncode, ran.stdout.replace(b'\r\n', b'\n'), built.stdout + built.stderr


class Pre431(unittest.TestCase):
    def test_loop_store_before_power_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre431-') as directory:
            for name, text in REFUSED.items():
                for general in (False, True):
                    with self.subTest(case=name, general=general):
                        status, _, output = build_run(directory, text, name, general)
                        self.assertNotEqual(status, 0, output)
                        self.assertIn(REFUSAL, output)
                        self.assertNotIn('Traceback', output)
                        self.assertNotIn('integer overflow', output)

    def test_in_range_and_pre_existing_stops_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre431-') as directory:
            want = run_cpython(directory, SAFE, 'safe')
            for general in (False, True):
                with self.subTest(general=general):
                    status, stdout, output = build_run(directory, SAFE, 'safe', general)
                    self.assertEqual((status, stdout), want, output)


if __name__ == '__main__':
    unittest.main()
