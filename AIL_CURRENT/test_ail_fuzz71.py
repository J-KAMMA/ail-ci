"""Fuzz round 71: a float formatted with a fixed-point spec is never truncated by a buffer.

The typed core's `ail_fmt_spec_float` formatted into `char buf[512]`, the general path's
`ail_obj_format` into `char buf[64]` (v1) / `char buf[66]` (v2), and the full runtime's
`ail2f_float_body` into `char body[400]` after silently clamping a precision above 300 to 300.
CPython prints all the digits a huge value or a large precision needs, so these paths produced
a shorter string (or, where `snprintf`'s would-be length was trusted, read past the buffer and
printed stack bytes). `f"{1e308:.0f}"` and `f"{1.5:.600f}"` were the smallest reproductions;
`%.600f`, `{:.600f}".format(x)`, a negative value, and a width wider than the result are kept
here too, on both builds.

Each program is built twice (default build, AIL_UNIFIED_FORCE=1 general path) and must print
exactly what CPython prints with the same exit status.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

HUGE_FIXED = r'''def main() -> None:
    x = 1e308
    print(f"{x:.0f}")
    print("%.0f" % x)
    print("{:.0f}".format(x))
    y = -1e308
    a = f"{y:.0f}"
    print(a[:4], len(a), a[-3:])
    print(len("%.0f" % y), ("%.0f" % y)[:4])
    print(f"{1.5:1000.2f}"[:7], len(f"{1.5:1000.2f}"), f"{1.5:1000.2f}"[-4:])
    print(f"{1e308:800.2f}"[:7], len(f"{1e308:800.2f}"), f"{1e308:800.2f}"[-4:])


main()
'''

HUGE_PRECISION = r'''def main() -> None:
    x = 1.5
    a = f"{x:.600f}"
    print(len(a), a[:5], a[-5:])
    b = "%.600f" % x
    print(len(b), b[:5], b[-5:])
    c = "{:.600f}".format(x)
    print(len(c), c[:5], c[-5:])
    d = f"{-0.5:.700f}"
    print(len(d), d[:8], d[-3:])
    e = f"{1e308:.1000f}"
    print(len(e), e[:3], e[-3:])
    out = ""
    for i in range(3):
        out += f"{x:.600f}"
    print(len(out), out.count("1.5"), out[:3])
    print(len(f"{0.0:.600f}"), f"{0.0:.600f}"[:10])
    print(len(f"{-1.5:.600f}"), f"{-1.5:.600f}"[:10])
    print(len(f"{1e-300:.600f}"), f"{1e-300:.600f}"[:10])
    print(f"{x:.0f}", f"{x:.1f}", f"{x:.2f}", f"{x:.6f}")
    print(len(f"{1e308:1200.0f}"), f"{1e308:1200.0f}"[:3], f"{1e308:1200.0f}"[-3:])
    g = "{:.600}".format(x)
    print(len(g), g[:5], g[-5:])
    h = f"{1e308:.1000}"
    print(len(h), h[:3], h[-3:])
    i = f"{x:.200%}"
    print(len(i), i[:5], i[-3:])


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


class Fuzz71Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz71-') as directory:
            want, rc, err = _cpython(directory, slug, text)
            self.assertEqual(rc, 0, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, 0), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_huge_value_fixed_spec(self):
        self.check('huge_fixed', HUGE_FIXED)

    def test_huge_precision_fixed_spec(self):
        self.check('huge_precision', HUGE_PRECISION)


if __name__ == '__main__':
    unittest.main()
