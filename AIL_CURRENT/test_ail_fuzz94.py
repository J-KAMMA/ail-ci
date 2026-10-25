"""Differential fuzz round 94: nested functions, recursion, defaults and loop closures.

A mutable literal default of a nested `def` directly in its enclosing body was copied at each
call site, so every call got a fresh list/dict/set where CPython shares the object built when the
`def` ran: `def f(x, acc=[]); f(1); f(2)` printed `[1] [2]` instead of `[1] [1, 2]`. Such a nested
default is now refused by name on both builds. Immutable defaults, keyword arguments, `nonlocal`
counters changed in loops, self recursion and early returns were compared and agree.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MUTABLE_NESTED_DEFAULT = '''
def main():
    def f(x, acc=[]):
        acc.append(x)
        return list(acc)
    print(f(1), f(2), f(3))


main()
'''

LOOP_CLOSURES = '''
def main():
    fs = []
    total = 0
    for i in range(3):
        def f(n=1, acc=0):
            nonlocal total
            total += n + acc
            if n <= 0:
                return total
            return f(n - 1, acc + i)
        fs.append(f)
    print([f(0) for f in fs], total)
    print([f(2) for f in fs], total)


main()
'''

RECURSIVE_DEFAULTS = '''
def outer(n, k=2):
    if n <= 0:
        return k
    def inner(m):
        return m + k
    return outer(n - 1, inner(n))


def main():
    print(outer(0), outer(1), outer(3))

    def f(n, step=1):
        if n <= 0:
            return 0
        if n % 2 == 0:
            return n + f(n - step, step)
        return -n + f(step=step, n=n - step)
    print(f(0), f(1), f(2), f(5), f(6, 2))

    total = 0
    def rec(k, step=1):
        nonlocal total
        if k <= 0:
            return total
        total += k
        return rec(k - step)
    print(rec(0), rec(1), rec(10), total)


main()
'''

EARLY_RETURN = '''
def main():
    total = 0
    def run(n):
        nonlocal total
        while n > 0:
            total += n
            n -= 1
            if total % 7 == 0:
                return total
        return total
    print(run(10), run(3), total)

    def rec(n, step=1):
        nonlocal total
        if n <= 0:
            return total
        for j in range(step):
            total += j
            if total > 20:
                return total
        return rec(n - 1, step + 1)
    print(rec(0), rec(1), rec(4))


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


class Fuzz94Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz94-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, want_rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_mutable_default_of_a_nested_def_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz94-') as directory:
            want, want_rc, err = _cpython(directory, 'mutable_default', MUTABLE_NESTED_DEFAULT)
            self.assertEqual(want_rc, 0, err)
            self.assertEqual(want, b'[1] [1, 2] [1, 2, 3]\n')
            for general in (True, False):
                got, build_err = _build_and_run(directory, 'mutable_default_%s' % ('g' if general else 'd'),
                                                MUTABLE_NESTED_DEFAULT, general)
                self.assertIsNone(got, 'general=%s built a mutable nested default\n%s' % (general, build_err))
                self.assertIn('mutable literal default', build_err)

    def test_loop_closures_and_nonlocal_counters(self):
        self.check('loop_closures', LOOP_CLOSURES)

    def test_recursive_defaults_and_keyword_calls(self):
        self.check('recursive_defaults', RECURSIVE_DEFAULTS)

    def test_early_returns_inside_loops(self):
        self.check('early_return', EARLY_RETURN)


if __name__ == '__main__':
    unittest.main()
