"""Pre-21: the sign of a zero float remainder follows the divisor, like CPython.

The boxed runtime computed a float `%` with `fmod` and only corrected the sign of a NONZERO
remainder, so the zero cases kept `fmod`'s sign (the dividend's): `0.0 % -3.0` printed `0.0`
and `-0.0 % 3.0` printed `-0.0`. CPython returns a zero with the divisor's sign in both cases.
The typed path's `ail_ffloormod` already did this; the boxed path now copies it.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ZERO_SIGN = r'''class Box:
    pass


def mod(a: float, b: float) -> float:
    return a % b


def main() -> None:
    vals = [0.0, -0.0]
    divs = [3.0, -3.0]
    for a in vals:
        for b in divs:
            print(a % b)
    print(mod(0.0, -3.0), mod(-0.0, 3.0), mod(-0.0, -3.0), mod(0.0, 3.0))
    pairs = [[0.0, -3.0], [-0.0, 3.0], [-0.0, -3.0], [0.0, 3.0]]
    for pair in pairs:
        print(pair[0] % pair[1])
    boxes = [Box(), Box(), Box()]
    boxes[0].a = 0.0
    boxes[0].b = -3.0
    boxes[1].a = -0.0
    boxes[1].b = 3.0
    boxes[2].a = -0.0
    boxes[2].b = -3.0
    for box in boxes:
        print(box.a % box.b)
    d = {"a": 0.0, "b": -3.0}
    print(d["a"] % d["b"])
    d["a"] = -0.0
    d["b"] = 3.0
    print(d["a"] % d["b"])
    print(0.0 % -3.0, -0.0 % 3.0, -0.0 % -3.0, 0.0 % 3.0)
    print(divmod(0.0, -3.0)[1], divmod(-0.0, 3.0)[1], divmod(-0.0, -3.0)[1])
    print(-7 % 3, 7 % -3, -7 % -3, 1 % -3, -1 % 3)


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
    exe = Path(directory) / ('exe_' + name)
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


class Pre21Tests(unittest.TestCase):
    def test_float_modulo_zero_sign(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre21-') as directory:
            want, rc, err = _cpython(directory, 'zero_sign', ZERO_SIGN)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'zero_sign_%s' % ('g' if general else 'd'),
                                                ZERO_SIGN, general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, build_err))
                self.assertEqual(got, (want, 0), 'general=%s\n%s' % (general, build_err))


if __name__ == '__main__':
    unittest.main()
