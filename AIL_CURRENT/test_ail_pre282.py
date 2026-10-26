"""ZeroDivisionError's class prefix and CPython's wording on the default typed path (job pre282).

The reviewer of job pre274 recorded that the default build's uncaught zero-division traps printed
the bare text, e.g. ``0.0 cannot be raised to a negative power`` for ``print(0 ** -1)``, where
CPython writes ``ZeroDivisionError: `` first.  The typed scalar path used ``ail_die`` for these
traps; ``ail_zdie`` now prints CPython's whole line when nothing catches it and raises a catchable
``ZeroDivisionError`` carrying the same text inside a ``try``.  The same wording fix covers
``/`` with a float operand, float ``//`` and ``%``, and the integer zero exprs, all of which
CPython words differently from one another.

The general build already wrote the class prefix through its boxed exception path; its text for a
*caught* float ``/`` is still the boxed op's ``division by zero``, a separate pre-existing
difference, so the two uncaught float-``/`` programs and the caught literal float-``/`` program
check stderr only on the default build.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

UNCAUGHT_INT_DIV = r'''def main():
    print("before")
    print(1 // 0)
main()
'''

UNCAUGHT_POW = r'''def main():
    print(0 ** -1)
main()
'''

UNCAUGHT_POW_FLOAT = r'''def main():
    print(0.0 ** -1.0)
main()
'''

UNCAUGHT_FLOAT_DIV = r'''def main():
    print(1.0 / 0.0)
main()
'''

UNCAUGHT_FLOAT_DIV_NEGZERO = r'''def main():
    print(1.0 / -0.0)
main()
'''

UNCAUGHT_ROUTE = r'''class Box:
    pass
def main():
    box = Box()
    box.z = 0
    xs = [0]
    print("before")
    print(xs[0] // box.z)
main()
'''

CAUGHT_INT = r'''def main():
    big = 2 ** 62
    try:
        print(1 / 0)
    except ZeroDivisionError as e:
        print("div", type(e).__name__, str(e), e.args)
    try:
        print(big // 0)
    except ZeroDivisionError as e:
        print("floordiv", type(e).__name__, str(e), e.args)
    try:
        print(1 % 0)
    except ZeroDivisionError as e:
        print("mod", type(e).__name__, str(e), e.args)
    try:
        print(divmod(1, 0))
    except ZeroDivisionError as e:
        print("divmod", type(e).__name__, str(e), e.args)
    try:
        print(0 ** -1)
    except ZeroDivisionError as e:
        print("ipow", type(e).__name__, str(e), e.args)
    print("done")
main()
'''

CAUGHT_FLOAT = r'''def main():
    try:
        print(1.0 // 0.0)
    except ZeroDivisionError as e:
        print("ffloordiv", type(e).__name__, str(e), e.args)
    try:
        print(1.0 % 0.0)
    except ZeroDivisionError as e:
        print("fmod", type(e).__name__, str(e), e.args)
    try:
        print(1.0 % -0.0)
    except ZeroDivisionError as e:
        print("fmodneg", type(e).__name__, str(e), e.args)
    try:
        print(0.0 ** -1.0)
    except ZeroDivisionError as e:
        print("fpow", type(e).__name__, str(e), e.args)
    print("done")
main()
'''

CAUGHT_FLOAT_DIV = r'''def main():
    try:
        print(1.0 / 0.0)
    except ZeroDivisionError as e:
        print("fdiv", type(e).__name__, str(e), e.args)
    print("done")
main()
'''

ROUTES = r'''class Box:
    pass
def main():
    n = -1
    xs = [0, 0.0]
    box = Box()
    box.z = 0
    box.f = 0.0
    d = {"z": 0, "f": 0.0, "n": n}
    try:
        print(xs[0] ** d["n"])
    except ZeroDivisionError as e:
        print("list int", str(e))
    try:
        print(box.z ** d["n"])
    except ZeroDivisionError as e:
        print("attr int", str(e))
    try:
        print(d["z"] ** n)
    except ZeroDivisionError as e:
        print("dict int", str(e))
    try:
        print(xs[1] ** d["n"])
    except ZeroDivisionError as e:
        print("list float", str(e))
    try:
        print(box.f ** d["n"])
    except ZeroDivisionError as e:
        print("attr float", str(e))
    try:
        print(d["f"] ** d["n"])
    except ZeroDivisionError as e:
        print("dict float", str(e))
    try:
        print(xs[0] // xs[0])
    except ZeroDivisionError as e:
        print("alias idiv", str(e))
    try:
        print(xs[1] % xs[1])
    except ZeroDivisionError as e:
        print("alias fmod", str(e))
    print("done")
main()
'''

ARG_INT = r'''def power(b, e):
    return b ** e
def main():
    n = -1
    try:
        print(power(0, n))
    except ZeroDivisionError as e:
        print("caught", type(e).__name__, str(e), e.args)
    print("done")
main()
'''

ARG_FLOAT = r'''def power(b, e):
    return b ** e
def main():
    try:
        print(power(0.0, -1.0))
    except ZeroDivisionError as e:
        print("caught", type(e).__name__, str(e), e.args)
    print("done")
main()
'''

LAMBDA = r'''def main():
    f = lambda a, b: a ** b
    for z, n in ((0.0, -1.0), (0.0, -1)):
        try:
            print(f(z, n))
        except ZeroDivisionError as e:
            print(type(e).__name__, str(e), e.args)
    print("done")
main()
'''

NO_DIVISION = r'''def main():
    print(1 + 2)
main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return (done.stdout.replace(b'\r\n', b'\n'), done.returncode,
            done.stderr.decode('utf-8', 'replace'))


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
    return ((got.stdout.replace(b'\r\n', b'\n'), got.returncode),
            got.stderr.decode('utf-8', 'replace'))


class Pre282Tests(unittest.TestCase):
    def check(self, slug, text, stderr_general=True, general_builds=(True, False)):
        with tempfile.TemporaryDirectory(prefix='ail-pre282-') as directory:
            want, want_rc, pyerr = _cpython(directory, slug, text)
            last = pyerr.strip().splitlines()[-1] if want_rc and pyerr.strip() else ''
            for general in general_builds:
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (slug, general, err))
                if not want_rc:
                    self.assertEqual(err.strip(), '', '%s (general=%s)' % (slug, general))
                elif general and not stderr_general:
                    continue
                else:
                    self.assertEqual(err.strip(), last, '%s (general=%s)' % (slug, general))

    def test_uncaught_int_division_prefix_and_flush(self):
        self.check('uncaught_int_div', UNCAUGHT_INT_DIV)

    def test_uncaught_pow_trap_prefix(self):
        self.check('uncaught_pow', UNCAUGHT_POW)
        self.check('uncaught_pow_float', UNCAUGHT_POW_FLOAT)

    def test_uncaught_float_division_text(self):
        self.check('uncaught_float_div', UNCAUGHT_FLOAT_DIV, stderr_general=False)
        self.check('uncaught_float_div_negzero', UNCAUGHT_FLOAT_DIV_NEGZERO, stderr_general=False)

    def test_uncaught_route_through_list_and_attribute(self):
        self.check('uncaught_route', UNCAUGHT_ROUTE)

    def test_caught_int_trap_text(self):
        self.check('caught_int', CAUGHT_INT)

    def test_caught_float_trap_text(self):
        self.check('caught_float', CAUGHT_FLOAT)

    def test_caught_float_division_text_default_build(self):
        self.check('caught_float_div', CAUGHT_FLOAT_DIV, general_builds=(False,))

    def test_values_through_list_attribute_dict_and_aliases(self):
        self.check('routes', ROUTES)

    def test_argument_and_lambda_routes(self):
        self.check('arg_int', ARG_INT)
        self.check('arg_float', ARG_FLOAT)
        self.check('lambda_pow', LAMBDA)

    def test_program_without_division_emits_no_zdiv(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre282-nodiv-') as directory:
            src = Path(directory) / 'nodiv.ail'
            src.write_text(NO_DIVISION, encoding='utf-8')
            debug = Path(directory) / 'dbg'
            env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
            env.pop('AIL_UNIFIED_FORCE', None)
            built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile',
                                    src.name, '--syntax', 'python', '-o', 'exe_nodiv',
                                    '--debug-dir', str(debug)], cwd=directory,
                                   capture_output=True, text=True, timeout=900, env=env)
            self.assertEqual(built.returncode, 0, (built.stdout + built.stderr)[-3000:])
            generated = (debug / 'program.c').read_text(encoding='utf-8')
            self.assertNotIn('ail_zdie', generated)
            got = subprocess.run([str(Path(directory) / 'exe_nodiv')], capture_output=True,
                                 timeout=120, cwd=directory)
            self.assertEqual((got.stdout, got.returncode), (b'3\n', 0))


if __name__ == '__main__':
    unittest.main()
