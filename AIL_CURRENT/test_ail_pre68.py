"""pre68: a literal `%d`/`%i`/`%u` conversion accepts a float like CPython.

The compile-time fast path for a literal format string lowered `"%d"` to
`ail_obj_format`'s `d` spec, which rejects a float ("unsupported format string
passed to non-int").  CPython's %-formatting accepts a float for `d`, `i` and
`u`, truncating toward zero (and raising OverflowError / ValueError for inf /
NaN).  A conversion whose argument is not provably an int now takes the
run-time formatter (safetyrt.FMT) for those three directives.  Widths, signs,
the `%%` escape, ints/bools, and values reaching the conversion through an
argument, a list item, an attribute and a dict value are compared with CPython
on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

LITERAL_FLOAT = r'''class Box:
    def __init__(self, v):
        self.v = v


def fmt(v):
    return "%d" % v


def main():
    d = {"v": 12.75}
    xs = [-3.75, 0.25]
    box = Box(-9.9)
    print("%d" % 3.7, "%d" % -3.7, "%d" % 0.0, "%d" % -0.0)
    print("%5d" % 3.7, "%-5d|" % 3.7, "%05d" % 3.7, "%+d" % 3.7, "% d" % 3.7)
    print("%d%%" % 12.5, "%d%%" % -0.5, "%d%%" % 100.0)
    print(fmt(3.7), fmt(-3.7))
    print("%d" % d["v"], "%d" % xs[0], "%d" % xs[1], "%d" % box.v)
    print("%i" % 3.7, "%u" % -3.7, "%i" % 42, "%u" % True)
    print("%d %s %d" % (3.7, "x", -0.0))
    print("%d" % True, "%d" % False, "%d" % 42, "%d" % -42)
    print("%x" % 255, "%o" % 8)


main()
'''

NONFINITE_AND_WRONG_TYPE = r'''def show(v):
    try:
        print("%d" % v)
    except Exception as e:
        print(type(e).__name__, e)
    try:
        print("%5d" % v)
    except Exception as e:
        print(type(e).__name__, e)


def main():
    for v in (float("inf"), float("-inf"), float("nan"), "x", None):
        show(v)


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


class Pre68Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-pre68-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                                text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_literal_d_float(self):
        self.check('literal_d_float', LITERAL_FLOAT)

    def test_nonfinite_and_wrong_type(self):
        self.check('nonfinite_and_wrong_type', NONFINITE_AND_WRONG_TYPE)


if __name__ == '__main__':
    unittest.main()
