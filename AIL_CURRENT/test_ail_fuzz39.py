"""Differential fuzz round 39: object identity and copying, against CPython 3.12.

`is` / `is not` with a tuple constant was a silent difference: CPython merges equal tuple constants of one code object
(`a = (); b = (); a is b` is True, and `()` is a singleton), while each tuple display here is an object of its own, so
`p is q` for two empty tuples printed False. The tuple rewrite now leaves such a comparison for numidentity.py, which
refuses it by name (DIFFERENCES C?-job-fuzz39-10230820-1); a literal passed to both parameters of `def same(a, b):
return a is b` is refused too. Different tuple constants, the same object reached twice, list/dict/set identity,
`.copy()`, mutable default arguments and small-int identity are unchanged and compared with CPython.

Programs are built with the general path forced and with the default build; stdout and the exit status must match.
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


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-fuzz39-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


def check_refused(test, name, text, marker='C?-job-fuzz39-10230820-1', word='tuple'):
    with tempfile.TemporaryDirectory(prefix='ail-fuzz39-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(marker, message, (name, general, message[-1200:]))
            if word is not None:
                test.assertIn(word, message, (name, general, message[-1200:]))


REFUSED = {
    'empty_tuple_names': 'def main():\n    p = ()\n    q = ()\n    print(p is q)\n\n\nmain()\n',
    'value_tuple_names': 'def main():\n    a = (1, 2)\n    b = (1, 2)\n    print(a is b)\n\n\nmain()\n',
    'literal': 'def main():\n    r = (1,)\n    print(r is (1,))\n\n\nmain()\n',
    'through_argument': ('def same(a, b):\n    return a is b\n\n\ndef main():\n    print(same((1,), (1,)))\n'
                          '    print(same((), ()))\n\n\nmain()\n'),
    'through_data': ('def same(a, b):\n    return a is b\n\n\ndef main():\n    d = {"k": (1,)}\n'
                      '    xs = [(1,)]\n    print(same(d["k"], (1,)))\n    print(xs[0] is (1,))\n\n\nmain()\n'),
    'is_before_parenthesis': 'def main():\n    a = ()\n    b = ()\n    print(a is(b))\n\n\nmain()\n',
}

NUMBER_REFUSED = {
    'mixed_tuple_and_float_binding': ('def show(a):\n    print(a)\n\n\ndef f() -> None:\n    x = (1,)\n'
                                      '    x = 2.5\n    z = 2.5\n    print(x is z)\n\n\ndef main() -> None:\n'
                                      '    f()\n    show((1, 2))\n\n\nmain()\n'),
}

MATCH = {
    'copy_and_defaults': '''
def add(x: int, acc: list[int] = []) -> int:
    acc.append(x)
    return len(acc)


def main() -> None:
    a = [[1, 2], [3]]
    b = a.copy()
    b.append([9])
    b[0].append(99)
    print(a, b)
    d = {"x": [1], "y": {"z": [2]}}
    e = d.copy()
    e["x"].append(7)
    e["w"] = [8]
    print(sorted(d), sorted(e), d["x"], d["y"])
    s = {1, 2}
    t = s.copy()
    t.add(3)
    print(sorted(s), sorted(t))
    print(add(1), add(2), add(3))


main()
''',
    'identity': '''
class H:
    def __init__(self, v):
        self.v = v


def same(a, b):
    return a is b


def main() -> None:
    a = []
    b = []
    c = a
    d = {}
    e = d
    print(a is b, a is c, a == b, d is e, e is d)
    print((1,) is (2,), same((1,), (2,)), (1, 2) is (2, 1))
    p = (1,)
    print(p is p, same(p, p), p == (1,))
    g = {"k": (1,)}
    xs = [(1,)]
    h = H((1,))
    print(g["k"] is g["k"], xs[0] is xs[0], h.v is h.v)
    print(1 is 1, 256 is 256, None is None, True is True, 1 == 1.0)


main()
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class TupleConstantIdentity(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_mixed_binding_still_refuses_the_number(self):
        for name, text in sorted(NUMBER_REFUSED.items()):
            check_refused(self, 'number_' + name, text, 'C115', None)

    def test_other_identity_and_copying_is_cpython(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)
