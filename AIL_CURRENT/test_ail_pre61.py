"""Pre61: functools.partial of a def or lambda with bound values compiles.

The general path lowers `partial(f, a, b, k=v)` to plain lambda closures. The synthetic inner
lambdas had no source location, so the lambda scan that looks for a name bound after a lambda
stopped with `AttributeError: 'Lambda' object has no attribute 'lineno'` (pyboxed2.py). The
lowering now copies the partial() call's location onto every lambda it builds. Bound values that
arrive through an argument, a list item, a dict value or an attribute keep working, as do an empty
binding list, negative values and map() over the partial. The shapes the general path still refuses
(a callable that is not a def/lambda of the program, too many bound arguments, a non-trailing
keyword, *args, no function) stay refused by name.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


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
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre61-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('not in the subset', message, (name, general, message[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre61-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


MATCH = {
    'lambda_bound': '''from functools import partial

p = partial(lambda a, b: a * b, 6)
print(p(7), partial(lambda x: x + 1, 41)())
''',
    'def_bound_map': '''from functools import partial


def add(a, b):
    return a + b


p = partial(add, 1)
print(p(2), list(map(p, [1, 2, 3])))
r = partial(add, b=10)
print(r(5))
''',
    'routes': '''from functools import partial


def scale(a, b):
    return a * b


def call(f, v):
    return f(v)


p = partial(scale, 3)
xs = [p]
d = {"p": p}


class C:
    pass


c = C()
c.p = p
q = c.p
print(p(4), xs[0](5), d["p"](6), q(7), call(p, 8))
print(list(map(p, [1, 2, 3])))
print(partial(scale)(2, 5))
''',
    'runtime_bound': '''from functools import partial


def add(a, b):
    return a + b


n = 3
p = partial(add, n)
print(p(4), p(-7))
print(partial(add, 0)(0), partial(add, -2)(5))
''',
}

REFUSED = {
    'not_a_def': 'from functools import partial\nprint(partial(len)([1, 2]))\n',
    'too_many': 'from functools import partial\n\ndef f(a, b):\n    return a + b\n\nprint(partial(f, 1, 2, 3)())\n',
    'keyword_not_last': 'from functools import partial\n\ndef f(a, b):\n    return a + b\n\nprint(partial(f, a=1)(2))\n',
    'no_function': 'from functools import partial\nprint(partial())\n',
    'starred': 'from functools import partial\n\ndef f(a, b):\n    return a + b\n\nprint(partial(f, *[1])(2))\n',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class PartialBoundValues(unittest.TestCase):
    def test_matching_programs(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)

    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)


if __name__ == '__main__':
    unittest.main()
