"""Zero division raised inside a callback on the typed path.

The typed path's `pydiv`/`pymod` helpers called `ail_die`, a fatal trap.  A `try` in the
program converted the trap into a catchable exception, so caught cases looked right, but an
uncaught `// 0` inside a key function printed the bare trap text and exited 1 without the
`ZeroDivisionError: ` prefix.  The typed helpers now raise `AIL_EXC_ZERODIV` directly, with
CPython's messages for int and float `//` and `%` (the general path's int `%` message is
fixed too).  Both builds are compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CAUGHT_ROUTES = r'''from typing import Callable


class Box:
    def __init__(self, v: int) -> None:
        self.v: int = v


def divide(a: int, b: int) -> int:
    return a // b


def apply(f: Callable[[int], int], x: int) -> int:
    return f(x)


def main() -> None:
    d = {"z": 0}
    xs = [5, 0]
    box = Box(0)
    m = -9223372036854775807 - 1
    for n in [7, 0, -7, 9223372036854775807, m]:
        try:
            print(divide(n, 0))
        except ZeroDivisionError as e:
            print("arg", type(e).__name__, e)
    for divisor in [xs[1], box.v, d["z"]]:
        try:
            print(divide(7, divisor))
        except ZeroDivisionError as e:
            print("route", type(e).__name__, e)
    try:
        print(sorted([3, 1, 2], key=lambda x: x // 0))
    except ZeroDivisionError as e:
        print("sorted", type(e).__name__, e)
    try:
        print(apply(lambda x: x // 0, 1))
    except ZeroDivisionError as e:
        print("hof", type(e).__name__, e)
    ys = [3, 1, 2]
    try:
        ys.sort(key=lambda x: x // 0)
        print(ys)
    except ZeroDivisionError as e:
        print("sort", type(e).__name__, e)
    for f in [-7.5, 7.5, 0.0, -0.0]:
        try:
            print(f // 0)
        except ZeroDivisionError as e:
            print("float//", type(e).__name__, e)
        try:
            print(f % 0)
        except ZeroDivisionError as e:
            print("float%", type(e).__name__, e)
        try:
            print(f / 0)
        except ZeroDivisionError as e:
            print("float/", type(e).__name__, e)
    for flag in [True, False]:
        try:
            print(flag // 0)
        except ZeroDivisionError as e:
            print("bool", type(e).__name__, e)
    for k in [7, 0, -7]:
        try:
            print(k % 0)
        except ZeroDivisionError as e:
            print("int%", type(e).__name__, e)
        try:
            print(k / 0)
        except ZeroDivisionError as e:
            print("int/", type(e).__name__, e)
    try:
        print(sorted([], key=lambda x: x // 0))
    except ZeroDivisionError as e:
        print("empty", type(e).__name__, e)
    try:
        try:
            print(sorted([3, 1, 2], key=lambda x: x // 0))
        finally:
            print("inner finally")
    except ZeroDivisionError as e:
        print("outer", type(e).__name__, e)
    print("done")


main()
'''

SORTED_LAMBDA_UNCAUGHT = r'''def main() -> None:
    print(sorted([3, 1, 2], key=lambda x: x // 0))


main()
'''

DEF_KEY_UNCAUGHT = r'''def key(x: int) -> int:
    return x // 0


def main() -> None:
    print(sorted([3, 1, 2], key=key))


main()
'''

HOF_UNCAUGHT = r'''from typing import Callable


def apply(f: Callable[[int], int], x: int) -> int:
    return f(x)


def main() -> None:
    print(apply(lambda x: x // 0, 1))


main()
'''

SORT_UNCAUGHT = r'''def main() -> None:
    xs = [3, 1, 2]
    xs.sort(key=lambda x: x // 0)
    print(xs)


main()
'''

GLOBAL_LAMBDA_UNCAUGHT = r'''f = lambda x: x // 0


def main() -> None:
    print(sorted([3, 1, 2], key=f))


main()
'''

ARG_UNCAUGHT = r'''def divide(a: int, b: int) -> int:
    return a // b


def main() -> None:
    print(divide(7, 0))


main()
'''

MOD_UNCAUGHT = r'''def main() -> None:
    print(7 % 0)


main()
'''

FLOAT_FLOOR_UNCAUGHT = r'''def main() -> None:
    print(sorted([3.0, 1.0, 2.0], key=lambda x: x // 0))


main()
'''

FLOAT_MOD_UNCAUGHT = r'''def main() -> None:
    print(7.5 % 0)


main()
'''

FLOAT_TRUE_DIV_UNCAUGHT = r'''def main() -> None:
    print(7.5 / 0)


main()
'''

TRUE_DIV_UNCAUGHT = r'''def main() -> None:
    print(7 / 0)


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr.decode('utf-8', 'replace')


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre115Tests(unittest.TestCase):
    def check(self, slug, text, rc=0, uncaught=False):
        with tempfile.TemporaryDirectory(prefix='ail-pre115-') as directory:
            want, want_rc, want_err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, rc, want_err)
            want_last = want_err.rstrip().splitlines()[-1] if uncaught else None
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                stdout, got_rc = got
                self.assertEqual((stdout, got_rc), (want, rc),
                                 '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                if uncaught:
                    got_last = build_err.rstrip().splitlines()[-1]
                    self.assertEqual(got_last, want_last,
                                     '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_caught_routes_and_types(self):
        self.check('caught_routes', CAUGHT_ROUTES)

    def test_uncaught_sorted_key_lambda(self):
        self.check('sorted_lambda_uncaught', SORTED_LAMBDA_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_def_key(self):
        self.check('def_key_uncaught', DEF_KEY_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_typed_hof(self):
        self.check('hof_uncaught', HOF_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_list_sort(self):
        self.check('sort_uncaught', SORT_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_global_lambda(self):
        self.check('global_lambda_uncaught', GLOBAL_LAMBDA_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_direct_argument(self):
        self.check('arg_uncaught', ARG_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_integer_modulo(self):
        self.check('mod_uncaught', MOD_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_float_floor_division(self):
        self.check('float_floor_uncaught', FLOAT_FLOOR_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_float_modulo(self):
        self.check('float_mod_uncaught', FLOAT_MOD_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_float_true_division(self):
        self.check('float_true_div_uncaught', FLOAT_TRUE_DIV_UNCAUGHT, rc=1, uncaught=True)

    def test_uncaught_true_division(self):
        self.check('true_div_uncaught', TRUE_DIV_UNCAUGHT, rc=1, uncaught=True)


if __name__ == '__main__':
    unittest.main()
