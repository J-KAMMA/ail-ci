"""Typed reach for the hot functions of the prog3 programs (2026-11-01), against CPython 3.12.

`lab/census/programs/gdev/g12_008.py` spends its time in `simulate_mm1`, which called
`random.expovariate`: the typed path knew `uniform` / `gauss` / `normalvariate` but not
`expovariate`, so the whole program fell to the general path (CPython under the hybrid).  The
module-level draw is now built on the typed path (`stdlib3.py`, `pyfunc.py`, `cruntime.py`), with
CPython's default `lambd=1.0`, keyword form, negative rates and the `ZeroDivisionError` for 0.0.

The other hot functions of the eight programs are recorded with their first refusal in
`lab/progfix/prog3.md`; the ones that need a large new feature (generators, `datetime`, a
heterogeneous `json.dumps`, an optional list, enum members in a module-level table) stay as
follow-ups there.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
HAVE_CC = shutil.which('gcc') is not None or shutil.which('cc') is not None
G12 = REPO / 'lab' / 'census' / 'programs' / 'gdev' / 'g12_008.py'

EXPO = '''import random
from dataclasses import dataclass

random.seed(12345)

@dataclass
class Box:
    rate: float

def draw(lambd: float) -> float:
    return random.expovariate(lambd)

def main() -> None:
    box = Box(3.0)
    rates = [0.25, 4.0]
    print(random.expovariate())
    print(random.expovariate(2.0))
    print(random.expovariate(lambd=0.5))
    print(random.expovariate(-2.0))
    print(random.expovariate(1))
    print(random.expovariate(1e-9), random.expovariate(1e9))
    print(draw(2.0))
    print(draw(rates[0]), draw(rates[1]))
    print(draw(box.rate))
    total = 0.0
    for rate in rates:
        total += draw(rate)
    print(total)

main()
'''

ZERO = '''import random

random.seed(1)
try:
    print(random.expovariate(0.0))
except Exception as error:
    print(type(error).__name__, error)
try:
    print(random.expovariate(-0.0))
except Exception as error:
    print(type(error).__name__, error)
try:
    print(random.expovariate(0))
except Exception as error:
    print(type(error).__name__, error)
'''

UNCAUGHT = '''import random

random.seed(1)
print("before")
print(random.expovariate(0.0))
print("after")
'''

STATE = '''import random

random.seed(42)
print(random.random())
print(random.expovariate(1.0))
print(random.random())
print(random.expovariate(2.5))
print(random.getrandbits(32))
'''


def run(cmd, cwd, env=None, timeout=900):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', errors='replace')


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class Prog3TypedReach(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='prog3_')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def build(self, text, name, typed_only=False):
        directory = Path(self.tmp)
        source = directory / (name + '.py')
        source.write_text(text, encoding='utf-8')
        exe = directory / (name + '_x')
        env = dict(os.environ, AIL_NO_CACHE='1')
        for key in ('AIL_UNIFIED_FORCE', 'AIL_QUIET_FALLBACK', 'AIL_IR'):
            env.pop(key, None)
        if typed_only:
            env['AIL_NO_GENERAL'] = '1'
        else:
            env.pop('AIL_NO_GENERAL', None)
        res = run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                   '--syntax', 'python', '-o', exe.name], directory, env)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        self.assertNotIn('built on the general path', res.stderr)
        return source, exe

    def compare(self, text, name):
        source, exe = self.build(text, name, typed_only=True)
        want = run([sys.executable, str(source)], Path(self.tmp))
        got = run([str(exe)], Path(self.tmp))
        self.assertEqual(got.stdout, want.stdout, name)
        self.assertEqual(got.returncode, want.returncode, name)
        if want.returncode:
            self.assertEqual(bool(got.stderr.strip()), True, name)
        return want, got

    def test_g12_simulate_mm1_is_typed(self):
        self.assertTrue(G12.is_file(), G12)
        self.compare(G12.read_text(encoding='utf-8'), 'g12_008')

    def test_expovariate_forms_and_routes(self):
        self.compare(EXPO, 'expo')

    def test_expovariate_zero_division(self):
        want, _ = self.compare(ZERO, 'expo_zero')
        self.assertIn('ZeroDivisionError float division by zero', want.stdout)

    def test_expovariate_uncaught_zero_division(self):
        want, got = self.compare(UNCAUGHT, 'expo_uncaught')
        self.assertEqual(want.returncode, 1)
        self.assertIn('before', want.stdout)
        self.assertNotIn('after', want.stdout)

    def test_expovariate_keeps_the_generator_state(self):
        self.compare(STATE, 'expo_state')


if __name__ == "__main__":
    unittest.main()
