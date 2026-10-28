"""pre436: a routed power ignores a container mutation that runs after the call.

The pre424 review recorded as pre-existing that a module list mutated after the
routed power trap stopped with ``integer overflow`` where CPython prints the
bignum.  The routed-power check dropped any list with more than one binding
before it looked at the order, so the later item store hid the literal the call
actually saw.  A call-site mutation is considered only when it can run before the
call, and it reaches a container through an alias, a nested list or dict value or
a for-loop target, so a later mutation leaves the exact out-of-int64 refusal in
place.  A mutation before the call still matches CPython, as do in-range and
non-integer operands.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = {
    'module_list_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
print(power(*xs))
xs[1] = 3
''',
    'module_append_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
print(power(*xs))
xs.append(3)
''',
    'alias_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
alias = xs
print(power(*alias))
alias[1] = 3
''',
    'dict_value_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
d = {'k': xs}
print(power(*d['k']))
d['k'][1] = 3
''',
    'local_list_mutated_after': '''
def power(b, e):
    return b ** e

def go():
    xs = [2, 100]
    result = power(*xs)
    xs[1] = 3
    return result

print(go())
''',
    'parameter_mutated_after': '''
def power(b, e):
    return b ** e

def go(a):
    result = power(*a)
    a[1] = 3
    return result

print(go([2, 100]))
''',
    'helper_mutated_after': '''
def power(b, e):
    return b ** e

def mutate(a):
    a[1] = 3

xs = [2, 100]
print(power(*xs))
mutate(xs)
''',
    'boundary_63': '''
def power(b, e):
    return b ** e

xs = [2, 63]
print(power(*xs))
xs[1] = 3
''',
    'negative_base': '''
def power(b, e):
    return b ** e

xs = [-2, 100]
print(power(*xs))
xs[1] = 3
''',
    'nested_dict_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
d = {'k': xs}
print(power(*xs))
d['k'][1] = 3
''',
    'nested_list_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
ys = [xs]
print(power(*xs))
ys[0][1] = 3
''',
    'loop_item_mutated_after': '''
def power(b, e):
    return b ** e

xs = [2, 100]
print(power(*xs))
for item in [xs]:
    item[1] = 3
''',
    'unrelated_effect_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
other = [1, 2]
other[0] = 9
print(power(*xs))
''',
}

MATCHING = {
    'module_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
xs[1] = 3
print(power(*xs))
''',
    'module_slice_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
xs[:] = [2, 3]
print(power(*xs))
''',
    'module_helper_before': '''
def power(b, e):
    return b ** e

def mutate(a):
    a[1] = 3

xs = [2, 100]
mutate(xs)
print(power(*xs))
''',
    'local_mutated_before': '''
def power(b, e):
    return b ** e

def go():
    xs = [2, 100]
    xs[1] = 3
    return power(*xs)

print(go())
''',
    'parameter_mutated_before': '''
def power(b, e):
    return b ** e

def go(a):
    a[1] = 3
    return power(*a)

print(go([2, 100]))
''',
    'alias_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
alias = xs
alias[1] = 3
print(power(*xs))
''',
    'dict_value_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
d = {'k': xs}
d['k'][1] = 3
print(power(*d['k']))
''',
    'method_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
xs.clear()
xs.extend([2, 3])
print(power(*xs))
''',
    'in_range_after': '''
def power(b, e):
    return b ** e

xs = [2, 10]
print(power(*xs))
xs[1] = 3
''',
    'in_range_after_types': '''
def power(b, e):
    return b ** e

xs = [2.0, 10]
ys = [True, 10]
zs = [2, -3]
print(power(*xs), power(*ys), power(*zs))
xs[1] = 100
ys[1] = 100
zs[1] = 100
''',
    'in_range_after_safe_bases': '''
def power(b, e):
    return b ** e

xs = [0, 1000000]
ys = [1, 1000000]
zs = [-1, 1000001]
print(power(*xs), power(*ys), power(*zs))
xs[1] = 3
ys[1] = 3
zs[1] = 3
''',
    'nested_dict_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
d = {'k': xs}
d['k'][1] = 3
print(power(*xs))
''',
    'nested_list_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
ys = [xs]
ys[0][1] = 3
print(power(*xs))
''',
    'nested_list_alias_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
ys = [xs]
alias = ys[0]
alias[1] = 3
print(power(*xs))
''',
    'deep_nested_list_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
ys = [xs]
zs = {'k': ys}
zs['k'][0][1] = 3
print(power(*xs))
''',
    'loop_item_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
for item in [xs]:
    item[1] = 3
print(power(*xs))
''',
    'loop_over_nested_list_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
ys = [xs]
for item in ys:
    item[1] = 3
print(power(*xs))
''',
    'nested_argument_mutated_before': '''
def power(b, e):
    return b ** e

def go(a, b):
    b[1] = 3
    return power(*a)

xs = [2, 100]
print(go(xs, xs))
''',
    'loop_tuple_target_mutated_before': '''
def power(b, e):
    return b ** e

xs = [2, 100]
for (item,) in [(xs,)]:
    item[1] = 3
print(power(*xs))
''',
    'unrelated': '''
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


def _build_and_run(directory, name, text, general):
    source = Path(directory) / (name + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                            source.name, '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=1200, env=env)
    if built.returncode:
        return None, built.stdout + built.stderr
    ran = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return ((ran.stdout.replace(b'\r\n', b'\n'), ran.returncode), built.stdout + built.stderr)


class Pre436Tests(unittest.TestCase):
    def test_mutation_after_the_call_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre436-') as directory:
            for slug, text in REFUSALS.items():
                self.assertEqual(_run_cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNone(got, '%s (general=%s) compiled\n%s'
                                      % (slug, general, build_err))
                    self.assertIn('int64 constant expression out of range', build_err, slug)
                    self.assertIn('through a call', build_err, slug)
                    self.assertNotIn('integer overflow', build_err, slug)

    def test_reachable_mutations_and_in_range_values_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre436-') as directory:
            for slug, text in MATCHING.items():
                want = _run_cpython(directory, slug, text)
                for general in (True, False):
                    got, build_err = _build_and_run(
                        directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, build_err))
                    self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, build_err))


if __name__ == '__main__':
    unittest.main()
