"""Pre406: a routed known base of a constant-exponent power matches CPython.

A reviewer of pre391 recorded as pre-existing that the base of ``**`` (and of ``**=``) reached
through a dict value, a list item or a function argument still trapped with ``integer
overflow`` on both builds where CPython prints the exact bignum.  The constant-base rule only
looked at a syntactically constant base, so a value read from a safe literal container or a
known call-site argument was invisible.

On an int64 build the route check resolves such a base through the same safe value map as the
int() checks (and, for an augmented target, through a copy of the program with that statement
removed), then refuses a constant exponent whose exact result leaves int64 by name.  A build
whose integers are exact bigints (ail-ci#198) accepts the same programs and must print what
CPython prints, so the expectation is chosen from the compiler's own integer semantics: the
capability probe is an out-of-int64 ``**`` through no route.  A mutated container, a name with
several bindings, disagreeing call sites, in-range results and the safe bases 0/1/-1 keep
their CPython behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


EXACT_INTEGERS = {}


def exact_integers(general):
    """Whether this build's int is a CPython-style exact bigint instead of int64."""
    key = bool(general)
    if key not in EXACT_INTEGERS:
        with tempfile.TemporaryDirectory(prefix='ail-pre406-cap-') as directory:
            exe, built = build(directory, 'capability' + ('g' if general else 'd'),
                               'print(2 ** 63)\n', general)
            if built.returncode != 0:
                EXACT_INTEGERS[key] = False
            else:
                got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     cwd=directory)
                EXACT_INTEGERS[key] = (got.returncode == 0
                                       and got.stdout.strip() == b'9223372036854775808')
    return EXACT_INTEGERS[key]


def check_out_of_range(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre406-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name + ('g' if general else 'd'), text, general)
            if built.returncode == 0:
                test.assertTrue(exact_integers(general),
                                (name, general, 'an int64 build accepted an out-of-range power'))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120,
                                     cwd=directory)
                test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                 (name, general, got.stderr[-800:]))
                test.assertEqual(got.returncode, want[1],
                                 (name, general, got.stderr[-800:]))
                continue
            test.assertFalse(exact_integers(general),
                             (name, general, 'an exact-integer build refused a CPython value',
                              (built.stdout + built.stderr)[-1200:]))
            message = built.stdout + built.stderr
            test.assertIn('int64 constant expression out of range', message,
                          (name, general, message[-1200:]))
            test.assertNotIn('integer overflow', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre406-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                             (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'dict_value': '''
d = {'n': 10}
print(d['n'] ** 40)
''',
    'list_item': '''
values = [10]
print(values[0] ** 40)
''',
    'argument': '''
def power(b):
    print(b ** 40)


power(10)
''',
    'alias': '''
items = {'n': 10}
alias = items
print(alias['n'] ** 40)
''',
    'negative_base': '''
d = {'n': -10}
print(d['n'] ** 39)
''',
    'module_exponent': '''
e = 40
d = {'n': 10}
print(d['n'] ** e)
''',
    'augmented_dict': '''
d = {'n': 10}
print("hello")
d['n'] **= 40
print(d['n'])
''',
    'augmented_list': '''
values = [10]
values[0] **= 40
print(values[0])
''',
    'augmented_argument': '''
def power(b):
    b **= 40
    print(b)


power(10)
''',
}

MATCH = {
    'in_range_routes': '''
d = {'n': 2}
values = [3]


def power(b):
    print(b ** 10)


print(d['n'] ** 10)
print(values[0] ** 5)
power(2)
print((-2) ** 41)
''',
    'safe_bases': '''
d = {'z': 0, 'o': 1, 'm': -1}
print(d['z'] ** 100000, d['o'] ** 100000, d['m'] ** 100001)
print(2.0 ** 40)
print(True ** 40)
print(2 ** -1)
''',
    'mutated_dict': '''
d = {'n': 10}
d['n'] = 2
print(d['n'] ** 40)
''',
    'mutated_list': '''
values = [10]
values[0] = 2
print(values[0] ** 40)
''',
    'container_call': '''
values = [2]
values.append(3)
print(values[0] ** 10)
''',
    'argument_in_range': '''
def power(b):
    print(b ** 40)


power(2)
''',
    'augmented_in_range': '''
d = {'n': 2}
d['n'] **= 10
print(d['n'])
values = [3]
values[0] **= 5
print(values[0])
x = 2
x **= 10
print(x)
''',
    'no_feature': '''
d = {'n': 10}
print(d['n'] + 1)
values = [1, 2, 3]
print(values[0] * 2)


def add(b):
    return b + 7


print(add(5))
''',
}


class Pre406Tests(unittest.TestCase):
    def test_a_known_routed_base_out_of_int64_matches_cpython(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                check_out_of_range(self, slug, text)

    def test_in_range_safe_and_mutated_routes_match_cpython(self):
        for slug, text in MATCH.items():
            with self.subTest(case=slug):
                check_program(self, slug, text)


if __name__ == '__main__':
    unittest.main()
