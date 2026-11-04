"""Differential fuzz finding fz227: int / int was not CPython's exact true division.

CPython's long_true_divide rounds the exact quotient once. `(double)a / (double)b` instead
rounds each operand first, so once either is beyond 2**53 the result can be one ulp away:

    x = 4611686018427387904
    (x // 52) / 3        CPython 2.9562089861714024e+16, AIL 2.9562089861714028e+16

The typed path emitted the two conversions, the general path's scalar specialisation did too,
and both boxed operator runtimes did. They now share `ail__idiv_exact`, CPython's 55-bit
quotient plus sticky remainder, rounded once; both operands within +-2**53 keep the old double
division (their conversions are exact, so one IEEE division already rounds the exact quotient).
Each program is compared with CPython on the general build, the IR build and the legacy
(AIL_IR=0) build.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DIRECT_CASE = r'''def main() -> None:
    x = 4611686018427387904
    print((x // 52) / 3)
    print((x // 53) / 3)
    print(4611686018427387904 / 52)
    print(9223372036854775807 / 3)
    print(-9223372036854775807 / 7)
    print(9007199254740993 / 2)
    # the +-2**53 boundary of the double fast path
    print(9007199254740991 / 3)
    print(-9007199254740992 / 3)
    print(9007199254740992 / 3)
    print(-9007199254740993 / 3)
    print(0 / 3, 0 / -3)


main()
'''

FLOW_CASE = r'''class Box:
    v: int = 0

    def __init__(self, v: int) -> None:
        self.v = v


def divide(a: int, b: int) -> float:
    return a / b


def main() -> None:
    # each pair rounds at least one operand as a double; these differ on the old lowering
    nums = [6976454540695398849, 4865782901354085936, -931725450029404348]
    divisors = [3684474835157277, -7048155917072976836, -7491968275375482579]
    for i in range(3):
        print(nums[i] / divisors[i])
    print(divide(6976454540695398849, 3684474835157277), divide(-931725450029404348, -7491968275375482579))
    d = {"a": 6976454540695398849, "b": 3684474835157277}
    print(d["a"] / d["b"])
    box = Box(4865782901354085936)
    print(box.v / -7048155917072976836)
    print(0 / 3, 0 / -3)


main()
'''

AUG_CASE = r'''def main() -> None:
    a = 6976454540695398849
    a /= 3684474835157277
    print(a)
    b = 4865782901354085936
    b /= -7048155917072976836
    print(b)
    print(True / 2, False / 3)


main()
'''

ZERO_CASE = r'''def main() -> None:
    print(1 / 2, 3 / 2, -1 / 2)
    try:
        print(1 / 0)
    except ZeroDivisionError:
        print("zerodiv")
    z = 0
    try:
        print(5 / z)
    except ZeroDivisionError:
        print("zerodiv-z")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build_and_run(directory, name, text, mode):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'g':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'ir0':
        env['AIL_IR'] = '0'
    else:
        env['AIL_IR'] = '1'
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Fz227Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fz227-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for mode in ('g', 'ir1', 'ir0'):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, mode), text, mode)
                self.assertIsNotNone(got, '%s (mode=%s)\n%s' % (text[:2000], mode, build_err))
                self.assertEqual(got, (want, rc), '%s (mode=%s)\n%s' % (text[:2000], mode, build_err))

    def test_direct(self):
        self.check('direct', DIRECT_CASE)

    def test_flow(self):
        self.check('flow', FLOW_CASE)

    def test_aug(self):
        self.check('aug', AUG_CASE)

    def test_zero(self):
        self.check('zero', ZERO_CASE)


if __name__ == '__main__':
    unittest.main()
