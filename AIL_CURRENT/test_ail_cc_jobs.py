"""A mixed-mode build compiles its translation units (typed clones + the boxed program) concurrently
(pyc._cc_jobs, AIL_CC_JOBS; 1 = serial). The parallel build must link the byte-identical executable
the serial one does, and a C compile failure must report the first failing unit in serial order with
exactly the serial build's message.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / 'python' / 'pkg-v12'

PROGRAM = '''
def fib(n: int) -> int:
    a = 0
    b = 1
    for _ in range(n):
        a, b = b, a + b
    return a

def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s += x * x
    return s

def collatz(n: int) -> int:
    steps = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps

d = {"a": [1, 2, 3], "b": "x"}
print(d, fib(30), total([1, 2, 3, 4]), collatz(27))
'''

EXPECTED = "{'a': [1, 2, 3], 'b': 'x'} 832040 30 111\n"

# A compiler that rejects the units whose file name matches $FAILON with a real gcc diagnostic.
FAILING_CC = '''#!/bin/sh
for a in "$@"; do case "$a" in *.c) f=$a;; esac; done
if [ -n "$f" ] && basename "$f" | grep -Eq "$FAILON"; then
  { cat "$f"; echo 'int ail_injected_error = ;'; } > "$f.bad.c"
  gcc -c -o /dev/null -x c "$f.bad.c"; rc=$?; rm -f "$f.bad.c"; exit $rc
fi
exec gcc "$@"
'''

BUILD = '''
import sys
sys.path.insert(0, sys.argv[1])
import pyc
try:
    pyc.build(open(sys.argv[2]).read(), sys.argv[3], strict=False)
except Exception as e:
    print(type(e).__name__, e)
'''


@unittest.skipIf(os.name == 'nt' or not shutil.which('gcc'), 'needs gcc and a POSIX shell')
class ParallelUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ail-cc-jobs-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / 'prog.py').write_text(PROGRAM, encoding='utf-8')
        (self.tmp / 'build.py').write_text(BUILD, encoding='utf-8')

    def build(self, jobs, **env):
        out = self.tmp / 'out'
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir()
        env = dict(os.environ, AIL_CC_JOBS=str(jobs), AIL_NO_CACHE='1', **env)
        r = subprocess.run([sys.executable, str(self.tmp / 'build.py'), str(PKG), str(self.tmp / 'prog.py'),
                            str(out / 'prog')], env=env, capture_output=True, text=True, timeout=600)
        return r.stdout + r.stderr, out

    def test_identical_executable(self):
        digests = []
        for jobs in (1, 2):
            text, out = self.build(jobs)
            self.assertTrue((out / 'prog_mix0.c').exists(), 'no typed clone was built: ' + text)
            run = subprocess.run([str(out / 'prog')], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.stdout, EXPECTED)
            digests.append(hashlib.sha256((out / 'prog').read_bytes()).hexdigest())
        self.assertEqual(digests[0], digests[1])

    def test_identical_compile_error(self):
        cc = self.tmp / 'cc.sh'
        cc.write_text(FAILING_CC, encoding='utf-8')
        cc.chmod(0o755)
        for failon in ('mix1', '^prog\\.c$', 'mix2|^prog\\.c$'):
            with self.subTest(failon=failon):
                serial, _ = self.build(1, PIPE_CC=str(cc), FAILON=failon)
                parallel, _ = self.build(2, PIPE_CC=str(cc), FAILON=failon)
                self.assertIn('the C compiler rejected this', serial)
                self.assertIn('.bad.c:', serial)                     # gcc's own diagnostic is reported
                self.assertEqual(serial, parallel)


if __name__ == '__main__':
    unittest.main()
