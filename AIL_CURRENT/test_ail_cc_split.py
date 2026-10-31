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
def fibr(n: int) -> int:
    if n < 2:
        return n
    return fibr(n - 1) + fibr(n - 2)

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

def spread(xs: list[int]) -> int:
    lo = xs[0]
    hi = xs[0]
    for x in xs:
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    return hi - lo

def main():
    print(fibr(20), collatz(27), total(squares(10)))
    xs = squares(1000)
    print(len(xs), total(xs), spread(xs))

main()
'''
EXPECTED = '6765 111 285\n1000 332833500 998001\n'

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
        text = declarations + '\n'.join(bodies)
        old = ccsplit.MIN_MOVABLE
        ccsplit.MIN_MOVABLE = 1
        try:
            units = ccsplit.plan((declarations, heads, bodies), text, main, 2)
        finally:
            ccsplit.MIN_MOVABLE = old
        self.assertIsNotNone(units, 'reason %s %s' % (ccsplit.last_reason, ccsplit.last_detail))
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
        text = declarations + '\n'.join(bodies)
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 2))     # below MIN_MOVABLE
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 1))
        self.assertIsNone(ccsplit.plan(None, text, main, 4))
        self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text + ' ', main, 2))   # pieces do not add up

    def test_unshareable_state_refuses(self):
        declarations, heads, bodies = self.split()
        declarations = declarations.replace('static char *pool_cur;', 'static int tbl[] = {1, 2};')
        main = 'int main(void) { return 0; }\n'
        text = declarations + '\n'.join(bodies)
        old = ccsplit.MIN_MOVABLE
        ccsplit.MIN_MOVABLE = 1
        try:
            self.assertIsNone(ccsplit.plan((declarations, heads, bodies), text, main, 2))
        finally:
            ccsplit.MIN_MOVABLE = old


class SmallerC(unittest.TestCase):
    """Less C for the same program: shared exit cleanup outside loops, one body for identical clones."""

    FREES = ''.join('ail_list_free(&v_%d); ' % k for k in range(9))

    BODY = ('    if (a) {\n        return 1LL;\n    }\n'
            '    while (b) {\n        if (c) {\n            return 2LL;\n        }\n    }\n'
            '    if (d) {\n        return 3LL;\n    }\n')

    def rewrite(self, frees, merge):
        import pyfunc
        old = os.environ.get('AIL_EXIT_MERGE')
        if merge is None:
            os.environ.pop('AIL_EXIT_MERGE', None)
        else:
            os.environ['AIL_EXIT_MERGE'] = merge
        try:
            return pyfunc._rewrite_returns(self.BODY, frees, 'int64_t')
        finally:
            if old is None:
                os.environ.pop('AIL_EXIT_MERGE', None)
            else:
                os.environ['AIL_EXIT_MERGE'] = old

    def test_returns_outside_loops_share_one_exit_when_asked(self):
        text = self.rewrite(self.FREES, '1')
        self.assertEqual(text.count('goto ail_exit_ret;'), 2)
        self.assertEqual(text.count(self.FREES), 2)          # the loop's own copy and the shared block
        self.assertIn('{ int64_t _r1 = 2LL; ' + self.FREES + 'return _r1; }', text)
        self.assertIn('ail_exit_ret: ;\n    ' + self.FREES + 'return _rv;', text)
        self.assertTrue(text.startswith('    int64_t _rv;\n'))

    def test_default_keeps_one_copy_per_return(self):
        text = self.rewrite(self.FREES, None)
        self.assertNotIn('ail_exit_ret', text)
        self.assertEqual(text.count(self.FREES), 3)
        self.assertNotIn('ail_exit_ret', self.rewrite('ail_list_free(&v_0); ', '1'))   # too few frees

    def test_identical_clone_becomes_a_call(self):
        import pyfunc
        head = 'ail_str fmt(double v_v)'
        body = ('static void ail_unwind_fmt(void **p) { ail_sarena_free(p[0]); }\n'
                + head + ' {\n    return ail_str_g(v_v);\n}\n')
        clone = body.replace('fmt', 'fmt__t0')
        alias = pyfunc._clone_alias(head, body, 'fmt', 'ail_str fmt__t0(double v_v)', clone, 'fmt__t0')
        self.assertEqual(alias, 'ail_str fmt__t0(double v_v) {\n    return fmt(v_v);\n}\n')
        other = clone.replace('ail_str_g(v_v)', 'ail_str_r(v_v)')
        self.assertIsNone(pyfunc._clone_alias(head, body, 'fmt', 'ail_str fmt__t0(double v_v)', other, 'fmt__t0'))


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
