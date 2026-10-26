"""Zero to a negative power names CPython's ZeroDivisionError (job pre265).

The reviewer of job rbpre33 recorded a pre-existing difference: on the default build a
constant ``0 ** -1`` raised ``ZeroDivisionError: division by zero`` where CPython names the
power, ``ZeroDivisionError: 0.0 cannot be raised to a negative power``.  A constant negative
exponent takes the float ``pow()`` path, and its shared ``ail_fpow`` helper still used the
older generic division message.  The helper now raises a catchable ZeroDivisionError carrying
CPython's text, so both the caught message and the uncaught one agree.  Non-zero negative
exponents keep their float result, and a zero base reaching the operation as an argument, a
list item, an attribute or a dict value is covered too.  A *variable* negative exponent stays
the deliberate exact-integer trap described in SEMANTICS.md (it is not part of this fix).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ZERO_NEGATIVE = '''class IntBox:
    def __init__(self, v) -> None:
        self.v = v


def negative_power(b):
    return b ** -1


def negative_power_float(b):
    return b ** -1.0


def main() -> None:
    xs = [0, 2]
    ys = [0.0]
    d = {"z": 0, "two": 2}
    box = IntBox(0)
    two = IntBox(2)

    try:
        print("direct", 0 ** -1)
    except Exception as e:
        print("direct", type(e).__name__, str(e))

    try:
        print("direct2", 0 ** -2)
    except Exception as e:
        print("direct2", type(e).__name__, str(e))

    try:
        print("direct100", 0 ** -100)
    except Exception as e:
        print("direct100", type(e).__name__, str(e))

    try:
        print("float", 0.0 ** -1)
    except Exception as e:
        print("float", type(e).__name__, str(e))

    try:
        print("float2", 0.0 ** -2)
    except Exception as e:
        print("float2", type(e).__name__, str(e))

    try:
        print("negzero", (-0.0) ** -1)
    except Exception as e:
        print("negzero", type(e).__name__, str(e))

    try:
        print("bool", False ** -1)
    except Exception as e:
        print("bool", type(e).__name__, str(e))

    try:
        print("exponent_float", 0 ** -1.0)
    except Exception as e:
        print("exponent_float", type(e).__name__, str(e))

    try:
        print("fraction", 0.0 ** -0.5)
    except Exception as e:
        print("fraction", type(e).__name__, str(e))

    try:
        print("base_arg", negative_power(0))
    except Exception as e:
        print("base_arg", type(e).__name__, str(e))

    try:
        print("base_arg_float", negative_power_float(0.0))
    except Exception as e:
        print("base_arg_float", type(e).__name__, str(e))

    try:
        print("base_list", xs[0] ** -1)
    except Exception as e:
        print("base_list", type(e).__name__, str(e))

    try:
        print("base_list_float", ys[0] ** -1)
    except Exception as e:
        print("base_list_float", type(e).__name__, str(e))

    try:
        print("base_attr", box.v ** -1)
    except Exception as e:
        print("base_attr", type(e).__name__, str(e))

    try:
        print("base_dict", d["z"] ** -1)
    except Exception as e:
        print("base_dict", type(e).__name__, str(e))

    print("fit", 2 ** -1, 10 ** -2, (-2) ** -1, 3 ** -2, 0 ** -0.0, 0 ** 0)
    print("fit_arg", negative_power(2))
    print("fit_routes", xs[1] ** -1, two.v ** -1, d["two"] ** -1)
    print("fit_float", 1.0 ** -1000, 2.0 ** -2, (-2.0) ** -1)
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


class Pre265Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre265-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_zero_to_negative_power_message(self):
        self.check('zero_negative', ZERO_NEGATIVE)


if __name__ == '__main__':
    unittest.main()
