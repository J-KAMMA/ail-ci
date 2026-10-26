"""Differential round 37: a loop condition's comparison names the operator CPython named.

Found while fuzzing while loops and counters against CPython on both builds:

An ordering comparison (`<`, `<=`, `>`, `>=`) between built-in values that cannot
be ordered (a str and an int, a list and an int, None and an int, and the same
comparison nested in a list or tuple) always raised TypeError with a hardcoded
`'<'` in its message on both the general path and the default build.  CPython
names the operator that was written: `while s > 0` with `s = "5"` printed
`TypeError '<' not supported between instances of 'str' and 'int'` where CPython
prints `'>' ...`; `>=` printed `'<'` too, and a chained `2 > 1 > "x"` was the
same.  The runtime comparison helper now takes the operator symbol from the
`lt`/`le`/`gt`/`ge` entry point, passes it through nested list/tuple compares,
and uses it in the message.  A sort or another caller that has no source
operator still asks for `<`.

The program below keeps that shape compared with CPython on both builds, with
the operands reaching the comparison through an argument, a list item, an
attribute and a dict value, and catches each error so the whole program runs.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ORDER_MESSAGES = r'''class C:
    pass


def probe(a, b) -> None:
    k = 0
    while k < 4:
        try:
            if k == 0:
                print("<", a < b)
            elif k == 1:
                print("<=", a <= b)
            elif k == 2:
                print(">", a > b)
            else:
                print(">=", a >= b)
        except TypeError as e:
            print(k, e)
        k += 1


def main() -> None:
    probe(1, "x")
    probe("x", 1)
    probe(1, None)
    probe(None, 1)
    probe(True, "x")
    probe([1], 1)
    probe(1, [2])
    xs = ["x", 4]
    d = {"a": "s", "b": 7}
    c = C()
    c.s = "z"
    c.n = 8
    probe(xs[0], xs[1])
    probe(d["a"], d["b"])
    probe(c.s, c.n)
    probe([1, 2], [1, "x"])
    probe((1, 2), (1, "x"))
    for k in range(4):
        try:
            if k == 0:
                print("chain", 0 < 1 < "x")
            elif k == 1:
                print("chain", 0 <= 1 <= "x")
            elif k == 2:
                print("chain", 2 > 1 > "x")
            else:
                print("chain", 2 >= 1 >= "x")
        except TypeError as e:
            print("chain", k, e)
    s = "5"
    try:
        while s > 0:
            break
    except TypeError as e:
        print("while", e)
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


class Fuzz37Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz37-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_order_error_names_the_operator(self):
        self.check('order_messages', ORDER_MESSAGES)


if __name__ == '__main__':
    unittest.main()
