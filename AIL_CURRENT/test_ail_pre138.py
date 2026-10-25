"""pre138: integer `%` by zero names the operation the way CPython does.

CPython 3.12 splits the ZeroDivisionError text of the integer operators: `%` says
"integer modulo by zero", while `//` and divmod() keep "integer division or modulo by
zero".  The boxed emitters reused the combined text for `%` (`ail_obj_mod` and
`ail_op_mod` in the shared runtime), so a caught `1 % 0` printed the wrong message on
both builds.  The typed path already named the modulo operation.

The programs also keep the neighbours that must not move: `//`, divmod() and the three
float messages, the int64 boundaries (`INT64_MIN % -1` is 0), `%=` by zero, and values
reaching the operation through an argument, a list item, an attribute and a dict value.
Each program is built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MOD_ZERO = r'''def m(a, b):
    return a % b


class Box:
    def __init__(self, v):
        self.v = v


def main():
    z = 0
    xs = [8, z]
    d = {"a": 8, "b": z}
    box = Box(z)
    try:
        print("arg", 7 % z)
    except ZeroDivisionError as e:
        print("arg ZeroDivisionError", e)
    try:
        print("neg", -7 % z)
    except ZeroDivisionError as e:
        print("neg ZeroDivisionError", e)
    try:
        print("bool", True % z)
    except ZeroDivisionError as e:
        print("bool ZeroDivisionError", e)
    try:
        print("list", xs[0] % xs[1])
    except ZeroDivisionError as e:
        print("list ZeroDivisionError", e)
    try:
        print("dict", d["a"] % d["b"])
    except ZeroDivisionError as e:
        print("dict ZeroDivisionError", e)
    try:
        print("attr", 8 % box.v)
    except ZeroDivisionError as e:
        print("attr ZeroDivisionError", e)
    try:
        print("call", m(xs[0], d["b"]))
    except ZeroDivisionError as e:
        print("call ZeroDivisionError", e)
    x = 8
    try:
        x %= z
        print("modassign", x)
    except ZeroDivisionError as e:
        print("modassign ZeroDivisionError", e)
    lo = -9223372036854775807 - 1
    print("min", lo % -1, lo % 3, lo % -3, m(lo, -1), m(lo, 2))


main()
'''

NEIGHBOURS = r'''def main():
    z = 0
    try:
        print("floordiv", 7 // z)
    except ZeroDivisionError as e:
        print("floordiv ZeroDivisionError", e)
    try:
        print("divmod", divmod(7, z))
    except ZeroDivisionError as e:
        print("divmod ZeroDivisionError", e)
    try:
        print("floatmod", 7.0 % 0.0)
    except ZeroDivisionError as e:
        print("floatmod ZeroDivisionError", e)
    try:
        print("floatdiv", 7.0 // 0.0)
    except ZeroDivisionError as e:
        print("floatdiv ZeroDivisionError", e)
    try:
        print("floatdivmod", divmod(7.0, 0.0))
    except ZeroDivisionError as e:
        print("floatdivmod ZeroDivisionError", e)
    lo = -9223372036854775807 - 1
    print("min", lo % -1, lo % 3, lo % -3, lo % 2)
    print("float", divmod(7.5, 2.0), 7.5 % 2.0, -7.5 // 2.0, -0.0 % 2.0)
    print("fmt", "%d/%s" % (7, "x"))


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


class Pre138Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre138-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_integer_modulo_by_zero_message(self):
        self.check('mod_zero', MOD_ZERO)

    def test_division_neighbours_unchanged(self):
        self.check('neighbours', NEIGHBOURS)


if __name__ == '__main__':
    unittest.main()
