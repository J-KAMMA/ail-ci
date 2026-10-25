"""Differential fuzz round 31: float format specs the IR emitter used to drop.

Found with small programs compared against CPython on both builds:

1. The IR text emitter's `fmt_value` (ir/lower_text.py) built every f-string field with the
   three small padding formatters, which cover only [[fill]align][0][width][.precision] and a
   negative sign. A positive '+' or space sign was parsed and then silently discarded, so
   `f"{0.5:+.1f}"` printed "0.5" where CPython prints "+0.5" -- and only when the field followed
   another field in the same f-string, because otherwise the legacy emitter built the function.
   The same code path also lost '#', grouping, '=' alignment, a type-less float spec and the
   g/e/% types. `fmt_value` now asks `_fmt_general_needed` and refuses by name (`NotS0`), so the
   whole function falls back to the legacy emitter, which already sends those specs to
   `ail_fmt_gen`.

The values below reach the formatter as a local, an argument, a list item, a dict value and an
attribute, and cover zero, negative zero, positive and negative values.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FLOAT_FORMAT_SPECS = r'''class Box:
    def __init__(self, v: float) -> None:
        self.v: float = v


def show(v: float) -> None:
    print(f"{v:+.1f}|{v: .1f}|{v:+.3e}|{v:+g}|{v:+%}|{v:08.2f}")


def main() -> None:
    x: float = 0.5
    print(f"{x:.0f}|{x:.1f}|{x:.2f}|{x:.3f}|{x:8.2f}|{x:08.2f}|{x:+.1f}|{x: .1f}")
    show(0.5)
    show(-0.0)
    show(-2.5)
    xs: list[float] = [0.0, 0.5, -0.0, 2.675]
    for v in xs:
        show(v)
    d: dict[str, float] = {"k": 0.5, "n": -0.0}
    show(d["k"])
    show(d["n"])
    b: Box = Box(0.125)
    show(b.v)
    print(f"{b.v:+.1f}|{b.v: .1f}|{b.v:08.2f}")
    for x in [0.5, -2.5, 0.0, -0.0, 1.2345, 1234.5]:
        print(f"{x:10}|{x:10.3}|{x:g}|{x:.3g}|{x:#.2f}|{x:,.2f}|{x:=10.2f}|{x:*^10.2f}")


main()
'''


GENERAL_SPEC_NONFLOAT = r'''def main() -> None:
    xs: list[int] = [0, 7, -7, 42]
    for n in xs:
        print(f"{n:+d}|{n: d}|{n:+05d}|{n:,}|{n:#x}|{n:08X}")
    ss: list[str] = ["a", "", "hé"]
    for x in ss:
        print(f"[{x:*>6}]|[{x:*^7}]|[{x:.1}]|[{x:6}]")


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


class Fuzz31Tests(unittest.TestCase):
    def check(self, slug, text, rc=0):
        with tempfile.TemporaryDirectory(prefix='ail-fuzz31-') as directory:
            want, got_rc, err = _cpython(directory, slug, text)
            self.assertEqual(got_rc, rc, err)
            for general in (True, False):
                got, build_err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (text[:2000], general, build_err))
                self.assertEqual(got, (want, rc), '%s (general=%s)\n%s' % (text[:2000], general, build_err))

    def test_float_sign_and_general_specs(self):
        self.check('float_format_specs', FLOAT_FORMAT_SPECS)

    def test_int_sign_and_str_fill_specs(self):
        self.check('general_spec_nonfloat', GENERAL_SPEC_NONFLOAT)


if __name__ == '__main__':
    unittest.main()
