"""fuzz42: bool arithmetic and truthiness.

The general path's abs() lowering returned its argument unchanged when it was not negative,
so a bool kept the BOOL tag: `abs(False)` printed `False` where CPython prints `0`, and
`abs(True)` printed `True` where CPython prints `1`. The same inline lowering was used by
the key=/map() wrapper for a builtin `abs`. Both now call ail_bi_abs, which boxes an intlike
argument as an int (and keeps the float and INT64_MIN handling). The programs below are built
with the general path forced and with the default build; stdout and the exit status must match
CPython.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ABS_BOOL = r'''def ident(x):
    return x

def main():
    b = False
    t = True
    print(abs(False), abs(True))
    print(abs(b), abs(t))
    print(abs(-True), abs(-False))
    print(abs(-3), abs(3), abs(-2.5), abs(-0.0))
    xs = [True, False]
    print(abs(xs[0]), abs(xs[1]))
    d = {"t": True, "f": False}
    print(abs(d["t"]), abs(d["f"]))
    print(abs(ident(False)), abs(ident(True)))
    print(abs(not 0), abs(1 > 2), abs(bool([])), abs(all([True])), abs(any([])))
    print(abs(True + True), abs(False - True))
    print(list(map(abs, [True, False])))
    print(sum([True, True], 10))
    print(-True, -False, abs(False), abs(True))
main()
'''

ABS_BOOL_ATTR = r'''class Box:
    def __init__(self, v):
        self.v = v

def main():
    a = Box(False)
    print(abs(a.v), abs(Box(True).v))
    d = {"x": Box(False)}
    print(abs(d["x"].v))
    print(list(map(abs, [Box(True).v, a.v])))
    print(sum([True, True], 10))
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


class Fuzz42Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz42-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_abs_bool(self):
        self.check('abs_bool', ABS_BOOL)

    def test_abs_bool_attribute(self):
        self.check('abs_bool_attr', ABS_BOOL_ATTR)


if __name__ == '__main__':
    unittest.main()
