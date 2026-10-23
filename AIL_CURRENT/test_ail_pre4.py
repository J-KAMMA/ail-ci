"""print() differences recorded before job fuzz75.

p12: `print(..., end=g(), sep=f())` -- the general path evaluated sep before end even
when the source spells end first. CPython evaluates a call's positionals first and then its
keyword values in source order, so `end` here runs before `sep`.

p13: a non-literal None sep/end (`sep=none()`, `end=attrs.none`) is the default, as in
CPython, on both stdout and `file=sys.stderr`; a non-str value is the TypeError naming the
keyword and the value's type. The stderr path no longer builds `sep.join(...)` on a raw None.

Both the general (AIL_UNIFIED_FORCE=1) and the default build are compared with CPython, over
stdout and stderr.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'

PRINT_ORDER = r"""def f():
    print("f")
    return "-"


def g():
    print("g")
    return "!"


def main():
    print("a", "b", end=g(), sep=f())
    print("c", "d", sep=f(), end=g())
    xs = ["e", "f"]
    print(*xs, end=g(), sep=f())
    print("g", *xs, end=g(), sep=f())


main()
"""

PRINT_NONE = r"""import sys


class Holder:
    def __init__(self, v):
        self.v = v


def none(label):
    print(label)
    return None


def main():
    h = Holder(None)
    xs = ["-", None, ""]
    d = {"sep": None, "end": None}
    print("a", "b", sep=none("sep"), end=none("end"))
    print("c", "d", sep=h.v, end=h.v)
    print("e", "f", sep=xs[1], end=xs[2])
    print("g", "h", sep=d["sep"], end=d["end"])
    print("i", "j", sep=xs[0], end=xs[2])
    print("k", "l", sep=none("err-sep"), end=none("err-end"), file=sys.stderr)
    print("m", "n", sep=h.v, end=h.v, file=sys.stderr)
    print("o", "p", sep=d["sep"], end=d["end"], file=sys.stderr)


main()
"""

PRINT_TYPES = r"""import sys


def main():
    for v in (1, 1.5, True, ["x"], {"a": 1}):
        try:
            print("a", "b", sep=v)
        except TypeError as e:
            print(type(e).__name__, e)
        try:
            print("a", "b", end=v)
        except TypeError as e:
            print(type(e).__name__, e)
        try:
            print("a", "b", sep=v, file=sys.stderr)
        except TypeError as e:
            print(type(e).__name__, e)


main()
"""


def build_and_run(directory, text, name, general):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    env = {key: value for key, value in os.environ.items()
           if key not in ('AIL_UNIFIED_FORCE', 'AIL_IR', 'AIL_NO_GENERAL')}
    env.update(AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', str(CLI), 'compile', source.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=600, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class Pre4(unittest.TestCase):
    def check(self, name, text):
        for general in (False, True):
            with self.subTest(build='general' if general else 'default'):
                with tempfile.TemporaryDirectory() as directory:
                    built, ran, expected = build_and_run(
                        directory, text, name + ('_g' if general else '_d'), general)
                    self.assertEqual(expected.returncode, 0, expected.stderr)
                    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
                    self.assertEqual((ran.returncode, ran.stdout, ran.stderr),
                                     (expected.returncode, expected.stdout, expected.stderr),
                                     ran.stderr)

    def test_p12_end_is_evaluated_before_sep_when_written_first(self):
        self.check('p12', PRINT_ORDER)

    def test_p13_nonliteral_none_sep_and_end_mean_the_defaults(self):
        self.check('p13', PRINT_NONE)

    def test_p13_nonstr_sep_end_raise_cpython_typeerror(self):
        self.check('p13types', PRINT_TYPES)


if __name__ == '__main__':
    unittest.main()
