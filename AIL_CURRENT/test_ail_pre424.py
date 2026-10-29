"""pre424 follow-up: routed powers print CPython's exact integers.

The pre415 review recorded as pre-existing, on both builds, that a constant
power reached through a call stopped with ``integer overflow`` when a list
holding its operands was mutated only in unreachable code.  pre424 added a
routed-power pass that refused those calls by name.  Integers are now exact
bigints by default (ail-ci#198), so a power reached through a call, a literal
tuple/list, an alias, a list item, a class attribute, a dict value or a wrapper
argument prints CPython's exact integer; the int64 routed-power pass is no
longer needed and was removed.  A mutation that can run before the call (an
item or slice store, an alias, a helper call or a module-level store) still
matches CPython, and a function-local shadow never falls back to a module
value.  The one remaining refusal is the separate unsupported mixed
star/keyword call, which is refused by name on both builds.  On an int64-only
build, which cannot print these values, the exact-output test skips.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

EXACT_INTEGERS = {
    'dead_loop_module': '''
def power(b, e):
    return b ** e

xs = [2, 100]
for unused in ():
    xs[1] = 3
print(power(*xs))
''',
    'dead_loop_local': '''
def power(b, e):
    return b ** e

def go(xs):
    for unused in ():
        xs[1] = 3
    return power(*xs)

print(go([2, 100]))
''',
    'dead_if': '''
def power(b, e):
    return b ** e

xs = [2, 100]
if False:
    xs[1] = 3
print(power(*xs))
''',
    'dead_else': '''
def power(b, e):
    return b ** e

xs = [2, 100]
if True:
    pass
else:
    xs[1] = 3
print(power(*xs))
''',
    'dead_after_return': '''
def power(b, e):
    return b ** e

def go():
    xs = [2, 100]
    return power(*xs)
    xs[1] = 3

print(go())
''',
    'direct_star_tuple': '''
def power(b, e):
    return b ** e

print(power(*(2, 100)))
''',
    'module_list': '''
def power(b, e):
    return b ** e

values = [2, 100]
print(power(*values))
''',
    'alias': '''
def power(b, e):
    return b ** e

args = (2, 100)
alias = args
print(power(*alias))
''',
    'list_item': '''
def power(b, e):
    return b ** e

holder = [(2, 100)]
print(power(*holder[0]))
''',
    'class_attribute': '''
def power(b, e):
    return b ** e

class Box:
    args = (2, 100)

print(power(*Box.args))
''',
    'dict_value': '''
def power(b, e):
    return b ** e

settings = {"args": (2, 100)}
print(power(*settings["args"]))
''',
    'wrapper_argument': '''
def power(b, e):
    return b ** e

def go(a):
    return power(*a)

print(go((2, 100)))
''',
    'local_tuple': '''
def go():
    args = (2, 100)
    return power(*args)

def power(b, e):
    return b ** e

print(go())
''',
    'negative': '''
def power(b, e):
    return b ** e

args = (-2, 100)
print(power(*args))
''',
}

NAMED_REFUSALS = {
    'mixed_star_keyword': ('''
def power(b, e):
    return b ** e

args = (2,)
print(power(*args, e=100))
''', 'a *argument in a call'),
}

MATCHING = {
    'mutation_before_parameter': '''
def power(b, e):
    return b ** e

def go(a):
    a[1] = 3
    return power(*a)

print(go([2, 100]))
''',
    'mutation_before_slice': '''
def power(b, e):
    return b ** e

def go(a):
    a[:] = [2, 3]
    return power(*a)

print(go([2, 100]))
''',
    'mutation_before_helper': '''
def power(b, e):
    return b ** e

def mutate(a):
    a[1] = 3

def go(a):
    mutate(a)
    return power(*a)

print(go([2, 100]))
''',
    'mutation_before_module_call': '''
def power(b, e):
    return b ** e

xs = [2, 100]
xs[1] = 3
print(power(*xs))
''',
    'shadow_scalar': '''
def power(b, e):
    return b ** e

x = 2

def go(n):
    x = n
    return power(x, 100)

print(go(1))
''',
    'shadow_tuple': '''
def power(b, e):
    return b ** e

args = (2, 100)

def go(n):
    args = (1, n)
    return power(*args)

print(go(100))
''',
    'shadow_list': '''
def power(b, e):
    return b ** e

values = [2, 100]

def go(n):
    values = [1, n]
    return power(*values)

print(go(100))
''',
    'in_range_routes': '''
def power(b, e):
    return b ** e

def go(a):
    return power(*a)

args = (2, 10)
values = [2, 10]
holder = [(2, 10)]
settings = {'args': (2, 10)}

class Box:
    args = (2, 10)

print(power(*args), power(*values), power(*holder[0]), power(*Box.args))
print(power(*settings['args']), go((2, 10)), go([2, 10]))
print(power(*(2, 62)), power(*(2.0, 10)), power(*(True, 10)), power(*(2, -3)))
print(power(*(0, 1000000)), power(*(1, 1000000)), power(*(-1, 1000001)))
''',
    'unrelated_power': '''
def add(a, b):
    return a + b

def power(b, e):
    return b ** e

print(add(2, 3), power(2, 10))
xs = [1, 2, 3]
print(xs[1], len(xs))
''',
}


def _run_cpython(directory, name, text):
    source = Path(directory) / (name + '_cpython.py')
    source.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=1200, env=env)


def _build_and_run(directory, name, text, general):
    exe, built = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace')[-1500:])


EXACT_INT_PROBE = 'print(2 ** 100)\n'
EXACT_INT_OUTPUT = b'1267650600228229401496703205376\n'


def _exact_integers(directory):
    got, _ = _build_and_run(directory, 'exact_int_probe', EXACT_INT_PROBE, False)
    return got == (EXACT_INT_OUTPUT, 0)


class Pre424Tests(unittest.TestCase):
    def test_routed_and_dead_mutation_powers_print_exact_integers(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre424-') as directory:
            if not _exact_integers(directory):
                self.skipTest('int64-only build; exact integers need the bigint build')
            for slug, text in EXACT_INTEGERS.items():
                want = _run_cpython(directory, slug, text)
                self.assertEqual(want[1], 0, slug)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_mixed_star_keyword_is_still_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre424-') as directory:
            for slug, (text, message) in NAMED_REFUSALS.items():
                self.assertEqual(_run_cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    _, built = _build(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertNotEqual(built.returncode, 0,
                                        '%s (general=%s) compiled\n%s'
                                        % (slug, general, built.stdout + built.stderr))
                    self.assertIn(message, built.stdout + built.stderr, slug)
                    self.assertNotIn('integer overflow', built.stdout + built.stderr, slug)

    def test_reachable_mutations_shadowing_and_in_range_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre424-') as directory:
            for slug, text in MATCHING.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()
