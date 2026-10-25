"""Differential fuzz round 32: a list display of mixed element types, through lambda/map/filter.

Found with small programs around lambdas and higher-order functions.  A display whose elements
have different types (`[0, 1, "a", None, [2, "b"]]`) was typed as a list of its first non-None
element's type (`list[int]` here).  On the general path the value is a boxed list, but `print`
then used the typed list's repr helper: `str()` of an int, not `repr()`, so a string element lost
its quotes (`[0, 1, a]` instead of `[0, 1, 'a']`).  A leading str element was worse: the typed
str repr read an int as a str handle and stopped with "argument of type 'int' is not iterable".
The element type of a mixed display is now unknown, so the general runtime's own recursive repr
is used; homogeneous typed lists are unchanged.

The program reaches the display through a name, a function argument and result, a list item, a
dict value and an attribute, and includes map/filter/comprehension results, None, empty, nested,
negative/huge ints, bool/int and int/float mixes, and strings that need quoting or escaping.
It is built with the general path forced and with the default build; stdout and the exit status
must equal CPython 3.12.
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


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    src = Path(directory) / (name + '_' + mode + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), ''


MIXED_DISPLAY = r'''from typing import Callable


def show(xs) -> None:
    print(xs)


def ident(xs):
    return xs


class Box:
    def __init__(self, v) -> None:
        self.v = v


def main() -> None:
    xs = [0, 1, "a", None, [2, "b"]]
    print(xs)
    show(xs)
    print(ident(xs))
    print(xs[4])
    print(ident(xs)[0])
    d = {"k": xs}
    print(d["k"])
    b = Box(xs)
    print(b.v)
    print(list(map(lambda x: x, xs)))
    print(list(filter(lambda x: x is not None, xs)))
    print([x for x in xs])
    print(sorted([(3, "b"), (1, "a"), (2, "c")], key=lambda t: t[0]))
    print({"a": 1, "b": "x"})
    print([1.5, 2])
    print([True, 2])
    print([None, "q"])
    print(["a'b", 'c"d', "e\nf", "t\tq"])
    print([[], [1], ["a"]])
    print([])
    print([["a"], ["b", 2]])
    print([-(10 ** 18), 0, 10 ** 18, "big"])
    print([None, None])
    print([1, None, "z"])
    print("done")


main()
'''


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class MixedDisplay(unittest.TestCase):
    def check(self, name, text, modes=('general', 'default')):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz32-') as directory:
            want = _cpython(directory, name, text)
            for mode in modes:
                got, err = _build_run(directory, name, text, mode)
                self.assertIsNotNone(got, '%s (%s)\n%s' % (name, mode, err))
                self.assertEqual(got, want, '%s (%s)' % (name, mode))

    def test_mixed_display(self):
        self.check('mixed_display', MIXED_DISPLAY)


if __name__ == '__main__':
    unittest.main()
