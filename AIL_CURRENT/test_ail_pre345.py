"""pre345: the pre9 review's pre-existing int() float-literal and int-shadow cases.

The pre9 reviewer recorded as already present before that job: the pre290 finite
float-literal refusals (a value outside int64 reached ``int()`` directly, through a
unary sign, a constant conditional, a constant, a list/tuple/dict item, an alias or a
wrapper argument), the infinity literal refusal, and the int-shadowing refusal.  CPython
prints the exact big integer for the finite values and raises OverflowError for infinity.

Reproducing them on this tree shows that both builds already refuse every out-of-range
program at compile time with a named message (``int() of a float outside int64`` or
``not in the subset``), which the task allows, so no compiler change is needed.  In-range
literals (including the int64 boundaries), a local/parameter named ``int`` and a local
shadow in an unrelated function keep CPython's result.  The test checks every route on
both builds so a wrong output or an unnamed failure is never accepted.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSALS = ('int() of a float outside int64',
            'not in the subset: a nan/inf float literal',
            'not in the subset: AIL function',
            'not in the subset: AIL constant')

CASES = {
    'direct': ('''
print(int(1e300))
''', 'refused'),
    'negative': ('''
print(int(-1e300))
''', 'refused'),
    'exact_two_to_63': ('''
print(int(9223372036854775808.0))
''', 'refused'),
    'next_below_int64_min': ('''
print(int(-9223372036854777856.0))
''', 'refused'),
    'unary_paren': ('''
print(int(-(1e300)))
''', 'refused'),
    'constant_conditional': ('''
print(int(1e300 if True else 0.0))
''', 'refused'),
    'module_constant': ('''
X = 1e300
print(int(X))
''', 'refused'),
    'list_item': ('''
xs = [1e300]
print(int(xs[0]))
''', 'refused'),
    'tuple_item': ('''
xs = (1e300, 1.5)
print(int(xs[0]))
''', 'refused'),
    'dict_value': ('''
d = {"v": 1e300}
print(int(d["v"]))
''', 'refused'),
    'aliased_list': ('''
a = [1e300]
b = a
print(int(b[0]))
''', 'refused'),
    'wrapper_positional': ('''
def take(x):
    return int(x)

def outer(y):
    return take(y)

print(outer(1e300))
''', 'refused'),
    'wrapper_keyword': ('''
def take(x):
    return int(x)

print(take(x=1e300))
''', 'refused'),
    'identity_positional_only': ('''
def take(x, /):
    return int(x)

print(take(1e300))
''', 'refused'),
    'infinity_literal': ('''
print(int(1e400))
''', 'refused'),
    'negative_infinity_literal': ('''
print(int(-1e400))
''', 'refused'),
    'in_range_boundaries': ('''
print(int(1_000.5), int(-2.9), int(0.0), int(-0.0))
print(int(9223372036854774784.0))
print(int(-9223372036854775808.0))
''', 'ran'),
    'local_int_shadow': ('''
def main():
    int = lambda x: 7
    print(int(1e300))

main()
''', 'ran'),
    'parameter_int_shadow': ('''
def f(int, x):
    return int(x)

print(f(lambda v: 7, 1e300))
''', 'ran'),
    'unrelated_local_int_shadow': ('''
def f():
    int = lambda x: 7
    return int(1.5)

def g():
    return int(1e300)

print(f(), g())
''', 'refused'),
    'module_function_int': ('''
def int(x):
    return 7

print(int(1e300))
''', 'refused'),
    'module_constant_int': ('''
print(int(1e300))
int = lambda x: 7
''', 'refused'),
}


def compile_source(directory, name, source, general):
    path = Path(directory) / (name + '.ail')
    path.write_text(source, encoding='utf-8')
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    exe = Path(directory) / (name + ('_g' if general else '_d'))
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', path.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def run_cpython(directory, name, source):
    path = Path(directory) / (name + '_cpython.py')
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, '-B', path.name], cwd=directory, capture_output=True,
                         text=True, timeout=120)
    return ran.stdout.replace('\r\n', '\n'), ran.returncode


class Pre345(unittest.TestCase):
    def test_pre9_pre_existing_int_float_and_shadow_cases(self):
        for slug, (source, expected_mode) in CASES.items():
            with tempfile.TemporaryDirectory(prefix='ail-pre345-') as directory:
                expected, status = run_cpython(directory, 'pre345_' + slug, source)
            modes = set()
            for general in (False, True):
                with self.subTest(slug=slug, general=general), \
                        tempfile.TemporaryDirectory(prefix='ail-pre345-') as directory:
                    built, exe = compile_source(directory, 'pre345_' + slug, source, general)
                    output = built.stdout + built.stderr
                    if expected_mode == 'refused':
                        self.assertNotEqual(built.returncode, 0, '%s built' % slug)
                        self.assertFalse(exe.exists(), '%s built an executable' % slug)
                        self.assertTrue(any(marker in output for marker in REFUSALS),
                                        output[-4000:])
                        modes.add('refused')
                    else:
                        self.assertEqual(built.returncode, 0, output[-4000:])
                        self.assertTrue(exe.exists(), '%s did not build' % slug)
                        ran = subprocess.run([str(exe)], cwd=directory, capture_output=True,
                                             text=True, timeout=120)
                        self.assertEqual(ran.returncode, status, ran.stdout + ran.stderr)
                        self.assertEqual(ran.stdout.replace('\r\n', '\n'), expected,
                                         ran.stdout + ran.stderr)
                        modes.add('ran')
            self.assertEqual(len(modes), 1, '%s builds disagree: %s' % (slug, sorted(modes)))


if __name__ == '__main__':
    unittest.main()
