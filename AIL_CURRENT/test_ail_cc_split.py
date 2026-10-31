"""A typed program's C is cut into several translation units that gcc compiles in parallel
(pyc._split_build, ccsplit.py; AIL_CC_SPLIT=1 keeps one unit). The split build must print what the
one-unit build prints, share the run-time state between units, and fall back to one unit when a unit
does not compile.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'
sys.path.insert(0, str(PKG))

import ccsplit  # noqa: E402

PROGRAM = '''
def fib(n: int) -> int:
    a = 0
    b = 1
    i = 0
    while i < n:
        a, b = b, a + b
        i += 1
    return a

def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps

def squares(n: int) -> list[int]:
    out = []
    for i in range(n):
        out.append(i * i)
    return out

def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x
    return s

def words(n: int) -> str:
    parts = []
    for i in range(n):
        parts.append("w" + str(i))
    return " ".join(parts)

def main():
    print(fib(30), collatz(27), total(squares(10)))
    print(words(5))
    xs = squares(1000)
    print(len(xs), total(xs))
    print(len(words(200)))

main()
'''
EXPECTED = '832040 111 285\nw0 w1 w2 w3 w4\n1000 332833500\n1090\n'

BUILD = '''
import sys
sys.path.insert(0, sys.argv[1])
import pyc
try:
    pyc.build(open(sys.argv[2]).read(), sys.argv[3], strict=True)
except Exception as e:
    print(type(e).__name__, e)
'''

# a compiler that rejects the second unit of a split build
FAILING_CC = '''#!/bin/sh
for a in "$@"; do case "$a" in *.c) f=$a;; esac; done
case "$f" in *_u1.c) echo 'injected failure' >&2; exit 1;; esac
exec gcc "$@"
'''


class PlanTests(unittest.TestCase):
    """ccsplit.plan on a hand-written split."""

    def split(self):
        declarations = ('#include <stdint.h>\n'
                        '#ifndef AIL_LINK_STATE\n#define AIL_LINK_STATE(type, name, init) static type name init\n#endif\n'
                        'AIL_LINK_STATE(int64_t, counter, = 0);\n'
                        'static char *pool_cur;\n'
                        'static const int table[3] = {1, 2, 3};\n'
                        'int64_t a(void);\nint64_t b(void);\nstatic int64_t h(int64_t);\n')
        heads = ['int64_t a(void)', 'int64_t b(void)', 'static int64_t h(int64_t x)']
        bodies = ['int64_t a(void) {\n    return h(counter++) + table[0];\n}\n',
                  'int64_t b(void) {\n    return h(counter++) + table[1];\n}\n',
                  'static int64_t h(int64_t x) {\n    return x + 1;\n}\n']
        # the declarations list the prototypes the way _to_c_once does
        return declarations, heads, bodies

    def test_units_define_state_once(self):
        declarations, heads, bodies = self.split()
        main = 'int main(void) { return (int)(a() + b()); }\n'
        text = declarations + '\n'.join(bodies) + main
        old = ccsplit.MIN_MOVABLE
        ccsplit.MIN_MOVABLE = 1
        try:
            units = ccsplit.plan((declarations, heads, bodies), text, main, 2)
        finally:
            ccsplit.MIN_MOVABLE = old
        self.assertEqual(len(units), 2)
        defining = [u for u in units if 'define AIL_LINK_STATE(type, name, init) type name init' in u]
        self.assertEqual(len(defining), 1)
        self.assertEqual(sum('int main(void)' in u for u in units), 1)
        self.assertEqual(sum('\nchar *pool_cur;' in u for u in units), 1)
        self.assertEqual(sum('extern char *pool_cur;' in u for u in units), 1)
        # each movable function is defined in exactly one unit, the static helper in both
        self.assertEqual(sum('int64_t a(void) {' in u for u in units), 1)
        self.assertEqual(sum('int64_t b(void) {' in u for u in units), 1)
        self.assertEqual(sum('static int64_t h(int64_t x) {' in u for u in units), 2)

    def test_deterministic_and_small_programs_stay_one_unit(self):
        declarations, heads, bodies = self.split()
        main = 'int main(void) { return 0; }\n'
        text = declarations + '\n'.join(bodies) + main
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 2))     # below MIN_MOVABLE
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 1))
        self.assertIsNone(ccsplit.plan(None, text, main, 4))
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text + ' ', main, 2))   # pieces do not add up

    def test_unshareable_state_refuses(self):
        declarations, heads, bodies = self.split()
        declarations = declarations.replace('static char *pool_cur;', 'static int tbl[] = {1, 2};')
        main = 'int main(void) { return 0; }\n'
        text = declarations + '\n'.join(bodies) + main
        old = ccsplit.MIN_MOVABLE
        ccsplit.MIN_MOVABLE = 1
        try:
            self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 2))
        finally:
            ccsplit.MIN_MOVABLE = old


@unittest.skipIf(os.name == 'nt' or not shutil.which('gcc'), 'needs gcc and a POSIX shell')
class SplitBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ail-cc-split-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / 'prog.py').write_text(PROGRAM, encoding='utf-8')
        (self.tmp / 'build.py').write_text(BUILD, encoding='utf-8')

    def build(self, name, **env):
        out = self.tmp / name
        out.mkdir()
        log = out / 'split.log'
        env = dict(os.environ, AIL_NO_CACHE='1', AIL_CC_SPLIT_LOG=str(log), AIL_CC_SPLIT_MIN='1', **env)
        r = subprocess.run([sys.executable, str(self.tmp / 'build.py'), str(PKG), str(self.tmp / 'prog.py'),
                            str(out / 'prog')], env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.stdout + r.stderr, '', r.stdout + r.stderr)
        run = subprocess.run([str(out / 'prog')], capture_output=True, text=True, timeout=60)
        return run, (log.read_text() if log.exists() else ''), out

    def test_same_output_split_and_single(self):
        single, single_log, _ = self.build('one', AIL_CC_SPLIT='1')
        split, split_log, out = self.build('split', AIL_CC_SPLIT='3')
        self.assertEqual(single.stdout, EXPECTED)
        self.assertEqual(single.returncode, 0)
        self.assertEqual(single_log, '')
        self.assertRegex(split_log, r'^[2-3] units', 'the program was not split: ' + split_log)
        self.assertEqual(split.stdout, single.stdout)
        self.assertEqual(split.returncode, single.returncode)
        # the intermediate units are removed after the link
        self.assertEqual(sorted(p.name for p in out.glob('prog_u*')), [])

    def test_unit_assignment_is_deterministic(self):
        _, first, _ = self.build('a', AIL_CC_SPLIT='3')
        _, second, _ = self.build('b', AIL_CC_SPLIT='3')
        self.assertTrue(first.startswith(('2 units', '3 units')))
        self.assertEqual(first, second)

    def test_failing_unit_falls_back_to_one_unit(self):
        cc = self.tmp / 'cc.sh'
        cc.write_text(FAILING_CC, encoding='utf-8')
        cc.chmod(0o755)
        run, log, _ = self.build('fail', AIL_CC_SPLIT='3', PIPE_CC=str(cc))
        self.assertEqual(run.stdout, EXPECTED)
        self.assertRegex(log, r'^[2-3] units')


if __name__ == '__main__':
    unittest.main()
