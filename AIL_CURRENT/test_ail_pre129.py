"""pre129: a bound method of random.Random read as a value is refused by name.

CPython returns a bound method for `f = random.expovariate` / `g = r.expovariate`,
and the later call draws from the same generator. The general path only dispatches
method *calls*; the read looked for a field and raised
`AttributeError: 'Random' object has no attribute 'expovariate'` at run time, while
CPython printed values. The read is now refused at compile time with a message that
names the bound method, on both builds (the default build reaches the general path
for Random programs, whose typed path still refuses Random's plain-positional
randrange requirement). Direct calls, including the same methods reached through an
argument, a list item, an attribute and a dict value, are unchanged and compared
with CPython.

A known non-Random class with a field of a Random method's name (`gauss`) and an
instance field shadowing a method (`f`) still compile and match CPython: the refusal
only applies when the receiver is a Random or its class is not statically known.
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
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    return exe, built


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre129-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre129-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn('bound method', message, (name, general, message[-1500:]))
            test.assertIn('read as a value', message, (name, general, message[-1500:]))


REFUSED = {
    'module_function': 'import random\n\n\ndef main():\n    random.seed(1)\n    f = random.expovariate\n'
                       '    print(f(2.0))\n\n\nmain()\n',
    'random_object': 'import random\n\n\ndef main():\n    r = random.Random(3)\n    f = r.expovariate\n'
                     '    print(f(2.0))\n\n\nmain()\n',
    'argument': 'import random\n\n\ndef bind(r):\n    return r.expovariate\n\n\ndef main():\n'
                '    print(bind(random.Random(8))(2.0))\n\n\nmain()\n',
    'list_item': 'import random\n\n\ndef main():\n    rs = [random.Random(8)]\n'
                 '    f = rs[0].expovariate\n    print(f(2.0))\n\n\nmain()\n',
    'attribute': 'import random\n\n\nclass Holder:\n    def __init__(self, r):\n        self.r = r\n\n\n'
                 'def main():\n    h = Holder(random.Random(8))\n    f = h.r.gauss\n'
                 '    print(f(1.0, 2.0))\n\n\nmain()\n',
    'dict_value': 'import random\n\n\ndef main():\n    d = {"r": random.Random(8)}\n'
                  '    f = d["r"].random\n    print(f())\n\n\nmain()\n',
    'alias': 'import random\n\n\ndef main():\n    r = random.Random(8)\n    q = r\n'
             '    f = q.triangular\n    print(f(1.0, 3.0, 2.0))\n\n\nmain()\n',
}

MATCH = {
    'direct_calls': '''import random


class Holder:
    def __init__(self, r):
        self.r = r


def draw(r):
    return r.expovariate(2.0)


def main() -> None:
    r = random.Random(8)
    h = Holder(r)
    d = {"r": r}
    xs = [r]
    print(draw(r))
    print(h.r.gauss(1.0, 2.0))
    print(d["r"].random())
    print(xs[0].randint(1, 6))
    print(r.expovariate(0.5))
    print(r.triangular(1.0, 3.0, 2.0))


main()
''',
    'field_named_gauss': '''class A:
    def __init__(self):
        self.gauss = 5.0
        self.f = 7


def main() -> None:
    a = A()
    print(a.gauss, a.f)


main()
''',
    'field_shadows_method': '''class A:
    def __init__(self):
        self.f = 5

    def f(self):
        return 1


def main() -> None:
    for make in (A, A):
        a = make()
        print(a.f)


main()
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class BoundMethodValueTests(unittest.TestCase):
    def test_random_bound_methods_are_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_direct_calls_and_fields_still_match_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
