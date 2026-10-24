"""pre87: integer ``%`` by zero names CPython's "integer modulo by zero".

The general path and the typed path's fallback reported ``integer division or
modulo by zero`` for ``%``.  CPython reserves that text for ``//`` and
``divmod``; ``%`` raises ``ZeroDivisionError: integer modulo by zero``.

The probe reaches the operation through a plain helper, a typed helper, a
lambda, a list item, an attribute, a dict value, negative and INT64_MIN
dividends, bools, an IntEnum and an IntFlag.  The companion program keeps the
neighbouring ``//``, ``divmod`` and float zero messages unchanged.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

INT_MODULO_ZERO = r'''from enum import IntEnum, IntFlag


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


class Z(IntEnum):
    ZERO = 0


class F(IntFlag):
    ZERO = 0


def mod_plain(a, b):
    return a % b


def mod_typed(a: int, b: int) -> int:
    return a % b


def report(label: str, a: int, b: int) -> None:
    try:
        print(label, a % b)
    except ZeroDivisionError as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    xs = [5, 6]
    d = {"a": 5, "z": 0}
    box = Box(5)
    try:
        print("plain", mod_plain(5, 0))
    except ZeroDivisionError as e:
        print("plain", type(e).__name__, str(e))
    try:
        print("typed", mod_typed(5, 0))
    except ZeroDivisionError as e:
        print("typed", type(e).__name__, str(e))
    try:
        print("lambda", (lambda x: x % 0)(7))
    except ZeroDivisionError as e:
        print("lambda", type(e).__name__, str(e))
    try:
        print("lambda-literals", 5 % 0)
    except ZeroDivisionError as e:
        print("lambda-literals", type(e).__name__, str(e))
    report("argument", xs[0], d["z"])
    report("list-item", xs[0], xs[1 - 1])
    report("attribute", box.v, d["z"])
    report("dict-value", d["a"], 0)
    report("negative", -7, 0)
    report("min", -9223372036854775807 - 1, 0)
    report("bool-divisor", 5, False)
    report("bool-dividend", True, 0)
    report("intenum", 5, Z.ZERO)
    report("intflag", 5, F.ZERO)
    print("done")


main()
'''

ZERO_NEIGHBOURS = r'''def floor_plain(a, b):
    return a // b


def divmod_plain(a, b):
    return divmod(a, b)


def report_floor(label: str, a: int, b: int) -> None:
    try:
        print(label, a // b)
    except ZeroDivisionError as e:
        print(label, type(e).__name__, str(e))


def main() -> None:
    try:
        print("floor", floor_plain(5, 0))
    except ZeroDivisionError as e:
        print("floor", type(e).__name__, str(e))
    try:
        print("divmod", divmod_plain(5, 0))
    except ZeroDivisionError as e:
        print("divmod", type(e).__name__, str(e))
    try:
        print("float-mod", 5.0 % 0.0)
    except ZeroDivisionError as e:
        print("float-mod", type(e).__name__, str(e))
    try:
        print("float-floor", 5.0 // 0.0)
    except ZeroDivisionError as e:
        print("float-floor", type(e).__name__, str(e))
    try:
        print("float-divmod", divmod(5.0, 0.0))
    except ZeroDivisionError as e:
        print("float-divmod", type(e).__name__, str(e))
    report_floor("floor-typed", 5, 0)
    print("normal", (-7 % 3, 7 % -3, -7 % -3, 0 % -5))
    print("divmod-normal", divmod(-7, 3))
    print("done")


main()
'''


CALLBACK_ZERO = r'''from enum import IntEnum, IntFlag


class Z(IntEnum):
    ZERO = 0


class F(IntFlag):
    ZERO = 0


def mod_plain(a, b):
    return a % b


def floor_plain(a, b):
    return a // b


def divmod_plain(a, b):
    return divmod(a, b)


def show(label, f):
    try:
        print(label, f())
    except ZeroDivisionError as e:
        print(label, type(e).__name__, str(e))


def cb_mod():
    return mod_plain(-7, 0)


def cb_floor():
    return floor_plain(5, 0)


def cb_divmod():
    return divmod_plain(5, 0)


def main():
    xs = [mod_plain, floor_plain]
    d = {"mod": mod_plain, "floor": floor_plain}
    show("lambda-mod", lambda: mod_plain(5, 0))
    show("lambda-floor", lambda: floor_plain(5, 0))
    show("lambda-divmod", lambda: divmod_plain(5, 0))
    show("lambda-negative", lambda: mod_plain(-7, 0))
    show("lambda-min", lambda: mod_plain(-9223372036854775807 - 1, 0))
    show("lambda-bool", lambda: mod_plain(5, False))
    show("lambda-intenum", lambda: mod_plain(5, Z.ZERO))
    show("lambda-intflag", lambda: mod_plain(5, F.ZERO))
    show("named", cb_mod)
    show("named-floor", cb_floor)
    show("named-divmod", cb_divmod)
    show("list-item", lambda: xs[0](5, 0))
    show("dict-value", lambda: d["mod"](5, 0))
    g = cb_mod
    show("alias", g)
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


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


class Pre87Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre87-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_int_modulo_zero(self):
        self.check('int_modulo_zero', INT_MODULO_ZERO)

    def test_zero_neighbours(self):
        self.check('zero_neighbours', ZERO_NEIGHBOURS)

    def test_callback_zero(self):
        self.check('callback_zero', CALLBACK_ZERO)


if __name__ == '__main__':
    unittest.main()
