"""Differential round 66: the `z` format option is not silently ignored.

CPython's `z` option (after the sign, before `#`/`0`/width) is only valid for
float formatting: it coerces a negative zero -- including a small negative
value that rounds to zero at the requested precision -- to positive zero.
For an int, bool or str it is a ValueError.  The general path's runtime
formatter consumed the flag and then formatted as if it had not been written,
so `"{:z}".format(0)` printed `0` and `"{:z}".format(-0.0)` printed `-0.0`
where CPython raises ValueError and prints `0.0` respectively.

The programs below keep the shape compared with CPython on both builds,
including the fill-character reading (`{:z>5}` uses `z` as the fill, not the
flag), values reaching the format through an argument, a list item, an
attribute, a dict value and a nested spec, and the int/bool/str refusals.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

Z_FLOATS = r'''def main():
    for v in [0.0, -0.0, 1.5, -1.5, 1e300, -1e300, 1e-300, -1e-300, -0.0001, -0.005]:
        print(repr(v), ("{:z}").format(v))
    for v in [-0.0, -0.0001, -0.005, 0.0]:
        print("p", repr(v), ("{:z.2f}").format(v), ("{:z.1f}").format(v),
              ("{:z.2e}").format(v), ("{:z.2g}").format(v), ("{:z.2%}").format(v))
    inf = float("inf")
    nan = float("nan")
    for v in [inf, -inf, nan]:
        print("x", repr(v), ("{:z}").format(v), ("{:z.2f}").format(v), ("{:z.2e}").format(v))
    print("sign", ("{:+z}").format(-0.0), ("{: z}").format(-0.0), ("{:+z}").format(1.5))
    print("width", ("{:z0}").format(-0.0), ("{:z05}").format(-0.0), ("{:z8.2f}").format(-0.0))
    print("empty", "".format())


main()
'''

Z_ERRORS = r'''class C:
    pass


def fmt(v, spec):
    try:
        return ("{:" + spec + "}").format(v)
    except Exception as e:
        return type(e).__name__ + ": " + str(e)


def main():
    for v in [0, 7, -7, True, False, 10 ** 18, -(10 ** 18)]:
        print("i", repr(v), fmt(v, "z"), fmt(v, "+z"))
    for v in ["", "abc", "h\u00e9"]:
        print("s", repr(v), fmt(v, "z"))
    c = C()
    c.v = -0.0
    c.s = "z.2f"
    xs = [-0.0, -0.0001]
    d = {"v": -0.0, "s": "z.3f"}
    print("src", ("{0.v:{0.s}}").format(c))
    print("list", fmt(xs[0], c.s), fmt(xs[1], "z.3f"))
    print("dict", fmt(d["v"], d["s"]))
    print("arg", fmt(-0.0, "z"), fmt(-0.0001, "z.2f"))
    print("fill", fmt("ab", "z>5"), fmt(0, "z>5"), fmt(-0.0, "z>5"))
    print("nest", "{0:{1}}".format(-0.0, "z"), "{0:{1}}".format(-0.0001, "z.2f"))
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


class Fuzz66Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz66-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_z_option_on_floats(self):
        self.check('z_floats', Z_FLOATS)

    def test_z_option_refusals_and_sources(self):
        self.check('z_errors', Z_ERRORS)


if __name__ == '__main__':
    unittest.main()
