"""pre107: random.expovariate's default rate follows CPython 3.12.

The Random preludes declared expovariate(lambd) without the default, so
`random.expovariate()` was refused by both builds while `gauss(mu)` already
matched after cov8.  The general path's module-level functions go through
prelude_random_boxed.py, and the typed Random object through prelude_random.py;
both now default lambd to 1.0, as CPython does.

The programs cover the default and explicit rates, int/float/negative/zero and
infinite rates, a value reaching the call through an argument, a list item, an
attribute and a dict value, keyword calls and a seeded Random object.  Each is
built on both builds and compared with CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULE_FUNCS = r'''import random


def draw(rate: float) -> float:
    return random.expovariate(rate)


class Cfg:
    def __init__(self) -> None:
        self.rate = 0.25


def main() -> None:
    random.seed(3)
    rates = [2.0, 0.5]
    cfg = {"rate": 4.0}
    box = Cfg()
    print(random.expovariate())
    print(random.expovariate(2.5))
    print(random.expovariate(3))
    print(random.expovariate(-0.5))
    print(random.expovariate(lambd=2.0))
    print(random.expovariate(float("inf")))
    print(draw(2.0))
    print(random.expovariate(rates[0]))
    print(random.expovariate(box.rate))
    print(random.expovariate(cfg["rate"]))
    try:
        print(random.expovariate(0.0))
    except ZeroDivisionError as e:
        print(type(e).__name__, str(e))


main()
'''

RANDOM_OBJECT = r'''import random


def main() -> None:
    r = random.Random(11)
    print(r.expovariate())
    print(r.expovariate(2.0))
    print(r.expovariate(lambd=0.5))
    print(r.expovariate(-2.0))


main()
'''

GAUSS_DEFAULT = r'''import random


def main() -> None:
    random.seed(2)
    print(random.gauss(2.5))
    print(random.gauss())
    m = 1.5
    s = 2.0
    print(random.gauss(m, s))


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


class Pre107Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre107-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_module_functions(self):
        self.check('module_funcs', MODULE_FUNCS)

    def test_random_object(self):
        self.check('random_object', RANDOM_OBJECT)

    def test_gauss_defaults_regression(self):
        self.check('gauss_defaults', GAUSS_DEFAULT)


if __name__ == '__main__':
    unittest.main()
